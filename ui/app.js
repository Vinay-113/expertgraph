/* Public issue text is always rendered as text, never HTML or executable code. */
const $ = id => document.getElementById(id);
const names = {bm25:'Lexical · BM25', semantic:'Semantic · MiniLM', graph:'Graph · lexical seeds',
  fixed_hybrid:'Fixed three-expert hybrid', bm25_semantic:'BM25 + semantic (no graph)', routed_hybrid:'Learned routed hybrid'};
const samples = {
  retry:'Find the linked Requests reports about missing HTTPAdapter or retries= behavior that reference each other.',
  config:'Giving pytest a nonexistent config path either does nothing or raises FileNotFoundError depending on the extension. Which report covers both cases?',
  python:'A Windows Python 3.14t installer changed but its checksum stayed the same, causing CI installation to fail.',
  ood:'What ingredients are used in a chocolate cake?',
  unknown:'Find the HTTP error report containing GALAXY_HTTP_5K82P.',
  action:'Patch my production Requests proxy configuration now and prove that the incident is resolved.'
};
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}
function link(url, text) {
  const n = el('a', '', text), u = new URL(url);
  if (u.protocol !== 'https:' || u.hostname !== 'github.com') throw new Error('Invalid evidence source');
  n.href = u.href; n.target = '_blank'; n.rel = 'noopener noreferrer';
  return n;
}
function weights(values) {
  $('weights').replaceChildren();
  for (const [key, value] of Object.entries(values)) {
    const w = el('div', 'weight'), top = el('div', 'weighttop');
    top.append(el('span', '', names[key]), el('b', '', (value * 100).toFixed(1) + '%'));
    const track = el('div', 'track'), fill = el('div', 'fill');
    fill.style.width = (value * 100) + '%'; track.append(fill); w.append(top, track); $('weights').append(w);
  }
}
function pathElement(p) {
  const path = el('div', 'path'), chain = el('div', 'chain');
  path.append(el('div', 'small', p.relation === 'mentions' ? 'Entity mention · not a dependency' : 'Explicit reference · not a causal claim'));
  p.nodes.forEach((node, j) => {if (j) chain.append(el('span', 'arrow', '→')); chain.append(el('span', 'node', node));});
  path.append(chain); p.sources.forEach(url => path.append(link(url, 'Source supporting this edge ↗')));
  return path;
}
function evidenceCard(e, i) {
  const card = el('article', 'evidence'), top = el('div', 'cardtop'), heading = el('h3');
  top.append(el('div', 'sourceid', e.id), el('span', 'badge', 'Reporter statement'));
  heading.append(el('span', 'number', (i + 1) + '. '), document.createTextNode(e.title));
  card.append(top, heading, el('blockquote', '', e.quote), link(e.url, 'Open original report ↗'));
  if (e.paths.length) {
    const detail = el('details');
    detail.append(el('summary', '', e.paths.length + ' inspectable graph path' + (e.paths.length > 1 ? 's' : '')));
    e.paths.forEach(p => detail.append(pathElement(p))); card.append(detail);
  }
  return card;
}
function render(data) {
  weights(data.expert_weights);
  $('routingNote').textContent = data.method === 'routed_hybrid' ? 'Learned query-dependent fusion weights; experts are not independent votes.' : 'Comparison method: ' + names[data.method] + '. These are fixed contributions, not a learned gate.';
  const status = $('status'); status.className = 'status' + (data.status === 'abstained' ? ' warning' : '');
  const label = data.status === 'abstained' ? (data.abstention_reason === 'scope_guard' ? 'Abstained · outside available evidence or actions' : 'Abstained · inspect candidates before concluding') : 'Candidate evidence · source review required';
  status.replaceChildren(el('b', '', label), el('span', 'small', data.summary));
  if (data.scope_checks?.length) {
    const list = el('ul', 'scope-warning'); data.scope_checks.forEach(x => list.append(el('li', '', x.detail))); status.append(list);
  }
  $('confidence').textContent = data.confidence === null ? 'Not applicable' : data.confidence.toFixed(3) + ' / 1';
  $('confidenceNote').textContent = data.confidence_scope + (data.threshold === null ? '.' : '. Raw-model threshold: ' + data.threshold.toFixed(3) + '. Scope rules can override acceptance; high estimates still make errors.');
  $('evidence').replaceChildren(...data.evidence.map(evidenceCard));
  if (!data.evidence.length) $('evidence').append(el('div', 'empty', 'No candidate reports found.'));
  $('neighbors').replaceChildren();
  if (data.graph_neighbors?.length) {
    const panel = el('section', 'panel');
    panel.append(el('h2', '', 'Explicitly linked reports'), el('p', 'small', 'Graph neighbours from lexical seeds, separate from the selected top five. They do not alter evaluation metrics.'));
    for (const e of data.graph_neighbors) {
      const detail = el('details'); detail.append(el('summary', '', e.id + ' · ' + e.title), link(e.url, 'Open linked report ↗'));
      e.paths.filter(p => p.relation === 'explicit_reference').forEach(p => detail.append(pathElement(p))); panel.append(detail);
    }
    $('neighbors').append(panel);
  }
}
async function search(event) {
  event.preventDefault(); $('searchButton').disabled = true; $('searchButton').textContent = 'Retrieving…'; $('error').className = 'error hidden';
  try {
    const response = await fetch('/api/query', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:$('query').value, method:$('method').value})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error); render(data);
  } catch (err) {$('error').textContent = err.message; $('error').className = 'error';}
  finally {$('searchButton').disabled = false; $('searchButton').textContent = 'Find evidence →';}
}
$('searchForm').addEventListener('submit', search);
document.querySelectorAll('[data-sample]').forEach(b => b.addEventListener('click', () => {$('query').value = samples[b.dataset.sample]; $('searchForm').requestSubmit();}));
$('method').addEventListener('change', () => {if ($('query').value.trim() && !$('searchButton').disabled) $('searchForm').requestSubmit();});
weights({bm25:1 / 3, semantic:1 / 3, graph:1 / 3});
fetch('/api/results').then(r => {if (!r.ok) throw new Error('Pilot results unavailable'); return r.json();}).then(data => {
  $('docCount').textContent = data.corpus.documents; $('edgeCount').textContent = data.corpus.reference_edges;
  for (const key of ['bm25','semantic','graph','fixed_hybrid','routed_hybrid']) {
    const m = data.pilot[key], row = el('tr', key === 'routed_hybrid' ? 'highlight' : '');
    [names[key], m.recall_at_5.toFixed(3), m.mrr.toFixed(3), m.ndcg_at_5.toFixed(3), m.median_latency_ms.toFixed(1)].forEach(x => row.append(el('td', '', x))); $('metrics').append(row);
  }
  $('evaluationNote').textContent = 'Original pilot retained unchanged. Development-selected single expert: ' + names[data.best_single_expert_selected_on_dev] + '. Latency excludes indexing and startup. High relevance estimates are not validated correctness probabilities.';
  data.limitations.forEach(x => $('limitations').append(el('li', '', x)));
}).catch(e => {$('evaluationNote').textContent = e.message;});
fetch('/api/validation').then(r => r.ok ? r.json() : null).then(data => {
  if (!data) return;
  $('validation').className = 'panel';
  for (const key of data.methods) {
    const m = data.challenge[key], row = el('tr', key === 'routed_hybrid' ? 'highlight' : '');
    [names[key], m.recall_at_5.toFixed(3), m.mrr.toFixed(3), m.ndcg_at_5.toFixed(3)].forEach(x => row.append(el('td', '', x))); $('stressMetrics').append(row);
  }
  const s = data.challenge.selective;
  $('stressNote').textContent = 'Raw frozen routed model accepted ' + s.negatives_accepted + '/' + s.negative_queries + ' negative requests. Accepted top1 precision against draft labels: ' + (s.accepted_top1_precision === null ? 'undefined' : s.accepted_top1_precision.toFixed(3)) + '. Incomplete labels mean this is not established true accuracy.';
  const g = data.scope_guard_regression;
  if (g) $('guardNote').textContent = 'Scope-rule regression check: ' + g.negatives_accepted_with_guard + '/' + g.negative_queries + ' negatives accepted after guards. Rules were added after observing this suite; this is not independent validation of the guard.';
}).catch(() => {});
