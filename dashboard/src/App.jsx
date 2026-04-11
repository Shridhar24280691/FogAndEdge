import { useEffect, useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from "recharts";
import "./App.css";

const API_URL =
  "https://939fbyoanh.execute-api.us-east-1.amazonaws.com/default/smarthome-ingest-readings";

const initialData = {
  summary: {},
  rooms: [],
  sensorCharts: {
    temperature: [],
    voltage: [],
    current: [],
    power: [],
    housePower: [],
    houseConsumption: []
  },
  motionOverview: [],
  alerts: []
};

function safeNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeHousePower(raw, summary) {
  const first = Array.isArray(raw) && raw.length > 0 ? raw[0] : {};

  const currentPower = safeNumber(
    first?.power_W ?? summary?.currentTotalPower ?? 0
  );

  const thresholdPower = safeNumber(
    first?.threshold_W ?? 5000
  );

  return [
    { name: "Current House Power", value: currentPower, fill: "#ef4444" },
    { name: "Threshold Power", value: thresholdPower, fill: "#2563eb" }
  ];
}

const CustomBar = ({ x, y, width, height, payload }) => {
  return (
    <rect
      x={x}
      y={y}
      width={width}
      height={height}
      rx={8}
      ry={8}
      fill={payload.fill}
    />
  );
};

function App() {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        setError("");
        const res = await fetch(API_URL);

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const json = await res.json();
        console.log("API response:", json);

        setData({
          summary: json?.summary || {},
          rooms: Array.isArray(json?.rooms) ? json.rooms : [],
          sensorCharts: {
            temperature: Array.isArray(json?.sensorCharts?.temperature)
              ? json.sensorCharts.temperature
              : [],
            voltage: Array.isArray(json?.sensorCharts?.voltage)
              ? json.sensorCharts.voltage
              : [],
            current: Array.isArray(json?.sensorCharts?.current)
              ? json.sensorCharts.current
              : [],
            power: Array.isArray(json?.sensorCharts?.power)
              ? json.sensorCharts.power
              : [],
            housePower: Array.isArray(json?.sensorCharts?.housePower)
              ? json.sensorCharts.housePower
              : [],
            houseConsumption: Array.isArray(json?.sensorCharts?.houseConsumption)
              ? json.sensorCharts.houseConsumption
              : []
          },
          motionOverview: Array.isArray(json?.motionOverview)
            ? json.motionOverview
            : [],
          alerts: Array.isArray(json?.alerts) ? json.alerts : []
        });
      } catch (err) {
        console.error("Failed to load dashboard data:", err);
        setError("Failed to load dashboard data.");
        setData(initialData);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
    const interval = setInterval(fetchDashboard, 10000);
    return () => clearInterval(interval);
  }, []);

  const summary = data?.summary || {};
  const rooms = Array.isArray(data?.rooms) ? data.rooms : [];
  const sensorCharts = data?.sensorCharts || initialData.sensorCharts;
  const motionOverview = Array.isArray(data?.motionOverview)
    ? data.motionOverview
    : [];
  const alerts = Array.isArray(data?.alerts) ? data.alerts : [];

  const overallHousePowerBarData = useMemo(() => {
    return normalizeHousePower(sensorCharts.housePower, summary);
  }, [sensorCharts.housePower, summary]);

  const renderChart = (title, chartData = [], dataKey, color, unit) => (
    <div className="card chart-card">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={Array.isArray(chartData) ? chartData : []}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="room" />
          <YAxis />
          <Tooltip
            formatter={(value) => [`${safeNumber(value).toFixed(2)} ${unit}`, title]}
          />
          <Legend />
          <Bar dataKey={dataKey} fill={color} radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );

  if (loading) return <div className="app">Loading dashboard...</div>;

  return (
    <div className="app">
      <h2>Smart Home Dashboard</h2>

      {error && (
        <div className="card" style={{ marginBottom: "20px", color: "red" }}>
          {error}
        </div>
      )}

      <div className="stats-grid">
        <div className="card stat-card">
          <h3>Total House Power</h3>
          <p>{safeNumber(summary.currentTotalPower).toFixed(1)} W</p>
        </div>
        <div className="card stat-card">
          <h3>Rooms</h3>
          <p>{safeNumber(summary.roomCount, rooms.length)}</p>
        </div>
        <div className="card stat-card">
          <h3>Alerts</h3>
          <p>{safeNumber(summary.alertCount, alerts.length)}</p>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="card" style={{ marginBottom: "20px" }}>
          <div className="section-title">Active Alerts</div>
          <div className="alerts-list">
            {alerts.map((alert, index) => (
              <div className="alert-item" key={index}>
                <strong>{alert?.severity?.toUpperCase() || "ALERT"}:</strong>{" "}
                {alert?.message || "Unknown alert"}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: "20px" }}>
        <div className="section-title">Overall House Power vs Threshold</div>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={overallHousePowerBarData}
            margin={{ top: 10, right: 20, left: 10, bottom: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis />
            <Tooltip
              formatter={(value) => [`${safeNumber(value).toFixed(1)} W`, "Power"]}
            />
            <Legend />
            <Bar
              dataKey="value"
              name="Power (W)"
              shape={<CustomBar />}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <div className="section-title">Room Overview</div>
        <div className="rooms-grid">
          {rooms.map((room, index) => (
            <div className="card room-card" key={room?.room || index}>
              <h3>{room?.room || "-"}</h3>
              <p><strong>Temperature:</strong> {safeNumber(room?.temperature_C).toFixed(1)} °C</p>
              <p><strong>Voltage:</strong> {safeNumber(room?.avg_voltage_V).toFixed(1)} V</p>
              <p><strong>Current:</strong> {safeNumber(room?.total_current_A).toFixed(2)} A</p>
              <p><strong>Total Power:</strong> {safeNumber(room?.total_power_W).toFixed(1)} W</p>
              <p>
                <strong>Motion:</strong>{" "}
                <span className={`motion-badge ${room?.motion ? "active" : "inactive"}`}>
                  {room?.motion ? "Detected" : "No Motion"}
                </span>
              </p>
              <p><strong>Updated:</strong> {room?.updatedAt || "-"}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="charts-grid">
        {renderChart("Temperature by Room", sensorCharts.temperature, "temperature_C", "#f97316", "°C")}
        {renderChart("Voltage by Room", sensorCharts.voltage, "voltage_V", "#3b82f6", "V")}
        {renderChart("Current by Room", sensorCharts.current, "current_A", "#8b5cf6", "A")}
        {renderChart("Total Power by Room", sensorCharts.power, "power_W", "#10b981", "W")}
      </div>

      <div className="card">
        <div className="section-title">Motion Overview</div>
        <div className="motion-grid">
          {motionOverview.map((item, index) => (
            <div className="motion-item" key={item?.room || index}>
              <h3>{item?.room || "-"}</h3>
              <p>
                Status:{" "}
                <span className={`motion-badge ${item?.motion ? "active" : "inactive"}`}>
                  {item?.motion ? "Motion Detected" : "No Motion"}
                </span>
              </p>
              <p>Active devices: {safeNumber(item?.activeDevices)}</p>
              <p>Last update: {item?.updatedAt || "-"}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;