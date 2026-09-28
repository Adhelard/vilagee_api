from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import os
import json
from mqtt_client import mqtt_client
from dotenv import load_dotenv
from loguru import logger
import ngrok
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Routers
from routers.ESP32 import router as esp32_router
from routers.chat import router as chat_router

# Load environment variables from .env
load_dotenv()

# Safely load variables (fallback strings provided for testing)
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN", "391yYxWp5219LhNdtN1aSSTO6g9_wfaeMaetSpSNDcosubK5")
MQTT_BROKER_IP   = os.getenv("MQTT_BROKER_IP", "10.246.171.113")
APPLICATION_PORT = 5000


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ──────────────────────────
    # STARTUP
    # ──────────────────────────
    logger.info("Connecting to MQTT broker...")
    try:
        mqtt_client.connect_async(MQTT_BROKER_IP, 1883, 60)
        mqtt_client.loop_start()
        logger.info("MQTT connection initiated.")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")

    logger.info("Setting up ngrok Endpoint...")
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    listener = await ngrok.forward(addr=f"127.0.0.1:{APPLICATION_PORT}")
    logger.info(f"Ingress established at {listener.url()}")

    yield  # ← app berjalan di sini

    # ──────────────────────────
    # SHUTDOWN
    # ──────────────────────────
    logger.info("Disconnecting from MQTT...")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()

    logger.info("Tearing Down ngrok Endpoint...")
    try:
        await ngrok.disconnect()
    except Exception:
        ngrok.disconnect()


# ══════════════════════════════════════════════════
#  FastAPI App
# ══════════════════════════════════════════════════
app = FastAPI(
    lifespan=lifespan,
    title="Vilagee Smart Village API",
    description="Backend IoT + Multi-Agent AI untuk monitoring desa pintar",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include Routers ──────────────────────────────
app.include_router(esp32_router)
app.include_router(chat_router)


# ── Core Endpoints ───────────────────────────────
@app.get("/")
def read_root():
    return {
        "status": "Vilagee IoT running",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.post("/api/webhook/mqtt")
async def handle_supabase_webhook(request: Request):
    """
    Webhook dari Supabase Database Trigger.
    Menerima perubahan tabel 'controls' dan meneruskan ke MQTT.
    """
    payload = await request.json()

    record    = payload.get("record", {})
    component = record.get("component")
    device_id = record.get("device_id")
    action    = record.get("action")

    if device_id and action:
        topic    = f"esp32/{device_id}/control"
        mqtt_msg = json.dumps({"command": component, "status": action})

        mqtt_client.publish(topic, mqtt_msg)
        logger.info(f"Published MQTT → Topic: {topic} | Message: {mqtt_msg}")

        return {"status": "success", "topic": topic, "message": mqtt_msg}

    return {"status": "ignored", "reason": "Data tidak valid atau action kosong"}


if __name__ == "__main__":
    # reload=False WAJIB saat pakai ngrok programatik
    uvicorn.run("main:app", host="127.0.0.1", port=APPLICATION_PORT, reload=False)
