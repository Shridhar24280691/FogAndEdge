import json
from collections import defaultdict, deque
from datetime import datetime, timezone

from paho.mqtt import client as mqtt_client
from awscrt import io, mqtt
from awsiot import mqtt_connection_builder

BROKER = "localhost"
PORT = 1883
HOME_ID = "home1"

RAW_TOPIC = f"home/{HOME_ID}/sensors/+"
AGG_TOPIC_TEMPLATE = "home/{home_id}/aggregates/{device_id}"
ALERT_TOPIC_TEMPLATE = "home/{home_id}/alerts/{device_id}"

WINDOW_SIZE = 6
PUBLISH_PERIOD = 10
ENERGY_WINDOW_SLOTS = int(3600 / PUBLISH_PERIOD)

HOME_POWER_THRESHOLD_W = 5000.0

AWS_ENDPOINT = "a1bqm601es3mh3-ats.iot.us-east-1.amazonaws.com"
AWS_CLIENT_ID = "fog-cloud-publisher-home1"
AWS_CERT = "C:/FogAndEdge/certs/ef58ff1fb135d12e3389bef8d451e8869b0bf11bcffc240b08c3e982b1d7883c-certificate.pem.crt"
AWS_KEY = "C:/FogAndEdge/certs/ef58ff1fb135d12e3389bef8d451e8869b0bf11bcffc240b08c3e982b1d7883c-private.pem.key"
AWS_CA = "C:/FogAndEdge/certs/AmazonRootCA1.pem"

device_windows = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
latest_device_power = {}
latest_device_energy_wh = {}
device_to_room = {}

room_temperatures = {}
home_energy_window = deque(maxlen=ENERGY_WINDOW_SLOTS)

aws_connection = None


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connect_aws():
    global aws_connection

    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    aws_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=AWS_ENDPOINT,
        cert_filepath=AWS_CERT,
        pri_key_filepath=AWS_KEY,
        client_bootstrap=client_bootstrap,
        ca_filepath=AWS_CA,
        client_id=AWS_CLIENT_ID,
        clean_session=True,
        keep_alive_secs=30
    )

    print("Connecting to AWS IoT Core...")
    aws_connection.connect().result()
    print("Connected to AWS IoT Core")


def on_connect(client, userdata, flags, reason_code, properties=None):
    print("Fog processor connected with code", reason_code)
    client.subscribe(RAW_TOPIC, qos=1)
    print("Subscribed to", RAW_TOPIC)


def publish_aws(topic, payload):
    aws_connection.publish(
        topic=topic,
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception as e:
        print("Invalid JSON:", e)
        return

    device_id = data.get("deviceId")
    room = data.get("room", "unknown")
    sensor_type = data.get("sensorType", "appliance")

    if not device_id:
        return

    if sensor_type == "temperature":
        temperature = float(data.get("temperature_C", 0.0))
        room_temperatures[room] = temperature

        room_payload = {
            "recordType": "aggregate",
            "homeId": HOME_ID,
            "deviceId": device_id,
            "sensorType": "temperature",
            "room": room,
            "timestamp": now_iso(),
            "temperature_C": round(temperature, 1),
            "last_power_W": 0.0,
            "avg_power_last_min_W": 0.0,
            "home_total_W": round(sum(latest_device_power.values()), 1),
            "room_total_W": round(sum(
                p for d, p in latest_device_power.items()
                if device_to_room.get(d) == room
            ), 1),
            "voltage_V": 0.0,
            "current_A": 0.0,
            "motion": False,
            "energy_last_hour_kWh": round(sum(home_energy_window) / 1000.0, 3),
            "power_threshold_W": HOME_POWER_THRESHOLD_W
        }

        room_topic = AGG_TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
        publish_aws(room_topic, room_payload)
        print("[ROOM->AWS]", room_topic, room_payload)
        return

    power = float(data.get("power_W", 0.0))
    energy_wh = float(data.get("energy_Wh", 0.0))
    motion = bool(data.get("motion", False))
    voltage = float(data.get("voltage_V", 0.0))
    current = float(data.get("current_A", 0.0))

    device_to_room[device_id] = room
    device_windows[device_id].append(power)
    latest_device_power[device_id] = power
    latest_device_energy_wh[device_id] = energy_wh

    avg_power = sum(device_windows[device_id]) / len(device_windows[device_id])
    home_total = sum(latest_device_power.values())

    room_totals = defaultdict(float)
    for dev, pwr in latest_device_power.items():
        dev_room = device_to_room.get(dev, "unknown")
        room_totals[dev_room] += pwr

    interval_total_wh = sum(latest_device_energy_wh.values())
    home_energy_window.append(interval_total_wh)
    energy_last_hour_wh = sum(home_energy_window)
    energy_last_hour_kwh = energy_last_hour_wh / 1000.0

    agg_payload = {
        "recordType": "aggregate",
        "homeId": HOME_ID,
        "deviceId": device_id,
        "sensorType": "appliance",
        "room": room,
        "timestamp": now_iso(),
        "last_power_W": round(power, 1),
        "avg_power_last_min_W": round(avg_power, 1),
        "home_total_W": round(home_total, 1),
        "room_total_W": round(room_totals[room], 1),
        "room_temperature_C": room_temperatures.get(room, 0.0),
        "voltage_V": round(voltage, 1),
        "current_A": round(current, 2),
        "motion": motion,
        "energy_last_hour_kWh": round(energy_last_hour_kwh, 3),
        "power_threshold_W": HOME_POWER_THRESHOLD_W
    }

    agg_topic = AGG_TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
    publish_aws(agg_topic, agg_payload)
    print("[AGG->AWS]", agg_topic, agg_payload)

    alerts = []
    if motion is False and power > 200:
        alerts.append("Power_high_without_motion")
    if avg_power > 2000:
        alerts.append("High_average_load_appliance")
    if home_total > HOME_POWER_THRESHOLD_W:
        alerts.append("Home_power_threshold_exceeded")

    if alerts:
        top_rooms = sorted(
            [{"room": r, "power_W": round(v, 1)} for r, v in room_totals.items()],
            key=lambda x: x["power_W"],
            reverse=True
        )[:3]

        top_devices = sorted(
            [{"deviceId": d, "room": device_to_room.get(d, "unknown"), "power_W": round(p, 1)}
             for d, p in latest_device_power.items()],
            key=lambda x: x["power_W"],
            reverse=True
        )[:5]

        alert_payload = {
            "recordType": "alert",
            "homeId": HOME_ID,
            "deviceId": device_id,
            "room": room,
            "timestamp": now_iso(),
            "alerts": alerts,
            "home_total_W": round(home_total, 1),
            "power_threshold_W": HOME_POWER_THRESHOLD_W,
            "energy_last_hour_kWh": round(energy_last_hour_kwh, 3),
            "topRooms": top_rooms,
            "topDevices": top_devices,
            "last_reading": data
        }

        alert_topic = ALERT_TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
        publish_aws(alert_topic, alert_payload)
        print("[ALERT->AWS]", alert_topic, alert_payload)


def main():
    connect_aws()

    client = mqtt_client.Client(
        mqtt_client.CallbackAPIVersion.VERSION2,
        client_id="fog-processor-home1",
        protocol=mqtt_client.MQTTv311
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    client.loop_forever()


if __name__ == "__main__":
    main()