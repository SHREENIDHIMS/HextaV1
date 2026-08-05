"""Permission helpers for role-based access control.

Defines the action/resource matrix used by admin endpoints.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.auth.rbac import ADMIN_ROLES


def require_role(user: dict | None, role: str) -> None:
    """Raise 403 if the user's role doesn't meet the minimum requirement.

    Role hierarchy (higher = more permissive):
    super_admin > admin > loan_officer > underwriter > compliance
    """
    hierarchy = ["compliance", "underwriter", "loan_officer", "admin", "super_admin"]
    user_role = user.get("role", "loan_officer") if user else "loan_officer"

    # Fail-closed: an unknown user or required role is denied, never granted.
    if user_role not in hierarchy:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown role '{user_role}' cannot perform this action",
        )
    if role not in hierarchy:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown required role '{role}'",
        )

    user_idx = hierarchy.index(user_role)
    required_idx = hierarchy.index(role)

    if user_idx < required_idx:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user_role}' cannot perform this action (requires '{role}')",
        )
