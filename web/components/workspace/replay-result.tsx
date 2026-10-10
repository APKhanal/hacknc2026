"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "./app-shell";
import { AeroButton, AeroPanel } from "@/components/ui/aero";
import { VerdictBadge } from "@/components/ui/verdict-badge";
import { computeWeeklyBand, sampleRepresentativePaths } from "@/lib/fanchart";
import { classifyBreachRate } from "@/lib/verdict";
import { evidenceAmount } from "@/lib/money";
import type { Customer, RunInputs, SavedReplay, SimResult, TxnRecord } from "@/lib/types";

const usd = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
const percent = (n: number) => new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 }).format(n);
const points = (n: number) => `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n * 100)} percentage point${Math.abs(n * 100) === 1 ? "" : "s"}`;
const dateOf = (record: TxnRecord) => String(record.purchase_date ?? record.transaction_date ?? record.payment_date ?? record.deposit_date ?? "Unavailable");

function BalanceChart({ result }: { result: SimResult }) {
  const [week, setWeek] = React.useState(0);
  // Only worth overlaying when a decision was actually applied - with no
  // delta, baseline_band is identical to the decision band already drawn.
  const showBaseline = result.delta_breach_rate !== null && result.baseline_band.length > 0;
  const chart = React.useMemo(() => {
    if (result.paths.length !== result.n_paths || result.paths.some(p => p.balances.length !== result.horizon_weeks + 1 || p.balances.some(v => !Number.isFinite(v)))) return null;
    const band = computeWeeklyBand(result.paths), samples = sampleRepresentativePaths(result.paths, 20);
    if (!band.length) return null;
    let min = result.breach_threshold, max = result.breach_threshold;
    for (const path of result.paths) for (const value of path.balances) { min = Math.min(min, value); max = Math.max(max, value); }
    if (showBaseline) for (const b of result.baseline_band) { min = Math.min(min, b.p10); max = Math.max(max, b.p90); }
    const pad = Math.max((max - min) * .05, 1);
    return { band, samples, min: min - pad, max: max + pad };
  }, [result, showBaseline]);
  if (!chart) return <p role="alert">This replay has incomplete balance paths. The summary remains available. Reload the replay to try again.</p>;
  const { band, samples, min, max } = chart;
  const x = (w: number) => 78 + w / Math.max(result.horizon_weeks, 1) * 672;
  const y = (v: number) => 238 - (v - min) / Math.max(max - min, 1) * 214;
  const upper = band.map(p => `${x(p.week)},${y(p.p90)}`).join(" L ");
  const lower = [...band].reverse().map(p => `${x(p.week)},${y(p.p10)}`).join(" L ");
  const median = band.map(p => `${x(p.week)},${y(p.p50)}`).join(" L ");
  const baseUpper = result.baseline_band.map(p => `${x(p.week)},${y(p.p90)}`).join(" L ");
  const baseLower = [...result.baseline_band].reverse().map(p => `${x(p.week)},${y(p.p10)}`).join(" L ");
  const baseMedian = result.baseline_band.map(p => `${x(p.week)},${y(p.p50)}`).join(" L ");
  const selected = band[Math.min(week, band.length - 1)];
  const selectedBaseline = result.baseline_band[Math.min(week, result.baseline_band.length - 1)];
  return <>
    <svg className="balance-chart" viewBox="0 0 770 275" role="img" aria-label={`${result.n_paths} simulated balance paths, middle 80% range, median, and 20 representative paths across ${result.horizon_weeks} weeks${showBaseline ? ", with a baseline comparison" : ""}.`}>
      {[min, (min + max) / 2, max].map(value => <g key={value}><line className="chart-grid" x1={78} x2={750} y1={y(value)} y2={y(value)} /><text className="chart-label" x={68} y={y(value)} textAnchor="end" dominantBaseline="middle">{Math.round(value).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })}</text></g>)}
      {showBaseline && <path className="chart-baseline-band" d={`M ${baseUpper} L ${baseLower} Z`} />}
      <path className="chart-band" d={`M ${upper} L ${lower} Z`} />
      {samples.map(p => <path key={p.path_id} className="chart-sample" d={`M ${p.balances.map((v, w) => `${x(w)},${y(v)}`).join(" L ")}`} />)}
      {showBaseline && <path className="chart-baseline-median" d={`M ${baseMedian}`} />}
      <path className="chart-median" d={`M ${median}`} />
      <line className="chart-threshold" x1={78} x2={750} y1={y(result.breach_threshold)} y2={y(result.breach_threshold)} />
      <line className="chart-selected" x1={x(week)} x2={x(week)} y1={24} y2={238} />
      {[0, Math.round(result.horizon_weeks / 2), result.horizon_weeks].map(w => <text key={w} className="chart-label" x={x(w)} y={265} textAnchor={w === 0 ? "start" : w === result.horizon_weeks ? "end" : "middle"}>Week {w}</text>)}
    </svg>
    <p>Middle 80% of simulated balances · Median line · 20 sample paths · Threshold {usd(result.breach_threshold)}.</p>
    {showBaseline && (
      <div className="chart-legend">
        <span><span className="chart-legend-swatch" style={{ background: "#13294b" }} />With this decision</span>
        <span><span className="chart-legend-swatch" style={{ background: "#eb6834" }} />Baseline (no decision)</span>
      </div>
    )}
    <label className="week-control" htmlFor="chart-week">Inspect week {week}<input id="chart-week" type="range" min={0} max={result.horizon_weeks} value={week} onChange={e => setWeek(Number(e.target.value))} /></label>
    <table className="integration-table"><caption className="sr-only">Balances at week {week}</caption><thead><tr>{showBaseline && <th>Series</th>}<th>10th percentile</th><th>Median</th><th>90th percentile</th></tr></thead><tbody>
      <tr>{showBaseline && <td>With this decision</td>}<td>{usd(selected.p10)}</td><td>{usd(selected.p50)}</td><td>{usd(selected.p90)}</td></tr>
      {showBaseline && selectedBaseline && <tr><td>Baseline</td><td>{usd(selectedBaseline.p10)}</td><td>{usd(selectedBaseline.p50)}</td><td>{usd(selectedBaseline.p90)}</td></tr>}
    </tbody></table>
    <p className="small-copy">Week 0 is the opening balance; later weeks are week-end balances. The range describes each week separately, not a guarantee about an entire path.</p>
  </>;
}

