import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar
} from "recharts";
import "./App.css";

const API_URL = "https://h33ink3dw1.execute-api.us-east-1.amazonaws.com/default/dashboard";

function StatCard({ title, value, unit }) {
  return (
    <div className="card stat-card">
      <h3>{title}</h3>
      <p>{value} {unit || ""}</p>
    </div>
  );
}

function AlertsPanel({ alerts }) {
  return (
    <div className="card">
      <h3>Alerts</h3>
      <div className="alerts-list">
        {alerts.length === 0 ? (
          <p>No alerts</p>
        ) : (
          alerts.map((alert, index) => (
            <div key={index} className="alert-item">
              <p><strong>Device:</strong> {alert.deviceId || alert.last_reading?.deviceId || "Unknown"}</p>
              <p><strong>Room:</strong> {alert.room || alert.last_reading?.room || "Unknown"}</p>
              <p><strong>Alerts:</strong> {Array.isArray(alert.alerts) ? alert.alerts.join(", ") : "N/A"}</p>
              <p><strong>Time:</strong> {alert.timestamp || "N/A"}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function SensorTable({ data }) {
  return (
    <div className="card">
      <h3>Latest Sensor Readings</h3>
      <table>
        <thead>
          <tr>
            <th>Device</th>
            <th>Room</th>
            <th>Power (W)</th>
            <th>Avg Power (W)</th>
            <th>Temp (C)</th>
            <th>Motion</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, index) => (
            <tr key={index}>
              <td>{item.deviceId}</td>
              <td>{item.room}</td>
              <td>{item.last_power_W}</td>
              <td>{item.avg_power_last_min_W}</td>
              <td>{item.temperature_C}</td>
              <td>{String(item.motion)}</td>
              <td>{item.timestamp}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function App() {
  const [dashboard, setDashboard] = useState({
    summary: { currentTotalPower: 0, deviceCount: 0, alertCount: 0 },
    latestAggregates: [],
    powerTrend: [],
    alerts: []
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [debug, setDebug] = useState(null);

  const loadDashboard = async () => {
    try {
      setError("");
      const res = await fetch(API_URL, {
        method: "GET"
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const raw = await res.json();
      console.log("RAW API RESPONSE:", raw);

      const data = typeof raw.body === "string" ? JSON.parse(raw.body) : raw;
      console.log("PARSED DASHBOARD DATA:", data);

      setDebug(data);

      setDashboard({
        summary: data.summary || { currentTotalPower: 0, deviceCount: 0, alertCount: 0 },
        latestAggregates: data.latestAggregates || [],
        powerTrend: data.powerTrend || [],
        alerts: data.alerts || []
      });

      setLoading(false);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      setError(String(err));
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    const timer = setInterval(loadDashboard, 5000);
    return () => clearInterval(timer);
  }, []);

  const barData = dashboard.latestAggregates.map((item) => ({
    deviceId: item.deviceId,
    power: Number(item.last_power_W || 0)
  }));

  const lineData = dashboard.powerTrend.map((item) => ({
    timestamp: item.timestamp,
    home_total_W: Number(item.home_total_W || 0)
  }));

  return (
    <div className="app">
      <h1>Smart Home Energy Dashboard</h1>

      {loading && <div className="card"><p>Loading dashboard...</p></div>}
      {error && <div className="card"><p>Error: {error}</p></div>}

      <div className="stats-grid">
        <StatCard title="Current Total Power" value={dashboard.summary.currentTotalPower} unit="W" />
        <StatCard title="Devices" value={dashboard.summary.deviceCount} />
        <StatCard title="Alerts" value={dashboard.summary.alertCount} />
      </div>

      <div className="grid two-col">
        <div className="card">
          <h3>Total Home Power Trend</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={lineData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" hide />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="home_total_W" stroke="#3b82f6" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Current Device Power</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="deviceId" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="power" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid two-col">
        <SensorTable data={dashboard.latestAggregates} />
        <AlertsPanel alerts={dashboard.alerts} />
      </div>

      <div className="card">
        <h3>Debug</h3>
        <pre style={{ whiteSpace: "pre-wrap", fontSize: "12px" }}>
          {JSON.stringify(debug, null, 2)}
        </pre>
      </div>
    </div>
  );
}

export default App;