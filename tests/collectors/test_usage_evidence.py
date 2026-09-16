import json
from datetime import datetime, timezone

from dal.cli.main import main
from dal.collectors import collect_queries
from dal.documents import load_document
from dal.evidence import SnapshotRepository, serialize_snapshot
from dal.identity import stable_id

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)
REPEATED_JOIN = """
WITH first_orders AS (
    SELECT o.customer_id FROM sales.orders o
    JOIN sales.customers c ON o.customer_id = c.id
), second_orders AS (
    SELECT other_orders.customer_id FROM sales.orders other_orders
    JOIN sales.customers other_customers ON other_orders.customer_id = other_customers.id
)
SELECT * FROM first_orders UNION ALL SELECT * FROM second_orders
"""


def test_identical_join_in_two_ctes_emits_one_claim_per_query():
    result = collect_queries([{"QueryExecutionId": "query-1", "sql": REPEATED_JOIN}], collected_at=NOW)

    assert len(result.objects) == 1
    assert len(result.evidence) == 3
    assert len({record.record_id for record in result.evidence}) == 3
    join, = [record for record in result.evidence if record.claim_path == "/usage/join_expression"]
    assert join.subject_id == result.objects[0]["id"]
    assert join.claim_value == result.objects[0]["predicate"]
    assert join.content.uri == "athena:query/query-1"
    assert {record.subject_id for record in result.evidence if record.claim_path == "/usage/query"} == {
        stable_id("table", "sales.orders"), stable_id("table", "sales.customers"),
    }
    assert serialize_snapshot(result.evidence)


def test_repeated_query_records_are_idempotent():
    query = {"QueryExecutionId": "query-1", "sql": REPEATED_JOIN}
    once = collect_queries([query], collected_at=NOW)
    repeated = collect_queries([query, query], collected_at=NOW)

    assert repeated == once
    assert serialize_snapshot(repeated.evidence) == serialize_snapshot(once.evidence)


def test_same_join_in_distinct_executions_keeps_both_sources():
    queries = [{"QueryExecutionId": query_id, "sql": REPEATED_JOIN} for query_id in ("query-1", "query-2")]
    result = collect_queries(queries, collected_at=NOW)

    assert len(result.objects) == 1
    assert len(result.evidence) == 6
    joins = [record for record in result.evidence if record.claim_path == "/usage/join_expression"]
    assert len(joins) == 2
    assert {record.content.uri for record in joins} == {"athena:query/query-1", "athena:query/query-2"}
    assert len({record.source.revision for record in joins}) == 2
    reversed_result = collect_queries(reversed(queries), collected_at=NOW)
    assert serialize_snapshot(result.evidence) == serialize_snapshot(reversed_result.evidence)


def test_different_join_predicates_in_one_query_keep_separate_claims():
    sql = REPEATED_JOIN.replace("other_orders.customer_id = other_customers.id",
                                "other_orders.customer_id = other_customers.id AND other_customers.active = true")
    result = collect_queries([{"QueryExecutionId": "query-1", "sql": sql}], collected_at=NOW)

    assert len(result.objects) == 2
    joins = [record for record in result.evidence if record.claim_path == "/usage/join_expression"]
    assert len(joins) == 2
    assert len({record.record_id for record in joins}) == 2
    assert {record.subject_id for record in joins} == {item["id"] for item in result.objects}
    assert len({record.claim_value for record in joins}) == 2
    assert serialize_snapshot(result.evidence)


def test_refresh_with_repeated_cte_join_builds_and_reuses_evidence(tmp_path, capsys):
    source = tmp_path / "snapshot.json"
    source.write_text(json.dumps({
        "collected_at": NOW.isoformat(),
        "tables": [
            {"database": "sales", "table": {"Name": name, "StorageDescriptor": {
                "Columns": [{"Name": column, "Type": "bigint"}],
            }}}
            for name, column in (("orders", "customer_id"), ("customers", "id"))
        ],
        "queries": [{"QueryExecutionId": "query-1", "sql": REPEATED_JOIN}],
    }))
    root = tmp_path / "repo"
    args = ["--repository", str(root), "build", "--refresh", str(source)]

    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    snapshots = list((root / "evidence").glob("*.json"))
    snapshot, = snapshots
    before = snapshot.read_bytes()
    records = SnapshotRepository(root / "evidence").get(snapshot.stem)
    assert len({record.record_id for record in records}) == len(records)
    assert len([record for record in records if record.claim_path == "/usage/join_expression"]) == 1
    document = load_document((root / "semantic/collected.yaml").read_text())
    join, = [item for item in document["objects"] if item["kind"] == "join"]
    assert main(["--repository", str(root), "join", "get", join["id"]]) == 0
    assert json.loads(capsys.readouterr().out)["payload"]["predicate"] == join["predicate"]

    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["revision"] == first["revision"]
    assert list((root / "evidence").glob("*.json")) == snapshots
    assert snapshot.read_bytes() == before
