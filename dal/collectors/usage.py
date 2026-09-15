"""Collect existing Athena history and extract actual join predicates by SQL scope."""

from datetime import datetime

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

from dal.evidence import SourceKind, content_digest
from dal.identity import stable_id

from .types import CollectionResult, claim


def collect_athena(client, query_ids, *, collected_at: datetime, max_queries: int = 10000):
    identifiers = list(dict.fromkeys(query_ids))
    if len(identifiers) > max_queries or max_queries < 1:
        raise ValueError("Athena query limit exceeded")
    queries = []
    for start in range(0, len(identifiers), 50):
        response = client.batch_get_query_execution(QueryExecutionIds=identifiers[start:start + 50])
        if response.get("UnprocessedQueryExecutionIds"):
            raise ValueError("Athena did not return all requested executions; retry the collection")
        queries.extend(response.get("QueryExecutions", []))
    return collect_queries(queries, collected_at=collected_at)


def collect_queries(queries, *, collected_at: datetime):
    objects, evidence, diagnostics = {}, [], []
    for query in queries:
        sql = query.get("Query", query.get("sql", ""))
        if not isinstance(sql, str) or not sql.strip() or "-- context-graph-collector" in sql:
            continue
        state = query.get("Status", {}).get("State", "SUCCEEDED")
        if state != "SUCCEEDED":
            continue
        query_id = str(query.get("QueryExecutionId") or content_digest(sql))
        default_db = query.get("QueryExecutionContext", {}).get("Database") or query.get("database")
        revision = content_digest({"id": query_id, "sql": sql})
        try:
            tree = sqlglot.parse_one(sql, read="athena")
        except sqlglot.errors.ParseError:
            diagnostics.append(f"Could not parse query {query_id}")
            continue
        referenced = set()
        for scope in traverse_scope(tree):
            sources = {alias: table for alias, table in scope.sources.items() if isinstance(table, exp.Table)}
            resolved = {alias: ".".join(part for part in (table.catalog, table.db or default_db, table.name) if part)
                        for alias, table in sources.items()}
            referenced.update(resolved.values())
            for join in scope.expression.args.get("joins", []):
                on = join.args.get("on")
                if on is None:
                    continue
                pairs = []
                for comparison in on.find_all(exp.EQ):
                    left, right = comparison.left, comparison.right
                    if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
                        continue
                    if left.table not in resolved or right.table not in resolved or resolved[left.table] == resolved[right.table]:
                        continue
                    pairs.append((f"{resolved[left.table]}.{left.name}", f"{resolved[right.table]}.{right.name}"))
                # OR predicates do not establish a generally reusable equality join.
                if not pairs or on.find(exp.Or) is not None:
                    continue
                joined_source = resolved.get(join.this.alias_or_name)
                # ON operand order is not SQL join direction. Preserve the
                # joined table on the right, especially for outer joins.
                pairs = sorted((right, left) if joined_source and left.startswith(joined_source + ".")
                               else (left, right) for left, right in pairs)
                normalized = tuple(sorted(tuple(sorted(pair)) for pair in pairs))
                predicate = on.copy()
                for col in predicate.find_all(exp.Column):
                    if col.table in resolved:
                        table = sqlglot.to_table(resolved[col.table])
                        col.set("table", table.this.copy())
                        col.set("db", table.args.get("db"))
                        col.set("catalog", table.args.get("catalog"))
                sql_predicate = predicate.sql(dialect="athena")
                join_type = (join.side or join.kind or "inner").lower()
                identifier = stable_id("join", content_digest({
                    "left": [left for left, _ in pairs], "right": [right for _, right in pairs],
                    "predicate": sql_predicate, "join_type": join_type,
                }))
                item = {"id": identifier, "kind": "join", "name": " ↔ ".join(normalized[0]),
                        "left": [stable_id("column", left) for left, _ in pairs],
                        "right": [stable_id("column", right) for _, right in pairs],
                        "predicate": sql_predicate, "join_type": join_type}
                objects[identifier] = item
                evidence.append(claim(identifier, "/usage/join_expression", item["predicate"],
                                      kind=SourceKind.QUERY_LOG, revision=revision, collected_at=collected_at,
                                      uri=f"athena:query/{query_id}"))
        for source in sorted(referenced):
            evidence.append(claim(stable_id("table", source), "/usage/query", query_id,
                                  kind=SourceKind.QUERY_LOG, revision=revision, collected_at=collected_at,
                                  uri=f"athena:query/{query_id}"))
    return CollectionResult(tuple(objects.values()), tuple(evidence), tuple(diagnostics))
