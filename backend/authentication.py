"""Authentication and user management for Internal Company Knowledge Assistant.

Provides secure password hashing (using bcrypt with PBKDF2-HMAC-SHA256 fallback),
user registration, authentication, and role assignment.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.database import get_current_timestamp, get_db_connection

# Try importing bcrypt, fallback to hashlib if unavailable
try:
    import bcrypt

    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False


def hash_password(password: str) -> str:
    """Hash a plaintext password securely.

    Args:
        password: Raw user password.

    Returns:
        str: Formatted password hash string with algorithm prefix.
    """
    if not password:
        raise ValueError("Password cannot be empty.")

    if HAS_BCRYPT:
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return f"bcrypt${hashed.decode('utf-8')}"
    else:
        # PBKDF2-HMAC-SHA256 standard fallback
        salt = secrets.token_hex(16)
        iterations = 100_000
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return f"pbkdf2_sha256${iterations}${salt}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a raw password against the stored hash.

    Args:
        password: Raw user password.
        stored_hash: Stored hash from database.

    Returns:
        bool: True if password matches, False otherwise.
    """
    if not password or not stored_hash:
        return False

    try:
        parts = stored_hash.split("$")
        algo = parts[0]

        if algo == "bcrypt" and HAS_BCRYPT:
            bcrypt_hash = "$".join(parts[1:]).encode("utf-8")
            return bcrypt.checkpw(password.encode("utf-8"), bcrypt_hash)
        elif algo == "pbkdf2_sha256":
            iterations = int(parts[1])
            salt = parts[2]
            expected_key_hex = parts[3]
            calculated_key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            )
            return hmac.compare_digest(calculated_key.hex(), expected_key_hex)
        else:
            return False
    except Exception:
        return False


def create_user(
    username: str,
    password: str,
    full_name: str,
    role: str = "Employee",
    group_ids: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new user account with secure credentials.

    Args:
        username: Unique username.
        password: Raw password (min 6 chars).
        full_name: Display name.
        role: User role ('Administrator', 'Employee', 'Reviewer').
        group_ids: List of access_group IDs to join.
        db_path: Optional database path.

    Returns:
        Dict[str, Any]: Dictionary representation of created user (excluding password).
    """
    username = username.strip().lower()
    full_name = full_name.strip()

    if not username:
        raise ValueError("Username is required.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if role not in ("Administrator", "Employee", "Reviewer"):
        raise ValueError(f"Invalid role: {role}")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    pwd_hash = hash_password(password)
    now = get_current_timestamp()

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (user_id, username, password_hash, full_name, role, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'Active', ?);
            """,
            (user_id, username, pwd_hash, full_name, role, now),
        )

        # Default group is General
        assigned_groups = set(group_ids or [])
        assigned_groups.add("grp_general")

        for gid in assigned_groups:
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_groups (user_id, group_id)
                VALUES (?, ?);
                """,
                (user_id, gid),
            )

    return {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "role": role,
        "status": "Active",
        "created_at": now,
        "groups": list(assigned_groups),
    }


def authenticate_user(
    username: str,
    password: str,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Authenticate a user by username and password.

    Args:
        username: Username to authenticate.
        password: Raw password.
        db_path: Optional database path.

    Returns:
        Optional[Dict[str, Any]]: User record dictionary if successful, None if failed.
    """
    cleaned_username = username.strip().lower()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, username, password_hash, full_name, role, status, created_at
            FROM users
            WHERE username = ?;
            """,
            (cleaned_username,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        if row["status"] != "Active":
            return None

        if not verify_password(password, row["password_hash"]):
            return None

        # Fetch groups
        cursor.execute(
            """
            SELECT g.group_id, g.group_name
            FROM user_groups ug
            JOIN access_groups g ON ug.group_id = g.group_id
            WHERE ug.user_id = ?;
            """,
            (row["user_id"],),
        )
        groups = [dict(g) for g in cursor.fetchall()]

        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "full_name": row["full_name"],
            "role": row["role"],
            "status": row["status"],
            "created_at": row["created_at"],
            "groups": groups,
            "group_ids": [g["group_id"] for g in groups],
        }


def get_user_by_id(user_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch user details by user ID."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, username, full_name, role, status, created_at
            FROM users
            WHERE user_id = ?;
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute(
            """
            SELECT g.group_id, g.group_name
            FROM user_groups ug
            JOIN access_groups g ON ug.group_id = g.group_id
            WHERE ug.user_id = ?;
            """,
            (user_id,),
        )
        groups = [dict(g) for g in cursor.fetchall()]

        user_dict = dict(row)
        user_dict["groups"] = groups
        user_dict["group_ids"] = [g["group_id"] for g in groups]
        return user_dict


def list_users(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all registered users with their assigned groups."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, username, full_name, role, status, created_at
            FROM users
            ORDER BY created_at ASC;
            """
        )
        users = []
        for row in cursor.fetchall():
            u = dict(row)
            cursor.execute(
                """
                SELECT g.group_id, g.group_name
                FROM user_groups ug
                JOIN access_groups g ON ug.group_id = g.group_id
                WHERE ug.user_id = ?;
                """,
                (u["user_id"],),
            )
            groups = [dict(g) for g in cursor.fetchall()]
            u["groups"] = groups
            u["group_ids"] = [g["group_id"] for g in groups]
            users.append(u)
        return users


