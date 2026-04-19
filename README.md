## ✨ Features

- **Multi-room sensor monitoring** - Temperature, voltage, current, power, motion across 4 rooms
- **Fog computing layer** - Local aggregation & rule-based anomaly detection
- **Real-time alerts** - House power > 5000W, high power without motion
- **Scalable AWS backend** - IoT Core → Lambda → SQS → DynamoDB
- **Live React dashboard** - Charts, room stats, active alerts
- **Optimized storage** - Only summaries & alerts stored (no raw sensor spam)

## 🏗️ Architecture Overview
Sensors (10s intervals)
↓ MQTT (local)
Fog Node (aggregation + alerts)
↓ MQTT over TLS
AWS IoT Core → Lambda/SQS → DynamoDB
↓ API Gateway
React Dashboard (AWS Amplify)

text

## 📱 Live Demo

**[View Dashboard](https://main.d2za4tbv92h2ur.amplifyapp.com)**

**Demo Flow:**
1. Start sensor simulator → generates realistic appliance data
2. Watch fog node process readings → see aggregation logs
3. Trigger 5000W threshold → watch alert appear
4. Check room-level charts → motion-aware alerts

## 🚀 Quick Start (Local Development)

### Prerequisites
- Node.js 18+
- AWS CLI configured
- Docker (optional, for sensor simulator)

### 1. Clone & Install
```bash
git clone https://github.com/yourusername/smart-home-energy-monitor.git
cd smart-home-energy-monitor
npm install
```

### 2. Environment Setup
```bash
cp .env.example .env
# Fill AWS credentials, IoT endpoint, DynamoDB table names
```

### 3. Start Components
```bash
# Terminal 1: Sensor Simulator
npm run sensors

# Terminal 2: Fog Node
npm run fog

# Terminal 3: Local API (optional)
npm run dev
```

### 4. Deploy to AWS
```bash
# Backend (CloudFormation/Serverless)
npm run deploy

# Frontend (Amplify)
npm run amplify-deploy
```

## 🛠️ Project Structure
├── /sensors/ # Sensor simulator (temperature, current, voltage, power, motion)
├── /fog/ # Fog node (MQTT subscriber, aggregation, alert logic)
├── /backend/ # AWS Lambda functions (IoT handler, API Gateway, SQS processor)
├── /frontend/ # React dashboard (Amplify hosted)
├── /aws/ # CloudFormation/Serverless Framework config
├── /docs/ # Architecture diagrams, report
└── README.md

text

## 🔌 Sensors (Real-world equivalents)

| Sensor Type | Example | Purpose |
|-------------|---------|---------|
| Temperature | DS18B20 | Room comfort monitoring |
| Current | ACS712 | Appliance load detection |
| Voltage | ZMPT101B | Supply stability |
| Power | Calculated | Total consumption alerting |
| Motion | PIR HC-SR501 | Occupancy-aware alerts |

## 🎯 Alert Logic (Fog Layer)

**Rule 1:** `houseTotalPower > 5000W` → **HIGH alert**  
**Rule 2:** `roomPower > threshold AND noMotion` → **MEDIUM alert**

## ☁️ AWS Services Used

| Service | Purpose |
|---------|---------|
| AWS IoT Core | MQTT ingestion (port 8883, TLS) |
| AWS Lambda | Processing, API responses |
| Amazon SQS | Async alert queue |
| DynamoDB | Summary storage, alerts |
| API Gateway | Dashboard REST endpoints |
| AWS Amplify | React frontend hosting |

## 📊 Dashboard Features

![Dashboard Screenshot](screenshots/dashboard.png)

- **House Overview**: Total power, active rooms, alert count
- **Room Details**: Per-room power, temperature, motion status
- **Charts**: Current, voltage, temperature trends
- **Alerts Panel**: Real-time severity notifications

## 🧪 Testing the System

### Trigger House Alert
```bash
# In sensor simulator, force high power readings
npm run sensors -- --override-power=6000
```

### Trigger Room Alert
```bash
# High power + no motion
npm run sensors -- --room=kitchen --power=2500 --motion=false
```

## 🔒 Security & Communication

- **Sensor → Fog**: MQTT (local network, port 1883)
- **Fog → AWS**: MQTT over TLS (port 8883, X.509 certs)
- **Dashboard → Backend**: HTTPS via API Gateway (CORS enabled)

## 📈 Performance

- **Sensor interval**: 10 seconds
- **Fog processing**: <100ms per message
- **Dashboard refresh**: 5 seconds
- **DynamoDB writes**: Summary only (90% reduction)

## 🛠️ Tech Stack

```yaml
Frontend:     React 18, Chart.js, Tailwind CSS
Backend:      Node.js 20, AWS SDK v3
Sensors:      Node.js MQTT client (mqtt.js)
Fog:          Node.js, Redis (local state)
Cloud:        AWS IoT Core, Lambda, SQS, DynamoDB, API Gateway, Amplify
Communication: MQTT, MQTT over TLS, HTTPS
```

## 📝 Deployment Notes

**Backend (Serverless Framework):**
```bash
npm install -g serverless
serverless deploy --stage prod
```

**Frontend (Amplify):**
```bash
amplify init
amplify add hosting
amplify publish
```
