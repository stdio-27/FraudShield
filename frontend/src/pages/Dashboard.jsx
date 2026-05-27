import { useState, useEffect } from 'react';
import api from '../services/api';
import StatCard from '../components/StatCard';
import ChartWrapper from '../components/ChartWrapper';
import LoadingSpinner from '../components/LoadingSpinner';
import {
  Activity,
  DollarSign,
  ShieldAlert,
  Gauge,
  AlertTriangle,
} from 'lucide-react';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [timeSeries, setTimeSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      setError(null);
      const [summaryRes, tsRes] = await Promise.all([
        api.get('/analytics/summary'),
        api.get('/analytics/time-series?window_minutes=120'),
      ]);
      setSummary(summaryRes.data);
      setTimeSeries(tsRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Auto-refresh every 30 seconds to pick up Redis-cached updates
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <LoadingSpinner message="Loading executive dashboard…" />;

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <AlertTriangle className="w-10 h-10 text-amber-400" />
        <p className="text-sm text-amber-400 font-medium">{error}</p>
        <button
          onClick={() => { setLoading(true); fetchData(); }}
          className="px-4 py-2 rounded-lg bg-slate-800 text-sm text-slate-300 hover:bg-slate-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  const s = summary || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Executive Dashboard</h2>
          <p className="text-sm text-slate-400 mt-1">Real-time fraud detection analytics</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/40 text-xs text-slate-400">
          <div className="live-dot" />
          Auto-refresh 30s
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Total Transactions"
          value={s.total_transactions?.toLocaleString() || '0'}
          icon={Activity}
          accentColor="blue"
          trend="up"
        />
        <StatCard
          title="Total Volume"
          value={`$${(s.total_volume || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          icon={DollarSign}
          accentColor="emerald"
          trend="up"
        />
        <StatCard
          title="Flagged Incidents"
          value={s.flagged_count?.toLocaleString() || '0'}
          subtitle={`${s.fraud_rate_pct || 0}% fraud rate`}
          icon={ShieldAlert}
          accentColor="red"
          trend={s.flagged_count > 0 ? 'up' : 'neutral'}
        />
        <StatCard
          title="Avg Risk Score"
          value={(s.avg_fraud_score || 0).toFixed(4)}
          subtitle={`Peak: ${(s.max_fraud_score || 0).toFixed(4)}`}
          icon={Gauge}
          accentColor="amber"
          trend="neutral"
        />
      </div>

      {/* Time-Series Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartWrapper
          data={timeSeries?.buckets}
          title="Transaction Velocity (5-min bins)"
          dataKey="tx_count"
          color="#3b82f6"
        />
        <ChartWrapper
          data={timeSeries?.buckets}
          title="Flagged Fraud Over Time"
          dataKey="flagged_count"
          color="#ef4444"
        />
      </div>
    </div>
  );
}
