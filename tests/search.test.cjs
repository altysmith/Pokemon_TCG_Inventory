const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {test} = require('node:test');
const vm = require('node:vm');

const source = readFileSync(require('node:path').join(__dirname, '../web/search.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function setup(hosted = false) {
  const nodes = new Map();
  function node() {
    return {
      value: '', children: [], dataset: {}, selectedOptions: [{textContent: 'Standard · Marks H, I, J'}],
      classList: {toggle() {}, add() {}},
      addEventListener() {}, setAttribute() {}, focus() {},
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      add(child) { this.children.push(child); },
    };
  }
  let resolveFacets;
  const facets = new Promise(resolve => { resolveFacets = resolve; });
  const urls = [];
  const context = vm.createContext({
    document: {
      querySelector(id) { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); },
      createElement: node,
    },
    Option: function(text, value) { this.text = text; this.value = value; this.dataset = {}; },
    AbortController, URLSearchParams,
    fetch: async url => {
      urls.push(url);
      if (url === '/health') return {ok: true, json: async () => hosted
        ? {ok: true, multi_user: true}
        : {iteration: 18, local_catalog_available: true}};
      if (url === '/catalog/facets') return facets;
      return {ok: true, json: async () => ({ok: true, total: 1, items: [{
        id: 'energy', name: 'Special Energy', number: '1', set_code: 'TST', set_name: 'Test', quantity: 0,
      }]})};
    },
  });
  vm.runInContext(source, context);
  nodes.get('#catalog_format').value = 'standard';
  nodes.get('#catalog_card_type').value = 'special-energy';
  return {context, nodes, urls, resolveFacets};
}

for (const failure of [false, true]) {
  test(`search renders without sets and survives ${failure ? 'failed' : 'delayed'} facets`, async () => {
    const {context, nodes, urls, resolveFacets} = setup();
    await tick();
    vm.runInContext('restartSearch()', context);
    await tick();
    assert.match(urls.at(-1), /format=standard&type=special-energy/);
    const result = nodes.get('#catalog_results').children[0];
    assert.equal(result.children[1].children[0].textContent, 'Special Energy');
    assert.match(nodes.get('#catalog_status').textContent, /1 matching English card/);
    resolveFacets({ok: !failure, json: async () => failure
      ? {ok: false, error: 'Search options unavailable'}
      : {ok: true, sets: [{id: 'test', code: 'TST', name: 'Test'}]}});
    await tick();
    assert.equal(nodes.get('#catalog_results').children[0], result);
    assert.equal(nodes.get('#catalog_pagination').hidden, false);
    assert.match(nodes.get('#catalog_status').textContent, /1 matching English card/);
    if (!failure) assert.equal(nodes.get('#catalog_set').children.length, 1);
  });
}

test('hosted anonymous health response allows set options to load', async () => {
  const {nodes, urls, resolveFacets} = setup(true);
  await tick();
  assert.ok(urls.includes('/catalog/facets'));
  resolveFacets({ok: true, json: async () => ({ok: true, sets: [{id: 'test', code: 'TST', name: 'Test'}]})});
  await tick();
  assert.equal(nodes.get('#catalog_set').children.length, 1);
  assert.match(nodes.get('#catalog_status').textContent, /Choices ready/);
});
