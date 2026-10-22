// Mirrors the backend alert engine: CRITICAL >= 0.95, HIGH >= ALERT_THRESHOLD (default 0.85).
export const HIGH_CONFIDENCE_THRESHOLD = 0.85;
export const CRITICAL_THRESHOLD = 0.95;

export function severityOf(score) {
  if (score >= CRITICAL_THRESHOLD) return { key: 'critical', label: 'Critical', tone: 'high' };
  if (score >= HIGH_CONFIDENCE_THRESHOLD) return { key: 'high', label: 'High', tone: 'high' };
  return { key: 'elevated', label: 'Elevated', tone: 'medium' };
}

export const STATUS_META = {
  open: { label: 'Open', tone: 'high' },
  investigating: { label: 'Investigating', tone: 'medium' },
  confirmed_fraud: { label: 'Confirmed fraud', tone: 'neutral' },
  false_positive: { label: 'False positive', tone: 'low' },
};

export const STATUS_ORDER = ['open', 'investigating', 'confirmed_fraud', 'false_positive'];

const FEATURE_LABELS = {
  Amount: 'Transaction amount',
  hour_of_day: 'Hour of day',
  is_weekend: 'Weekend flag',
  amount_zscore: 'Amount z-score',
  amount_log: 'Log-scaled amount',
  high_value_flag: 'High-value flag (> $1,000)',
};

/** Human description for a model feature name. */
export function describeFeature(name) {
  if (FEATURE_LABELS[name]) return FEATURE_LABELS[name];
  if (/^V\d+$/.test(name)) return 'Anonymised PCA component';
  return 'Model feature';
}
