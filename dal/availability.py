"""Shared join eligibility from resource dependencies and explicit physical facts."""


def unavailable_from_claims(claims):
    """Latest physical existence claim wins; a same-time disagreement fails closed."""
    latest = {}
    for subject, collected_at, exists in claims:
        if not isinstance(exists, bool):
            continue
        previous = latest.get(subject)
        if previous is None or collected_at > previous[0]:
            latest[subject] = (collected_at, exists)
        elif collected_at == previous[0]:
            latest[subject] = (collected_at, exists and previous[1])
    return {subject for subject, (_, exists) in latest.items() if not exists}


def join_dependency_failures(objects, unavailable=()):
    indexed = {item["id"]: item for item in objects}
    unavailable = set(unavailable)
    failures = {}

    def problem(identifier, kind):
        item = indexed.get(identifier)
        if item is None or item.get("kind") != kind:
            return f"{identifier}: missing {kind}"
        if item.get("status") == "deprecated":
            return f"{identifier}: deprecated {kind}"
        if item.get("restricted"):
            return f"{identifier}: restricted {kind}"
        if identifier in unavailable:
            return f"{identifier}: physical evidence reports it absent"
        return None

    for item in objects:
        if item.get("kind") != "join":
            continue
        reasons = []
        for endpoint in item.get("left", []) + item.get("right", []):
            reason = problem(endpoint, "column")
            if reason:
                reasons.append(reason)
                continue
            reason = problem(indexed[endpoint].get("parent_id"), "table")
            if reason:
                reasons.append(reason)
        if reasons:
            failures[item["id"]] = tuple(dict.fromkeys(reasons))
    return failures
