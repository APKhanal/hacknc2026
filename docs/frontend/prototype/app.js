import { chartData, evidenceAmount } from './chart-data.mjs';

const $ = id => document.getElementById(id);
const number = new Intl.NumberFormat('en-US');
const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const shortUsd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
const decimal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const dateFormat = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
const questions = { flight: 'Can I afford $1,400 today?', gym: 'Can I afford $65/month starting today?' };
const mobile = matchMedia('(max-width: 640px)');
let active = null;
let computed = null;
let evidenceIds = [];
let evidencePage = 0;
let evidenceOpener = null;
let toastTimer;

function text(id, value) { $(id).textContent = value; }
function element(tag, textValue, className) {
  const node = document.createElement(tag);
  if (textValue !== undefined) node.textContent = textValue;
  if (className) node.className = className;
  return node;
}
function fact(label, value) {
  const row = element('div'); row.append(element('dt', label), element('dd', value)); return row;
}
function params() { return new URLSearchParams(location.search); }
function updateParams(changes) {
  const url = new URL(location.href);
  for (const [key, value] of Object.entries(changes)) {
    if (value == null) url.searchParams.delete(key); else url.searchParams.set(key, value);
  }
  history.replaceState(null, '', url);
}
function replayHref(view) {
  const query = new URLSearchParams({ profile: params().get('profile') || 'alex', scenario: params().get('scenario') || 'flight' });
  if (view === 'model') query.set('view', 'model');
  return `?${query}`;
}
function toast(message) {
  clearTimeout(toastTimer); text('status', message); $('status').hidden = false;
  toastTimer = setTimeout(() => { $('status').hidden = true; }, 4500);
}
async function getSample(profile, scenario) {
  if (!['alex', 'drew'].includes(profile) || !Object.hasOwn(questions, scenario)) {
    throw new Error('This preview link is not one of the available saved examples. Open a new question to choose an example.');
  }
  const response = await fetch(`samples/${profile}-${scenario}.json`);
  if (!response.ok) throw new Error('The example could not be loaded. Check the local preview server and try again.');
  return response.json();
}

document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => {
  $('question').value = questions[button.dataset.example]; $('question').focus();
  $('form-error').hidden = true; $('question').removeAttribute('aria-invalid');
}));
$('question-form').addEventListener('submit', async event => {
  event.preventDefault();
  const raw = $('question').value.trim().toLowerCase().replaceAll(',', '');
  const scenario = Object.keys(questions).find(key => questions[key].toLowerCase().replaceAll(',', '') === raw);
  if (!scenario) {
    text('form-error', raw ? 'This design preview includes the two example questions below. Choose one to explore its saved simulation.' : 'Enter an example question with an amount and timing.');
    $('form-error').hidden = false; $('question').setAttribute('aria-invalid', 'true'); $('question').focus(); return;
  }
  $('question').removeAttribute('aria-invalid'); $('form-error').hidden = true;
  $('submit').disabled = true; text('submit', 'Opening saved example…');
  $('loading-status').hidden = false; text('loading-status', 'Loading the precomputed simulation…');
  const timer = setTimeout(() => text('loading-status', 'Still loading the saved example…'), 4000);
  try {
    const profile = $('profile').value;
    const sample = await getSample(profile, scenario);
    history.pushState(null, '', `?profile=${profile}&scenario=${scenario}`);
    showReplay(sample); $('replay-title').focus(); window.scrollTo({ top: 0 });
  } catch (error) {
    text('form-error', error.message); $('form-error').hidden = false;
  } finally {
    clearTimeout(timer); $('submit').disabled = false; text('submit', 'Explore futures →'); $('loading-status').hidden = true;
  }
});

