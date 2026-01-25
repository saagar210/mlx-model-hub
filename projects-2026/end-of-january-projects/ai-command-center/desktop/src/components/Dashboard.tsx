import { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, Legend,
} from 'recharts';
import { Activity, Clock, Shield, Database } from 'lucide-react';
import type { Metrics } from '../lib/types';

const COLORS = ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6'];

export function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [latencyHistory, setLatencyHistory] = useState<{ timestamp: number; latency_ms: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = async () => {
    try {
      const response = await fetch('http://localhost:4000/metrics');
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
        setError(null);
      } else {
        setError('Router not responding');
      }

      const historyResponse = await fetch('http://localhost:4000/metrics/history?minutes=60');
      if (historyResponse.ok) {
        const historyData = await historyResponse.json();
        setLatencyHistory(historyData.history || []);
      }
    } catch {
      setError('Could not connect to router');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="text-gray-400">Loading metrics...</div>;
  }

  if (error || !metrics) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <p className="text-gray-400">{error || 'No metrics available'}</p>
          <p className="text-sm text-gray-500 mt-2">Make sure the Smart Router is running on port 4000</p>
        </div>
      </div>
    );
  }

  const modelData = Object.entries(metrics.requests.by_model).map(([name, value]) => ({
    name,
    value,
  }));

  const complexityData = Object.entries(metrics.requests.by_complexity).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
  }));

  const cacheData = [
    { name: 'Hits', value: metrics.cache.hits },
    { name: 'Misses', value: metrics.cache.misses },
  ];

  const latencyChartData = latencyHistory.slice(-50).map((item) => ({
    time: new Date(item.timestamp * 1000).toLocaleTimeString(),
    latency: Math.round(item.latency_ms),
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Activity className="w-5 h-5" />}
          label="Total Requests"
          value={metrics.requests.total.toLocaleString()}
          color="green"
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="Avg Latency"
          value={`${Math.round(metrics.latency.avg_ms)}ms`}
          color="blue"
        />
        <StatCard
          icon={<Shield className="w-5 h-5" />}
          label="Injection Attempts"
          value={metrics.security.injection_attempts.toString()}
          color="red"
        />
        <StatCard
          icon={<Database className="w-5 h-5" />}
          label="Cache Hit Rate"
          value={`${(metrics.cache.hit_rate * 100).toFixed(1)}%`}
          color="purple"
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Latency Over Time</h3>
          {latencyChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={latencyChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                <YAxis stroke="#9CA3AF" fontSize={12} unit="ms" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                  labelStyle={{ color: '#9CA3AF' }}
                />
                <Line
                  type="monotone"
                  dataKey="latency"
                  stroke="#10B981"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-500">
              No latency data yet
            </div>
          )}
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Model Usage</h3>
          {modelData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={modelData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
                  labelLine={false}
                >
                  {modelData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-500">
              No model usage data yet
            </div>
          )}
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Complexity Distribution</h3>
          {complexityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={complexityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="name" stroke="#9CA3AF" />
                <YAxis stroke="#9CA3AF" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                />
                <Bar dataKey="value" fill="#3B82F6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-500">
              No complexity data yet
            </div>
          )}
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Cache Performance</h3>
          {cacheData.some(d => d.value > 0) ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={cacheData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
                >
                  <Cell fill="#10B981" />
                  <Cell fill="#EF4444" />
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-500">
              No cache data yet
            </div>
          )}
        </div>
      </div>

      {/* Latency Percentiles */}
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-lg font-semibold text-white mb-4">Latency Percentiles</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <p className="text-3xl font-bold text-green-400">{Math.round(metrics.latency.p50_ms)}ms</p>
            <p className="text-gray-400">P50</p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-bold text-yellow-400">{Math.round(metrics.latency.p95_ms)}ms</p>
            <p className="text-gray-400">P95</p>
          </div>
          <div className="text-center">
            <p className="text-3xl font-bold text-red-400">{Math.round(metrics.latency.p99_ms)}ms</p>
            <p className="text-gray-400">P99</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: 'green' | 'blue' | 'red' | 'purple';
}) {
  const colorClasses = {
    green: 'bg-green-900/30 text-green-400',
    blue: 'bg-blue-900/30 text-blue-400',
    red: 'bg-red-900/30 text-red-400',
    purple: 'bg-purple-900/30 text-purple-400',
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>{icon}</div>
        <div>
          <p className="text-gray-400 text-sm">{label}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
        </div>
      </div>
    </div>
  );
}
