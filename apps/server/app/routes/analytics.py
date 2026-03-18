"""Analytics routes — usage stats, model breakdown, top repos.

Endpoints:
    GET /api/analytics/summary — High-level generation stats for current user
    GET /api/analytics/usage   — Usage over time (for chart rendering)
    GET /api/analytics/models  — Model usage breakdown
    GET /api/analytics/repos   — Most generated repos (top 20)
"""

from datetime import date, timedelta

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import CurrentUser
from app.models import Generation, UsageStat, get_db
from app.models.schemas import (
    AnalyticsSummaryResponse,
    ModelUsageItem,
    ModelUsageResponse,
    RepoUsageItem,
    RepoUsageResponse,
    UsageDataPoint,
    UsageResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Map period strings to number of days
_PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90}


# ---------- GET /api/analytics/summary ----------


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_summary(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummaryResponse:
    """High-level generation statistics for the current user.

    Returns total counts by status, average duration, total tokens,
    success rate, and most-used model/provider.
    """
    user_id = current_user["sub"]

    # Aggregate counts by status
    status_query = select(
        func.count().label("total"),
        func.count().filter(Generation.status == "completed").label("completed"),
        func.count().filter(Generation.status == "failed").label("failed"),
        func.count().filter(Generation.status == "cancelled").label("cancelled"),
        func.avg(Generation.total_duration_ms).filter(
            Generation.status == "completed"
        ).label("avg_duration_ms"),
        func.coalesce(func.sum(Generation.total_tokens), 0).label("total_tokens"),
    ).where(Generation.user_id == user_id)

    result = await db.execute(status_query)
    row = result.one()

    total = row.total or 0
    completed = row.completed or 0
    success_rate = round(completed / total, 4) if total > 0 else 0.0

    # Most used model — extract from config JSONB
    model_query = (
        select(
            Generation.config.op("->>")("model").label("model_name"),
            func.count().label("cnt"),
        )
        .where(
            Generation.user_id == user_id,
            Generation.config.isnot(None),
        )
        .group_by("model_name")
        .order_by(desc("cnt"))
        .limit(1)
    )
    model_result = await db.execute(model_query)
    model_row = model_result.first()
    most_used_model = model_row.model_name if model_row else None

    # Most used provider — extract from config JSONB
    provider_query = (
        select(
            Generation.config.op("->>")("provider").label("provider_name"),
            func.count().label("cnt"),
        )
        .where(
            Generation.user_id == user_id,
            Generation.config.isnot(None),
        )
        .group_by("provider_name")
        .order_by(desc("cnt"))
        .limit(1)
    )
    provider_result = await db.execute(provider_query)
    provider_row = provider_result.first()
    most_used_provider = provider_row.provider_name if provider_row else None

    return AnalyticsSummaryResponse(
        total_generations=total,
        completed=completed,
        failed=row.failed or 0,
        cancelled=row.cancelled or 0,
        avg_duration_ms=round(float(row.avg_duration_ms), 2) if row.avg_duration_ms else None,
        total_tokens=row.total_tokens or 0,
        success_rate=success_rate,
        most_used_model=most_used_model,
        most_used_provider=most_used_provider,
    )


# ---------- GET /api/analytics/usage ----------


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    period: str = Query(
        default="30d",
        description="Time period: 7d, 30d, or 90d",
    ),
) -> UsageResponse:
    """Usage over time from the usage_stats table, suitable for chart rendering.

    Returns one data point per day within the given period.
    """
    user_id = current_user["sub"]
    days = _PERIOD_DAYS.get(period, 30)
    since = date.today() - timedelta(days=days)

    query = (
        select(
            UsageStat.date,
            UsageStat.generations_count,
            UsageStat.tokens_used,
        )
        .where(
            UsageStat.user_id == user_id,
            UsageStat.date >= since,
        )
        .order_by(UsageStat.date.asc())
    )

    result = await db.execute(query)
    rows = result.all()

    data = [
        UsageDataPoint(
            date=row.date,
            generations_count=row.generations_count,
            tokens_used=row.tokens_used,
        )
        for row in rows
    ]

    return UsageResponse(period=period, data=data)


# ---------- GET /api/analytics/models ----------


@router.get("/models", response_model=ModelUsageResponse)
async def get_model_usage(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ModelUsageResponse:
    """Model usage breakdown extracted from the generations config JSONB.

    Returns count, average duration, and total tokens per model.
    """
    user_id = current_user["sub"]

    model_col = Generation.config.op("->>")("model").label("model_name")

    query = (
        select(
            model_col,
            func.count().label("cnt"),
            func.avg(Generation.total_duration_ms).label("avg_dur"),
            func.coalesce(func.sum(Generation.total_tokens), 0).label("total_tok"),
        )
        .where(
            Generation.user_id == user_id,
            Generation.config.isnot(None),
        )
        .group_by("model_name")
        .order_by(desc("cnt"))
    )

    result = await db.execute(query)
    rows = result.all()

    items = [
        ModelUsageItem(
            model=row.model_name or "unknown",
            count=row.cnt,
            avg_duration_ms=round(float(row.avg_dur), 2) if row.avg_dur else None,
            total_tokens=row.total_tok or 0,
        )
        for row in rows
    ]

    return ModelUsageResponse(items=items)


# ---------- GET /api/analytics/repos ----------


@router.get("/repos", response_model=RepoUsageResponse)
async def get_repo_usage(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> RepoUsageResponse:
    """Most generated repos for the current user, top 20 by count."""
    user_id = current_user["sub"]

    query = (
        select(
            Generation.repo_name,
            func.count().label("cnt"),
            func.max(Generation.created_at).label("last_gen"),
        )
        .where(Generation.user_id == user_id)
        .group_by(Generation.repo_name)
        .order_by(desc("cnt"))
        .limit(20)
    )

    result = await db.execute(query)
    rows = result.all()

    items = [
        RepoUsageItem(
            repo_name=row.repo_name,
            count=row.cnt,
            last_generated=row.last_gen,
        )
        for row in rows
    ]

    return RepoUsageResponse(items=items)
