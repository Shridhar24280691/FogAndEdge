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

APPLIANCES = [ # Device ID, Room, Max Power in Watts
    ("bedroom-lights", "bedroom", 120),
    ("bedroom-heater", "bedroom", 1600),
    ("bedroom-computer", "bedroom", 450),
    ("kitchen-microwave", "kitchen", 1400),
    ("kitchen-induction", "kitchen", 2200),
    ("kitchen-exhaust", "kitchen", 180),
    ("kitchen-refrigerator", "kitchen", 250),
    ("kitchen-dishwasher", "kitchen", 1800),
    ("kitchen-lights", "kitchen", 100),
    ("bathroom-geyser", "bathroom", 2200),
    ("bathroom-lights", "bathroom", 80),
    ("bathroom-washer", "bathroom", 1000),
    ("livingroom-heater", "livingroom", 1800),
    ("livingroom-television", "livingroom", 180),
    ("livingroom-lights", "livingroom", 120),
]
# Room sensors temperature only
ROOM_SENSORS = [
    ("bathroom-temp", "bathroom"),
    ("bedroom-temp", "bedroom"),
    ("kitchen-temp", "kitchen"),
    ("livingroom-temp", "livingroom"),
]

def connect_mqtt(): # Connect to local Mosquitto broker using MQTT v3.1.1 for compatibility
    client_id = f"edge-publisher-{random.randint(1000, 9999)}"
    client = mqtt_client.Client(client_id=client_id, protocol=mqtt_client.MQTTv311) # Use MQTT v3.1.1 for compatibility with Mosquitto
    client.connect(BROKER, PORT)
    return client
# Simulate power consumption with a random chance of being off (0W) or on (random value up to max_power)
def simulate_power(max_power):
    if random.random() < 0.55:
        return 0.0
    return max_power * random.uniform(0.4, 0.95)
# Build payload for appliance sensor with realistic voltage, current, power, energy, and motion values
def build_appliance_payload(device_id, room, max_power):
    voltage = random.uniform(220.0, 240.0)
    power = simulate_power(max_power)
    current = power / voltage if voltage > 0 else 0.0
    energy = power * (PUBLISH_PERIOD / 3600.0)
    motion = random.random() < 0.6

    return {
        "homeId": HOME_ID,
        "deviceId": device_id,
        "sensorType": "appliance",
        "room": room,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "voltage_V": round(voltage, 1),
        "current_A": round(current, 2),
        "power_W": round(power, 1),
        "energy_Wh": round(energy, 3),
        "motion": motion,
        "source": "mosquitto-edge"
    }
# Build payload for room sensor with realistic temperature values
def build_room_sensor_payload(device_id, room):
    temp = random.uniform(10.0, 30.0)
    return {
        "homeId": HOME_ID,
        "deviceId": device_id,
        "sensorType": "temperature",
        "room": room,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature_C": round(temp, 1),
        "source": "mosquitto-edge"
    }
# The main function connects to the local Mosquitto broker, then continuously publishes simulated appliance and room sensor data every 10 seconds. It handles graceful shutdown on keyboard interrupt.
def main():
    client = connect_mqtt()
    client.loop_start()
    print("Publishing to local Mosquitto broker...")
    try:
        while True:
            for device_id, room, max_power in APPLIANCES:
                topic = TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
                payload = build_appliance_payload(device_id, room, max_power)
                client.publish(topic, json.dumps(payload), qos=1)
                print("Published appliance:", topic, payload)

            for device_id, room in ROOM_SENSORS:
                topic = TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
                payload = build_room_sensor_payload(device_id, room)
                client.publish(topic, json.dumps(payload), qos=1)
                print("Published room sensor:", topic, payload)

            time.sleep(PUBLISH_PERIOD)
    except KeyboardInterrupt:
        print("Stopping edge publisher")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()