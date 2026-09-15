# Native context graph specification

## Purpose

An AI agent needs to understand organizational concepts, their physical data bindings, correct joins and filters, data availability, and querying methodology. DAL provides this context with useful initial responses and purposeful follow-up, balancing correct task completion, tool turns, latency, and tokens.

The product does not execute arbitrary warehouse queries on behalf of the agent. It returns context and known SQL. Independent evaluation can execute controlled, read-only SQL against an evaluation fixture.

## Resource contract

Every resource has `id`, `kind`, and `name`. Optional common fields include description, source, aliases, status, bindings, object_ids, evidence_refs, curation, recommendation, restricted, and freshness.

| Kind | Purpose and relevant fields |
| --- | --- |
| database | Physical namespace; optional owner. |
| table | Physical source; optional grain, primary_key, required_filters, owner. |
| column | Table parent_id, data_type, nullable, optional expression or unit. |
| join | Paired left/right column IDs; optional known predicate, cardinality, join_type, grain_effect, required_filters. |
| entity | Organizational concept, physical bindings, identifier_ids. |
| property | Conceptual attribute, physical bindings, data_type, unit. |
| relation | Ontology relation with from_id and to_id; optional cardinality and bindings. |
| metric | expression, grain, required_filters, unit, dialect, relevant object_ids. |
| doctrine | Methodology prose in content, scoped through object_ids; empty scope is global. |
| gold_query | Curated question, sql, dialect, optional parameters and object_ids. |

Grain is optional. When known, describe it with a mapping such as `grain: {description: One row per order}`. Missing grain is a health gap, not a failed build.

A join without a known predicate remains useful evidence of a relationship; the system must not fabricate executable SQL. Physical overlap alone is not proof of a valid business join. SQL execution records and curated queries can supply stronger, specific support.

Missing retrieval matches return empty results, without additional graph-membership states.

## One graph, distinct meanings

All resources share one graph and one file store. A business entity is an ontology
resource, not a generic name for every graph node.

| Connection | Meaning | Representation |
| --- | --- | --- |
| Relation | Named business meaning, such as Customer places Order | A relation resource between entities/properties |
| Join | How data can be connected, including conditions and cardinality | A join resource with table endpoints derived from paired columns |
| Mapping | Where business meaning is implemented in data | bindings on the semantic resource |

Mappings always point from ontology to data: entity to table/column, property to
column, or relation to join. A relation can map to a join, but neither is a
duplicate representation of the other.

Membership uses parent_id. Methodology scope and query references use object_ids.
These remain normal resource fields, with inverse lookup for navigation—not
additional categories of domain relationship. Evidence references likewise do not
create another business relation.

Search returns connections grouped into relations, joins and mappings.
dal connections OBJECT_ID and GET /api/v1/graph/connections expose the same groups.
Each relation/join includes its canonical resource ID and name; join results retain
the paired columns and complete known predicate/filters. Structural navigation
returns native objects with a via field. Internal join_column, join_table,
ontology_binding and context indexes never appear as public relationship types.

Distinct observed predicates, conditions and join directions remain distinct
definitions. Evidence is not allowed to choose a definition by collection order.

## Evidence

There are three evidence layers:

- **physical:** extracted schemas, profiles, measured overlap, corruption findings, and data timestamps.
- **usage:** actual query logs, with extensible source types for lineage, dashboards, reports, and organizational communications.
- **curation:** authored interpretations, methodology, ontology bindings, and curated questions. A model is a curator, not a new evidence layer.

An evidence record identifies a subject, claim path, claim value, source kind and revision, collection time, and content reference. Strength is optional, not fabricated. A measurement carries a measured value and optional unit. Absence of measurement means unmeasured; measured zero is not unknown.

Published means selected for use, not necessarily empirically correct. Source evidence may disagree with current curation. Retain these distinctions and source values.

## Lifecycle

A proposal is `open`, then `published` or `dismissed`. A published resource may become `deprecated`. No separate approval state or resource-specific review lifecycle exists.

Publishing edits the canonical file and records the decision in the proposal. Deprecation uses a proposal setting the resource status to deprecated. Stable IDs, field preconditions, and expected repository revisions protect against stale writes.

Direct file edits are supported and become searchable after a build. Git is the revision history; DAL does not automatically commit, push, or reinterpret Git branches as review decisions. External editors must coordinate multi-file edits; DAL's process lock cannot lock arbitrary editors.

## Storage and build

Canonical resources, proposals, and immutable source evidence are files. The DuckDB bundle is disposable derived state, not an editable authority.

Build validates the whole repository, resolves cross-file IDs, derives links and indexes, checks evidence, and computes a content revision. Identical inputs reuse verified output. Changed resources update from the previous immutable bundle. Interrupted work retries from its pinned, verified base. Activation occurs only after a complete bundle passes integrity checks.

The build is resumable at the immutable-snapshot boundary. It does not claim per-batch resume within an embedding request or source API call. Failed compilation leaves the previous active revision unchanged.

## Retrieval and interfaces

All delivery surfaces call the same application service. One search mixes BM25 with optional local embeddings and explicit graph/evidence signals. There are no named ranking modes.

Responses prioritize a few useful objects, retain whole SQL predicates and filters, disclose omitted matches, and offer next commands. When a result cannot fit, it is omitted with a follow-up command rather than truncating SQL into invalid guidance. Each operation uses one immutable bundle revision.

The browser UI includes search, catalog details, ontology, doctrine, gold queries, proposals, and health. The REST API serves the UI and exposes the same resources. MCP is a thin read-only adapter. Evaluation is not a product endpoint.

## Health

Separate operational failures from knowledge gaps. Report which checks ran and which lacked inputs.

Checks include document corruption, broken references, bundle checksums, stale compiled resources, missing tables, schema changes, new columns, stale evidence, source corruption, and source data age when a genuine data-update timestamp is available.

Collection time is not a substitute for data freshness. A successful local check without a physical snapshot does not certify a live warehouse. Each finding includes a recovery instruction.

## Evaluation

Use independent tasks, expected outcomes, and fixed inputs. Retrieval-ID regression only checks retrieval. SQL correctness is checked against expected result rows, including duplicates and order where relevant. Model tokens come from provider usage, not response-byte estimates. Report tool calls, model turns, latency, and tokens separately.

Ablation holds the question and expected outcome constant while removing a context contribution. Development archive questions are not a held-out accuracy benchmark. Adoption or publication must not be described as automatically validated by ablation; automatic gating is not implemented.
