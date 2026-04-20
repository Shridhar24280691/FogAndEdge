import json
import boto3
from decimal import Decimal
from datetime import datetime, timezone
import uuid
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
state_table = dynamodb.Table("SmartHomeState")
alerts_table = dynamodb.Table("SmartHomeAlerts")

ALLOWED_ORIGIN = "https://main.d2za4tbv92h2ur.amplifyapp.com"
HOME_ID = "home1"
ROOMS = ["livingroom", "kitchen", "bedroom", "bathroom"]
HOME_POWER_THRESHOLD_W = 5000.0
ROOM_POWER_WITHOUT_MOTION_THRESHOLD_W = 1500.0

live_devices = {}
latest_summary = {
    "currentTotalPower": 0.0,
    "energyLastHourKWh": 0.0,
    "timestamp": "-"
}


def decimal_default(obj):
    if isinstance(obj, Decimal): 
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

# Standardized response function for API Gateway with CORS headers and JSON body
def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS"
        },
        "body": json.dumps(body, default=decimal_default)
    }

# Helper function to convert Decimal to float for JSON serialization
def to_decimal(val):
    if isinstance(val, (float, int)):
        return Decimal(str(val))
    return val

def safe_float(value, default=0.0): # Safely convert a value to float, returning a default if conversion fails
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def now_iso():# Get the current time in ISO 8601 format with UTC timezone
    return datetime.now(timezone.utc).isoformat()

 # Normalize the incoming path by removing the stage prefix if present, to allow for consistent routing regardless of API Gateway stage
def normalize_path(event):
    path = event.get("rawPath") or event.get("path") or "/"
    stage = event.get("requestContext", {}).get("stage", "")

    if stage and path.startswith(f"/{stage}/"):
        path = path[len(stage) + 1:]
    elif stage and path == f"/{stage}":
        path = "/"

    return path

 # Convert an ISO timestamp to a minute bucket string (e.g., "2024-06-01T12:34") for aggregation purposes. If parsing fails, return the current time's minute bucket.
def minute_bucket(ts):
    try:
        if ts.endswith("Z"):
            ts = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return now_iso()[:16]

 # Build alert messages based on the types of alerts received, including details about the device, room, and power levels that triggered the alert. This function creates human-readable messages for each alert type.
def update_live_cache(event):
    device_id = event.get("deviceId")
    room = event.get("room", "unknown")

    if not device_id:
        return
 # Update the in-memory cache of live devices with the latest readings and status for each device, including power, current, voltage, temperature, motion, and timestamps. This cache is used to build the dashboard view without needing to query DynamoDB for every request.
    live_devices[device_id] = {
        "deviceId": device_id,
        "room": room,
        "sensorType": event.get("sensorType", "appliance"),
        "timestamp": event.get("timestamp", now_iso()),
        "last_power_W": safe_float(event.get("last_power_W", 0)),
        "avg_power_last_min_W": safe_float(event.get("avg_power_last_min_W", 0)),
        "room_temperature_C": safe_float(
            event.get("room_temperature_C", event.get("temperature_C", 0))
        ),
        "current_A": safe_float(event.get("current_A", 0)),
        "voltage_V": safe_float(event.get("voltage_V", 0)),
        "motion": bool(event.get("motion", False))
    }

def upsert_summary(event):
    global latest_summary
# This function processes incoming aggregate data from the fog processor, updates the latest summary of home power consumption and energy usage, and stores this information in DynamoDB for both current state and historical records. It also handles the logic for calculating rolling averages and energy consumption over the last hour based on the incoming data.
    home_id = event.get("homeId", HOME_ID)
    timestamp = event.get("timestamp") or now_iso()
    current_total_power = safe_float(event.get("home_total_W", 0))
    energy_last_hour_kwh = safe_float(event.get("energy_last_hour_kWh", 0))
