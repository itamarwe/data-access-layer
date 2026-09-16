# Author facts on objects; doctrine explains methods

## What doctrine is for

Doctrine is reusable analytical methodology: how to choose, combine, or interpret
organizational data to answer a class of questions. It holds reasoning and procedures
that are not themselves an object's definition or usage constraint. Examples include
choosing comparable observation periods, reconciling two measurement approaches,
and deciding when a proxy supports a conclusion.

Object fields explain **what this object is and how it can be used correctly**.
Doctrine explains **how to approach an analytical task using those definitions**.
Neither prose nor importance makes a statement doctrine. A critical warning about
one column still belongs on that column. Mentioning multiple objects is also not
enough: joins, relations, and metrics already have fields for cross-object meaning.

## Choose the destination

Split a source note into independently meaningful claims before writing. Resolve
each claim's owner and source, then choose its destination by meaning—not by the
source label (“gotcha”, “note”, “warning”) or the number of mentioned tables.

- **Object fact or constraint:** use the existing object's dedicated field. If no
  dedicated field fits, use its `description`; do not invent a `gotchas` field or
  create a doctrine just to hold prose. Search existing objects before proposing a
  new table, join, metric, or ontology definition.
- **Analytical method:** use doctrine when there is useful guidance left after the
  object facts have been placed. A method can concern one object, several, or none
  specifically. Link the objects it applies to, rather than assigning it a fake owner.
- **Support for a claim:** attach evidence to that object and claim, with the actual
  source, date, and uncertainty. A usage example is not automatically a general rule.
- **Reusable question and SQL:** use a gold query. It can reference the applicable
  doctrine and data objects; it does not replace their definitions.
- **Unresolved owner or interpretation:** keep it for clarification/review. Do not
  relabel an unresolved fact as global methodology or invent a target or SQL rule.

| Finding | Destination |
| --- | --- |
| Amounts in this column are cents | Column `unit` and `description` |
| One row per order and line item | Table `grain` |
| Every use of this table must exclude internal test orders | Table `required_filters`; explain why in its description and support it with evidence |
| Only the production-revenue metric excludes test orders | Metric `required_filters`; do not impose that task-specific rule on every use of the table |
| Join on the stable identifier, not display name | Join `predicate` and `description` |
| The join duplicates orders unless the current-record filter is applied | Join `required_filters`, `cardinality`, and `grain_effect`, only as supported |
| Meaning of “active customer” | Entity/property definition with data bindings; place executable rules on the relevant data resources |
| Net revenue is sales less refunds from a second table | Metric `expression`, `object_ids`, and definition; cross-table calculation is not doctrine |
| This table has a known late-arrival caveat | Table `description` (and supported freshness metadata); not a standalone doctrine |
| Aggregate actuals to the target grain, align populations, then interpret the variance | Doctrine scoped to the actuals and targets; their grains and formulas stay on their objects |
| How to reconstruct an as-of population from one history table | Doctrine scoped to that table for the procedure; history columns and grain remain object facts |
| How to compare incomplete periods when the user has not specified a cutoff | Object-independent doctrine, with its applicability stated in the content |
| A reviewed question with reusable SQL | Gold query |

## Scope and document boundaries

Use doctrine `object_ids` to link known resources to which the method applies.
These are scope/reference links, not ownership. Do not list every object mentioned
incidentally or create a placeholder object to attach a method to.

For a method with no particular object, omit `object_ids` or use `[]`. DAL treats
this as global retrieval scope, **not** an instruction that applies to every task.
State the analytical situation in the name and content, including prerequisites
and exceptions. “Owner unknown” is not the same as “no object needed.”

Organize doctrine around one coherent analytical decision or procedure, not one
document per extracted sentence. Extend an existing method when purpose and scope
match; split methods when they apply under materially different conditions. Keep
the content actionable: when to use it, what to do, why, and limitations where they
matter. There is no required document length or section template.

Do not duplicate canonical predicates, grains, or formulas in methodology. Reference
their owning resources and explain the reasoning that connects them. If a source
disagrees with an existing definition, retain the conflicting evidence and propose
the change; do not use a doctrine as an overriding second definition.

## Mixed notes: separate fact from method

Suppose a source note says: “Amounts are cents, each row is an order, and for a
monthly actual-versus-target comparison aggregate orders to the target period and
population before calculating variance.” Route the unit to the amount column and
the grain to the orders table. The comparison procedure is the doctrine. Do not
create three doctrines, or copy the unit and grain into the method as new authorities.

This synthetic example illustrates those destinations, plus a method with no
particular object. It assumes the facts have already been reviewed; it is not a
template to copy into a real graph without source support.

```yaml
version: 1
objects:
  - id: table:orders
    kind: table
    name: Orders
    grain:
      description: One row per order.
  - id: column:orders.amount
    kind: column
    name: Amount
    parent_id: table:orders
    unit: cents
  - id: table:targets
    kind: table
    name: Targets
    grain:
      description: One row per month and region.
  - id: doctrine:actuals-versus-targets
    kind: doctrine
    name: Comparing actuals with targets
    object_ids: [table:orders, table:targets]
    content: >-
      For an actual-versus-target comparison, aggregate actuals to the target's
      declared grain before combining them. Align time windows and populations.
      Do not interpret variance until those bases are comparable; inspect each
      resource's definition for its current grain and measurement units.
  - id: doctrine:incomplete-period-comparison
    kind: doctrine
    name: Comparing incomplete reporting periods
    object_ids: []
    content: >-
      When a requested comparison includes an incomplete period, establish an
      as-of cutoff and compare equivalent observation windows. If the cutoff is
      unknown, clarify it before reporting a trend. State the chosen windows.
```

Do not present inferred SQL or cardinality as measured. Classification requires
semantic interpretation; keyword matching alone is not a safe authoring algorithm.

## Repair existing context

For a cleanup, inspect existing doctrine and propose moves to resource fields.
Combine a field's existing and new knowledge without duplicating or contradicting it.
Remove a redundant doctrine only after preserving its useful content, evidence, and
references and obtaining the user's authorization. Do not bulk-delete methodology
based on document length or count. Keep stable IDs for methods that remain, repair
references for moved content, then validate and rebuild. Object facts and doctrine
use the same proposal/publication lifecycle; doctrine has no higher authority.

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
