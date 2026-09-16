# Native context evaluation

Run these commands from the repository root after following the runtime setup in
the [main README](../README.md). All committed fixtures and results are synthetic.

## Retrieval benchmark

The default is BM25: no model download, hosted API, or warehouse credentials.

```sh
python -m evals.context_graph.benchmark --output output/benchmark.json
```

For BM25 versus real local embeddings:

```sh
python -m pip install -e '.[dev,embeddings]'
python -m evals.context_graph.benchmark --search both --output output/benchmark.json
```

The first hybrid run can download `BAAI/bge-small-en-v1.5` weights. Inference is
local. To require already cached weights, add `--local-files-only`. Missing
dependencies or unavailable embeddings stop the hybrid benchmark; it never scores
a BM25 fallback as hybrid. Use `--search hybrid` to run only that variant, or
`--embedding-model MODEL` for another supported FastEmbed model.

The npm convenience command is `npm run benchmark -- --search both`; Python and
the same dependencies are still required. It does not install Python dependencies.

Five questions cover ontology, joins, query methodology, snapshot information,
and discovery of the next relevant object. The runner builds an isolated temporary
bundle from 17 objects and uses the production catalog service. It does not alter
your graph. It requests up to eight detailed and 20 compact matches, using the
existing regression fixture's retrieval configuration.

Each case requires all its expected object IDs to appear as actual matches within
one search call and the token budget. Compact matches count; incidental endpoint
IDs do not. Consequently this checks discovery, not whether a response includes
every fact an agent needs to write correct SQL. The gate requires 100% success
within budget and mean recall of 1.0. Latency is reported but has no pass threshold.

The default budget is 1,600 **estimated question plus response tokens**. This is
different from `dal search --token-budget`, which bounds the response alone.
Estimates use UTF-8 byte length divided by four, not a provider tokenizer.
Experiment with a tighter budget:

```sh
python -m evals.context_graph.benchmark --tokens 800 --output output/budget-800.json
```

A tighter budget may fail the gate; that is a measured tradeoff, not a runner
error. Exit codes: `0` all gates passed, `1` at least one gate failed, `2` the run
could not execute. JSON is printed to stdout and optionally written with `--output`.

The report includes per-case recall, success, estimated tokens, tool calls
(`turns`), search latency, embedding availability, and aggregate scores. These
are **not LLM turns**: this runner does not call an agent. Model loading and bundle
building are timed separately; search latency includes first-query costs. Timings
depend on machine, cache, and load; five observations do not establish a reliable
production p95. The fixture hash identifies the exact cases and graph content.

See [the recorded BM25/hybrid run](results/synthetic-retrieval.json) for results and
environment details. BM25 intentionally reports no embeddings (and thus a
`degraded_search_rate` of 1 under the shared reporting schema); its lexical-only
baseline is working as configured. Hybrid must report available embeddings.

## SQL correctness controls and ablation

```sh
python -m pytest tests/evaluation/test_sql_tasks.py -v
python -m pytest tests/evaluation evals/context_graph
```

Two different results are intentionally reported:

- **Retrieval regression** checks which objects search returned. Compact object
  matches count; incidental relationship endpoint IDs do not. This cannot show
  that an agent understands freshness, picks a valid join, or produces correct SQL.
- **Controlled SQL outcomes** execute the answer against a read-only synthetic
  SQLite fixture and compare result values and row multiplicity. Wrong joins,
  missing filters and incorrect aggregations fail even if retrieval passed.

`dal.evaluation.sql_tasks.TaskAgent` accepts a task and a recorded ContextSession.
An integration calls the model, invokes session tools and supplies usage for every
model call in AgentAnswer. All model calls count toward turns. Provider token totals
include context consumed on repeated calls; tool payload estimates are separate to
avoid double counting. Failed discovery calls remain in the trace. Answer SQL is
restricted to read-only queries, bounded work and bounded output on local fixtures.

The checked-in replay tests validate the evaluator and its negative controls. They
are **not live model performance results**. Replay answers explicitly carry
`mode="replay"`; live adapters must use `mode="live"` and actual provider usage.

The library catalog, questions, methodology, and snapshot date in
`context_graph/synthetic_catalog.py` are entirely invented. They form a
**development retrieval fixture**, not a held-out test set. Case references point
to the synthetic objects; they do not attest to production data or freshness.
The controlled join/filter tasks are independent of catalog gold questions. A live
benchmark must reserve held-out questions and fixture variants from development,
record the agent/model configuration, and evaluate unchanged tasks across variants.

For ablation, `ablate_sql_task` holds question, expected rows, budgets, agent and
database constant while changing available context. Removing an object must not
change the required outcome or turn its absence into a failed ID lookup criterion.

The SQL tests include wrong-join and missing-filter controls, duplicate-row
checks, read-only execution safeguards, budgets, and a paired doctrine-removal
ablation. Their agent answers are scripted replays. This demonstrates that the
scoring and ablation mechanism catches the controlled errors; it does not measure
whether a live model benefits from that doctrine. There is no packaged live-model
benchmark command yet. To test new context with an actual agent, implement the
`TaskAgent` adapter, use held-out tasks, and compare unchanged tasks with and
without the added context while recording actual model usage.

The optional `context_graph/measure_archive.py` command measures a locally supplied
catalog without publishing its questions, SQL, or evidence. No input archives or
production benchmark outputs are included in this repository.
