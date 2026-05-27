import { useState } from 'react';
import { ChevronDown, ChevronUp, Zap } from 'lucide-react';

function ScoreBadge({ score }) {
  let classes = 'badge-safe';
  if (score >= 0.85) classes = 'badge-danger';
  else if (score >= 0.5) classes = 'badge-warning';

  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${classes}`}>
      {score >= 0.85 && <Zap className="w-3 h-3" />}
      {(score * 100).toFixed(1)}%
    </span>
  );
}

function StatusDropdown({ currentStatus, onStatusChange }) {
  const [open, setOpen] = useState(false);
  const statuses = ['open', 'investigating', 'confirmed_fraud', 'false_positive'];
  const statusStyles = {
    open: 'badge-danger',
    investigating: 'badge-warning',
    confirmed_fraud: 'badge-info',
    false_positive: 'badge-safe',
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${statusStyles[currentStatus]}`}
      >
        {currentStatus.replace('_', ' ')}
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 glass-card border border-slate-600/50 rounded-lg py-1 min-w-[160px] shadow-xl">
          {statuses.map((s) => (
            <button
              key={s}
              onClick={() => { onStatusChange(s); setOpen(false); }}
              className={`block w-full text-left px-4 py-2 text-xs font-medium transition-colors ${
                s === currentStatus
                  ? 'text-emerald-400 bg-emerald-500/10'
                  : 'text-slate-300 hover:bg-slate-800/80'
              }`}
            >
              {s.replace('_', ' ')}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AlertRow({ alert, index, onStatusChange }) {
  const [expanded, setExpanded] = useState(false);
  const reasons = alert.shap_reasons || [];

  return (
    <>
      <tr
        className={`border-b border-slate-800/40 transition-colors hover:bg-slate-800/30 ${
          index % 2 === 0 ? 'bg-slate-900/30' : ''
        }`}
      >
        <td className="px-4 py-3 text-xs text-slate-500 font-mono">
          {alert.tx_id?.slice(0, 8)}…
        </td>
        <td className="px-4 py-3">
          <ScoreBadge score={alert.fraud_score} />
        </td>
        <td className="px-4 py-3">
          <StatusDropdown currentStatus={alert.status || 'open'} onStatusChange={(s) => onStatusChange(alert.alert_id, s)} />
        </td>
        <td className="px-4 py-3 text-right">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-slate-400 hover:text-emerald-400 transition-colors flex items-center gap-1 ml-auto"
          >
            SHAP
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-900/60">
          <td colSpan={4} className="px-6 py-4">
            <p className="text-xs font-semibold text-slate-400 mb-3 uppercase tracking-wider">
              Top 5 SHAP Feature Attributions
            </p>
            {reasons.length === 0 ? (
              <p className="text-xs text-slate-500">No SHAP data available for this alert.</p>
            ) : (
              <div className="space-y-2">
                {reasons.map((r, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-xs font-mono text-slate-300 w-28 truncate" title={r.feature}>
                      {r.feature}
                    </span>
                    <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          r.direction === 'INCREASE RISK' ? 'bg-red-500' : 'bg-emerald-500'
                        }`}
                        style={{ width: `${Math.min(Math.abs(r.attribution_score) * 100, 100)}%` }}
                      />
                    </div>
                    <span className={`text-xs font-semibold w-16 text-right ${
                      r.direction === 'INCREASE RISK' ? 'text-red-400' : 'text-emerald-400'
                    }`}>
                      {r.attribution_score.toFixed(4)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
