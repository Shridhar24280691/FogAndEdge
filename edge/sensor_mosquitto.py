import json
import random
import time
from datetime import datetime, timezone
from paho.mqtt import client as mqtt_client

BROKER = "localhost" # Local Mosquitto broker
PORT = 1883 # Default MQTT port
TOPIC_TEMPLATE = "home/{home_id}/sensors/{device_id}" # MQTT topic template for publishing sensor data
HOME_ID = "home1" # Home ID for topic structure and payloads
PUBLISH_PERIOD = 10 # Publish every 10 seconds to simulate real-time sensor data

APPLIANCES = [ # Device ID, Room, Max Power in Watts
    ("bedroom-lights", "bedroom", 120), # Bedroom lights with max power of 120W
    ("bedroom-heater", "bedroom", 1600), # Bedroom heater with max power of 1600W
    ("bedroom-computer", "bedroom", 450), # Bedroom computer with max power of 450W
    ("kitchen-microwave", "kitchen", 1400), # Kitchen microwave with max power of 1400W
    ("kitchen-induction", "kitchen", 2200), # Kitchen induction cooktop with max power of 2200W
    ("kitchen-exhaust", "kitchen", 180), # Kitchen exhaust fan with max power of 180W
    ("kitchen-refrigerator", "kitchen", 250), # Kitchen refrigerator with max power of 250W
    ("kitchen-dishwasher", "kitchen", 1800), # Kitchen dishwasher with max power of 1800W
    ("kitchen-lights", "kitchen", 100), # Kitchen lights with max power of 100W
    ("bathroom-geyser", "bathroom", 2200), # Bathroom geyser with max power of 2200W
    ("bathroom-lights", "bathroom", 80), # Bathroom lights with max power of 80W
    ("bathroom-washer", "bathroom", 1000), # Bathroom washer with max power of 1000W
    ("livingroom-heater", "livingroom", 1800), # Living room heater with max power of 1800W
    ("livingroom-television", "livingroom", 180), # Living room television with max power of 180W
    ("livingroom-lights", "livingroom", 120), # Living room lights with max power of 120W
]
# Room sensors temperature only
ROOM_SENSORS = [
    ("bathroom-temp", "bathroom"), # Bathroom temperature sensor
    ("bedroom-temp", "bedroom"), # Bedroom temperature sensor
    ("kitchen-temp", "kitchen"), # Kitchen temperature sensor
    ("livingroom-temp", "livingroom"), # Living room temperature sensor
]

def connect_mqtt(): # Connect to local Mosquitto broker using MQTT v3.1.1 for compatibility
    client_id = f"edge-publisher-{random.randint(1000, 9999)}" # Unique client ID for MQTT connection
    client = mqtt_client.Client(client_id=client_id, protocol=mqtt_client.MQTTv311) # Use MQTT v3.1.1 for compatibility with Mosquitto
    client.connect(BROKER, PORT) # Connect to local Mosquitto broker
    return client

# Simulate power consumption with a random chance of being off (0W) or on (random value up to max_power)
def simulate_power(max_power):
    if random.random() < 0.55: # 55% chance the appliance is off (0W)
        return 0.0
    return max_power * random.uniform(0.4, 0.95) # If on, power is between 40% and 95% of max power to simulate realistic usage patterns

# Build payload for appliance sensor with realistic voltage, current, power, energy, and motion values
def build_appliance_payload(device_id, room, max_power):
    voltage = random.uniform(220.0, 240.0) # Simulate voltage between 220V and 240V
    power = simulate_power(max_power) # Simulate power consumption based on max power and random on/off state
    current = power / voltage if voltage > 0 else 0.0 # Calculate current using power and voltage, handle division by zero just in case
    energy = power * (PUBLISH_PERIOD / 3600.0) # Calculate energy in kWh for the publish period (power in W * time in hours)
    motion = random.random() < 0.6 # 60% chance of motion detected

    return {
        "homeId": HOME_ID,
        "deviceId": device_id,
        "sensorType": "appliance",
        "room": room,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "voltage_V": round(voltage, 1),
        "current_A": round(current, 2),
        "power_W": round(power, 1),
        "motion": motion,
        "source": "mosquitto-edge"
    }
# Build payload for room sensor with realistic temperature values
def build_room_sensor_payload(device_id, room):
    temp = random.uniform(10.0, 30.0) # Simulate room temperature between 10°C and 30°C
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
        while True: # Publish appliance sensor data with realistic power consumption values
            for device_id, room, max_power in APPLIANCES:
                topic = TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
                payload = build_appliance_payload(device_id, room, max_power)
                client.publish(topic, json.dumps(payload), qos=1)
                print("Published appliance:", topic, payload)
# Publish room sensor data with realistic temperature values
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