function showReplay(sample) {
  const chart = chartData(sample.result);
  active = sample; computed = chart;
  const { result: result, inputs, profile } = sample;
  $('entry').hidden = true; $('replay').hidden = false; $('load-error').hidden = true;
  document.body.classList.add('replaying');
  for (const id of ['how-link', 'replay-link']) $(id).hidden = true;
  for (const id of ['new-link', 'copy-link']) $(id).hidden = false;
  text('profile-label', `${profile.name} · Synthetic demo profile`);
  text('replay-title', `${usd.format(inputs.delta.amount)}${inputs.delta.kind === 'recurring' ? '/month' : ''}, from another angle.`);
  text('saved-question', inputs.delta.raw_text);
  text('scenario-rate', percent.format(result.delta_breach_rate ?? result.baseline_breach_rate));
  text('baseline-rate', percent.format(result.baseline_breach_rate));
  text('risk-label', `of simulated futures fall below ${usd.format(result.breach_threshold)}`);
  const crossed = result.paths.filter(path => path.first_breach_week !== null).length;
  text('path-description', `${number.format(crossed)} of ${number.format(result.n_paths)} simulated paths cross the threshold over ${number.format(result.horizon_weeks)} weeks.`);
  text('culprit-label', result.culprit?.label || 'No contributing charge');
  text('culprit-amount', result.culprit ? `${usd.format(result.culprit.amount)} per occurrence` : 'For this simulation');
  text('culprit-description', result.culprit
    ? `Removing this recurring charge reduces the simulated breach rate by ${decimal.format(result.culprit.marginal_contribution * 100)} percentage ${Math.abs(result.culprit.marginal_contribution * 100 - 1) < .00001 ? 'point' : 'points'}. It is the selected contributor among eligible charges.`
    : 'No recurring charge had a positive measured contribution to the breach rate in this scenario.');
  $('culprit-evidence').hidden = !result.culprit?.evidence.length;
  $('run-facts').replaceChildren(fact('Simulated paths', number.format(result.n_paths)), fact('Horizon', `${number.format(result.horizon_weeks)} weeks`), fact('Data source', 'Synthetic bank data'));
  const model = inputs.model;
  $('model-facts').replaceChildren(
    fact('Opening balance', usd.format(model.opening_balance)),
    fact('Fit window', `${number.format(model.fit_window_days)} days`),
    fact('Typical income', `${usd.format(model.income.mean)} / ${decimal.format(model.income.cadence_days)} days`),
    fact('Weekly discretionary mean', usd.format(model.discretionary.weekly_mean)),
    fact('Weekly discretionary variation', usd.format(model.discretionary.weekly_std)),
  );
  $('recurring-list').replaceChildren(...model.recurring.map(charge => {
    const row = element('div', undefined, 'recurring-row'); const copy = element('div');
    copy.append(element('h4', charge.label), element('p', `${usd.format(charge.amount)} every ${decimal.format(charge.cadence_days)} days${charge.essential ? ' · Essential' : ''}`));
    const button = element('button', 'View transactions', 'text-button'); button.type = 'button';
    button.addEventListener('click', () => openEvidence(charge.evidence, charge.label, button));
    button.setAttribute('aria-label', `View ${charge.label} transactions`);
    row.append(copy, button); return row;
  }));
  $('paths-tab').href = replayHref(); $('model-tab').href = replayHref('model');
  const isModel = params().get('view') === 'model';
  $('model-view').hidden = !isModel; $('paths-view').hidden = isModel;
  text('panel-title', isModel ? 'Behind this result' : 'Your possible balances');
  for (const id of ['paths-tab', 'model-tab']) $(id).removeAttribute('aria-current');
  $(isModel ? 'model-tab' : 'paths-tab').setAttribute('aria-current', 'page');
  $('week').max = result.horizon_weeks;
  const requestedWeek = Number(params().get('week') ?? 52);
  $('week').value = Number.isFinite(requestedWeek) ? Math.min(result.horizon_weeks, Math.max(0, Math.round(requestedWeek))) : 52;
  drawChart(); updateWeek(false);
  const txn = params().get('txn');
  if (txn) {
    if (Object.hasOwn(inputs.evidence, txn)) openEvidence([txn], 'Saved transaction', $('model-tab'));
    else toast('This transaction is not in the saved evidence for this example.');
  }
}