# Update the latest summary in memory and also upsert it into DynamoDB for both current summary and historical records based on minute buckets. This allows for quick retrieval of the latest summary as well as historical trends over time.
    latest_summary = {
        "currentTotalPower": round(current_total_power, 1),
        "energyLastHourKWh": round(energy_last_hour_kwh, 3),
        "timestamp": timestamp
    }
 # Upsert current summary into DynamoDB with a fixed sort key for easy retrieval of the latest summary, and also store historical summaries with a timestamp-based sort key for trend analysis. This allows the dashboard to quickly access the latest
    current_item = {
        "pk": f"HOME#{home_id}",
        "sk": "SUMMARY#CURRENT", 
        "recordType": "summary_current",
        "homeId": home_id,
        "timestamp": timestamp,
        "currentTotalPower": to_decimal(current_total_power),
        "energyLastHourKWh": to_decimal(energy_last_hour_kwh)
    }
    state_table.put_item(Item=current_item) 
 # Also store historical summary with minute bucket for trend analysis and historical charts on the dashboard. This allows for tracking how power consumption changes over time and identifying patterns
    bucket = minute_bucket(timestamp)
    history_item = {
        "pk": f"HOME#{home_id}",
        "sk": f"SUMMARY#TS#{bucket}",
        "recordType": "summary_history",
        "homeId": home_id,
        "timestamp": timestamp,
        "minuteBucket": bucket,
        "currentTotalPower": to_decimal(current_total_power),
        "energyLastHourKWh": to_decimal(energy_last_hour_kwh)
    }
    state_table.put_item(Item=history_item)

 # Build alert messages based on the types of alerts received, including details about the device, room, and power levels that triggered the alert. This function creates human-readable messages for each alert type.
def build_alert_messages(alert_payload):
    alert_types = alert_payload.get("alerts", [])
    device_id = alert_payload.get("deviceId", "unknown")
    room = alert_payload.get("room", "unknown")
    event_ts = alert_payload.get("timestamp", now_iso())
    home_total_w = safe_float(alert_payload.get("home_total_W", 0))
    power_threshold_w = safe_float(
        alert_payload.get("power_threshold_W", HOME_POWER_THRESHOLD_W)
    )

    messages = []
# Generate human-readable alert messages based on the alert types and details provided in the payload, which can then be stored in DynamoDB and displayed on the dashboard for user awareness and action. Each alert type has a specific message format and severity level to help users understand the nature of the alert.
    for alert_type in alert_types:
        severity = "medium"
        message = f"{alert_type} on {device_id}"

        if alert_type == "Power_high_without_motion":
            message = f"{device_id} in {room} was drawing high power without motion detected at {event_ts}"
            severity = "medium"
        elif alert_type == "High_average_load_appliance":
            message = f"{device_id} in {room} had a high rolling average power load at {event_ts}"
            severity = "high"
        elif alert_type == "Home_power_threshold_exceeded":
            message = (
                f"House power was {home_total_w:.1f} W at {event_ts}, "
                f"above the {power_threshold_w:.0f} W threshold"
            )
            severity = "high"

        messages.append({
            "type": alert_type,
            "severity": severity,
            "message": message
        })

    return messages

 # Store alert messages in DynamoDB with details about the device, room, timestamp, and severity. This allows for historical tracking of alerts and displaying them on the dashboard for user awareness. Each alert is stored as a separate item in the alerts table with a unique ID.
def store_alert(alert):
    for alert_msg in build_alert_messages(alert):
        alert_item = {
            "alertId": str(uuid.uuid4()),
            "deviceid": alert.get("deviceId", "unknown"),
            "homeId": alert.get("homeId", HOME_ID),
            "room": alert.get("room", "unknown"),
            "timestamp": alert.get("timestamp") or now_iso(),
            "type": alert_msg["type"],
            "message": alert_msg["message"],
            "severity": alert_msg["severity"],
            "status": "active",
            "home_total_W": to_decimal(safe_float(alert.get("home_total_W", 0))),
            "energy_last_hour_kWh": to_decimal(
                safe_float(alert.get("energy_last_hour_kWh", 0))
            )
        }
        alerts_table.put_item(Item=alert_item)

 # Load recent alerts from DynamoDB, filter out any irrelevant messages, and return a list of recent alerts sorted by timestamp. This function is used to populate the recent alerts section on the dashboard, allowing users to see the latest issues and their details.
