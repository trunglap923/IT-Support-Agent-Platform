"""Normalize tool results into bounded, auditable working-memory observations."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.agent.working_memory.contracts import NormalizedToolObservation
from app.tools.results import ToolResult


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_identifier(value: str, limit: int, fallback: str) -> str:
    normalized = value.strip() or fallback
    if len(normalized) <= limit:
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{normalized[: limit - 13]}-{digest}"


def _safe_success_projection(
    tool_name: str, data: dict[str, Any]
) -> tuple[str, dict[str, str | int | bool | None], str | None]:
    if tool_name == "get_my_profile":
        return (
            "Authenticated profile lookup completed.",
            {"display_name_present": bool(str(data.get("display_name", "")).strip())},
            None,
        )
    if tool_name == "get_conversation_device":
        device = data.get("device")
        if not isinstance(device, dict):
            return (
                "No active device is attached to the conversation.",
                {"device_present": False},
                None,
            )
        return (
            "Active conversation device lookup completed.",
            {
                "device_present": True,
                "device_id": str(device.get("id", ""))[:80],
                "platform": str(device.get("platform", ""))[:40],
            },
            None,
        )
    if tool_name == "check_service_status":
        service_id = str(data.get("service_id", "unknown"))
        status = str(data.get("status", "unknown"))
        safe_service = service_id if service_id in {"vpn", "registry", "gitlab"} else "unknown"
        safe_status = status if status in {"healthy", "degraded", "down", "unknown"} else "unknown"
        return (
            f"Service {safe_service} reported status {safe_status}.",
            {"service_id": safe_service, "service_status": safe_status},
            None,
        )
    if tool_name in {"get_my_open_tickets", "get_my_recent_tickets"}:
        tickets = data.get("tickets")
        count = len(tickets) if isinstance(tickets, list) else 0
        return f"Ticket lookup returned {count} item(s).", {"ticket_count": count}, None
    if tool_name == "search_knowledge_base":
        sources = data.get("sources")
        count = len(sources) if isinstance(sources, list) else 0
        return (
            f"Knowledge search returned {count} source(s).",
            {"source_count": count},
            None,
        )
    if tool_name == "create_ticket":
        ticket = data.get("ticket")
        if isinstance(ticket, dict):
            ticket_id = str(ticket.get("id", ""))[:80]
            display_key = str(ticket.get("display_key", ""))[:40]
            receipt = f"ticket:{ticket_id}" if ticket_id else None
            return (
                "Approved ticket creation completed.",
                {"ticket_id": ticket_id, "display_key": display_key},
                receipt,
            )
    field_count = len(data)
    return (
        f"Tool {tool_name} completed with {field_count} top-level field(s).",
        {"field_count": field_count},
        None,
    )


def normalize_tool_result(
    result: ToolResult,
    arguments: dict[str, Any],
    *,
    observed_at: datetime | None = None,
) -> NormalizedToolObservation:
    """Create a safe projection without copying raw tool arguments or result data."""

    tool_name = _bounded_identifier(result.name, 80, "unknown_tool")
    call_id = _bounded_identifier(result.call_id, 160, f"tool:{_canonical_hash(result.name)}")
    error_code = result.error.code[:80] if result.error is not None else None
    receipt_ref: str | None = None
    if result.status == "success" and isinstance(result.data, dict):
        summary, safe_metadata, receipt_ref = _safe_success_projection(tool_name, result.data)
    else:
        safe_code = (error_code or "unknown_tool_result")[:80]
        summary = f"Tool {tool_name} returned {result.status}: {safe_code}."
        safe_metadata = {"retryable": bool(result.error and result.error.retryable)}
        error_code = safe_code
    return NormalizedToolObservation(
        call_id=call_id,
        tool_name=tool_name,
        status=result.status,
        error_code=error_code,
        summary=summary[:1_000],
        arguments_hash=_canonical_hash(arguments),
        result_hash=_canonical_hash(result.model_dump(mode="json")),
        receipt_ref=receipt_ref,
        safe_metadata=safe_metadata,
        observed_at=observed_at or datetime.now(UTC),
        reliability=0.9 if result.status != "unknown" else 0.4,
    )
