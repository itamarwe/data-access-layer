---
name: dal
description: "Use DAL to find ontology definitions, tables, columns, joins, query methodology, and curated SQL before querying organizational data. Also use for maintaining a file-based DAL context graph when requested."
---

# DAL context graph

Use the local `dal` CLI to retrieve the context needed for correct SQL. DAL retrieves
context; it does not execute warehouse queries. Use the user's separately authorized
data connection for execution.

<!-- installed-runtime -->

## Locate the graph

Use the context repository the user selected: the directory containing
`semantic/*.yaml` or `semantic/*.json`. Do not assume the software checkout or
current directory is the user's graph. If it is unknown, ask or inspect the
project's existing configuration.

Check the installed launcher's `--help` when command availability is uncertain.
If no installed launcher is listed above, use an existing `dal` command or read
[setup](references/setup.md) for the complete installer. It installs private Python
and DAL; warehouse credentials and embedding model weights are not included.

## Retrieve enough context to answer

Identify the independent facts needed to answer the question. For a single fact,
use one cross-type search. For a multi-part question, decompose it into focused
searches—one per fact—rather than putting every clause into one ranked query.
Preserve the original constraints and combine the retrieved facts before drafting SQL.

```sh
dal --repository /path/to/context search "one fact needed for the user's question" --token-budget 3200
```

Use leading results, compact matches, methodology, gold queries, gaps, and suggested
next commands together. Follow up only for missing facts that affect the answer;
do not enumerate every resource. A compact match is an identity, not the full
join predicate or query. Retrieve the complete resource when needed:

```sh
dal --repository /path/to/context table get TABLE_ID
dal --repository /path/to/context connections OBJECT_ID
dal --repository /path/to/context join get JOIN_ID
dal --repository /path/to/context column search "customer identifier" --table TABLE_ID
dal --repository /path/to/context table evidence TABLE_ID --limit 50
dal --repository /path/to/context table evidence TABLE_ID --column COLUMN_ID --claim /description --limit 50
```

`--repository` and `--bundle` go before the command. Resource commands use singular
names, including `gold-query`. IDs are opaque; use the returned IDs, not guesses.

Before drafting SQL, resolve the table grain, join predicate and direction,
cardinality, mandatory filters, and applicable methodology. Business relations,
data joins, and ontology-to-data mappings are distinct; membership is navigation.
Physical overlap or co-usage does not establish an executable join. Unknown grain
or an unmeasured property is a gap, not a value to invent.

Weigh physical, usage, and curation evidence by its actual claim, source, and date.
A catalog snapshot is not proof of current warehouse freshness. Deprecated objects
are excluded by default; inspect them only when relevant. Empty results mean no
matching context was found, not that the underlying data does not exist.

The token budget is an estimate, not a provider token count. If important details
were omitted, narrow the search, retrieve a specific object, or increase the budget.
For example, “monthly revenue by customer, excluding tests, using current customers”
needs facts about the revenue definition, timestamp/grain, test filter, and customer
join/current-record rule. Search those facts separately; do not treat a strong match
for revenue as evidence that the other parts were answered. Reuse retrieved resources
and stop when every required fact is supported or explicitly identified as missing.
Use 3,200 estimated output tokens as a practical starting budget for these searches;
a tiny response that only contains identities is not enough to write correct SQL.
Use the default ranking unless a concrete retrieval problem warrants a weight
override. Check reported embedding availability before describing a search as hybrid.

## Maintain context when requested

Canonical files are authoritative; `.dal/query/` is a generated cache. Edit files
or use proposals within the user's requested scope, then validate and build.
Do not publish proposals merely because they appear in search results. Proposal
publication requires the current revision and the user's authorization.

Route each finding to the resource and field it describes; do not turn every caveat
or “gotcha” into a doctrine document. Column meaning belongs in column `description`
(or `unit`/`expression`); row meaning in table `grain`; mandatory filters in
`required_filters`; join behavior in `predicate`, `cardinality`, `grain_effect`, or
the join's `description`. Update the existing field without losing its prior context.
Keep supporting reasons and uncertainty in evidence for that resource/claim.
Doctrine is reusable methodology above individual resource definitions, not a
catch-all for extracted strings. Consolidate related methodology into a coherent
document and link its applicable `object_ids`. Gold queries hold reusable questions
and SQL. If the target or interpretation is unclear, propose a change for review
rather than inventing a new doctrine. See [authoring](references/authoring.md) when
creating or repairing context from notes or extracted metadata.

```sh
dal --repository /path/to/context validate
dal --repository /path/to/context build
dal --repository /path/to/context health
```

Health reports include gaps and recovery instructions. Report unavailable live
checks as not checked; do not infer warehouse health from a healthy local bundle.
Use `dal proposal --help` for the installed revision's mutation arguments.

For visual review, `dal --repository /path/to/context serve` starts the local UI
and REST API. Keep the default local binding unless remote access is requested.
Keep private schema, SQL, and evidence in the user's graph, not this skill package.
