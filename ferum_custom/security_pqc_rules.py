from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe


def _is_client_user(user: str) -> bool:
    return user != "Administrator" and frappe.has_role("Client", user)


def project_permission_query_conditions(user: str, doctype: str | None = None) -> str:
    """Permission Query Conditions for `Project`.

    The Desk "Projects" workspace triggers count/list queries on `Project`.
    Historically, this site referenced `ferum_custom.security_pqc_rules.*` from
    `Project.permission_query_conditions`. If that module is missing, Desk breaks.

    Policy:
    - Client users are not allowed to see `Project` in Desk → deny.
    - Internal users: no extra filtering (standard ERPNext permissions apply).
    """
    _ = doctype
    if _is_client_user(user):
        return "1=0"
    return ""


def permission_query_conditions(user: str, doctype: str | None = None) -> str:
    if doctype == "Project":
        return project_permission_query_conditions(user, doctype=doctype)
    return ""


# Compatibility aliases for older configurations
project_pqc = project_permission_query_conditions
get_project_permission_query_conditions = project_permission_query_conditions


def __getattr__(name: str) -> Any:
    """Return a safe fallback for legacy configured function names.

    Frappe resolves doctype permission_query_conditions via dotted paths stored in DB.
    If the configured attribute name differs, we still prefer returning a safe default
    rather than crashing Desk.
    """

    def _fallback(user: str, doctype: str | None = None) -> str:
        return permission_query_conditions(user, doctype=doctype)

    legacy_prefixes = ("pqc_",)
    legacy_suffixes = ("_permission_query_conditions", "_pqc")
    if name.startswith(legacy_prefixes) or name.endswith(legacy_suffixes):
        return _fallback
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
