'use strict';
const names = {bm25:'BM25', semantic:'Semantic · MiniLM', graph:'Graph · lexical seeds',
  fixed_hybrid:'Fixed three-expert fusion', bm25_semantic:'BM25 + semantic', routed_hybrid:'Learned routed fusion'};
const byId = id => document.getElementById(id);
let recordings, selected;
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function sourceLink(url, label) {
  const parsed = new URL(url);
  if (parsed.protocol !== 'https:' || parsed.hostname !== 'github.com') throw new Error('Invalid source URL');
  const node = element('a', '', label); node.href = parsed.href;
  node.target = '_blank'; node.rel = 'noopener noreferrer'; return node;
}
function showPaths(item) {
  const detail = element('details'); detail.append(element('summary', '', 'Inspect recorded graph paths'));
  for (const path of item.paths) {
    const block = element('div', 'path');
    block.append(element('div', '', path.relation === 'explicit_reference' ? 'Explicit reference · association, not causality' : 'Entity mention · not a dependency'));
    block.append(element('div', '', path.nodes.join(' → ')));
    for (const url of path.sources) block.append(sourceLink(url, 'Source supporting this edge ↗'));
    detail.append(block);
  }
  return detail;
}
function render() {
  const example = recordings.examples.find(x => x.id === selected);
  const report = example.reports[byId('method').value];
  byId('query').value = example.query;
  document.querySelectorAll('[data-example]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.example === selected)));
  const status = element('div', 'status' + (report.status === 'abstained' ? ' warning' : ''));
  status.append(element('b', '', report.status === 'abstained' ? 'Abstained · candidates are not endorsed' : 'Candidate evidence · original source review required'));
  status.append(element('p', '', report.summary));
  for (const check of report.scope_checks) status.append(element('p', '', check.detail));
  const score = element('p', 'score', report.confidence === null ? 'Routed-model estimate: not applicable to this comparison method.' :
    'Raw routed-model estimate: ' + report.confidence.toFixed(3) + ' / 1. Unvalidated—not a correctness probability. Scope rules can override high estimates.');
  const weights = element('div', 'weights');
  for (const [name, weight] of Object.entries(report.expert_weights)) weights.append(element('span', 'weight', names[name] + ': ' + (weight * 100).toFixed(1) + '%'));
  const nodes = [status, score, weights];
  if (!report.evidence.length) nodes.push(element('p', 'small', 'This method returned no ranked candidate reports for this recorded query.'));
  report.evidence.forEach((item, index) => {
    const card = element('article', 'evidence');
    card.append(element('div', 'id', item.id + ' · reporter statement'), element('h3', '', (index + 1) + '. ' + item.title), sourceLink(item.url, 'Open original report ↗'));
    if (item.paths.length) card.append(showPaths(item)); nodes.push(card);
  });
  if (report.graph_neighbors.length) {
    const detail = element('details');
    detail.append(element('summary', '', 'Explicitly linked reports · separate from top-five ranking'));
    for (const item of report.graph_neighbors) {
      const block = element('div', 'path'); block.append(sourceLink(item.url, item.id + ' · ' + item.title));
      if (item.paths.length) block.append(showPaths(item)); detail.append(block);
    }
    nodes.push(detail);
  }
  byId('output').replaceChildren(...nodes);
}
byId('method').addEventListener('change', () => {if (recordings) render();});
fetch('./recordings.json').then(response => {if (!response.ok) throw new Error('Recording unavailable'); return response.json();}).then(data => {
  if (data.mode !== 'recorded_replay_not_live_inference') throw new Error('Unexpected recording format');
  recordings = data; selected = 'config';
  for (const example of data.examples) {
    const button = element('button', '', example.label); button.type = 'button'; button.dataset.example = example.id;
    button.addEventListener('click', () => {selected = example.id; render();}); byId('examples').append(button);
  }
  for (const method of data.validation.methods) {
    const row = element('tr');
    for (const value of [names[method], data.validation.original_pilot_extended_comparison[method].mrr.toFixed(3), data.validation.challenge[method].mrr.toFixed(3)]) row.append(element('td', '', value));
    byId('metrics').append(row);
  }
  byId('recorded').textContent = 'Outputs recorded ' + data.recorded_at.slice(0, 10) + ' · CPU inference'; render();
}).catch(error => {byId('error').hidden = false; byId('error').textContent = error.message + '. Use the repository setup instructions to run locally.'; byId('recorded').textContent = 'Recording could not be loaded';});
