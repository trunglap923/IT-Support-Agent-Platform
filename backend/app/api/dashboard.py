"""Role-scoped operational dashboard analytics."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ApprovalRequest,
    ServiceState,
    Ticket,
    TicketEvent,
    User,
    UserRole,
)
from app.dependencies import CurrentPrincipal, get_db_session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardMetrics(BaseModel):
    open: int
    in_progress: int
    high_priority_unresolved: int
    resolved_in_range: int
    pending_approvals: int


class DashboardComparison(BaseModel):
    resolved_in_range: int | None
    created_in_range: int | None


class DailyActivityPoint(BaseModel):
    date: date
    created: int
    started: int
    resolved: int


class IssueDistributionItem(BaseModel):
    issue_type: str
    count: int


class DashboardActivityItem(BaseModel):
    id: str
    event_type: str
    occurred_at: datetime
    ticket_id: UUID
    display_key: str
    title: str
    actor_name: str | None


class DashboardTicketItem(BaseModel):
    id: UUID
    display_key: str
    title: str
    issue_type: str
    severity: str
    status: str
    requester_name: str
    created_at: datetime
    updated_at: datetime


class DashboardServiceItem(BaseModel):
    service_id: str
    status: str
    message: str
    updated_at: datetime


class DashboardResponse(BaseModel):
    range_days: int
    generated_at: datetime
    scope: Literal["personal", "department", "global"]
    metrics: DashboardMetrics
    comparison: DashboardComparison
    daily_activity: list[DailyActivityPoint]
    issue_distribution: list[IssueDistributionItem]
    recent_activity: list[DashboardActivityItem]
    attention_tickets: list[DashboardTicketItem]
    services: list[DashboardServiceItem]


def _scope_statement(statement: Select[Any], principal: CurrentPrincipal) -> Select[Any]:
    if principal.role is UserRole.EMPLOYEE:
        return statement.where(Ticket.owner_id == principal.user_id)
    if principal.role is UserRole.IT:
        return statement.where(Ticket.department_id == principal.department_id)
    return statement


def _scope_name(principal: CurrentPrincipal) -> Literal["personal", "department", "global"]:
    if principal.role is UserRole.EMPLOYEE:
        return "personal"
    if principal.role is UserRole.IT:
        return "department"
    return "global"


def _in_window(value: datetime, start: datetime, end: datetime) -> bool:
    return start <= value < end


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    range_days: Annotated[int, Query()] = 7,
) -> DashboardResponse:
    if range_days not in {7, 30}:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_dashboard_range", "message": "range_days must be 7 or 30"},
        )
    now = datetime.now(UTC)
    today = now.date()
    current_start = datetime.combine(
        today - timedelta(days=range_days - 1), datetime.min.time(), tzinfo=UTC
    )
    previous_start = current_start - timedelta(days=range_days)

    ticket_statement = _scope_statement(
        select(Ticket, User.display_name)
        .join(User, User.id == Ticket.owner_id)
        .order_by(Ticket.updated_at.desc(), Ticket.id.desc()),
        principal,
    )
    ticket_rows = list((await session.execute(ticket_statement)).all())
    tickets = [row[0] for row in ticket_rows]
    requester_names = {ticket.id: display_name for ticket, display_name in ticket_rows}

    event_statement = _scope_statement(
        select(TicketEvent, Ticket, User.display_name)
        .join(Ticket, Ticket.id == TicketEvent.ticket_id)
        .outerjoin(User, User.id == TicketEvent.actor_id)
        .where(TicketEvent.created_at >= previous_start)
        .order_by(TicketEvent.created_at.desc(), TicketEvent.id.desc()),
        principal,
    )
    event_rows = list((await session.execute(event_statement)).all())

    approval_statement = (
        select(ApprovalRequest.id)
        .join(User, User.id == ApprovalRequest.owner_id)
        .where(ApprovalRequest.status == "pending")
    )
    if principal.role is UserRole.EMPLOYEE:
        approval_statement = approval_statement.where(ApprovalRequest.owner_id == principal.user_id)
    elif principal.role is UserRole.IT:
        approval_statement = approval_statement.where(User.department_id == principal.department_id)
    pending_approvals = len(list((await session.scalars(approval_statement)).all()))

    event_types_by_ticket: dict[UUID, set[str]] = {}
    resolved_at: dict[UUID, datetime] = {}
    for event, ticket, _ in event_rows:
        event_types_by_ticket.setdefault(ticket.id, set()).add(event.type)
        if event.type == "ticket.resolved":
            resolved_at[ticket.id] = max(
                resolved_at.get(ticket.id, event.created_at), event.created_at
            )
    for ticket in tickets:
        if ticket.status == "resolved" and ticket.id not in resolved_at:
            resolved_at[ticket.id] = ticket.updated_at

    current_resolved = sum(
        _in_window(timestamp, current_start, now + timedelta(microseconds=1))
        for timestamp in resolved_at.values()
    )
    previous_resolved = sum(
        _in_window(timestamp, previous_start, current_start) for timestamp in resolved_at.values()
    )
    current_created = sum(ticket.created_at >= current_start for ticket in tickets)
    previous_created = sum(
        _in_window(ticket.created_at, previous_start, current_start) for ticket in tickets
    )

    day_buckets = {
        today - timedelta(days=offset): {"created": 0, "started": 0, "resolved": 0}
        for offset in range(range_days)
    }
    for ticket in tickets:
        if ticket.created_at.date() in day_buckets:
            day_buckets[ticket.created_at.date()]["created"] += 1
    for event, _ticket, _ in event_rows:
        event_day = event.created_at.date()
        if event_day not in day_buckets:
            continue
        if event.type == "ticket.in_progress":
            day_buckets[event_day]["started"] += 1
        elif event.type == "ticket.resolved":
            day_buckets[event_day]["resolved"] += 1
    for ticket in tickets:
        known_types = event_types_by_ticket.get(ticket.id, set())
        if ticket.updated_at.date() not in day_buckets:
            continue
        if ticket.status == "in_progress" and "ticket.in_progress" not in known_types:
            day_buckets[ticket.updated_at.date()]["started"] += 1
        if ticket.status == "resolved" and "ticket.resolved" not in known_types:
            day_buckets[ticket.updated_at.date()]["resolved"] += 1

    issue_counts = Counter(ticket.issue_type for ticket in tickets)
    attention = sorted(
        (ticket for ticket in tickets if ticket.status != "resolved"),
        key=lambda ticket: (
            {"high": 0, "normal": 1, "low": 2}.get(ticket.severity, 3),
            ticket.created_at,
        ),
    )[:5]

    activities: list[DashboardActivityItem] = [
        DashboardActivityItem(
            id=str(event.id),
            event_type=event.type,
            occurred_at=event.created_at,
            ticket_id=ticket.id,
            display_key=ticket.display_key,
            title=ticket.title,
            actor_name=actor_name,
        )
        for event, ticket, actor_name in event_rows[:20]
    ]
    for ticket in tickets:
        known_types = event_types_by_ticket.get(ticket.id, set())
        if "ticket.created" not in known_types:
            activities.append(
                DashboardActivityItem(
                    id=f"ticket-created:{ticket.id}",
                    event_type="ticket.created",
                    occurred_at=ticket.created_at,
                    ticket_id=ticket.id,
                    display_key=ticket.display_key,
                    title=ticket.title,
                    actor_name=requester_names[ticket.id],
                )
            )
        current_event = f"ticket.{ticket.status}"
        if ticket.status != "open" and current_event not in known_types:
            activities.append(
                DashboardActivityItem(
                    id=f"ticket-status:{ticket.id}:{ticket.status}",
                    event_type=current_event,
                    occurred_at=ticket.updated_at,
                    ticket_id=ticket.id,
                    display_key=ticket.display_key,
                    title=ticket.title,
                    actor_name=None,
                )
            )
    activities.sort(key=lambda item: item.occurred_at, reverse=True)

    services = list(
        (await session.scalars(select(ServiceState).order_by(ServiceState.service_id.asc()))).all()
    )
    return DashboardResponse(
        range_days=range_days,
        generated_at=now,
        scope=_scope_name(principal),
        metrics=DashboardMetrics(
            open=sum(ticket.status == "open" for ticket in tickets),
            in_progress=sum(ticket.status == "in_progress" for ticket in tickets),
            high_priority_unresolved=sum(
                ticket.severity == "high" and ticket.status != "resolved" for ticket in tickets
            ),
            resolved_in_range=current_resolved,
            pending_approvals=pending_approvals,
        ),
        comparison=DashboardComparison(
            resolved_in_range=current_resolved - previous_resolved,
            created_in_range=current_created - previous_created,
        ),
        daily_activity=[
            DailyActivityPoint(date=day, **day_buckets[day]) for day in sorted(day_buckets)
        ],
        issue_distribution=[
            IssueDistributionItem(issue_type=issue_type, count=issue_counts.get(issue_type, 0))
            for issue_type in ("gitlab", "vpn", "docker", "other")
        ],
        recent_activity=activities[:6],
        attention_tickets=[
            DashboardTicketItem(
                id=ticket.id,
                display_key=ticket.display_key,
                title=ticket.title,
                issue_type=ticket.issue_type,
                severity=ticket.severity,
                status=ticket.status,
                requester_name=requester_names[ticket.id],
                created_at=ticket.created_at,
                updated_at=ticket.updated_at,
            )
            for ticket in attention
        ],
        services=[
            DashboardServiceItem(
                service_id=service.service_id,
                status=service.status,
                message=service.message,
                updated_at=service.updated_at,
            )
            for service in services
        ],
    )
