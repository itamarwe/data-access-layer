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

Start with the actual question, using one cross-type search:

```sh
dal --repository /path/to/context search "the user's data question" --token-budget 1600
```

Use leading results, compact matches, methodology, gold queries, gaps, and suggested
next commands together. Follow up only for missing facts that affect the answer;
do not enumerate every resource. A compact match is an identity, not the full
join predicate or query. Retrieve the complete resource when needed:

```sh
dal --repository /path/to/context table get TABLE_ID
dal --repository /path/to/context connections OBJECT_ID
dal --repository /path/to/context join get JOIN_ID
dal --repository /path/to/context table evidence TABLE_ID
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
Use the default ranking unless a concrete retrieval problem warrants a weight
override. Check reported embedding availability before describing a search as hybrid.

## Maintain context when requested

Canonical files are authoritative; `.dal/query/` is a generated cache. Edit files
or use proposals within the user's requested scope, then validate and build.
Do not publish proposals merely because they appear in search results. Proposal
publication requires the current revision and the user's authorization.

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
