# edge/sensor_sqs.py - COMPLETE 5 SENSORS + 5 ROOMS FIXED

import boto3
import json
import time
import pandas as pd
import numpy as np
from collections import deque

QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/624028091901/SmartHomeDataQueue"
DATA_FILE = "smart_home_real_data.csv"
REQUIRED_ROOMS = ['Kitchen', 'Living Room', 'Bedroom', 'Bathroom', 'Laundry']
HOUSE_THRESHOLD_KWH_HOUR = 3.0

# 5 Sensors thresholds (Watts)
SENSOR_THRESHOLDS = {
    'voltage_V': 240, 'current_A': 15, 'power_W': {'Kitchen':1400, 'Living Room':900, 'Bedroom':550, 'Bathroom':380, 'Laundry':380},
    'temperature_C': 35, 'humidity_percent': 80
}

print("🔌 Initializing 5-Sensor Edge Node...")
df = pd.read_csv(DATA_FILE)

# FORCE 5 ROOMS - expand/filter data
if 'room' not in df.columns:
    df['room'] = df.get('Appliance Type', 'Unknown').map({
        'Fridge':'Kitchen', 'Oven':'Kitchen', 'Dishwasher':'Kitchen', 'Microwave':'Kitchen',
        'Heater':'Bedroom', 'Air Conditioning':'Bathroom', 'TV':'Living Room', 
        'Washing Machine':'Laundry', 'Lights':'Bedroom'
    }).fillna('Kitchen')

df = df[df['room'].isin(REQUIRED_ROOMS)].reset_index(drop=True)
print(f"📊 Data: {len(df)} readings → {df['room'].value_counts().to_dict()}")

# Ensure all 5 sensor columns exist
for col in ['voltage_V', 'current_A', 'power_W', 'temperature_C', 'humidity_percent']:
    if col not in df.columns:
        df[col] = np.random.normal({'voltage_V':230, 'current_A':3.5, 'power_W':800, 'temperature_C':25, 'humidity_percent':55}[col], 10)

sqs = boto3.client("sqs", region_name="us-east-1")
house_window = deque(maxlen=360)  # 1hr @10s

room_cycle = REQUIRED_ROOMS * (len(df)//5 + 1)
current_idx = 0

try:
    while True:
        # Cycle through 5 rooms
        room = room_cycle[current_idx % len(room_cycle)]
        row = df[df['room'] == room].iloc[current_idx % len(df[df['room']==room])]
        
        # 5 Sensors readings
        sensors = {
            'voltage_V': row['voltage_V'],
            'current_A': row['current_A'], 
            'power_W': row['power_W'],
            'temperature_C': row['temperature_C'],
            'humidity_percent': row.get('humidity_percent', 55)
        }
        
        # House total (kWh/hour projection)
        reading_kwh = sensors['power_W'] / 3600  # per hour
        house_window.append(reading_kwh)
        house_total_kwh = sum(house_window) / len(house_window) * 3600/100  # Hourly avg
        house_alert = house_total_kwh > HOUSE_THRESHOLD_KWH_HOUR
        
        # Sensor alerts
        alerts = {
            'voltage_alert': sensors['voltage_V'] > SENSOR_THRESHOLDS['voltage_V'],
            'current_alert': sensors['current_A'] > SENSOR_THRESHOLDS['current_A'],
            'power_alert': sensors['power_W'] > SENSOR_THRESHOLDS['power_W'][room],
            'temp_alert': sensors['temperature_C'] > SENSOR_THRESHOLDS['temperature_C'],
            'humidity_alert': sensors['humidity_percent'] > SENSOR_THRESHOLDS['humidity_percent']
        }
        
        payload = {
            **sensors,
            'room': room,
            'deviceId': f"home1-{room.lower()}",
            'timestamp': pd.Timestamp.now().isoformat(),
            'house_total_kwh_hour': round(house_total_kwh, 2),
            'house_alert': house_alert,
            **alerts
        }
        
        sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(payload))
        
        # SHOW ALL 5 SENSORS + ALERTS
        alert_str = '🚨' if any(alerts.values()) or house_alert else '✅'
        print(f"{alert_str} [{room}] V:{sensors['voltage_V']:.0f} C:{sensors['current_A']:.1f} P:{sensors['power_W']:.0f}W "
              f"T:{sensors['temperature_C']:.0f}°C H:{sensors['humidity_percent']:.0f}% | House:{house_total_kwh:.2f}kWh {house_alert}")
        
        current_idx += 1
        time.sleep(10)
        
except KeyboardInterrupt:
    print("🛑 Edge node stopped.")
