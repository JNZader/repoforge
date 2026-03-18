"""History routes — list, detail, and delete generations.

Endpoints:
    GET    /api/history      — List user's generations with pagination and filters
    GET    /api/history/{id} — Get full generation detail (optionally with events)
    DELETE /api/history/{id} — Delete a generation and clean up its artifact
"""

import math
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.middleware.auth import CurrentUser
from app.middleware.rate_limit import API_LIMIT, get_user_id_key, limiter
from app.models import Generation, get_db
from app.models.schemas import (
    GenerationDetail,
    GenerationDetailWithEvents,
    GenerationListResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/history", tags=["history"])


# ---------- GET /api/history ----------


@router.get("", response_model=GenerationListResponse)
@limiter.limit(API_LIMIT, key_func=get_user_id_key)
async def list_generations(
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    mode: str | None = Query(default=None, description="Filter by mode (docs, skills, both)"),
    repo_name: str | None = Query(default=None, description="Search by repo name"),
    sort: str = Query(
        default="created_at_desc",
        description="Sort order: created_at_desc, created_at_asc",
    ),
) -> GenerationListResponse:
    """List the current user's generations with pagination and optional filters.

    Supports filtering by status, mode, and repo name search.
    Results are sorted by created_at descending by default.
    """
    user_id = current_user["sub"]

    # Base query scoped to current user
    base_query = select(Generation).where(Generation.user_id == user_id)

    # Apply filters
    if status_filter:
        base_query = base_query.where(Generation.status == status_filter)
    if mode:
        base_query = base_query.where(Generation.mode == mode)
    if repo_name:
        base_query = base_query.where(Generation.repo_name.ilike(f"%{repo_name}%"))

    # Count total matching records
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    if sort == "created_at_asc":
        base_query = base_query.order_by(Generation.created_at.asc())
    else:
        base_query = base_query.order_by(Generation.created_at.desc())

    # Apply pagination
    offset = (page - 1) * per_page
    base_query = base_query.offset(offset).limit(per_page)

    result = await db.execute(base_query)
    generations = result.scalars().all()

    pages = max(1, math.ceil(total / per_page))

    return GenerationListResponse(
        items=[GenerationDetail.model_validate(g) for g in generations],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


# ---------- GET /api/history/{generation_id} ----------


@router.get("/{generation_id}")
@limiter.limit(API_LIMIT, key_func=get_user_id_key)
async def get_generation_detail(
    request: Request,
    generation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    expand: str | None = Query(default=None, description="Expand related data: 'events'"),
) -> GenerationDetailWithEvents | GenerationDetail:
    """Get full generation detail, optionally including generation events.

    Use ``?expand=events`` to include the event log for replay/debugging.
    """
    user_id = current_user["sub"]

    query = select(Generation).where(
        Generation.id == generation_id,
        Generation.user_id == user_id,
    )

    # Eagerly load events if requested
    if expand == "events":
        query = query.options(selectinload(Generation.events))

    result = await db.execute(query)
    generation = result.scalar_one_or_none()

    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Generation not found."},
        )

    if expand == "events":
        return GenerationDetailWithEvents.model_validate(generation)

    return GenerationDetail.model_validate(generation)


# ---------- DELETE /api/history/{generation_id} ----------


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(API_LIMIT, key_func=get_user_id_key)
async def delete_generation(
    request: Request,
    generation_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a generation record and clean up its ZIP artifact file.

    Only the owning user can delete their generations.
    Cascade deletes associated generation_events via FK constraint.
    """
    user_id = current_user["sub"]

    result = await db.execute(
        select(Generation).where(
            Generation.id == generation_id,
            Generation.user_id == user_id,
        )
    )
    generation = result.scalar_one_or_none()

    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Generation not found."},
        )

    # Clean up ZIP artifact if it exists
    if generation.artifact_path:
        artifact = Path(generation.artifact_path)
        if artifact.exists():
            try:
                artifact.unlink()
                logger.info(
                    "artifact_deleted",
                    generation_id=generation_id,
                    path=str(artifact),
                )
            except OSError:
                logger.warning(
                    "artifact_delete_failed",
                    generation_id=generation_id,
                    path=str(artifact),
                )

    await db.delete(generation)
    await db.commit()

    logger.info("generation_deleted", generation_id=generation_id, user_id=user_id)