def load_recent_alerts(limit=10): 
    items = []
    scan_kwargs = {}

    while True:
        result = alerts_table.scan(**scan_kwargs)
        items.extend(result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    cleaned = []
    for i in items:
        msg = i.get("message", "")
        if msg == "Alert received from SQS":
            continue
        if msg.startswith("Alerts for "):
            continue

        cleaned.append({
            "severity": i.get("severity", "medium"),
            "message": msg if msg else i.get("type", "Alert"),
            "timestamp": i.get("timestamp", "-"),
            "room": i.get("room", "unknown"),
            "type": i.get("type", "generic_alert")
        })

    cleaned.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return cleaned[:limit]

 # Load historical summary data from DynamoDB for the dashboard's historical charts, allowing for analysis of power consumption trends over time. This function retrieves summary records based on minute buckets and returns a list of summaries with timestamps, current total power, and energy consumption over the last hour.
def load_summary_history(limit=60):
    try:
        result = state_table.query(
            KeyConditionExpression=Key("pk").eq(f"HOME#{HOME_ID}") &
                                   Key("sk").begins_with("SUMMARY#TS#")
        )
        items = result.get("Items", [])
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=False)
        items = items[-limit:]

        return [
            {
                "timestamp": item.get("timestamp", "-"),
                "currentTotalPower": safe_float(item.get("currentTotalPower", 0)),
                "energyLastHourKWh": safe_float(item.get("energyLastHourKWh", 0))
            }
            for item in items
        ]
    except Exception:
        return []

 # Build alert messages based on the types of alerts received, including details about the device, room, and power levels that triggered the alert. This function creates human-readable messages for each alert type.
def build_current_active_alerts(rooms):
    active_alerts = []

    if latest_summary["currentTotalPower"] > HOME_POWER_THRESHOLD_W:
        active_alerts.append({
            "severity": "high",
            "type": "Home_power_threshold_exceeded",
            "message": (
                f"Current house power is {latest_summary['currentTotalPower']:.1f} W, "
                f"above the {HOME_POWER_THRESHOLD_W:.0f} W threshold"
            ),
            "timestamp": latest_summary["timestamp"],
            "room": "house"
        })

    for r in rooms:
        if (not r["motion"]) and r["total_power_W"] > ROOM_POWER_WITHOUT_MOTION_THRESHOLD_W:
            active_alerts.append({
                "severity": "medium",
                "type": "Power_high_without_motion",
                "message": (
                    f"{r['room']} currently has high power usage "
                    f"({r['total_power_W']:.1f} W) without motion detected"
                ),
                "timestamp": r["updatedAt"],
                "room": r["room"]
            })

    return active_alerts

 # Build the dashboard body by aggregating live device data, calculating room-level summaries, and including recent alerts and historical summary data. This function constructs the complete response body for the dashboard API, allowing the frontend to display current conditions, trends, and alerts in a user-friendly format.
