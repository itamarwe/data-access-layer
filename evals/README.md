# Native context evaluation

Run `pytest tests/evaluation evals/context_graph` for offline regression checks.

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

The optional `context_graph/measure_archive.py` command measures a locally supplied
catalog without publishing its questions, SQL, or evidence. No input archives or
production benchmark outputs are included in this repository.
