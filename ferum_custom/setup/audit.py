from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import now_datetime


@dataclass(frozen=True)
class AuditIssue:
	code: str
	severity: str  # P0/P1/P2/P3
	message: str
	context: dict[str, Any] | None = None


def _safe_exc(exc: BaseException) -> str:
	msg = str(exc) or repr(exc)
	return f"{type(exc).__name__}: {msg}"


def _collect_hook_targets() -> set[str]:
	"""Collect active dotted targets from ferum_custom.hooks.

	Only considers *active* hook values (not commented examples in hooks.py).
	"""
	hooks = importlib.import_module("ferum_custom.hooks")

	paths: set[str] = set()

	def collect(obj: Any) -> None:
		if obj is None:
			return
		if isinstance(obj, str):
			if obj.startswith("ferum_custom.") and obj.count(".") >= 2:
				paths.add(obj)
			return
		if isinstance(obj, dict):
			for k, v in obj.items():
				collect(k)
				collect(v)
			return
		if isinstance(obj, (list, tuple, set)):
			for x in obj:
				collect(x)

	for attr in (
		"permission_query_conditions",
		"has_permission",
		"override_doctype_class",
		"doc_events",
		"scheduler_events",
		"override_whitelisted_methods",
		"before_tests",
		"after_job",
	):
		collect(getattr(hooks, attr, None))

	return paths


def check_hooks_imports() -> list[AuditIssue]:
	issues: list[AuditIssue] = []
	for path in sorted(_collect_hook_targets()):
		module = path.rsplit(".", 1)[0]
		try:
			importlib.import_module(module)
		except Exception as exc:
			issues.append(
				AuditIssue(
					code="hooks.import_failed",
					severity="P0",
					message=f"Failed to import hook target module: {module}",
					context={"path": path, "error": _safe_exc(exc)},
				)
			)
	return issues


def check_module_doctypes_meta(*, module: str = "Ferum Custom") -> list[AuditIssue]:
	issues: list[AuditIssue] = []
	if not frappe.db.exists("DocType", "DocType"):
		return issues

	doctypes = frappe.get_all("DocType", filters={"module": module, "custom": 0}, pluck="name")
	for dt in sorted(doctypes):
		try:
			frappe.get_meta(dt)
		except Exception as exc:
			issues.append(
				AuditIssue(
					code="doctype.meta_failed",
					severity="P0",
					message=f"Failed to load doctype meta: {dt}",
					context={"doctype": dt, "error": _safe_exc(exc)},
				)
			)
	return issues


def check_module_query_reports(*, module: str = "Ferum Custom") -> list[AuditIssue]:
	issues: list[AuditIssue] = []
	if not frappe.db.exists("DocType", "Report"):
		return issues

	reports = frappe.get_all("Report", filters={"module": module}, pluck="name")
	for name in sorted(reports):
		try:
			doc = frappe.get_doc("Report", name)
			if getattr(doc, "report_type", None) != "Query Report":
				continue
			# UI sends empty filters dict when no filters selected.
			frappe.desk.query_report.run(name, filters="{}", are_default_filters=True)
		except Exception as exc:
			issues.append(
				AuditIssue(
					code="report.query_failed",
					severity="P0",
					message=f"Query Report failed with empty filters: {name}",
					context={"report": name, "error": _safe_exc(exc)},
				)
			)
	return issues


def check_workflows() -> list[AuditIssue]:
	issues: list[AuditIssue] = []
	if not frappe.db.exists("DocType", "Workflow"):
		return issues

	for wf in frappe.get_all(
		"Workflow",
		fields=["name", "document_type", "is_active"],
		limit=2000,
	):
		dt = str(wf.get("document_type") or "").strip()
		if dt and not frappe.db.exists("DocType", dt):
			issues.append(
				AuditIssue(
					code="workflow.missing_doctype",
					severity="P0",
					message=f"Workflow references missing DocType: {dt}",
					context={"workflow": wf.get("name"), "document_type": dt},
				)
			)
	return issues