function svg(tag, attributes, content) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (content !== undefined) node.textContent = content;
  return node;
}
function drawChart() {
  if (!active) return;
  const { result } = active;
  const width = mobile.matches ? 430 : 760;
  const height = mobile.matches ? 290 : 330;
  const left = 57, right = width - 16, top = 25, bottom = height - 42;
  const x = week => left + week / result.horizon_weeks * (right - left);
  const y = value => bottom - (value - computed.min) / (computed.max - computed.min) * (bottom - top);
  const line = values => values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' ');
  const chart = $('chart'); chart.setAttribute('viewBox', `0 0 ${width} ${height}`);
  chart.replaceChildren(svg('title', { id: 'chart-title' }, 'Simulated balances over time'), svg('desc', { id: 'chart-desc' }, 'The shaded band shows the 10th to 90th percentiles. The dark line is the median. Twenty representative paths are shown. Use the week slider below to inspect numerical values.'));
  for (let i = 0; i <= 4; i++) {
    const value = computed.min + (computed.max - computed.min) * i / 4;
    chart.append(svg('line', { x1: left, x2: right, y1: y(value), y2: y(value), stroke: '#e5eff5' }), svg('text', { x: left - 9, y: y(value) + 4, 'text-anchor': 'end' }, shortUsd.format(value)));
  }
  const ticks = mobile.matches ? [0, .5, 1] : [0, .25, .5, .75, 1];
  for (const fraction of ticks) {
    const week = Math.round(fraction * result.horizon_weeks);
    chart.append(svg('text', { x: x(week), y: bottom + 27, 'text-anchor': fraction === 0 ? 'start' : fraction === 1 ? 'end' : 'middle' }, week ? `${week} weeks` : 'Now'));
  }
  chart.append(svg('text', { x: left, y: 13 }, 'Balance (USD)'));
  const lower = computed.band.map(point => point[0]); const upper = computed.band.map(point => point[2]);
  const area = line(upper) + lower.map((_, i) => { const w = lower.length - 1 - i; return `L${x(w).toFixed(2)},${y(lower[w]).toFixed(2)}`; }).join(' ') + ' Z';
  chart.append(svg('path', { d: area, fill: '#8bcaf0', opacity: '.34' }));
  for (const path of computed.samples) chart.append(svg('path', { d: line(path.balances), stroke: '#4b9cd3', 'stroke-width': '.8', opacity: '.5', fill: 'none' }));
  chart.append(svg('line', { x1: left, x2: right, y1: y(result.breach_threshold), y2: y(result.breach_threshold), stroke: '#607187', 'stroke-dasharray': '5 5' }));
  chart.append(svg('path', { d: line(computed.band.map(point => point[1])), stroke: '#13294b', 'stroke-width': '2.7', fill: 'none' }));
  chart.append(svg('line', { id: 'selected-week', x1: x(Number($('week').value)), x2: x(Number($('week').value)), y1: top, y2: bottom, stroke: '#17638f', 'stroke-dasharray': '2 5', opacity: '.6' }));
}
function updateWeek(sync = true) {
  if (!computed) return;
  const week = Number($('week').value); const values = computed.band[week];
  text('week-label', number.format(week));
  ['p10', 'p50', 'p90'].forEach((id, i) => text(id, usd.format(values[i])));
  const width = mobile.matches ? 430 : 760;
  const x = 57 + week / active.result.horizon_weeks * (width - 16 - 57);
  $('selected-week')?.setAttribute('x1', x); $('selected-week')?.setAttribute('x2', x);
  $('week').setAttribute('aria-valuetext', `Week ${week}. Median ${usd.format(values[1])}. 10th percentile ${usd.format(values[0])}. 90th percentile ${usd.format(values[2])}.`);
  if (sync) updateParams({ week });
}
$('week').addEventListener('input', () => updateWeek(false));
$('week').addEventListener('change', () => updateWeek());
mobile.addEventListener('change', () => { drawChart(); updateWeek(false); });

