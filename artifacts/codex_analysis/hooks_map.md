# Codex analysis — hooks & runtime entrypoints (`ferum_custom/hooks.py`)

Generated: 2026-02-16

This document enumerates **active** hook configuration in `ferum_custom/hooks.py` and maps each dotted target to
its source file and intent.

Notes:

- Only uncommented / active values are treated as runtime-relevant.
- Some dotted paths exist in `hooks.py` as **commented examples**; they are not executed (but can confuse audits if
  scanned by regex).
- For a runtime import check, use: `bench --site <site> execute ferum_custom.setup.audit.run`.

## 1) Permission query conditions (`permission_query_conditions`)

Purpose: restrict list/link queries at SQL level for specific DocTypes (especially for portal/client use cases).

| DocType | Hook target | Source | Summary |
|---|---|---|---|
| `Contract` | `ferum_custom.security.portal_permissions.contract_permission_query_conditions` | `ferum_custom/security/portal_permissions.py` | For role `Client`, optionally requires `Contract.is_portal_visible=1` (if column exists). |
| `File` | `ferum_custom.security.file_permissions.file_permission_query_conditions` | `ferum_custom/security/file_permissions.py` | Adds SQL conditions **only** for Ferum Project documents (`attached_to_doctype='Project'` + `attached_to_field='ferum_project_documents'`). Limits to projects user can access; clients additionally limited by allowed doc types. |
| `Project Site` | `ferum_custom.security.project_site_permissions.project_site_permission_query_conditions` | `ferum_custom/security/project_site_permissions.py` | Restricts Project Site lists by `Project Site.project in allowed_projects` (uses `project_access.projects_for_user`). |
| `Service Logbook` | `ferum_custom.security.project_site_permissions.service_logbook_permission_query_conditions` | `ferum_custom/security/project_site_permissions.py` | Restricts Service Logbook list by Project access via Project Site. |
| `Service Log Entry` | `ferum_custom.security.project_site_permissions.service_log_entry_permission_query_conditions` | `ferum_custom/security/project_site_permissions.py` | Restricts Service Log Entry list by Project access via Project Site. |

## 2) Document permission checks (`has_permission`)

Purpose: final allow/deny decision per document. Used as a “belt-and-suspenders” layer for portal users and for legacy
DocTypes.

| DocType | Hook target | Source | Summary |
|---|---|---|---|
| `Sales Invoice` | `ferum_custom.security.portal_permissions.sales_invoice_has_permission` | `ferum_custom/security/portal_permissions.py` | Denies all access to role `Client` (financial docs). |
| `ServiceAct` | `ferum_custom.security.portal_permissions.service_act_has_permission` | `ferum_custom/security/portal_permissions.py` | Denies all access to role `Client`. |
| `Invoice` | `ferum_custom.security.portal_permissions.invoice_has_permission` | `ferum_custom/security/portal_permissions.py` | Denies all access to role `Client` (custom financial doc). |
| `ServiceProject` / `Service Project` | `ferum_custom.security.service_project_permissions.service_project_has_permission` | `ferum_custom/security/service_project_permissions.py` | Legacy model: hides for all non-admin users and denies mutations; clients denied. |
| `Service Object` | `ferum_custom.security.service_object_permissions.service_object_has_permission` | `ferum_custom/security/service_object_permissions.py` | Legacy model: hides for all non-admin users and denies mutations; clients denied. |
| `File` | `ferum_custom.security.file_permissions.file_has_permission` | `ferum_custom/security/file_permissions.py` | Restricts Ferum Project documents by Project access + upload roles; non-Ferum files return `None` to avoid breaking standard attachments. |
| `Project Site` | `ferum_custom.security.project_site_permissions.project_site_has_permission` | `ferum_custom/security/project_site_permissions.py` | Uses `user_has_project_access` when `doc.project` set; otherwise allows only global access users. |
| `Service Logbook` | `ferum_custom.security.project_site_permissions.service_logbook_has_permission` | `ferum_custom/security/project_site_permissions.py` | Resolves site → project and checks project access. |
| `Service Log Entry` | `ferum_custom.security.project_site_permissions.service_log_entry_has_permission` | `ferum_custom/security/project_site_permissions.py` | Resolves site (direct or via logbook) → project and checks project access. |

## 3) Doctype class override (`override_doctype_class`)

| DocType | Hook target | Source | Summary |
|---|---|---|---|
| `Email Account` | `ferum_custom.overrides.email_account.FerumEmailAccount` | `ferum_custom/overrides/email_account.py` | Hardens incoming account disable logic: coerces `description` to string (handles dict/list) before calling core. |

