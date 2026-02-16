# Hook skeletons (Frappe / ERPNext)

Generated: 2026-02-16

These are minimal, copy-paste-friendly templates matching common hook patterns used in `ferum_custom`.

## 1) DocType event handler (`doc_events`)

Example: validate invariants on update.

```python
from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


def validate_my_doctype(doc: Document, method: str | None = None) -> None:
	_unused_method = method

	# Guard for schema drift / optional fields
	if not doc.meta.has_field("status"):
		return

	status = (getattr(doc, "status", None) or "").strip()
	if status not in {"Open", "Closed"}:
		frappe.throw(_("Invalid status"))
```

`hooks.py`:

```python
doc_events = {
	"My DocType": {
		"validate": "ferum_custom.services.my_module.validate_my_doctype",
	}
}
```

## 2) Scheduler task (`scheduler_events`)

Example: daily job with best-effort behavior and bounded work.

```python
from __future__ import annotations

import frappe


def run_daily_job() -> None:
	# Never assume all DocTypes exist (multi-app installs).
	if not frappe.db.exists("DocType", "My DocType"):
		return

	# Bounded scan. Prefer indexes and filters.
	names = frappe.get_all("My DocType", filters={"status": "Open"}, pluck="name", limit_page_length=5000)
	for name in names:
		# idempotent operations only
		pass
```

`hooks.py`:

```python
scheduler_events = {
	"daily": ["ferum_custom.services.my_jobs.run_daily_job"],
}
```

## 3) Permission hooks (`permission_query_conditions` + `has_permission`)

### 3.1 `permission_query_conditions` (SQL fragment)

Goal: restrict list/link queries.

```python
from __future__ import annotations

import frappe


def my_doctype_permission_query_conditions(user: str) -> str:
	user = str(user or "").strip()
	if not user or user == "Administrator":
		return ""

	# Always escape values (avoid SQL injection).
	allowed_company = frappe.db.escape("Ferum Demo")
	return f"`tabMy DocType`.`company` = {allowed_company}"
```

`hooks.py`:

```python
permission_query_conditions = {
	"My DocType": "ferum_custom.security.my_permissions.my_doctype_permission_query_conditions",
}
```

### 3.2 `has_permission` (per document)

Goal: final allow/deny per doc. Return `None` to fall back to standard permission logic.

```python
from __future__ import annotations

import frappe


def my_doctype_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool | None:
	user = user or frappe.session.user
	if not user or user == "Administrator":
		return None
	if not doc:
		return False

	# Deny some role
	if "Client" in frappe.get_roles(user):
		return False

	# Allow: fall back to standard checks
	return None
```

`hooks.py`:

```python
has_permission = {
	"My DocType": "ferum_custom.security.my_permissions.my_doctype_has_permission",
}
```

## 4) Whitelisted method override (`override_whitelisted_methods`)

Goal: swap an RPC endpoint implementation without forking Frappe core.

```python
from __future__ import annotations

import frappe


@frappe.whitelist()
@frappe.read_only()
def run(*args, **kwargs):
	# Keep the signature compatible with the original method.
	# Do minimal transformation, then call core or replacement logic.
	return {"ok": True}
```

`hooks.py`:

```python
override_whitelisted_methods = {
	"frappe.desk.query_report.run": "ferum_custom.overrides.query_report.run",
}
```
