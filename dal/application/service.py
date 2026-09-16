"""One catalog service shared by every delivery adapter."""

from __future__ import annotations

import json
import math
import shlex
from collections.abc import Mapping
from dataclasses import asdict, replace
from functools import wraps

from .embedding import QueryEmbedder, local_embedder
from .kinds import command_name, require_kind
from .models import (
    CatalogObject, CompactMatch, EvidenceSummary, GraphNeighbor, NextCommand,
    Omissions, RankingSignals, RankingWeights, SearchCapabilities, SearchOptions,
    SearchResponse, SearchResult, StartWith, TableDetail,
)
from .presentation import gaps, grain, status, summary
from .ranking import combine, cosine, normalized, publication_signal, tokenize
from .repository import BundleCatalog
from .connections import connections, neighbors
from .models import Connections


def pinned(operation):
    """Use one immutable revision for each complete public operation."""
    @wraps(operation)
    def invoke(self, *args, **kwargs):
        service = CatalogService(self.catalog.snapshot(), self.embedder)
        return operation(service, *args, **kwargs)
    return invoke


class CatalogService:
    def __init__(self, catalog: BundleCatalog, embedder: QueryEmbedder | None = None):
        self.catalog = catalog
        self.embedder = embedder
        self._embedding_reason: str | None = None
        self._embedding_resolved = embedder is not None

    @pinned
    def list(self, kind: str, *, limit: int = 20, offset: int = 0, include_deprecated: bool = False,
             parent_id: str | None = None, referenced_object_id: str | None = None) -> tuple[CatalogObject, ...]:
        require_kind(kind)
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be 1..100 and offset cannot be negative")
        return self.catalog.list_objects(kind, limit, offset, include_deprecated, parent_id, referenced_object_id)

    @pinned
    def resolve(self, object_ids: list[str]) -> tuple[CatalogObject, ...]:
        if not 1 <= len(object_ids) <= 100 or any(not isinstance(value, str) or not value for value in object_ids):
            raise ValueError("provide 1..100 nonempty object IDs")
        identifiers = tuple(dict.fromkeys(object_ids))
        found = self.catalog.objects(identifiers)
        return tuple(found[identifier] for identifier in identifiers if identifier in found)

    @pinned
    def get(self, kind: str, object_id: str) -> CatalogObject | None:
        return self.catalog.get_object(object_id, require_kind(kind))

    @pinned
    def table_detail(self, object_id: str, *, limit: int = 20, offset: int = 0) -> TableDetail | None:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be 1..100 and offset cannot be negative")
        table = self.catalog.get_object(object_id, "table")
        if table is None:
            return None
        columns = self.catalog.list_objects("column", limit + 1, offset, parent_id=object_id)
        more = len(columns) > limit
        return TableDetail(**asdict(table), columns=columns[:limit],
                           columns_page={"limit": limit, "offset": offset, "has_more": more},
                           next_commands=(f"dal column list --table {shlex.quote(object_id)} --limit {limit} --offset {offset + limit}",) if more else ())

    @pinned
    def neighbors(self, object_id: str, *, limit: int = 20) -> tuple[GraphNeighbor, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        return neighbors(self.catalog, object_id, limit)

    @pinned
    def connections(self, object_id: str, *, limit: int = 20) -> Connections:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        return connections(self.catalog, (object_id,), limit)

    @pinned
    def evidence(self, object_id: str, *, limit: int = 20, column_id: str | None = None,
                 claim_path: str | None = None) -> tuple[EvidenceSummary, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        if object_id in self.catalog.blocked_joins:
            return ()
        subject = object_id
        if column_id is not None:
            column = self.catalog.get_object(column_id, "column")
            if column is None or column.parent_id != object_id:
                raise ValueError("column must belong to the specified table")
            subject = column_id
        return self.catalog.evidence((subject,), limit, claim_path)

    def search_kind(
        self, kind: str, query: str, *, weights: Mapping[str, float] | None = None,
        options: SearchOptions | None = None, parent_id: str | None = None,
    ) -> SearchResponse:
        return self.search(query, kind=require_kind(kind), weights=weights, options=options, parent_id=parent_id)

    @pinned
    def search(
        self, query: str, *, kind: str | None = None,
        weights: Mapping[str, float] | None = None, options: SearchOptions | None = None,
        parent_id: str | None = None,
    ) -> SearchResponse:
        if kind:
            require_kind(kind)
        selected_weights = RankingWeights().override(weights)
        limits = options or SearchOptions()
        terms = tokenize(query)
        lexical = self.catalog.bm25(terms, limits.candidate_limit, kind, parent_id)
        embedding, capabilities = self._embedding_scores(query, kind, limits.candidate_limit, parent_id)
        identifiers = tuple(dict.fromkeys((*lexical, *embedding)))
        if not terms or not identifiers:
            return _fit(_empty(query, selected_weights, capabilities), limits.token_budget, limits.max_compact)
        objects = self.catalog.objects(identifiers)
        objects = {key: item for key, item in objects.items()
                   if limits.include_deprecated or status(item) != "deprecated"}
        lexical = normalized({key: value for key, value in lexical.items() if key in objects})
        degrees = normalized(self.catalog.degrees(objects))
        evidence = normalized(self.catalog.evidence_strengths(objects))
        ranked = []
        for object_id, item in objects.items():
            signals = RankingSignals(
                lexical.get(object_id, 0.0), embedding.get(object_id, 0.0),
                degrees.get(object_id, 0.0), evidence.get(object_id, 0.0),
                publication_signal(item),
            )
            ranked.append((combine(signals, selected_weights), item, signals))
        ranked.sort(key=lambda value: (-value[0], value[1].kind, value[1].name, value[1].id))
        return self._response(query, ranked, selected_weights, capabilities, limits)

    def _embedding_scores(
        self, query: str, kind: str | None, limit: int, parent_id: str | None = None,
    ) -> tuple[dict[str, float], SearchCapabilities]:
        vectors, index_status = self.catalog.embedding_index(kind, parent_id)
        if not vectors:
            reason = "embedding_index_missing" if index_status == "missing" else "embedding_index_empty"
            return {}, SearchCapabilities("bm25", "unavailable", reason)
        if not self._embedding_resolved:
            self.embedder, self._embedding_reason = local_embedder(self.catalog.embedding_health())
            self._embedding_resolved = True
        if self.embedder is None:
            reason = self._embedding_reason or "query_embedder_not_configured"
            return {}, SearchCapabilities("bm25", "unavailable", reason)
        embedded = tuple(self.embedder.embed((query,)))
        if len(embedded) != 1:
            raise ValueError("query embedder returned the wrong number of vectors")
        query_vector = tuple(float(value) for value in embedded[0])
        if len(query_vector) != self.embedder.dimensions:
            raise ValueError("query embedder returned the wrong dimensions")
        if not all(math.isfinite(value) for value in query_vector):
            raise ValueError("query embedder returned a non-finite value")
        if any(not all(math.isfinite(value) for value in vector) for vector in vectors.values()):
            raise ValueError("embedding index contains a non-finite value")
        compatible = {
            key: cosine(query_vector, vector) for key, vector in vectors.items()
            if len(vector) == self.embedder.dimensions
        }
        ordered = sorted(compatible.items(), key=lambda item: (-item[1], item[0]))[:limit]
        return dict(ordered), SearchCapabilities("bm25", "available")

    def _response(self, query, ranked, weights, capabilities, limits) -> SearchResponse:
        detailed_rows = ranked[:limits.max_details]
        compact_rows = ranked[limits.max_details:limits.max_details + limits.max_compact]
        detailed = tuple(_result(*row, catalog=self.catalog) for row in detailed_rows)
        compact = tuple(CompactMatch(item.id, item.kind, item.name, round(score, 6))
                        for score, item, _ in compact_rows)
        selected = tuple(item for _, item, _ in detailed_rows)
        returned_ids = tuple(item.id for item in selected) + tuple(item.id for item in compact)
        response = SearchResponse(
            query=query, read_as="Ranked context; inspect start_with first, then follow only useful next commands.",
            start_with=(StartWith(selected[0].id, "Highest score under the stated ranking mix.")
                        if selected else None), results=detailed, also_matched=compact,
            connections=connections(self.catalog, returned_ids, limits.max_connections),
            evidence=self.catalog.evidence((item.id for item in selected), limits.max_evidence),
            relevant_doctrine=self._doctrine(selected, ranked),
            relevant_gold_query=_first_summary(ranked, "gold_query"), gaps=gaps(selected),
            omissions=Omissions(len(ranked), len(detailed), len(compact),
                                max(0, len(ranked) - len(detailed) - len(compact))),
            estimated_tokens=0, next_commands=_next_commands(selected, compact),
            ranking_weights=weights, capabilities=capabilities,
        )
        return _fit(response, limits.token_budget, limits.max_compact)

    def _doctrine(self, selected, ranked):
        scope = {item.id for item in selected} | {item.parent_id for item in selected}
        # A typed table search still receives methodology scoped to that table.
        candidates = [item for _, item, _ in ranked if item.kind == "doctrine"]
        candidates.extend(self.catalog.list_objects("doctrine", 100, 0))
        for item in candidates:
            references = item.payload.get("object_ids", [])
            if status(item) != "deprecated" and (not references or scope.intersection(references)):
                return summary(item)
        return None


def _result(score, item, signals, *, catalog=None) -> SearchResult:
    fields = {
        "table": ("grain", "required_filters", "bindings"),
        "column": ("data_type", "expression", "required_filters", "bindings"),
        "join": ("left", "right", "predicate", "cardinality", "join_type", "required_filters"),
        "metric": ("expression", "required_filters", "object_ids", "grain"),
        "gold_query": ("question", "sql", "dialect", "object_ids"),
        "doctrine": ("content", "object_ids"),
        "relation": ("from_id", "to_id", "bindings"),
        "entity": ("bindings",), "property": ("bindings", "data_type"),
    }
    keys = (*fields.get(item.kind, ()), "freshness", "recommendation", "restricted")
    details = {key: item.payload[key] for key in keys if key in item.payload}
    if item.kind == "join" and catalog:
        columns = catalog.objects((*item.payload.get("left", []), *item.payload.get("right", [])))
        tables = catalog.objects(column.parent_id for column in columns.values() if column.parent_id)
        details["columns"] = [{"id": column.id, "name": column.name, "table_id": column.parent_id,
                               "source": tables[column.parent_id].source if column.parent_id in tables else None}
                              for column in columns.values()]
    return SearchResult(summary(item), round(score, 6), signals, item.source, item.parent_id,
                        grain(item), status(item), details or None)


def _first_summary(ranked, kind: str):
    return next((summary(item) for _, item, _ in ranked if item.kind == kind), None)


def _next_commands(selected, compact) -> tuple[NextCommand, ...]:
    candidates = [*selected[:1]]
    if compact:
        candidates.append(compact[0])
    return tuple(NextCommand(f"dal {command_name(item.kind)} get {shlex.quote(item.id)}",
                             "Load this resource's complete compiled payload.")
                 for item in candidates[:2])


def _fit(response: SearchResponse, budget: int, max_compact: int = 6) -> SearchResponse:
    candidates = tuple(CompactMatch(item.object.id, item.object.kind, item.object.name, item.score)
                       for item in response.results) + response.also_matched
    current = response
    while _estimate(current) > budget:
        if len(current.results) > 1:
            last = current.results[-1]
            compact = CompactMatch(last.object.id, last.object.kind, last.object.name, last.score)
            current = replace(current, results=current.results[:-1],
                              also_matched=((compact,) + current.also_matched)[:max_compact])
        elif current.also_matched:
            compact = current.also_matched[:-1]
            commands = current.next_commands if compact else current.next_commands[:1]
            current = replace(current, also_matched=compact, next_commands=commands)
        elif any((current.connections.relations, current.connections.joins, current.connections.mappings)):
            for group in ("mappings", "joins", "relations"):
                values = getattr(current.connections, group)
                if values:
                    current = replace(current, connections=replace(current.connections, **{group: values[:-1]}))
                    break
        elif current.relevant_gold_query:
            current = replace(current, relevant_gold_query=None)
        elif current.relevant_doctrine:
            current = replace(current, relevant_doctrine=None)
        elif current.evidence:
            current = replace(current, evidence=current.evidence[:-1])
        elif current.results:
            current = replace(current, results=(), start_with=None, gaps=(),
                              read_as="Matching context exceeds this budget. Use the next command for the complete object.")
        elif current.next_commands:
            current = replace(current, next_commands=())
        else:
            raise ValueError("query and response metadata exceed the token budget; shorten the query or increase --token-budget")
        current = replace(current, omissions=Omissions(
            current.omissions.total_matches, len(current.results), len(current.also_matched),
            max(0, current.omissions.total_matches - len(current.results) - len(current.also_matched)),
        ))
        visible = {item.object.id for item in current.results}
        current = replace(current, gaps=tuple(gap for gap in current.gaps if gap.object_id in visible))
    current = replace(current, estimated_tokens=_estimate(current))
    current = replace(current, estimated_tokens=_estimate(current))
    if current.estimated_tokens > budget:
        return _fit(current, budget, max_compact)
    # A full action can exceed the budget (for example, a long gold SQL query).
    # Retain its identity as a compact result when it fits; never truncate SQL.
    visible = {item.object.id for item in current.results} | {item.id for item in current.also_matched}
    for item in candidates:
        if item.id in visible or len(current.also_matched) >= max_compact:
            continue
        compact = current.also_matched + (item,)
        trial = replace(current, also_matched=compact, omissions=Omissions(
            current.omissions.total_matches, len(current.results), len(compact),
            max(0, current.omissions.total_matches - len(current.results) - len(compact)),
        ))
        trial = replace(trial, estimated_tokens=_estimate(trial))
        trial = replace(trial, estimated_tokens=_estimate(trial))
        if trial.estimated_tokens <= budget:
            current = trial
            visible.add(item.id)
    return current


def _estimate(response: SearchResponse) -> int:
    return math.ceil(len(json.dumps(asdict(response), default=str, ensure_ascii=False).encode("utf-8")) / 4)


def _empty(query, weights, capabilities) -> SearchResponse:
    response = SearchResponse(query, "No matching catalog context was found.", None, (), (), Connections(), (),
                              None, None, (), Omissions(0, 0, 0, 0), 0, (), weights, capabilities)
    return replace(response, estimated_tokens=_estimate(response))
