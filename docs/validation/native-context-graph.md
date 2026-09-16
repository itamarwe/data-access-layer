# Native context graph validation

The public repository uses synthetic examples and fixtures. It includes no
production archive, source fingerprints, or production benchmark results.

## Release check — 2026-09-15

The full offline suite passed: **204 tests in 9.68 seconds**. The frontend build
also passed. All five synthetic retrieval questions met the one-call,
1,600-estimated-token gate. These are local development checks, not live-agent
accuracy measurements.

## Reproduce the checks

```sh
python -m pytest
npm --prefix web run build
```

Tests cover native-model validation, builds, interrupted-build recovery, evidence,
proposals, health, CLI, REST API, MCP, UI assets, native JSON/YAML imports, former
DAL JSON graph migration, and rejection of unsupported DuckDB/ZIP imports.
Relationship tests distinguish business relations, data joins, mappings, and
resource navigation, including composite predicates and outer-join direction.

## Synthetic retrieval

`evals/context_graph/synthetic_catalog.py` defines an invented library with members,
loans, and books. Its methodology and snapshot date are fictional. Five development
questions cover identity, joins, query methodology, snapshot discovery, and finding
the next relevant resource. References resolve to objects in that fixture.

The retrieval gate requires every expected object within one search call and
1,600 estimated question-plus-response tokens. Compact matches count; incidental
IDs in connections or evidence do not. Tokens are estimated from UTF-8 bytes,
not measured with a model provider's tokenizer.

These checks do not show that an agent interprets a predicate or freshness caveat
correctly. Passing on a small synthetic catalog does not establish performance on
large organizational catalogs or prove the value of embeddings.

## Controlled SQL outcomes

The independent SQLite fixture checks answer values and row multiplicity. Wrong
joins, missing filters, and duplicate rows fail even when expected tables were
retrieved. Mutations and multiple statements are rejected. Expected answers are
not supplied to the agent input.

The checked-in agents are scripted replays, not live-model evaluations. Context
ablation holds the task, expected rows, database, and budgets constant. A live
benchmark must reserve held-out questions, use an actual agent, record provider
usage, and compare variants on unchanged tasks.

## Limits

No live-agent accuracy, production-scale latency, low-budget recall, or embedding
quality claim is made by this release. Optional local embedding integrations need
their model weights; they are not required by the offline regression suite.