def update_user_role(
    user_id: str,
    new_role: str,
    admin_user_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Update a user's role. Requires that the executing user is an Administrator."""
    if new_role not in ("Administrator", "Employee", "Reviewer"):
        raise ValueError(f"Invalid role: {new_role}")

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        # Verify executor is admin
        cursor.execute("SELECT role FROM users WHERE user_id = ?;", (admin_user_id,))
        exec_row = cursor.fetchone()
        if not exec_row or exec_row["role"] != "Administrator":
            raise PermissionError("Only an Administrator can update user roles.")

        cursor.execute(
            "UPDATE users SET role = ? WHERE user_id = ?;",
            (new_role, user_id),
        )
        return cursor.rowcount > 0


def update_user_status(
    user_id: str,
    new_status: str,
    admin_user_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Update user status ('Active' or 'Disabled'). Admin only."""
    if new_status not in ("Active", "Disabled"):
        raise ValueError(f"Invalid status: {new_status}")

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = ?;", (admin_user_id,))
        exec_row = cursor.fetchone()
        if not exec_row or exec_row["role"] != "Administrator":
            raise PermissionError("Only an Administrator can update user status.")

        cursor.execute(
            "UPDATE users SET status = ? WHERE user_id = ?;",
            (new_status, user_id),
        )
        return cursor.rowcount > 0


def assign_user_groups(
    user_id: str,
    group_ids: List[str],
    admin_user_id: str,
    db_path: Optional[str] = None,
) -> None:
    """Assign access groups to a user. Admin only."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE user_id = ?;", (admin_user_id,))
        exec_row = cursor.fetchone()
        if not exec_row or exec_row["role"] != "Administrator":
            raise PermissionError("Only an Administrator can assign user groups.")

        cursor.execute("DELETE FROM user_groups WHERE user_id = ?;", (user_id,))
        # Always ensure grp_general is included
        groups_to_add = set(group_ids)
        groups_to_add.add("grp_general")

        for gid in groups_to_add:
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_groups (user_id, group_id)
                VALUES (?, ?);
                """,
                (user_id, gid),
            )


def initialize_admin_if_empty(default_password: str = "Admin@12345", db_path: Optional[str] = None) -> str:
    """Ensure at least one administrator account exists upon initial startup."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE role = 'Administrator';")
        existing_admin = cursor.fetchone()
        if existing_admin:
            return existing_admin["user_id"]

    admin = create_user(
        username="admin",
        password=default_password,
        full_name="Default System Administrator",
        role="Administrator",
        group_ids=["grp_general", "grp_hr", "grp_eng", "grp_finance", "grp_exec"],
        db_path=db_path,
    )
    return admin["user_id"]
