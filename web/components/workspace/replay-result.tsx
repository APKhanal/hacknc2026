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
import {
  culpritMatters, describeTransaction, dipSentence, dipSummary, displayName, horizonLabel, money, money0,
  oddsStat, transactionDate, verdictSentence, weekDate, weekLabel,
} from "@/lib/summary";
import type { Customer, RunInputs, SavedReplay, SimResult, TxnRecord } from "@/lib/types";

const usd = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
const rawDate = (record: TxnRecord) => String(record.purchase_date ?? record.transaction_date ?? record.payment_date ?? record.deposit_date ?? "");
const days = (n: number) => n === 7 ? "week" : n === 14 ? "2 weeks" : n === 30 ? "month" : `${n} days`;

function BalanceChart({ result, asked, startWeek }: { result: SimResult; asked: Date | null; startWeek: number }) {
  const [week, setWeek] = React.useState(startWeek);
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
  if (!chart) return <p role="alert">Some of the simulation data is missing, so the chart can't be drawn. The summary above is still accurate. Reload to try again.</p>;
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
  const date = weekDate(asked, week);
  return <>
    <svg className="balance-chart" viewBox="0 0 770 275" role="img" aria-label={`Your balance over the next ${horizonLabel(result.horizon_weeks)} across ${result.n_paths} simulations${showBaseline ? ", with and without this purchase" : ""}.`}>
      {[min, (min + max) / 2, max].map(value => <g key={value}><line className="chart-grid" x1={78} x2={750} y1={y(value)} y2={y(value)} /><text className="chart-label" x={68} y={y(value)} textAnchor="end" dominantBaseline="middle">{money0(Math.round(value))}</text></g>)}
      {showBaseline && <path className="chart-baseline-band" d={`M ${baseUpper} L ${baseLower} Z`} />}
      <path className="chart-band" d={`M ${upper} L ${lower} Z`} />
      {samples.map(p => <path key={p.path_id} className="chart-sample" d={`M ${p.balances.map((v, w) => `${x(w)},${y(v)}`).join(" L ")}`} />)}
      {showBaseline && <path className="chart-baseline-median" d={`M ${baseMedian}`} />}
      <path className="chart-median" d={`M ${median}`} />
      <line className="chart-threshold" x1={78} x2={750} y1={y(result.breach_threshold)} y2={y(result.breach_threshold)} />
      <line className="chart-selected" x1={x(week)} x2={x(week)} y1={24} y2={238} />
      {[0, Math.round(result.horizon_weeks / 2), result.horizon_weeks].map(w => <text key={w} className="chart-label" x={x(w)} y={265} textAnchor={w === 0 ? "start" : w === result.horizon_weeks ? "end" : "middle"}>{weekLabel(w)}</text>)}
    </svg>
    <p>The dark line is your typical balance. The shaded area is where most simulations landed, and the dashed line is {money0(result.breach_threshold)}.</p>
    {showBaseline && (
      <div className="chart-legend">
        <span><span className="chart-legend-swatch" style={{ background: "#13294b" }} />With this purchase</span>
        <span><span className="chart-legend-swatch" style={{ background: "#eb6834" }} />Without it</span>
      </div>
    )}
    <label className="week-control" htmlFor="chart-week">Showing: {week === 0 ? "today" : `${weekLabel(week).toLowerCase()}${date ? `, the week of ${date}` : ""}`}<input id="chart-week" type="range" min={0} max={result.horizon_weeks} value={week} onChange={e => setWeek(Number(e.target.value))} /></label>
    <table className="integration-table"><caption className="sr-only">Balance at {weekLabel(week)}</caption><thead><tr>{showBaseline && <th></th>}<th>Bad week</th><th>Typical</th><th>Good week</th></tr></thead><tbody>
      <tr>{showBaseline && <td>With this purchase</td>}<td>{money0(selected.p10)}</td><td>{money0(selected.p50)}</td><td>{money0(selected.p90)}</td></tr>
      {showBaseline && selectedBaseline && <tr><td>Without it</td><td>{money0(selectedBaseline.p10)}</td><td>{money0(selectedBaseline.p50)}</td><td>{money0(selectedBaseline.p90)}</td></tr>}
    </tbody></table>
    <p className="small-copy">Your balance at the end of that week. A bad week means only 1 in 10 simulations ended lower; a good week means only 1 in 10 ended higher.</p>
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
  const transactions = React.useMemo(() => Object.entries(inputs?.evidence ?? {}).sort((a, b) => rawDate(b[1]).localeCompare(rawDate(a[1])) || a[0].localeCompare(b[0])), [inputs]);
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
  // A readable row ("DoorDash · Mar 25, 2026 · $57.97") instead of a raw ID.
  const txnLabel = (id: string) => {
    const raw = inputs?.evidence[id];
    if (!raw) return "Transaction";
    const value = evidenceAmount(raw, inputs?.amount_units?.evidence?.[id]);
    return [describeTransaction(raw), transactionDate(raw), value === null ? null : usd(value)].filter(Boolean).join(" · ");
  };
  const evidenceButton = (id: string) => <button key={id} type="button" className="text-button evidence-button" onClick={event => showEvidence(id, event)} aria-label={`View details for ${txnLabel(id)}`}>{txnLabel(id)}</button>;
  const record = txnId ? inputs?.evidence[txnId] : undefined;
  const unit = txnId ? inputs?.amount_units?.evidence[txnId] : undefined;
  const amount = record ? evidenceAmount(record, unit) : null;
  const rawName = customers.find(c => c.customer_id === inputs?.model.customer_id)?.name ?? saved?.customer;
  const name = rawName ? displayName(rawName) : null;
  const question = inputs?.delta.raw_text || saved?.question || inputs?.delta.label;
  const asked = inputs?.created_at ? new Date(inputs.created_at) : null;
  const rate = result.delta_breach_rate ?? result.baseline_breach_rate;
  const dip = dipSummary(result);
  const evidenceIds = React.useMemo(() => [...new Set(result.claims.flatMap(c => c.evidence))]
    .sort((a, b) => rawDate(inputs?.evidence[b] ?? {}).localeCompare(rawDate(inputs?.evidence[a] ?? {}))), [result, inputs]);
  async function copyLink() {
    const url = `${window.location.origin}${pathname}`;
    try { await navigator.clipboard.writeText(url); setCopyStatus("Link copied."); setCopyFallback(""); }
    catch { setCopyStatus("Copy the link below."); setCopyFallback(url); }
  }
  return <AppShell view="replays"><div className="page-heading"><h1>{question ? `“${question}”` : "Your decision, replayed."}</h1><p>{name ? `${name} · ` : ""}{result.n_paths} simulations of the next {horizonLabel(result.horizon_weeks)}{asked ? ` · asked ${asked.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}` : ""}</p></div>
    <div className="replay-toolbar"><div role="group" aria-label="Replay view"><AeroButton type="button" variant={modelView ? "secondary" : "primary"} aria-pressed={!modelView} onClick={() => query(false)}>Results</AeroButton><AeroButton type="button" variant={modelView ? "primary" : "secondary"} aria-pressed={modelView} onClick={() => query(true)}>What we assumed</AeroButton></div><AeroButton type="button" variant="secondary" onClick={copyLink}>Copy link</AeroButton></div>
    <p role="status" className="small-copy">{copyStatus}</p>{copyFallback && <input className="copy-link-input" readOnly value={copyFallback} aria-label="Replay link" onFocus={e => e.currentTarget.select()} />}
    {!modelView ? <>
      <AeroPanel className="result-panel">
        <h2>{verdictSentence(result, inputs?.delta ?? null, asked)}</h2>
        <div style={{ margin: "4px 0 14px" }}><VerdictBadge verdict={classifyBreachRate(rate)} /></div>
        {dipSentence(result, asked) && <p className="response-prose">{dipSentence(result, asked)}</p>}
        <dl className="result-stats">
          <div><dt>{result.delta_breach_rate === null ? "Chance of dipping below $0" : "With this purchase"}</dt><dd>{oddsStat(rate)}</dd></div>
          {result.delta_breach_rate !== null && <div><dt>Without it</dt><dd>{oddsStat(result.baseline_breach_rate)}</dd></div>}
          <div><dt>Typical lowest balance</dt><dd>{money0(result.median_min_balance)}</dd></div>
        </dl>
        <p>Chance your balance dips below {money0(result.breach_threshold)} at least once in the next {horizonLabel(result.horizon_weeks)}.{dip && dip.recovers ? " A dip can be brief, so check the chart to see how long it lasts." : ""}</p>
        <h2>How your balance could change</h2>
        <BalanceChart result={result} asked={asked} startWeek={dip && rate > result.baseline_breach_rate ? dip.firstWeek : 0} />
      </AeroPanel>
      {culpritMatters(result.culprit) && <AeroPanel className="result-panel"><h2>Biggest recurring cost</h2><p>{result.culprit.label} at {money(result.culprit.amount)} per payment{result.culprit.essential ? " (an essential bill)" : ""}. Without it, your chance of dipping below {money0(result.breach_threshold)} would be {Math.round(result.culprit.marginal_contribution * 100)} points lower.</p><details><summary>See the {result.culprit.evidence.length} payments</summary><div className="evidence-buttons">{result.culprit.evidence.map(evidenceButton)}</div></details></AeroPanel>}
      <AeroPanel className="result-panel"><h2>Where these numbers come from</h2>{evidenceIds.length ? <><p>Based on {evidenceIds.length} of {name ? `${name}'s` : "your"} transactions{inputs ? ` from the past ${inputs.model.fit_window_days === 365 ? "year" : `${inputs.model.fit_window_days} days`}` : ""}: paychecks, bills and everyday spending. We used them to simulate {result.n_paths} possible futures.</p><details><summary>Show the transactions</summary><div className="evidence-buttons">{evidenceIds.map(evidenceButton)}</div></details></> : <p>No supporting transactions were returned for this run.</p>}</AeroPanel>
    </> : inputs ? <>
      <AeroPanel className="result-panel"><h2>What we assumed</h2><p>These are the numbers we learned from {name ? `${name}'s` : "your"} past transactions when this question was asked.</p><dl className="model-details"><div><dt>Balance when you asked</dt><dd>{usd(inputs.model.opening_balance)}</dd></div><div><dt>Transactions looked at</dt><dd>Past {inputs.model.fit_window_days} days</dd></div><div><dt>Paycheck</dt><dd>{usd(inputs.model.income.mean)} every {days(inputs.model.income.cadence_days)}</dd></div><div><dt>Paycheck usually varies by</dt><dd>{usd(inputs.model.income.std)}</dd></div><div><dt>Everyday spending per week</dt><dd>{usd(inputs.model.discretionary.weekly_mean)}</dd></div><div><dt>Weekly spending usually varies by</dt><dd>{usd(inputs.model.discretionary.weekly_std)}</dd></div></dl><h3>Recurring bills</h3><ul className="evidence-list">{inputs.model.recurring.map(r => <li key={r.obligation_id}><strong>{r.label}</strong> · {usd(r.amount)} every {days(r.cadence_days)}{r.essential ? " · Essential" : ""}<details><summary>See the {r.evidence.length} payments</summary><div className="evidence-buttons">{r.evidence.map(evidenceButton)}</div></details></li>)}</ul><details><summary>Raw data (for developers)</summary><pre>{JSON.stringify({ model: inputs.model, delta: inputs.delta }, null, 2)}</pre></details></AeroPanel>
      <AeroPanel className="result-panel"><h2>All transactions used</h2><p>{transactions.length} transactions · newest first.</p><ul className="transaction-list">{transactions.slice(page * 10, page * 10 + 10).map(([id, raw]) => {const value = evidenceAmount(raw, inputs.amount_units?.evidence?.[id]);return <li key={id}><div><strong>{describeTransaction(raw)}</strong><span>{transactionDate(raw) ?? "Date unavailable"} · {value === null ? "Amount unavailable" : usd(value)}</span></div><button type="button" className="text-button evidence-button" onClick={event => showEvidence(id, event)} aria-label={`View details for ${txnLabel(id)}`}>Details</button></li>;})}</ul><div className="pagination"><AeroButton type="button" variant="secondary" disabled={page === 0} onClick={() => setPage(n => n - 1)}>Previous</AeroButton><span>Page {page + 1} of {Math.max(1, Math.ceil(transactions.length / 10))}</span><AeroButton type="button" variant="secondary" disabled={(page + 1) * 10 >= transactions.length} onClick={() => setPage(n => n + 1)}>Next</AeroButton></div></AeroPanel>
    </> : <AeroPanel className="result-panel"><h2>The assumptions couldn&apos;t load</h2><p>The results are still available. Reload to try again.</p><AeroButton type="button" onClick={() => router.refresh()}>Try again</AeroButton></AeroPanel>}
    {!inputs && !modelView && <p role="alert">Transaction details couldn&apos;t load. Reload to try again.</p>}
    <p className="inline-note"><Link href="/?view=overview">Ask another question</Link> · <Link href="/?view=replays">Back to replays</Link></p>
    <dialog ref={dialog} className="evidence-dialog" aria-labelledby="evidence-title" onCancel={event => { event.preventDefault(); query(modelView); }}><div className="evidence-dialog-heading"><h2 id="evidence-title">{record ? describeTransaction(record) : "Transaction details"}</h2><button ref={closeButton} className="aero-button aero-button--secondary" type="button" onClick={() => query(modelView)}>Close</button></div>{record ? <><dl className="model-details"><div><dt>Date</dt><dd>{transactionDate(record) ?? "Unavailable"}</dd></div><div><dt>Amount</dt><dd>{amount === null ? "Unavailable" : usd(amount)}</dd></div><div><dt>Description</dt><dd>{String(record.description ?? record.type ?? "Unavailable")}</dd></div><div><dt>Transaction ID</dt><dd>{String(record._id ?? txnId)}</dd></div></dl><details><summary>Original record (for developers)</summary><pre>{JSON.stringify(record, null, 2)}</pre><p className="small-copy">Stored amount unit: {unit ?? "unavailable"}</p></details><a className="text-button" href={`/api/backend/txn/${encodeURIComponent(txnId!)}`} target="_blank" rel="noreferrer">Open API record</a></> : <p role="alert">This transaction isn&apos;t in the saved data, so its details can&apos;t be shown.</p>}</dialog>
  </AppShell>;
}
