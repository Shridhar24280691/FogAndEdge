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
HOME_THRESHOLD_W = 6000.0

AWS_ENDPOINT = "ajfzkitfnbpep-ats.iot.us-east-1.amazonaws.com"
AWS_CLIENT_ID = "fog-cloud-publisher-home1"
AWS_CERT = "C:/FogAndEdge/certs/681bfabc3534e8c803c61dd80a4e59a30da009fde618eb8fa39b627a4959f6cd-certificate.pem.crt"
AWS_KEY = "C:/FogAndEdge/certs/681bfabc3534e8c803c61dd80a4e59a30da009fde618eb8fa39b627a4959f6cd-private.pem.key"
AWS_CA = "C:/FogAndEdge/certs/AmazonRootCA1.pem"

device_windows = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
latest_device_power = {}

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


def on_connect(client, userdata, flags, rc, properties=None):
    print("Fog processor connected with code", rc)
    client.subscribe(RAW_TOPIC, qos=1)
    print("Subscribed to", RAW_TOPIC)


def publish_local(client, topic, payload):
    client.publish(topic, json.dumps(payload), qos=1)


def publish_aws(topic, payload):
    aws_connection.publish(
        topic=topic,
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE
    )


def publish_both(client, topic, payload):
    publish_local(client, topic, payload)
    publish_aws(topic, payload)


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except Exception as e:
        print("Invalid JSON:", e)
        return

    device_id = data.get("deviceId")
    room = data.get("room", "unknown")
    power = float(data.get("power_W", 0.0))
    temperature = data.get("temperature_C")
    motion = data.get("motion")

    if not device_id:
        return

    device_windows[device_id].append(power)
    latest_device_power[device_id] = power

    avg_power = sum(device_windows[device_id]) / len(device_windows[device_id])
    home_total = sum(latest_device_power.values())

    agg_payload = {
        "homeId": HOME_ID,
        "deviceId": device_id,
        "room": room,
        "timestamp": now_iso(),
        "last_power_W": round(power, 1),
        "avg_power_last_min_W": round(avg_power, 1),
        "home_total_W": round(home_total, 1),
        "temperature_C": temperature,
        "motion": motion
    }

    agg_topic = AGG_TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
    publish_both(client, agg_topic, agg_payload)
    print("[AGG]", agg_topic, agg_payload)

    alerts = []
    if motion is False and power > 200:
        alerts.append("Power_high_without_motion")
    if temperature is not None and temperature > 27 and power > 500:
        alerts.append("Possible_overheating_appliance")
    if avg_power > 2000:
        alerts.append("High_average_load_appliance")
    if home_total > HOME_THRESHOLD_W:
        alerts.append("Home_overload_risk")

    if alerts:
        alert_payload = {
            "homeId": HOME_ID,
            "deviceId": device_id,
            "room": room,
            "timestamp": now_iso(),
            "alerts": alerts,
            "home_total_W": round(home_total, 1),
            "last_reading": data
        }

        alert_topic = ALERT_TOPIC_TEMPLATE.format(home_id=HOME_ID, device_id=device_id)
        publish_both(client, alert_topic, alert_payload)
        print("[ALERT]", alert_topic, alert_payload)


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