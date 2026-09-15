# DAL context graph

Give an AI agent the organizational context it needs to query data correctly, with useful answers in few turns and a bounded response size.

There is one native model, one compiler, and one application service shared by the CLI, REST API, browser UI, and MCP. Legacy archives are supported through an explicit one-way importer. The examples and evaluation fixtures are synthetic.

## Run it

Requires Python 3.11 or newer.

```sh
python -m pip install -e '.[dev]'
dal --repository examples/shop build
dal --repository examples/shop search "orders by customer"
dal --repository examples/shop serve
```

Open http://127.0.0.1:8765 for the UI; /api/docs contains the REST API reference. The server is local by default. Exposing it on another interface requires explicit remote access and a bearer token; use TLS at your reverse proxy.

For a new graph:

```sh
dal --repository /path/to/context init
dal --repository /path/to/context import /path/to/customer-archive.zip
dal --repository /path/to/context validate
dal --repository /path/to/context build
dal --repository /path/to/context search "customer retention" --token-budget 1600
```

The importer never overwrites conflicting authored objects. Its report identifies missing references and unreviewed material that was not published. Original archives are never modified or committed.

## Files are the source of truth

```text
semantic/*.yaml       native resources; JSON is also accepted
proposals/*.yaml      open, published, or dismissed proposals
evidence/*.json       immutable, content-addressed source records
.dal/query/           disposable DuckDB query bundles and active pointer
```

Track the first three directories with Git if their contents are appropriate for your repository. Treat organizational SQL, schema names, and source evidence as potentially sensitive. Do not commit credentials or generated bundles.

Edit resource files directly or use a proposal. Both change the same files; there is no second editable database. Run `dal build` to update retrieval after edits. The long-running server picks up a newly activated bundle on its next request.

Resources use `version: 1` and a flat `objects` array. References use stable IDs, so files and arrays can be reorganized without changing identity. See [the example](examples/shop/semantic/catalog.yaml) and [the specification](SPEC.md).

## Commands

- `dal search "question"`: one cross-type search entry point.
- `dal connections OBJECT_ID`: separate groups for business relations, data joins, and ontology-to-data mappings. Membership and knowledge references remain ordinary fields and navigation.
- `dal table|column|join|entity|property|relation|metric|doctrine|gold-query|database list|get|search`: typed access.
- `dal proposal list|create|publish|dismiss|deprecate`: optional curator review.
- `dal validate`, `dal build`, `dal health`: validation, compilation, and explicit health checks.
- `dal serve`: REST and browser UI.
- `dal mcp`: the same retrieval services over MCP stdio.

Global `--repository` and `--bundle` options precede the command. Search returns detailed leading matches, compact alternatives, evidence, related methodology, gaps, omissions, and useful next commands. `--token-budget` is an **estimated** bound based on UTF-8 bytes divided by four, not a model-tokenizer guarantee.

There is one default ranking mix. Override individual weights with `--weight lexical=0.5 --weight embedding=0.5`. BM25 runs without model downloads. For real local embeddings:

```sh
python -m pip install -e '.[embeddings]'
dal --repository examples/shop build --embedding-model BAAI/bge-small-en-v1.5
```

The first model acquisition may use the network; graph text is embedded locally. Search explicitly reports whether embeddings are available. It never substitutes synthetic vectors.

## Curation and source refresh

Tables, columns, joins, ontology definitions, doctrine, and gold queries all use the same proposal lifecycle. Canonical resources are `published` by default and may become `deprecated`. Deprecated resources are excluded from default retrieval; they remain accessible explicitly.

Proposals change fields relative to a stable resource ID, not array positions. Publication checks the current repository revision and the original values of the affected fields. A direct edit to the same field blocks an outdated proposal; unrelated edits and file moves do not.

A new object is proposed with `object: {id, kind, name, ...}`. An edit uses `patch: [{op: add, path: /description, value: ...}]`. Obtain the current revision from `dal proposal list`; supply it as `--expected-revision`. REST writes use the same value in `If-Match`.

`dal build --refresh source-snapshot.json` imports captured Glue/Athena facts before building. Live collectors are read-only Python functions with bounded, injected clients; source changes do not silently erase curated descriptions, grain, filters, or ontology bindings. See [architecture](docs/architecture/simplified-context-graph.md) for the snapshot contract and limitations.

## Verification

```sh
python -m pytest
npm --prefix web run build
```

Tests cover native validation, compilation, damaged-build recovery, proposals, health, API, CLI, UI assets, imports, MCP, retrieval, and independently scored SQL tasks. SQL replay tests are not live-model accuracy measurements. Evaluation is separate from the product API.

See [validation results](docs/validation/native-context-graph.md) for test coverage, synthetic evaluation results, and remaining limitations.

## License

Licensed under the [MIT License](LICENSE).
