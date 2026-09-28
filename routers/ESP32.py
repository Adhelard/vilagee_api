from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from dependencies import supabase

router = APIRouter(prefix="/api/esp32", tags=["ESP32 Subsystems"])

class RiverPayload(BaseModel):
    device_id: str
    water_gate: Optional[str] = None
    pump_status: Optional[bool] = None
    turbidity: Optional[float] = None
    water_level: Optional[float] = None

class FilterTankPayload(BaseModel):
    device_id: str
    turbidity: Optional[float] = None
    pump_status: Optional[bool] = None
    water_level: Optional[float] = None

class FishTankPayload(BaseModel):
    device_id: str
    water_level: Optional[float] = None
    pump_status: Optional[bool] = None

class SolarPanelPayload(BaseModel):
    device_id: str  
    servo_degree: Optional[float] = None
    light_level1: Optional[float] = None
    light_level2: Optional[float] = None
    battery_level: Optional[float] = None

class VillagePayload(BaseModel):
    device_id: str
    light_level: Optional[float] = None
    led1: Optional[bool] = None
    led2: Optional[bool] = None
    led3: Optional[bool] = None

class environmentPayload(BaseModel):
    device_id: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    altitude: Optional[float] = None
    barometrik: Optional[float] = None
    soil_moisture: Optional[float] = None
    temp_2: Optional[float] = None


# Helper function to keep code DRY (Don't Repeat Yourself)
def insert_sensor_data(table_name: str, payload: BaseModel):
    try:
        data = payload.model_dump(exclude_none=True)
        response = supabase.table(table_name).insert(data).execute()
        return {"status": "success", "table": table_name, "inserted": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/river")
async def log_river(payload: RiverPayload):
    return insert_sensor_data("river", payload)

@router.post("/filter-tank")
async def log_filter_tank(payload: FilterTankPayload):
    return insert_sensor_data("filter_tank", payload)

@router.post("/fish-tank")
async def log_fish_tank(payload: FishTankPayload):
    return insert_sensor_data("fish_tank", payload)

@router.post("/solar-panel")
async def log_solar_panel(payload: SolarPanelPayload):
    return insert_sensor_data("solar_panel", payload)

@router.post("/village")
async def log_village(payload: VillagePayload):
    return insert_sensor_data("village", payload)

@router.post("/environment")
async def log_environment(payload: environmentPayload):
    return insert_sensor_data("environment", payload)
    