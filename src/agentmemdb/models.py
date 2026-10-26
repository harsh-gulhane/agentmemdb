"""Memory categories, importance levels and validation of tool inputs."""

import json
from datetime import datetime, timezone

CATEGORIES = (
    "conversation",  # summary of a conversation or session
    "decision",  # a decision and why it was made
    "incident",  # alert or incident investigation and resolution
    "research",  # analysis, findings, deep dives
    "person",  # a colleague or contact
    "project",  # project context, status, goals
    "howto",  # procedures and runbooks
    "config",  # configuration and environment setup
    "other",
)

IMPORTANCE_LEVELS = ("low", "normal", "high", "critical")
IMPORTANCE_RANK = {level: rank for rank, level in enumerate(IMPORTANCE_LEVELS)}

ENTITIES_HINT = 'Expected a JSON array of objects like [{"type":"service","value":"billing-api"}]'


class ToolError(Exception):
    """Invalid input or missing memory; returned to the agent as {"error": message}."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: str) -> datetime:
    """Parse YYYY-MM-DD or ISO 8601; naive values are treated as UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        return utc_now() > parse_timestamp(expires_at)
    except (ValueError, TypeError, AttributeError):
        return False


def check_category(category: str) -> None:
    if category not in CATEGORIES:
        raise ToolError(f"Invalid category. Must be one of: {list(CATEGORIES)}")


def check_importance(importance: str) -> None:
    if importance not in IMPORTANCE_LEVELS:
        raise ToolError(f"Invalid importance. Must be one of: {list(IMPORTANCE_LEVELS)}")


def check_expiry(expires_at: str) -> None:
    try:
        parse_timestamp(expires_at)
    except ValueError:
        raise ToolError("Invalid expires_at. Use YYYY-MM-DD or an ISO 8601 timestamp") from None


def parse_tags(tags: str) -> list[str]:
    return [t.strip() for t in tags.split(",") if t.strip()]


def parse_entities(entities: str) -> list[tuple[str, str]]:
    """Parse the entities JSON into unique, lowercased (type, value) pairs."""
    if not entities:
        return []
    try:
        parsed = json.loads(entities)
    except json.JSONDecodeError as err:
        raise ToolError(f"Invalid entities JSON: {err}") from None
    if not isinstance(parsed, list):
        raise ToolError(f"Invalid entities: {ENTITIES_HINT}")
    pairs = []
    for entity in parsed:
        if not (
            isinstance(entity, dict)
            and isinstance(entity.get("type"), str)
            and isinstance(entity.get("value"), str)
            and entity["type"].strip()
            and entity["value"].strip()
        ):
            raise ToolError(f"Invalid entity {json.dumps(entity)}: {ENTITIES_HINT}")
        pairs.append((entity["type"].strip().lower(), entity["value"].strip().lower()))
    return list(dict.fromkeys(pairs))


def clamp(limit: int, upper: int = 100) -> int:
    return max(1, min(int(limit), upper))
