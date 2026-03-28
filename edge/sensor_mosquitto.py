import json
import random
import time
from datetime import datetime, timezone
from paho.mqtt import client as mqtt_client

BROKER = "localhost"
PORT = 1883
TOPIC_TEMPLATE = "home/{home_id}/sensors/{device_id}"
HOME_ID = "home1"
PUBLISH_PERIOD = 10

APPLIANCES = [
    ("kitchen-main", "kitchen", 3000),
    ("living-tvpc", "livingroom", 400),
    ("living-heater", "livingroom", 1800),
    ("bedroom-heater", "bedroom", 1600),
    ("bedroom-lights", "bedroom", 250),
    ("bathroom-washer", "bathroom", 1000),
    ("bathroom-geyser", "bathroom", 2200),
]

def connect_mqtt():
    client_id = f"edge-publisher-{random.randint(1000,9999)}"
    client = mqtt_client.Client(client_id=client_id, protocol=mqtt_client.MQTTv311)
    client.connect(BROKER, PORT)
    return client

def simulate_power(max_power):
    if random.random() < 0.55:
        return 0.0
    return max_power * random.uniform(0.4, 0.95)

def build_payload(device_id, room, max_power):
    voltage = random.uniform(220.0, 240.0)
    power = simulate_power(max_power)
    current = power / voltage if voltage > 0 else 0.0
    energy = power * (PUBLISH_PERIOD / 3600.0)
    temp = random.uniform(19.0, 30.0)
    motion = random.random() < 0.6

    return {
        "homeId": HOME_ID,
        "deviceId": device_id,
        "room": room,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "voltage_V": round(voltage, 1),
        "current_A": round(current, 2),
        "power_W": round(power, 1),
        "energy_Wh": round(energy, 3),
        "temperature_C": round(temp, 1),
        "motion": motion,
        "source": "mosquitto-edge"
    }

def main():
    client = connect_mqtt()
    client.loop_start()
    print("Publishing to local Mosquitto broker...")
    try:
        while True:
            for device_id, room, max_power in APPLIANCES:
                topic = TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
                payload = build_payload(device_id, room, max_power)
                client.publish(topic, json.dumps(payload), qos=1)
                print("Published:", topic, payload)
            time.sleep(PUBLISH_PERIOD)
    except KeyboardInterrupt:
        print("Stopping edge publisher")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
