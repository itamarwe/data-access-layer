# Simplified native architecture

## Decision

Use a native, flat file model and keep only one implementation in this branch. Ossie models, profile envelopes, extension conversions, the old MCP server, and the old graph explorer are removed. Original code and design history remain available on the original branch and in Git.

The replacement keeps useful implementation components: deterministic source identity, immutable evidence, BM25, real optional local embeddings, incremental DuckDB compilation, a shared application service, and a visual curator UI.

## Ownership

| Component | Owns | Does not own |
| --- | --- | --- |
| Native model and repository | Resource contract, complete-file validation, stable references, deterministic serialization | Query execution or a second editable store |
| Collectors and one-way import | Read-only extraction, source evidence, explicit migration diagnostics | Approval of unreviewed candidates |
| Curation service | Proposal decisions, field conflicts, writes to resource files | A separate resource lifecycle for each type |
| Compiler | Derived object/link/evidence indexes, BM25, embeddings, verified activation | Authored truth |
| Application service | Ranking, result packing, related context, evidence and next steps | HTTP, browser rendering, or mutation policy |
| CLI, REST, UI, MCP | Thin delivery adapters | Independent domain semantics |
| Evaluation | Retrieval regressions and independently scored controlled SQL tasks | Product API endpoints or automatic publication gates |

## One authoritative representation

One connected graph does not imply one flat relationship taxonomy. Named business
relations connect ontology entities/properties; joins describe data connectivity;
bindings map ontology to physical data. Membership (parent_id) and knowledge
references (object_ids) are normal resource fields, not extra domain relationships.

The application projects internal adjacency indexes into three connection groups:
relations, joins and mappings. A composite join appears once, with its canonical ID,
columns and complete conditions. Named relations remain navigable resources.
CLI, REST, MCP and the browser share this projection. Resource navigation uses via
to describe which field or inverse reference was followed; it does not expose
compiler edge names.

Existing files from the earlier native importer may contain reversed
column.bindings references. Move each reference to the semantic object's bindings
array, pointing back to the column, then remove the column's bindings field.
Do not overwrite an existing curated repository with a fresh import.
Rebuild after changing the files; compiler 2.1 creates a fresh cache when upgrading.

Search's former relationships array is replaced by grouped connections; neighbor
responses replace relationship with via. Clients must update with this branch.

Native resources live in semantic YAML or JSON files. Proposals describe optional review work. Evidence files preserve source claims independently of the selected interpretation. Git can version these files.

A persistent local DuckDB file is a **derived cache**. It is not an in-memory database reloaded and reindexed on every CLI call, and it must never be edited as a source of truth. Removing generated bundles and rebuilding from the source files restores retrieval.

Direct edits and proposal publication affect the same resource files. Multi-file resources are loaded as one graph for validation. Proposals identify an object by ID and a top-level field, rather than assuming a specific array position or filename.

Reviewed fields are recorded in curation.fields, so a later source refresh cannot overwrite a reviewed data type or source binding. Other source-backed fields can refresh. Existing curated descriptions, methodology, grain, filters, and ontology bindings are preserved.

## Build and serving

1. Read native files and explicit evidence inputs.
2. Validate structure and references.
3. Compute a deterministic content revision, including compiler and embedding configuration.
4. Reuse a verified matching bundle, or update a copy of the verified previous bundle.
5. Write complete indexes, evidence, metadata, and file checksums.
6. Verify the bundle and atomically change the active pointer.

The previous revision remains active on failure. An interrupted transaction restarts from the pinned immutable base; no partial database is trusted just because a build marker exists.

The compiler verifies cached file checksums before reuse or activation. Health can perform the same integrity check. Retrieval performs lightweight revision/schema checks and pins one bundle per operation; it does not hash a large database on every search.

An external editor is not bound by DAL's process lock. Edit a coherent set of files and then build; build captures the resulting input. Ordinary write failures roll back a proposal's files, but the current file writer does not promise a multi-file transaction surviving machine power loss. Git is the recovery history.

## Sources

The current native collectors support read-only Glue schema collection and Athena query-log parsing. They accept injected clients and explicit limits. Other usage source types are representable, but connectors for dashboards, reports, lineage platforms, and internal communications are not implemented here.

The CLI's refresh input is a captured JSON object:

~~~json
{
  "collected_at": "2026-09-14T10:00:00Z",
  "tables": [{
    "database": "shop",
    "table": {
      "Name": "orders",
      "StorageDescriptor": {"Columns": [{"Name": "order_id", "Type": "bigint"}]}
    }
  }],
  "queries": []
}
~~~

Run dal build --refresh with that file. See dal.collectors for bounded live collector functions. Collection is an explicit action; the UI does not silently access cloud accounts.

Physical relationships and observed query joins both remain join resources with independent supporting evidence. Endpoints and a usage count do not justify inventing a SQL predicate. Original SQL may establish a predicate; otherwise it is absent.

## Search and response size

Search has one configurable mix of lexical similarity, local semantic similarity, graph connectivity, evidence strength, and publication. Default retrieval excludes deprecated resources. Connectivity is a discovery signal, not proof that a join is correct.

Small graphs use exact cosine matching over stored vectors. This is local hybrid retrieval, not an approximate-nearest-neighbor performance claim. A future vector index can replace this internal operation without creating a new resource representation.

Result packing retains complete SQL and filters, and uses compact identities and next commands when a detailed object does not fit. The token budget uses a disclosed UTF-8 byte estimate, not provider usage. Measure actual model usage separately.

## UI and API

The server serves a browser UI, resource/search/proposal/health routes, and its generated API reference. Search and catalog details expose evidence values and collection times, joins and filters, scoped doctrine, gold queries, and knowledge gaps. Proposal review supports editing fields and creating new resources.

The server uses local binding by default. Remote binding requires explicit opt-in and a bearer token. It does not provide enterprise identity, per-resource access policy enforcement, or TLS termination; restricted is contextual guidance, not an authorization boundary.

## Migration and deliberate limits

Native DAL JSON/YAML documents and former DAL JSON graph exports (files or directories) are accepted by the import command. Unsupported nodes and missing join endpoints in former DAL exports are reported rather than silently published. Custom DuckDB catalogs and ZIP archives are not supported. The importer is the only compatibility boundary; no old runtime runs alongside the new one.

The branch is a replacement, not an assertion of feature parity with every old graph algorithm. Sketch collection, old investigation workflows, and automatic discovery/community jobs are not copied into the native core. Collecting new sketches can be added behind the collector boundary.

Automatic ablation gating, a scheduled build daemon, live-model benchmark accuracy, enterprise access controls, and warehouse-specific query execution are not claimed as completed features. Independent controlled SQL evaluation and context ablation are implemented separately.

## Acceptance evidence

See [the validation report](../validation/native-context-graph.md). It records test coverage and development checks using synthetic fixtures. Retrieval and replay SQL checks are explicitly not presented as held-out model accuracy. Production archives and their benchmark outputs are not distributed with this repository.
