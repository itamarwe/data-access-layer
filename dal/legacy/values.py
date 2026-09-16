"""Value normalization at the old graph import boundary."""

def publication(value: object) -> str:
    return "deprecated" if str(value).strip().lower() in {
        "deprecated", "dead", "frozen", "inactive", "superseded",
    } else "published"
