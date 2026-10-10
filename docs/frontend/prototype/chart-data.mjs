export function percentile(sorted, fraction) {
  if (!sorted.length) throw new Error('No balances are available.');
  const index = (sorted.length - 1) * fraction;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
}

export function chartData(result) {
  const { paths, horizon_weeks: horizon } = result;
  if (!paths?.length || paths.length !== result.n_paths || !Number.isInteger(horizon) || horizon < 1) {
    throw new Error('The saved simulation has no complete path data.');
  }
  if (paths.some(path => path.balances.length !== horizon + 1 || path.balances.some(v => !Number.isFinite(v)))) {
    throw new Error('The saved balances are incomplete.');
  }
  const band = Array.from({ length: horizon + 1 }, (_, week) => {
    const values = paths.map(path => path.balances[week]).sort((a, b) => a - b);
    return [percentile(values, .1), percentile(values, .5), percentile(values, .9)];
  });
  const ranked = [...paths].sort((a, b) => a.min_balance - b.min_balance || a.path_id - b.path_id);
  const count = Math.min(20, ranked.length);
  const samples = Array.from({ length: count }, (_, i) => ranked[count === 1 ? 0 : Math.round(i * (ranked.length - 1) / (count - 1))]);
  let min = Math.min(0, result.breach_threshold);
  let max = Math.max(0, result.breach_threshold);
  for (const path of paths) for (const value of path.balances) { min = Math.min(min, value); max = Math.max(max, value); }
  const padding = Math.max((max - min) * .06, 100);
  return { band, samples, min: min - padding, max: max + padding };
}

export function evidenceAmount(record, unit) {
  if (unit !== 'usd' && unit !== 'usd_cents') return null;
  const raw = record.amount ?? record.payment_amount;
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return null;
  return raw / (unit === 'usd_cents' ? 100 : 1);
}
