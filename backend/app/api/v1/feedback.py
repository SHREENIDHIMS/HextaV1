"""Feedback endpoints for response quality signals."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel

from app.auth.cookies import require_csrf
from app.dependencies import require_auth
from app.db.postgres.session import acquire

router = APIRouter()


class FeedbackRequest(BaseModel):
    response_id: str
    rating: int
    comment: str | None = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    request: FeedbackRequest,
    _csrf: None = Depends(require_csrf),
    user: dict = Depends(require_auth),
) -> dict:
    """Submit feedback (thumbs up/down) on a response."""
    if request.rating not in (-1, 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be 1 or -1",
        )

    with acquire() as conn:
        with conn.cursor() as cur:
            # Reject feedback for response_ids that never existed (spam/garbage
            # data) instead of storing arbitrary strings (B7).
            cur.execute(
                "SELECT 1 FROM audit_log WHERE response_id = %s LIMIT 1",
                (request.response_id,),
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Unknown response_id — no such response was served",
                )

            cur.execute(
                "INSERT INTO feedback (user_id, response_id, rating, comment) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (
                    user["id"],
                    request.response_id,
                    request.rating,
                    request.comment,
                ),
            )
            feedback_id = cur.fetchone()["id"]
        conn.commit()

    return {
        "message": "Feedback recorded",
        "feedback_id": feedback_id,
    }
