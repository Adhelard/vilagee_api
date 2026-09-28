import json
import paho.mqtt.client as mqtt
import os
from dependencies import supabase
from routers.ESP32 import (
    RiverPayload, FilterTankPayload, FishTankPayload, 
    SolarPanelPayload, VillagePayload, environmentPayload
)

# Map MQTT sub-topics to their respective models and database tables
TOPIC_ROUTER = {
    "esp32/river": {"model": RiverPayload, "table": "river"},
    "esp32/filter-tank": {"model": FilterTankPayload, "table": "filter_tank"},
    "esp32/fish-tank": {"model": FishTankPayload, "table": "fish_tank"},
    "esp32/solar-panel": {"model": SolarPanelPayload, "table": "solar_panel"},
    "esp32/village": {"model": VillagePayload, "table": "village"},
    "esp32/environment": {"model": environmentPayload, "table": "environment"}
}

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribe to all sub-topics under esp32/
    client.subscribe("esp32/#") 

def on_message(client, userdata, msg):
    topic = msg.topic
    if topic not in TOPIC_ROUTER:
        return # Ignore unknown topics
    
    try:
        route_info = TOPIC_ROUTER[topic]
        raw_payload = json.loads(msg.payload.decode())  
        
        # Validate using Pydantic
        validated_data = route_info["model"](**raw_payload)
        
        # Insert into Supabase
        supabase.table(route_info["table"]).insert(
            validated_data.model_dump(exclude_none=True)
        ).execute()
        
        print(f"✅ Saved to {route_info['table']}: {raw_payload}")
        
    except Exception as e:
        print(f"❌ Error processing {topic}: {e}")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message