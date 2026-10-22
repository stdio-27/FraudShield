import { cn } from '../lib/utils';
import { describeFeature } from '../lib/risk';
import { formatCompact } from '../lib/format';

const INCREASE = 'INCREASE RISK';

const fmtSigned = (v) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(3)}`;

/**
 * Visual breakdown of the TreeSHAP explanation stored with an alert.
 *
 * The API returns the five features with the largest |SHAP| value for the
 * transaction: `attribution_score` is that absolute value (log-odds of fraud,
 * measured on the scaled model features) and `direction` carries the sign.
 * Everything below is derived from those fields only.
 */
export default function ShapBreakdown({ reasons }) {
  if (!reasons?.length) {
    return (
      <p className="rounded-md border border-dashed px-4 py-6 text-center text-xs text-muted-foreground">
        No explanation was stored for this alert.
      </p>
    );
  }

  const items = reasons.map((r) => {
    const up = r.direction === INCREASE;
    return { ...r, up, signed: up ? r.attribution_score : -r.attribution_score };
  });
  const totalImpact = items.reduce((s, r) => s + r.attribution_score, 0);
  const maxImpact = Math.max(...items.map((r) => r.attribution_score), 1e-9);
  const towardFraud = items.filter((r) => r.up).reduce((s, r) => s + r.attribution_score, 0);
  const awayFromFraud = items.filter((r) => !r.up).reduce((s, r) => s + r.attribution_score, 0);
  const net = towardFraud - awayFromFraud;
  const oddsMultiplier = Math.exp(net);

  return (
    <div className="space-y-5">
      {/* Summary numbers */}
      <dl className="grid grid-cols-3 divide-x rounded-md border text-center">
        <div className="px-3 py-2.5">
          <dt className="text-2xs uppercase tracking-wider text-muted-foreground">Toward fraud</dt>
          <dd className="num mt-1 text-sm font-semibold text-risk-high">{fmtSigned(towardFraud)}</dd>
        </div>
        <div className="px-3 py-2.5">
          <dt className="text-2xs uppercase tracking-wider text-muted-foreground">Away from fraud</dt>
          <dd className="num mt-1 text-sm font-semibold text-risk-low">{fmtSigned(-awayFromFraud)}</dd>
        </div>
        <div className="px-3 py-2.5">
          <dt className="text-2xs uppercase tracking-wider text-muted-foreground">Net (top 5)</dt>
          <dd className="num mt-1 text-sm font-semibold">{fmtSigned(net)}</dd>
        </div>
      </dl>

      {/* Share of total impact, one segment per feature */}
      <div>
        <div className="mb-1.5 flex items-center justify-between text-2xs uppercase tracking-wider text-muted-foreground">
          <span>Share of explained impact</span>
          <span>100% = top 5 features</span>
        </div>
        <div className="flex h-2.5 w-full gap-px overflow-hidden rounded-full bg-muted" role="img" aria-label="Share of impact by feature">
          {items.map((r, i) => (
            <div
              key={r.feature}
              className={r.up ? 'bg-risk-high' : 'bg-risk-low'}
              style={{ width: `${(r.attribution_score / totalImpact) * 100}%`, opacity: 1 - i * 0.14 }}
              title={`${r.feature}: ${((r.attribution_score / totalImpact) * 100).toFixed(1)}%`}
            />
          ))}
        </div>
      </div>

      {/* Diverging bars */}
      <div>
        <div className="mb-2 grid grid-cols-[minmax(0,9rem)_1fr_3.75rem_2.75rem] items-center gap-3 text-2xs uppercase tracking-wider text-muted-foreground">
          <span>Feature</span>
          <div className="flex justify-between">
            <span>← Lowers risk</span>
            <span>Raises risk →</span>
          </div>
          <span className="text-right">SHAP</span>
          <span className="text-right">Share</span>
        </div>

        <ul className="divide-y rounded-md border">
          {items.map((r) => {
            const width = (r.attribution_score / maxImpact) * 50;
            return (
              <li
                key={r.feature}
                className="grid grid-cols-[minmax(0,9rem)_1fr_3.75rem_2.75rem] items-center gap-3 px-3 py-2.5"
              >
                <div className="min-w-0">
                  <p className="num truncate text-xs font-medium">{r.feature}</p>
                  <p className="truncate text-2xs text-muted-foreground">{describeFeature(r.feature)}</p>
                </div>

                <div className="relative h-4" role="img" aria-label={`${r.feature} ${r.up ? 'raises' : 'lowers'} risk`}>
                  <div className="absolute inset-y-0 left-1/2 w-px bg-border" aria-hidden="true" />
                  <div
                    className={cn(
                      'absolute top-1 h-2 rounded-sm',
                      r.up ? 'left-1/2 bg-risk-high/90' : 'right-1/2 bg-risk-low/90',
                    )}
                    style={{ width: `${width}%` }}
                  />
                </div>

                <span className={cn('num text-right text-xs font-medium', r.up ? 'text-risk-high' : 'text-risk-low')}>
                  {fmtSigned(r.signed)}
                </span>
                <span className="num text-right text-xs text-muted-foreground">
                  {((r.attribution_score / totalImpact) * 100).toFixed(0)}%
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        The five strongest features alone move the model’s odds of fraud by about{' '}
        <span className="num font-medium text-foreground">×{oddsMultiplier >= 1000 ? formatCompact(oddsMultiplier) : oddsMultiplier.toFixed(1)}</span>{' '}
        relative to its baseline. Values are TreeSHAP contributions from the XGBoost model in log-odds, computed on
        scaled features; <span className="num">V1–V28</span> are anonymised PCA components, so they rank influence
        without revealing the underlying attribute. Only the top 5 of 34 features are stored per alert.
      </p>
    </div>
  );
}