## 4) Whitelisted method override (`override_whitelisted_methods`)

| Method | Hook target | Source | Summary |
|---|---|---|---|
| `frappe.desk.query_report.run` | `ferum_custom.overrides.query_report.run` | `ferum_custom/overrides/query_report.py` | Makes Query Reports tolerant to empty filter dicts by pre-filling missing `%(field)s` placeholders; prevents runtime `KeyError` in SQL parameter formatting. |

Compatibility wrapper (historical import path):

- `ferum_custom/ferum_custom/overrides/query_report.py` re-exports `ferum_custom.overrides.query_report.run`.

## 5) Document events (`doc_events`)

### Contract

| Event | Hook target | Source | Summary |
|---|---|---|---|
| `validate` | `ferum_custom.services.contract_project_sync.validate_contract_party_is_customer` | `ferum_custom/services/contract_project_sync.py` | Enforces Contract party_type/customer invariants. |
| `on_update` | `ferum_custom.services.contract_project_sync.ensure_project_for_contract` | `ferum_custom/services/contract_project_sync.py` | Ensures 1:1 Project container exists for Active Contract; syncs selected fields Contract→Project. |

### Project

| Event | Hook target | Source | Summary |
|---|---|---|---|
| `validate` | `ferum_custom.services.contract_project_sync.validate_project_has_contract` | `ferum_custom/services/contract_project_sync.py` | For `Project.project_type='External'`, requires link to Contract. |
| `validate` | `ferum_custom.services.contract_project_sync.validate_project_unique_contract` | `ferum_custom/services/contract_project_sync.py` | Enforces Contract→Project uniqueness (1:1). |
| `validate` | `ferum_custom.services.project_full_cycle.validate_project_p0_stage_gates` | `ferum_custom/services/project_full_cycle.py` | Implements P0 stage gates (required blocks/checklists/files/approvals) when `ferum_p0_enabled=1`. |
| `after_insert` | `ferum_custom.services.project_full_cycle.create_initial_project_todos` | `ferum_custom/services/project_full_cycle.py` | Creates initial ToDo items / assigns roles for Project P0 onboarding. |

### Service Request / Service Report (both naming variants)

This app supports both DocType naming variants (`Service Request` and `ServiceRequest`, `Service Report` and
`ServiceReport`) for backward compatibility.

| DocType | Event | Hook target | Source | Summary |
|---|---|---|---|---|
| `Service Request` / `ServiceRequest` | `after_insert` | `ferum_custom.notifications.notify_new_service_request` | `ferum_custom/notifications.py` | Sends notifications (Telegram/FastAPI) for new requests; resolves Project+Project Site context. |
| `Service Request` / `ServiceRequest` | `on_update` | `ferum_custom.notifications.notify_service_request_status_change` | `ferum_custom/notifications.py` | Notifies on request status changes. |
| `Service Report` / `ServiceReport` | `after_insert` | `ferum_custom.notifications.notify_new_service_report` | `ferum_custom/notifications.py` | Notifies on new reports. |
| `Service Report` / `ServiceReport` | `on_submit` | `ferum_custom.notifications.notify_service_report_status_change` | `ferum_custom/notifications.py` | Notifies on report status change / submission. |

### Invoice + File

| DocType | Event | Hook target | Source | Summary |
|---|---|---|---|---|
| `Invoice` | `after_insert` | `ferum_custom.notifications.notify_new_invoice` | `ferum_custom/notifications.py` | Notifies on new invoice. |
| `Invoice` | `on_update` | `ferum_custom.notifications.notify_invoice_status_change` | `ferum_custom/notifications.py` | Notifies on invoice status changes. |
| `File` | `validate` | `ferum_custom.services.project_documents.validate_project_document_file` | `ferum_custom/services/project_documents.py` | Validates/normalizes Project document attachments (type/name rules) before save. |

## 6) Scheduler events (`scheduler_events`)

| Frequency | Hook target | Source | Summary |
|---|---|---|---|
| `daily` | `ferum_custom.services.service_schedule.generate_service_requests_from_schedule` | `ferum_custom/services/service_schedule.py` | Generates Service Requests from maintenance schedule (idempotent by design). |
| `daily` | `ferum_custom.services.project_escalations.run_daily_project_escalations` | `ferum_custom/services/project_escalations.py` | Sends/escalates P0 reminders based on deadlines/flags. |

## 7) Test hooks

| Hook | Target | Source | Summary |
|---|---|---|---|
| `before_tests` | `ferum_custom.setup.tests.before_tests` | `ferum_custom/setup/tests.py` | Ensures minimal ERPNext test records exist (Cost Centers) before app tests run. |
