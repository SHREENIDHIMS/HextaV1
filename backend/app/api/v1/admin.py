"""Admin endpoints for user management."""

from __future__ import annotations

import logging

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.audit.audit_logger import AuditLogEntry, log_query
from app.auth.permissions import require_role
from app.dependencies import require_auth
from app.db.postgres.session import acquire

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/users")
async def list_users(user: dict = Depends(require_auth)) -> dict:
    """List all users. Requires admin role."""
    require_role(user, "admin")

    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, full_name, role, department, allowed_departments, "
                "is_active, created_at FROM users ORDER BY id"
            )
            users = [dict(row) for row in cur.fetchall()]

    return {"users": users}


class UserPatchRequest(BaseModel):
    is_active: bool


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: int,
    body: UserPatchRequest,
    admin: dict = Depends(require_auth),
) -> dict:
    """Toggle a user's active status. Requires admin role.

    Admins cannot deactivate themselves.
    """
    require_role(admin, "admin")

    if int(admin["id"]) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own active status",
        )

    with acquire() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                "UPDATE users SET is_active = %s WHERE id = %s RETURNING id, email, is_active",
                (body.is_active, user_id),
            )
            updated = cur.fetchone()
        conn.commit()

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Every admin mutation is audit-logged (B9) — who changed what, when.
    log_query(AuditLogEntry(
        user_id=admin["id"],
        query=(
            f"admin.patch_user user_id={user_id} "
            f"email={updated['email']} is_active={updated['is_active']}"
        ),
        outcome="admin.action",
        response_id="",
    ))

    return {
        "id": updated["id"],
        "email": updated["email"],
        "is_active": updated["is_active"],
    }