def build_dashboard_body():
    rooms_map = {
        room: {
            "room": room,
            "temperature_C": 0.0,
            "avg_voltage_V": 0.0,
            "total_current_A": 0.0,
            "total_power_W": 0.0,
            "motion": False,
            "activeDevices": 0,
            "updatedAt": "-"
        }
        for room in ROOMS
    }

    voltage_counts = {room: 0 for room in ROOMS}

    for item in live_devices.values():
        room = item.get("room")
        if room not in rooms_map:
            continue

        power = safe_float(item.get("last_power_W", 0))
        current = safe_float(item.get("current_A", 0))
        voltage = safe_float(item.get("voltage_V", 0))
        temp = safe_float(item.get("room_temperature_C", 0))
        motion = bool(item.get("motion", False))
        ts = item.get("timestamp", "-")
        sensor_type = item.get("sensorType", "appliance")

        rooms_map[room]["total_power_W"] += power
        rooms_map[room]["total_current_A"] += current
        rooms_map[room]["motion"] = rooms_map[room]["motion"] or motion

        if sensor_type == "appliance" and power > 0:
            rooms_map[room]["activeDevices"] += 1

        if temp > 0:
            rooms_map[room]["temperature_C"] = temp

        if voltage > 0:
            rooms_map[room]["avg_voltage_V"] += voltage
            voltage_counts[room] += 1

        if str(ts) > rooms_map[room]["updatedAt"]:
            rooms_map[room]["updatedAt"] = str(ts)

    rooms = []
    for room in ROOMS:
        r = rooms_map[room]
        count = voltage_counts[room]
        if count > 0:
            r["avg_voltage_V"] = r["avg_voltage_V"] / count

        rooms.append({
            "room": r["room"],
            "temperature_C": round(r["temperature_C"], 1),
            "avg_voltage_V": round(r["avg_voltage_V"], 1),
            "total_current_A": round(r["total_current_A"], 2),
            "total_power_W": round(r["total_power_W"], 1),
            "motion": r["motion"],
            "activeDevices": r["activeDevices"],
            "updatedAt": r["updatedAt"]
        })

    active_alerts = build_current_active_alerts(rooms)
    recent_alerts = load_recent_alerts(10)
    summary_history = load_summary_history(60)

    body = {
        "summary": {
            "currentTotalPower": latest_summary["currentTotalPower"],
            "energyLastHourKWh": latest_summary["energyLastHourKWh"],
            "roomCount": len(rooms),
            "alertCount": len(active_alerts)
        },
        "rooms": rooms,
        "sensorCharts": {
            "temperature": [{"room": r["room"], "temperature_C": r["temperature_C"]} for r in rooms],
            "voltage": [{"room": r["room"], "voltage_V": r["avg_voltage_V"]} for r in rooms],
            "current": [{"room": r["room"], "current_A": r["total_current_A"]} for r in rooms],
            "power": [{"room": r["room"], "power_W": r["total_power_W"]} for r in rooms],
            "housePower": [{
                "label": "Current House Power",
                "power_W": latest_summary["currentTotalPower"],
                "threshold_W": HOME_POWER_THRESHOLD_W
            }],
            "houseConsumption": [{
                "label": "Energy Last Hour",
                "consumption_kWh": latest_summary["energyLastHourKWh"]
            }],
            "summaryHistory": summary_history
        },
        "motionOverview": [
            {
                "room": r["room"],
                "motion": r["motion"],
                "activeDevices": r["activeDevices"],
                "updatedAt": r["updatedAt"]
            }
            for r in rooms
        ],
        "activeAlerts": active_alerts,
        "recentAlerts": recent_alerts,
        "debug": {
            "deviceCountInMemory": len(live_devices),
            "summaryTimestamp": latest_summary["timestamp"]
        }
    }

    return body

 # Handle incoming HTTP requests from API Gateway, routing based on the HTTP method and path. For GET requests to allowed paths, it builds and returns the dashboard body. For OPTIONS requests, it returns a simple 200 response for CORS preflight. For any other routes, it returns a 404 response.
def handle_http(event):
    method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method", "")
        or "GET"
    )

    path = normalize_path(event)

    if method == "OPTIONS":
        return response(200, {"message": "ok"})

    allowed_paths = {"/", "/dashboard", "/smarthome-ingest-readings"}

    if method == "GET" and path in allowed_paths:
        return response(200, build_dashboard_body())

    return response(404, {
        "message": "Route not found",
        "method": method,
        "path": path
    })

 # The main Lambda handler function processes incoming events, determining if they are HTTP requests from API Gateway or messages from SQS. It routes HTTP requests to the appropriate handler and processes SQS messages to store alerts in DynamoDB. It also updates the live cache and summary data based on incoming aggregate data from the fog processor.
def lambda_handler(event, context):
    print("EVENT:", json.dumps(event))

    try:
        if "httpMethod" in event or "requestContext" in event:
            return handle_http(event)

        if "Records" in event:
            for record in event["Records"]:
                if record.get("eventSource") == "aws:sqs":
                    body = json.loads(record["body"])
                    store_alert(body)
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "alerts stored"})
            }

        update_live_cache(event)
        upsert_summary(event)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "aggregate processed"})
        }

    except Exception as e:
        print("ERROR:", str(e))
        return response(500, {"error": str(e)})