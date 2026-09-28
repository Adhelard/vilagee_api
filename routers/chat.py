"""
routers/chat.py
FastAPI endpoints untuk chat dengan multi-agent AI desa pintar.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from dependencies import supabase
from agents.graph import graph

router = APIRouter(prefix="/api/chat", tags=["AI Chat"])


# ══════════════════════════════════════════════════
#  REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = "user"


class ChatResponse(BaseModel):
    response: str
    session_id: str
    agent_trace: list[str]


# ══════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════
AGENT_NAMES = {
    "orchestrator", "ahli_cuaca", "ahli_perairan",
    "ahli_energi", "pembaca_situasi", "pengeksekusi", "ahli_alert"
}

def _save_to_chats(session_id: str, user: str, message: str,
                   agent_name: Optional[str] = None, metadata: dict = None):
    """Simpan pesan ke tabel chats di Supabase (fire & forget)."""
    try:
        supabase.table("chats").insert({
            "user":       user,
            "message":    message,
            "session_id": session_id,
            "agent_name": agent_name,
            "metadata":   metadata or {},
        }).execute()
    except Exception as e:
        print(f"[chat router] Gagal simpan ke chats: {e}")


def _extract_response_and_trace(result: dict) -> tuple[str, list[str]]:
    """Ambil respons final dan jejak agent dari hasil graph."""
    messages = result.get("messages", [])
    agent_trace = []
    final_response = "Maaf, tidak ada respons dari agen."

    for msg in messages:
        name = getattr(msg, "name", None)
        content = getattr(msg, "content", "")
        if not content:
            continue
        if name in AGENT_NAMES:
            label = {
                "orchestrator": "🧠 Agen Inti",
                "ahli_cuaca": "🌤️ Ahli Cuaca",
                "ahli_perairan": "💧 Ahli Perairan",
                "ahli_energi": "⚡ Ahli Energi",
                "pembaca_situasi": "👁️ Pembaca Situasi",
                "pengeksekusi": "🤖 Pengeksekusi",
                "ahli_alert": "🚨 Ahli Alert",
            }.get(name, name)
            preview = content[:120] + ("..." if len(content) > 120 else "")
            agent_trace.append(f"{label}: {preview}")

    # Respons final = pesan orchestrator terakhir
    orchestrator_msgs = [
        m for m in messages
        if getattr(m, "name", None) == "orchestrator" and getattr(m, "content", "")
    ]
    if orchestrator_msgs:
        final_response = orchestrator_msgs[-1].content
    elif messages:
        final_response = messages[-1].content

    return final_response, agent_trace


# ══════════════════════════════════════════════════
#  ENDPOINTS
# ══════════════════════════════════════════════════
@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Kirim pesan ke multi-agent sistem desa pintar.
    Response di-stream melalui Supabase Realtime ke frontend.
    """
    session_id = request.session_id or str(uuid.uuid4())

    # Simpan pesan user ke Supabase (realtime ke frontend)
    background_tasks.add_task(
        _save_to_chats,
        session_id,
        request.user_id or "user",
        request.message,
        None,
        {"role": "user"},
    )

    try:
        config = {"configurable": {"thread_id": session_id}}
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "turn": 0,
                "next": "",
            },
            config=config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    final_response, agent_trace = _extract_response_and_trace(result)

    # Simpan respons agent ke Supabase (realtime ke frontend)
    background_tasks.add_task(
        _save_to_chats,
        session_id,
        "assistant",
        final_response,
        "orchestrator",
        {"role": "assistant", "agent_trace": agent_trace},
    )

    return ChatResponse(
        response=final_response,
        session_id=session_id,
        agent_trace=agent_trace,
    )


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str, limit: int = 50):
    """Ambil riwayat percakapan berdasarkan session_id."""
    try:
        result = (
            supabase.table("chats")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return {"session_id": session_id, "messages": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions(limit: int = 20):
    """Daftar session chat terbaru."""
    try:
        result = (
            supabase.table("chats")
            .select("session_id, created_at, user, message")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Deduplicate by session_id
        seen = set()
        sessions = []
        for row in result.data:
            sid = row.get("session_id")
            if sid and sid not in seen:
                seen.add(sid)
                sessions.append(row)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
