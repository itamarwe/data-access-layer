import test from "node:test";
import assert from "node:assert/strict";
import { markdown, sqlBlock, valueView } from "../src/lib/format.js";
import { curated, referenceLink } from "../src/lib/resources.js";
import { resourceSheet, resourceRows, columnRows, connectionsView } from "../src/views/resource.js";
import { matchesProposal, proposalRow } from "../src/views/proposal.js";

const resource = (kind, payload = {}) => ({ id: `opaque/${kind}`, kind, name: kind, payload: { kind, name: kind, ...payload } });
const visible = (html) => html.replace(/<details[\s\S]*?<\/details>/g, "");

test("methodology supports readable headings, lists, tables and code without executing HTML", () => {
  const html = markdown('# Rules\n\n**Exclude tests** using `is_test`.\n\n- Filter first\n- Aggregate second\n\n| Field | Meaning |\n| --- | --- |\n| id | Order |\n\n```sql\nSELECT * FROM orders\n```\n\n<img src=x onerror=alert(1)>\n[bad](javascript:alert)');
  for (const text of ['<h3>Rules</h3>', '<strong>Exclude tests</strong>', '<ul>', '<table', 'sql-keyword', '&lt;img']) assert.ok(html.includes(text), text);
  assert.ok(!html.includes('<img'));
  assert.ok(!html.includes('href="javascript:'));
  assert.match(markdown('[Docs](https://example.com?a=1&b=2)'), /href="https:\/\/example.com\?a=1&amp;b=2"/);
});

test("SQL formatting preserves the saved SQL and escapes markup", () => {
  const sql = "SELECT '<script>' AS value\nFROM orders WHERE total < 10 -- note";
  const html = sqlBlock(sql);
  assert.match(html, /sql-string/);
  assert.match(html, /sql-comment/);
  const decoded = html.replace(/<[^>]*>/g, '').replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&#039;', "'").replaceAll('&quot;', '"').replaceAll('&amp;', '&');
  assert.equal(decoded, sql);
});

test("doctrine and gold query pages show content, not raw JSON by default", () => {
  const doctrine = resourceSheet(resource('doctrine', { content: '# Revenue\n\nUse **net** revenue.' }), new Map());
  assert.match(visible(doctrine), /<h3>Revenue<\/h3>/);
  assert.doesNotMatch(visible(doctrine), /&quot;content&quot;/);
  const gold = resourceSheet(resource('gold_query', { question: 'How many orders?', sql: 'SELECT COUNT(*) FROM orders', dialect: 'duckdb', parameters: { minimum: 0 } }), new Map());
  assert.match(visible(gold), /How many orders\?/);
  assert.match(gold, /data-copy-sql/);
  assert.match(visible(gold), /Minimum/);
  assert.doesNotMatch(visible(gold), /&quot;sql&quot;/);
});

test("curation labels require recorded field review and remain on the resource", () => {
  const table = resource('table', { description: 'Orders' });
  assert.equal(curated(table), '');
  assert.match(resourceSheet(table, new Map()), /Grain is not defined yet/);
  table.payload.curation = { fields: ['description'] };
  assert.match(curated(table, 'description'), /Curated/);
  assert.equal(curated(table, 'grain'), '');
  assert.match(resourceSheet(table, new Map()), /curation\?target=opaque%2Ftable/);
  const columns = columnRows([resource('column', { data_type: 'integer', nullable: false, description: 'Stable **identifier**', curation: { fields: ['description'] } })]);
  assert.match(columns, /<table/);
  assert.match(columns, /Not nullable/);
  assert.match(columns, /<strong>identifier<\/strong>/);
  assert.match(columns, /Curated/);
});

test("ontology links resolve opaque IDs and show business direction and physical mappings", () => {
  const orders = resource('entity'); orders.name = 'Order';
  const customer = { ...resource('entity'), id: 'opaque/customer', name: 'Customer' };
  const table = resource('table'); table.name = 'warehouse.orders';
  const resources = new Map([orders, customer, table].map((item) => [item.id, item]));
  const relation = resource('relation', { from_id: orders.id, to_id: customer.id, name: 'belongs to', bindings: [table.id] });
  const html = resourceSheet(relation, resources);
  assert.match(html, /Order<\/a>/);
  assert.match(html, /Customer<\/a>/);
  assert.match(html, /belongs to/);
  assert.match(html, /Mapped to data/);
  assert.match(resourceRows([relation], resources), /warehouse.orders/);
  assert.match(referenceLink('unknown', resources), /Resource details unavailable/);
  assert.doesNotMatch(referenceLink('unknown', resources), /href=/);
});

test("join curation appears with connected tables and its condition", () => {
  const join = resource('join', { description: 'Customer association', predicate: 'orders.customer_id = customers.id', curation: { fields: ['description'] } });
  const html = connectionsView({ relations: [], mappings: [], joins: [{ id: join.id, name: 'Orders customer join', source_id: 'orders', target_id: 'customers', details: {} }] }, new Map([[join.id, join]]));
  assert.match(html, /Customer association/);
  assert.match(html, /Curated/);
  assert.match(html, /orders.customer_id = customers.id/);
});

test("proposal search covers proposed values, reasons and exact resource scope", () => {
  const item = { reason: 'Review revenue', target: { object_id: 'orders' }, patch: [{ path: '/description', value: 'Exclude returns' }] };
  assert.ok(matchesProposal(item, 'REVENUE returns', 'orders'));
  assert.ok(!matchesProposal(item, 'revenue', 'customers'));
  assert.ok(!matchesProposal(item, 'missing'));
  const proposals = Array.from({ length: 80 }, (_, i) => ({ ...item, reason: `Proposal ${i}` }));
  assert.equal(proposals.filter((value) => matchesProposal(value, 'Proposal 79')).length, 1);
});

test("proposals show before/after, removals and false values without raw JSON", () => {
  const html = visible(proposalRow({ id: 'proposal', status: 'open', reason: 'Correct definition', target: { object_id: 'orders' }, before: { description: { present: true, value: 'Old definition' }, nullable: { present: true, value: true } }, patch: [{ op: 'replace', path: '/nullable', value: false }, { op: 'remove', path: '/description' }] }));
  for (const text of ['Before', 'After', 'Yes', 'No', 'Old definition', 'Field removed', 'data-decision="publish"']) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /&quot;op&quot;/);
  assert.equal(valueView(false), 'No');
});

test("batch resource resolution deduplicates, encodes IDs and chunks at 100", async () => {
  globalThis.sessionStorage = { getItem: () => null };
  const { resolveResources } = await import('../src/lib/api.js');
  const calls = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (path) => {
    const ids = new URL(path, 'http://localhost').searchParams.getAll('object_id'); calls.push(ids);
    return { ok: true, json: async () => ids.filter((id) => id !== 'missing').map((id) => ({ id })) };
  };
  try {
    const ids = ['opaque/&?id', 'missing', ...Array.from({ length: 100 }, (_, i) => String(i))];
    const found = await resolveResources([...ids, ids[0], undefined]);
    assert.deepEqual(calls.map((call) => call.length), [100, 2]);
    assert.ok(found.has('opaque/&?id'));
    assert.ok(!found.has('missing'));
  } finally { globalThis.fetch = original; }
});