function openEvidence(ids, label, opener) {
  evidenceIds = [...ids].sort((a, b) => {
    const records = active.inputs.evidence;
    const date = record => record?.purchase_date ?? record?.transaction_date ?? record?.payment_date ?? '';
    return date(records[b]).localeCompare(date(records[a])) || a.localeCompare(b);
  }); evidencePage = 0; evidenceOpener = opener;
  text('evidence-context', label); renderEvidence();
  if (!$('evidence-dialog').open) $('evidence-dialog').showModal();
  $('close-dialog').focus();
}
function renderEvidence() {
  const start = evidencePage * 5;
  const ids = evidenceIds.slice(start, start + 5);
  $('evidence-records').replaceChildren(...ids.map(id => {
    const record = active.inputs.evidence[id]; const unit = active.inputs.amount_units.evidence[id];
    const article = element('article', undefined, 'evidence-record');
    if (!record) { article.append(element('p', 'This referenced record is unavailable.', 'error')); return article; }
    const date = record.purchase_date ?? record.transaction_date ?? record.payment_date;
    const parsedDate = typeof date === 'string' ? new Date(`${date.slice(0, 10)}T12:00:00`) : null;
    const dateText = parsedDate && !Number.isNaN(parsedDate.getTime()) ? dateFormat.format(parsedDate) : 'Date unavailable';
    const amount = evidenceAmount(record, unit);
    article.append(element('h3', dateText), element('p', amount === null ? 'Amount unavailable' : usd.format(amount), 'amount'), element('p', record.description || 'Cached synthetic transaction', 'small'));
    const identifier = element('p', undefined, 'small'); identifier.append(element('code', record._id)); article.append(identifier);
    article.append(element('p', unit === 'usd_cents' ? 'Stored in cents. Displayed in dollars.' : unit === 'usd' ? 'Stored and displayed in dollars.' : 'Unknown monetary unit.', 'small'));
    const details = element('details'); details.append(element('summary', 'Original record'), element('pre', JSON.stringify(record, null, 2))); article.append(details);
    return article;
  }));
  if (!ids.length) $('evidence-records').append(element('p', 'No transaction evidence is available for this charge.'));
  text('evidence-page', ids.length ? `${start + 1}-${Math.min(start + 5, evidenceIds.length)} of ${evidenceIds.length}` : '0 records');
  $('previous-evidence').disabled = evidencePage === 0;
  $('next-evidence').disabled = start + 5 >= evidenceIds.length;
  if (ids[0]) updateParams({ txn: ids[0] });
}
$('culprit-evidence').addEventListener('click', event => openEvidence(active.result.culprit.evidence, active.result.culprit.label, event.currentTarget));
$('previous-evidence').addEventListener('click', () => { evidencePage--; renderEvidence(); $('evidence-dialog').scrollTo({ top: 0 }); });
$('next-evidence').addEventListener('click', () => { evidencePage++; renderEvidence(); $('evidence-dialog').scrollTo({ top: 0 }); });
$('close-dialog').addEventListener('click', () => $('evidence-dialog').close());
$('evidence-dialog').addEventListener('close', () => { updateParams({ txn: null }); evidenceOpener?.focus(); });
$('copy-link').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(location.href); toast('Design-preview link copied.'); }
  catch { $('copy-fallback').hidden = false; $('share-url').value = location.href; $('share-url').focus(); $('share-url').select(); }
});

async function init() {
  const query = params();
  if (!query.has('scenario')) return;
  $('entry').hidden = true; $('loading-status').hidden = false;
  text('status', 'Opening saved replay…'); $('status').hidden = false;
  try { showReplay(await getSample(query.get('profile') || 'alex', query.get('scenario'))); }
  catch (error) { $('replay').hidden = true; $('load-error').hidden = false; text('load-error-message', error.message); }
  finally { $('status').hidden = true; }
}
window.addEventListener('popstate', () => location.reload());
init();