export function ReplayResult({ result, inputs, customers = [] }: { result: SimResult; inputs: RunInputs | null; customers?: Customer[] }) {
  const router = useRouter(), pathname = usePathname(), params = useSearchParams();
  const modelView = params.get("view") === "model", txnId = params.get("txn");
  const [page, setPage] = React.useState(0);
  const [saved, setSaved] = React.useState<SavedReplay | null>(null);
  const [copyStatus, setCopyStatus] = React.useState("");
  const [copyFallback, setCopyFallback] = React.useState("");
  const dialog = React.useRef<HTMLDialogElement>(null), closeButton = React.useRef<HTMLButtonElement>(null), opener = React.useRef<HTMLElement | null>(null);
  const transactions = React.useMemo(() => Object.entries(inputs?.evidence ?? {}).sort((a, b) => dateOf(b[1]).localeCompare(dateOf(a[1])) || a[0].localeCompare(b[0])), [inputs]);
  React.useEffect(() => {
    try { const history = JSON.parse(localStorage.getItem("counterfactual.workspace.v1") ?? "null")?.recent; if (Array.isArray(history)) setSaved(history.find((r: SavedReplay) => r.run_id === result.run_id) ?? null); } catch { /* Saved inputs work without browser history. */ }
  }, [result.run_id]);
  React.useEffect(() => {
    const sheet = dialog.current;
    if (!sheet) return;
    if (txnId && !sheet.open) { sheet.showModal(); closeButton.current?.focus(); }
    if (!txnId && sheet.open) { sheet.close(); opener.current?.focus(); }
  }, [txnId]);
  function query(view: boolean, txn?: string) {
    const next = new URLSearchParams();
    if (view) next.set("view", "model");
    if (txn) next.set("txn", txn);
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }
  function showEvidence(id: string, event: React.MouseEvent<HTMLButtonElement>) { opener.current = event.currentTarget; query(modelView, id); }
  const evidenceButton = (id: string) => <button key={id} type="button" className="text-button evidence-button" onClick={event => showEvidence(id, event)} aria-label={`View transaction ${id}`}>{id}</button>;
  const record = txnId ? inputs?.evidence[txnId] : undefined;
  const unit = txnId ? inputs?.amount_units?.evidence[txnId] : undefined;
  const amount = record ? evidenceAmount(record, unit) : null;
  const profile = customers.find(c => c.customer_id === inputs?.model.customer_id)?.name ?? saved?.customer ?? inputs?.model.customer_id;
  const question = inputs?.delta.raw_text || saved?.question || inputs?.delta.label;
  async function copyLink() {
    const url = `${window.location.origin}${pathname}`;
    try { await navigator.clipboard.writeText(url); setCopyStatus("Replay link copied."); setCopyFallback(""); }
    catch { setCopyStatus("Copy the replay link below."); setCopyFallback(url); }
  }
  return <AppShell view="replays"><div className="page-heading"><h1>{question || "Your decision, replayed."}</h1><p>{profile ? `${profile} · ` : ""}{result.n_paths} simulated paths across {result.horizon_weeks} weeks.</p></div>
    <div className="replay-toolbar"><div role="group" aria-label="Replay view"><AeroButton type="button" variant={modelView ? "secondary" : "primary"} aria-pressed={!modelView} onClick={() => query(false)}>Results</AeroButton><AeroButton type="button" variant={modelView ? "primary" : "secondary"} aria-pressed={modelView} onClick={() => query(true)}>Saved model & evidence</AeroButton></div><AeroButton type="button" variant="secondary" onClick={copyLink}>Copy replay link</AeroButton></div>
    <p role="status" className="small-copy">{copyStatus}</p>{copyFallback && <input className="copy-link-input" readOnly value={copyFallback} aria-label="Replay link" onFocus={e => e.currentTarget.select()} />}
    {!modelView ? <>
      <AeroPanel className="result-panel"><dl className="result-stats"><div><dt>{result.delta_breach_rate === null ? "Baseline" : "With this decision"}</dt><dd>{percent(result.delta_breach_rate ?? result.baseline_breach_rate)}</dd><div style={{ marginTop: 8 }}><VerdictBadge verdict={classifyBreachRate(result.delta_breach_rate ?? result.baseline_breach_rate)} /></div></div><div><dt>Baseline breach rate</dt><dd>{percent(result.baseline_breach_rate)}</dd></div><div><dt>Median minimum balance</dt><dd>{usd(result.median_min_balance)}</dd></div></dl><p>Of simulated futures fall below {usd(result.breach_threshold)} at a week end.</p>{saved?.prose && <p className="response-prose">{saved.prose}</p>}<h2>How the balance could change</h2><BalanceChart result={result} /></AeroPanel>
      <AeroPanel className="result-panel"><h2>{result.culprit ? "The recurring charge to look at" : "No contributing recurring charge"}</h2>{result.culprit ? <><p>{result.culprit.label} · {usd(result.culprit.amount)}{result.culprit.essential ? " · Essential" : ""}. Removing this obligation reduced the breach rate by {points(result.culprit.marginal_contribution)} in this simulation.</p><div className="evidence-buttons">{result.culprit.evidence.map(evidenceButton)}</div></> : <p>No recurring obligation had a positive measured contribution. This does not mean that every simulated balance stayed above the threshold.</p>}</AeroPanel>
      <AeroPanel className="result-panel"><h2>Evidence behind the results</h2>{result.claims.length ? <ul className="evidence-list">{result.claims.map(claim => <li key={claim.claim_id}><strong>{claim.kind.replaceAll("_", " ")}</strong>: {typeof claim.value === "number" ? claim.unit === "usd" ? usd(claim.value) : claim.unit === "probability" ? claim.kind === "culprit_marginal_contribution" ? points(claim.value) : percent(claim.value) : claim.value : claim.value}{claim.unit && !["usd", "probability"].includes(claim.unit) ? ` (${claim.unit})` : ""}<details><summary>{claim.evidence.length} supporting transactions</summary><div className="evidence-buttons">{claim.evidence.map(evidenceButton)}</div></details></li>)}</ul> : <p>No claim evidence was returned.</p>}</AeroPanel>
    </> : inputs ? <>
      <AeroPanel className="result-panel"><h2>Model saved with this replay</h2><p>These are the fitted assumptions used in this run, not a later profile fit.</p><dl className="model-details"><div><dt>Opening balance</dt><dd>{usd(inputs.model.opening_balance)}</dd></div><div><dt>Fit window</dt><dd>{inputs.model.fit_window_days} days</dd></div><div><dt>Income</dt><dd>{usd(inputs.model.income.mean)} every {inputs.model.income.cadence_days} days</dd></div><div><dt>Income standard deviation</dt><dd>{usd(inputs.model.income.std)}</dd></div><div><dt>Weekly discretionary spending</dt><dd>{usd(inputs.model.discretionary.weekly_mean)}</dd></div><div><dt>Weekly spending standard deviation</dt><dd>{usd(inputs.model.discretionary.weekly_std)}</dd></div></dl><h3>Recurring obligations</h3><ul className="evidence-list">{inputs.model.recurring.map(r => <li key={r.obligation_id}><strong>{r.label}</strong> · {usd(r.amount)} every {r.cadence_days} days{r.essential ? " · Essential" : ""}<div className="evidence-buttons">{r.evidence.map(evidenceButton)}</div></li>)}</ul><details><summary>Original saved model and decision</summary><pre>{JSON.stringify({ model: inputs.model, delta: inputs.delta }, null, 2)}</pre></details></AeroPanel>
      <AeroPanel className="result-panel"><h2>Saved transactions</h2><p>{transactions.length} original records · newest first.</p><ul className="transaction-list">{transactions.slice(page * 10, page * 10 + 10).map(([id, raw]) => {const value = evidenceAmount(raw, inputs.amount_units?.evidence?.[id]);return <li key={id}><div><strong>{String(raw.description ?? raw.merchant ?? raw.type ?? "Transaction")}</strong><span>{dateOf(raw)} · {value === null ? "Amount unavailable" : usd(value)}</span></div>{evidenceButton(id)}</li>;})}</ul><div className="pagination"><AeroButton type="button" variant="secondary" disabled={page === 0} onClick={() => setPage(n => n - 1)}>Previous</AeroButton><span>Page {page + 1} of {Math.max(1, Math.ceil(transactions.length / 10))}</span><AeroButton type="button" variant="secondary" disabled={(page + 1) * 10 >= transactions.length} onClick={() => setPage(n => n + 1)}>Next</AeroButton></div></AeroPanel>
    </> : <AeroPanel className="result-panel"><h2>The saved model could not load</h2><p>The simulation summary remains available. Reload to retry fetching saved inputs.</p><AeroButton type="button" onClick={() => router.refresh()}>Retry saved inputs</AeroButton></AeroPanel>}
    {!inputs && !modelView && <p role="alert">Saved inputs are unavailable; evidence details cannot be displayed. Reload to retry.</p>}
    <p className="inline-note"><Link href="/?view=overview">Ask another question</Link> · <Link href="/?view=replays">Back to replays</Link></p>
    <dialog ref={dialog} className="evidence-dialog" aria-labelledby="evidence-title" onCancel={event => { event.preventDefault(); query(modelView); }}><div className="evidence-dialog-heading"><h2 id="evidence-title">Transaction evidence</h2><button ref={closeButton} className="aero-button aero-button--secondary" type="button" onClick={() => query(modelView)}>Close transaction evidence</button></div>{record ? <><dl className="model-details"><div><dt>Original transaction ID</dt><dd>{String(record._id ?? txnId)}</dd></div><div><dt>Date</dt><dd>{dateOf(record)}</dd></div><div><dt>Amount in USD</dt><dd>{amount === null ? "Unavailable: monetary unit missing or unsupported" : usd(amount)}</dd></div><div><dt>Stored monetary unit</dt><dd>{unit ?? "Unavailable"}</dd></div><div><dt>Description</dt><dd>{String(record.description ?? record.type ?? "Unavailable")}</dd></div></dl><details><summary>Untouched original JSON</summary><pre>{JSON.stringify(record, null, 2)}</pre></details><a className="text-button" href={`/api/backend/txn/${encodeURIComponent(txnId!)}`} target="_blank" rel="noreferrer">Open API record</a></> : <p role="alert">This transaction is not present in the saved evidence. Its details cannot be verified.</p>}</dialog>
  </AppShell>;
}
