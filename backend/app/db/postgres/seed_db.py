"""Seed the database with initial users for development."""

from __future__ import annotations

from app.auth.passwords import hash_password
from app.db.postgres.session import acquire


def seed_users() -> None:
    with acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM users"
            )
            count = cur.fetchone()["count"]
            if count > 0:
                return

            users = [
                {
                    "email": "admin@hexa.local",
                    "password_hash": hash_password("adminpass"),
                    "full_name": "Admin User",
                    "role": "super_admin",
                    "department": "general",
                    "allowed_departments": [],
                },
                {
                    "email": "officer@hexa.local",
                    "password_hash": hash_password("officerpass"),
                    "full_name": "Loan Officer",
                    "role": "loan_officer",
                    "department": "general",
                    "allowed_departments": ["compliance"],
                },
                {
                    "email": "underwriter@hexa.local",
                    "password_hash": hash_password("uwpass"),
                    "full_name": "Underwriter",
                    "role": "underwriter",
                    "department": "general",
                    "allowed_departments": [],
                },
                {
                    "email": "compliance@hexa.local",
                    "password_hash": hash_password("compliancepass"),
                    "full_name": "Compliance Officer",
                    "role": "compliance",
                    "department": "compliance",
                    "allowed_departments": ["general"],
                },
            ]

            for u in users:
                cur.execute(
                    "INSERT INTO users (email, password_hash, full_name, role, department, allowed_departments) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
                    (u["email"], u["password_hash"], u["full_name"], u["role"], u["department"], u["allowed_departments"]),
                )
            conn.commit()


if __name__ == "__main__":
    seed_users()