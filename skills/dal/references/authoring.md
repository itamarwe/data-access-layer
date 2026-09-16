# Route knowledge to its owner

Before writing files, map each finding to an existing resource ID, field, and source.
Do not classify by the source label (“gotcha”, “note”, “warning”); classify by meaning.

| Finding | Destination |
| --- | --- |
| Amounts in this column are cents | Column `unit` and `description` |
| One row per order and line item | Table `grain` |
| Exclude internal test orders | Table `required_filters`; explain why in its description/evidence |
| Join on the stable identifier, not display name | Join `predicate` and `description` |
| The join duplicates orders unless the current-record filter is applied | Join `required_filters`, `cardinality`, and `grain_effect`, only as supported |
| Meaning of “active customer” | Entity/property definition with data bindings; place executable rules on the relevant data resources |
| How to choose reporting periods and compare cohorts across domains | One scoped doctrine describing that methodology |
| A reviewed question with reusable SQL | Gold query |

Keep a finding's source and confidence in physical, usage, or curation evidence.
Do not present inferred SQL or cardinality as measured. Free-text notes need semantic
interpretation; keyword matching alone is not a safe authoring algorithm.

For a cleanup, inspect existing doctrine and propose moves to resource fields.
Combine a field's existing and new knowledge without duplicating or contradicting it.
Remove a redundant doctrine only after preserving its useful content, evidence, and
references and obtaining the user's authorization. Do not bulk-delete methodology
based on document length or count.

## Joins with unavailable endpoints

A join is unusable if an endpoint column or its table is missing, deprecated,
restricted, or reported absent by the latest physical `/exists` evidence. DAL excludes
such joins from retrieval and reports them in health; their authored records remain
for repair. A subsequent physical existence claim can restore availability, but does
not override explicit deprecation or restriction. `--include-deprecated` does not make
an unusable join safe.

Health checks do not edit files or silently change the compiled bundle. If an explicit
physical health snapshot finds a missing table, record the confirmed absence in
physical evidence (or deprecate the resource as appropriate), then rebuild. A partial
snapshot or absence from query logs is not proof that a table is unavailable.
