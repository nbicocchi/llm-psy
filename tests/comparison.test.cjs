const { test } = require('node:test');
const assert = require('node:assert/strict');
const { hasScore, position, selectRows, pairs } = require('../site/assets/comparison.js');
const fs = require('node:fs');
const vm = require('node:vm');

test('normalization is theoretical range position, including seven-point sums', () => {
  assert.equal(position(5, 5, 35), 0);
  assert.equal(position(20, 5, 35), 50);
  assert.equal(position(35, 5, 35), 100);
});
test('missing values and zero complete repetitions never become neutral scores', () => {
  assert.equal(hasScore({mean: null, n: 0}), false);
  assert.equal(hasScore(undefined), false);
  assert.equal(hasScore({mean: 3, n: 0}), false);
  assert.equal(hasScore({mean: 0, n: 1}), true);
});
const rows = [
  {id: 'a', model: 'Qwen-small', family: 'qwen', cells: {x: {mean: 2, n: 1}, y: {mean: 4, n: 2}}},
  {id: 'b', model: 'Llama-small', family: 'llama', cells: {x: {mean: 2, n: 1}}},
  {id: 'c', model: 'Qwen-large', family: 'qwen', cells: {x: {mean: null, n: 0}, y: {mean: 4, n: 2}}},
];
test('filters intersect and an empty explicit selection means all models', () => {
  assert.deepEqual(selectRows(rows, 'qwen', 'SMALL', []).map(row => row.id), ['a']);
  assert.deepEqual(selectRows(rows, '', '', ['a', 'b']).map(row => row.id), ['a', 'b']);
  assert.deepEqual(selectRows(rows, 'llama', '', ['a']), []);
});
test('scatter omits unpaired and incomplete scores', () => {
  assert.deepEqual(pairs(rows, 'x', 'y').map(row => row.id), ['a']);
});

// Small DOM contract double: exercise the whole renderer without installing a
// browser or npm dependencies. This is not a browser/layout accessibility test.
class Element {
  constructor(tag = 'div', multiple = false) {
    this.tag = tag;
    this.multiple = multiple;
    this.children = [];
    this.style = {};
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.classList = {add() {}};
    this.hidden = false;
    this.selected = false;
    this._value = '';
    this.textContent = '';
  }
  append(...children) { this.children.push(...children); }
  prepend(...children) { this.children.unshift(...children); }
  replaceChildren(...children) { this.children = children; this._value = ''; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  scrollIntoView() {}
  get options() { return this.children; }
  get selectedOptions() { return this.children.filter(child => child.selected); }
  set value(value) { this._value = value; }
  get value() { return this._value || (this.tag === 'select' && !this.multiple && this.children.length ? this.children[0].value : ''); }
}

test('renderer initializes charts, filters, model selection and cell inspection', () => {
  const scale = id => ({id, label: `Fixture / ${id}`, trait: id, experiment: 'fixture', min: 1, max: 5, aggregation: 'mean', protocol: {temperature: 0.7}, questionnaire_hash: 'q'});
  const cell = mean => ({mean, n: 1, planned: 3, sd: null, percent: position(mean, 1, 5), repetitions: [{score: mean, repetition: 1}], run_id: 'run', counts: {ok: 1, refusal: 0, invalid: 0, error: 0}, expected: 3});
  const group = {id: 'group', backend: {version: 'test'}, hardware: {}, columns: [scale('x'), scale('y')], rows: rows.map(row => ({...row, url: `/models/#${row.id}`, digest: 'digest', mode: 'Model default thinking policy', cells: Object.fromEntries(Object.entries(row.cells).map(([key, value]) => [key, value.mean === null ? {...cell(3), mean: null, n: 0, percent: null, repetitions: []} : cell(value.mean)]))}))};
  const ids = {};
  const selectIds = ['cohort-select', 'family-select', 'model-select', 'dot-scale', 'scatter-x', 'scatter-y'];
  const document = {
    getElementById(id) {
      if (!ids[id]) ids[id] = new Element(selectIds.includes(id) ? 'select' : 'div', id === 'model-select');
      return ids[id];
    },
    createElement: tag => new Element(tag),
    createElementNS: (_, tag) => new Element(tag),
  };
  document.getElementById('comparison-data').textContent = JSON.stringify({cohorts: [group]});
  vm.runInNewContext(fs.readFileSync(require.resolve('../site/assets/comparison.js'), 'utf8'), {document});
  assert.equal(ids['comparison-app'].hidden, false);
  assert.equal(ids['comparison-static'].hidden, true);
  assert.match(ids['comparison-status'].textContent, /3 of 3/);
  assert.match(ids['scatter-status'].textContent, /1 plotted \/ 3/);
  assert.equal(ids['dot-chart'].children[0].tag, 'svg');
  assert.equal(ids['scatter-chart'].children[0].tag, 'svg');
  const heatmap = ids.heatmap.children[0];
  const firstCell = heatmap.children[2].children[0].children[1].children[0];
  firstCell.listeners.click();
  assert.equal(ids['cell-detail'].hidden, false);
  assert.equal(ids['cell-detail'].children[0].textContent, 'Qwen-small / x');
  ids['family-select'].value = 'llama';
  ids['family-select'].listeners.change();
  assert.match(ids['comparison-status'].textContent, /1 of 3/);
  assert.match(ids['scatter-status'].textContent, /0 plotted \/ 1/);
  ids['family-select'].value = '';
  ids['comparison-search'].value = 'does-not-exist';
  ids['comparison-search'].listeners.input();
  assert.match(ids['comparison-status'].textContent, /0 of 3/);
  assert.equal(ids.heatmap.children[0].textContent, 'No model variants match these filters.');
  ids['comparison-search'].value = '';
  ids['model-select'].options[0].selected = true;
  ids['model-select'].listeners.change();
  assert.match(ids['comparison-status'].textContent, /1 of 3/);
  ids['clear-models'].listeners.click();
  assert.match(ids['comparison-status'].textContent, /3 of 3/);
  ids['scatter-y'].value = 'x';
  ids['scatter-y'].listeners.change();
  assert.match(ids['scatter-status'].textContent, /2 plotted \/ 3/);
});