def check_workspaces_objects_shortcuts(*, module: str = "Ferum Custom") -> list[AuditIssue]:
	"""Detect common UX regressions: 'Объекты' shortcuts pointing to Asset/Service Object."""
	issues: list[AuditIssue] = []
	if not frappe.db.exists("DocType", "Workspace") or not frappe.db.exists("DocType", "Workspace Shortcut"):
		return issues

	rows = frappe.get_all(
		"Workspace Shortcut",
		filters={"parenttype": "Workspace"},
		fields=["parent", "label", "link_to", "doc_view", "type", "url"],
		limit=5000,
	)

	ferum_workspaces = set(frappe.get_all("Workspace", filters={"module": module}, pluck="name", limit=2000))
	if not ferum_workspaces:
		return issues

	per_ws: dict[str, list[dict[str, Any]]] = {}
	for r in rows:
		ws = str(r.get("parent") or "").strip()
		if ws not in ferum_workspaces:
			continue
		label = str(r.get("label") or "").strip()
		url = str(r.get("url") or "").strip()
		if "объект" not in label.lower():
			continue
		per_ws.setdefault(ws, []).append({"label": label, "url": url})

	for ws, links in sorted(per_ws.items()):
		unique = {(l["label"], l["url"]) for l in links}
		urls = {u for _, u in unique if u}
		if len(urls) > 1:
			issues.append(
				AuditIssue(
					code="workspace.objects.inconsistent_urls",
					severity="P1",
					message=f"Workspace has multiple 'Объекты' URLs: {ws}",
					context={"workspace": ws, "urls": sorted(urls)},
				)
			)

		for l in unique:
			_label, url = l
			if not url:
				continue
				if "/app/asset" in url or "/app/service-object" in url:
					issues.append(
						AuditIssue(
							code="workspace.objects.legacy_route",
							severity="P1",
							message=f"Workspace 'Объекты' points to legacy route: {ws}",
							context={"workspace": ws, "label": _label, "url": url},
						)
					)

	return issues


def check_system_health() -> tuple[dict[str, Any] | None, list[AuditIssue]]:
	issues: list[AuditIssue] = []
	try:
		from ferum_custom.api.system_health import status

		# Bench execute context might not have a session user; use Administrator for checks.
		frappe.set_user("Administrator")
		out = status()
		return out, issues
	except Exception as exc:
		issues.append(
			AuditIssue(
				code="system_health.failed",
				severity="P1",
				message="Failed to compute system health status",
				context={"error": _safe_exc(exc)},
			)
		)
		return None, issues


def run(*, write_report: int | bool = 1) -> dict[str, Any]:
	"""Run a read-only runtime audit for the current site.

	Designed to be executed via:
	- `bench --site <site> execute ferum_custom.setup.audit.run`

	Never prints or returns secret values.
	"""
	generated_at = now_datetime().isoformat()
	site = str(getattr(frappe.local, "site", "") or "").strip() or None

	issues: list[AuditIssue] = []
	issues += check_hooks_imports()
	issues += check_module_doctypes_meta()
	issues += check_module_query_reports()
	issues += check_workflows()
	issues += check_workspaces_objects_shortcuts()
	health, health_issues = check_system_health()
	issues += health_issues

	ok = not any(i.severity in {"P0", "P1"} for i in issues)

	out: dict[str, Any] = {
		"ok": ok,
		"generated_at": generated_at,
		"site": site,
		"issues": [asdict(i) for i in issues],
		"system_health": health,
	}

	if bool(int(write_report)):
		# frappe.get_app_path("ferum_custom") -> .../apps/ferum_custom/ferum_custom
		root = Path(frappe.get_app_path("ferum_custom")).resolve().parent  # .../apps/ferum_custom
		audit_dir = root / "docs" / "audit"
		audit_dir.mkdir(parents=True, exist_ok=True)
		safe_site = (site or "unknown").replace("/", "_")
		path = audit_dir / f"{generated_at[:10]}_runtime_audit_{safe_site}.json"
		path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

	return out
