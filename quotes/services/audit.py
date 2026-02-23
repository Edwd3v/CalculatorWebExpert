from decimal import Decimal
from typing import Any

from quotes.models import AuditLog


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return value


def log_admin_action(*, actor, action: str, model_name: str, object_id: str | int | None = None, metadata: dict | None = None) -> None:
    AuditLog.objects.create(
        actor=actor,
        action=action,
        model_name=model_name,
        object_id=str(object_id or ""),
        metadata=_json_safe(metadata or {}),
    )
