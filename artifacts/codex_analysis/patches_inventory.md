# Codex analysis — patches inventory (`ferum_custom/patches.txt`)

Generated: 2026-02-16

Total patch entries: **56**.

Purpose buckets are heuristic (`ui`, `permissions`, `data/legacy`, `schema/ops`, `other`).

## Summary (counts)

| Stage | Purpose | Count |
|---|---|---:|
| `pre_model_sync` | `data/legacy` | 1 |
| `post_model_sync` | `data/legacy` | 10 |
| `post_model_sync` | `other` | 3 |
| `post_model_sync` | `permissions` | 6 |
| `post_model_sync` | `schema/ops` | 20 |
| `post_model_sync` | `ui` | 16 |

## Full list (ordered as in patches.txt)

| Stage | Patch (dotted) | File | Purpose | Idempotent | Risk flags |
|---|---|---|---|---|---|
| `pre_model_sync` | `ferum_custom.patches.v15_10.rename_legacy_project_site_doctype` | `ferum_custom/patches/v15_10/rename_legacy_project_site_doctype.py` | `data/legacy` | `likely` | renames_docs |
| `post_model_sync` | `ferum_custom.patches.v15_10.migrate_project_site_row_to_truth` | `ferum_custom/patches/v15_10/migrate_project_site_row_to_truth.py` | `data/legacy` | `likely` | renames_docs, manual_commit, large_batch |
| `post_model_sync` | `ferum_custom.patches.v15_10.repair_project_site_truth_names` | `ferum_custom/patches/v15_10/repair_project_site_truth_names.py` | `data/legacy` | `likely` | renames_docs, manual_commit, large_batch |
| `post_model_sync` | `ferum_custom.patches.v15_7.add_contract_project_objects_acts_model` | `ferum_custom/patches/v15_7/add_contract_project_objects_acts_model.py` | `schema/ops` | `maybe` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_7.backfill_contract_project_links` | `ferum_custom/patches/v15_7/backfill_contract_project_links.py` | `data/legacy` | `maybe` | raw_sql, manual_commit |
| `post_model_sync` | `ferum_custom.patches.v15_7.backfill_contract_service_objects_from_requests` | `ferum_custom/patches/v15_7/backfill_contract_service_objects_from_requests.py` | `data/legacy` | `likely` | writes_update_modified |
| `post_model_sync` | `ferum_custom.patches.v15_7.cleanup_ferum_custom_module_defs` | `ferum_custom/patches/v15_7/cleanup_ferum_custom_module_defs.py` | `schema/ops` | `likely` | deletes_docs |
| `post_model_sync` | `ferum_custom.patches.v15_7.create_contract_objects_acts_doctypes` | `ferum_custom/patches/v15_7/create_contract_objects_acts_doctypes.py` | `schema/ops` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_7.ensure_contract_year_field` | `ferum_custom/patches/v15_7/ensure_contract_year_field.py` | `schema/ops` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_7.export_missing_doctype_files` | `ferum_custom/patches/v15_7/export_missing_doctype_files.py` | `schema/ops` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_7.fix_accounts_settings_exchange_rate` | `ferum_custom/patches/v15_7/fix_accounts_settings_exchange_rate.py` | `schema/ops` | `unknown` |  |
| `post_model_sync` | `ferum_custom.patches.v15_7.fix_report_invoices_by_project` | `ferum_custom/patches/v15_7/fix_report_invoices_by_project.py` | `ui` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_7.fix_report_service_requests_by_project` | `ferum_custom/patches/v15_7/fix_report_service_requests_by_project.py` | `ui` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_7.fix_settings_invoice_notification_roles` | `ferum_custom/patches/v15_7/fix_settings_invoice_notification_roles.py` | `schema/ops` | `likely` | manual_commit, writes_update_modified |
| `post_model_sync` | `ferum_custom.patches.v15_7.fix_system_settings_language` | `ferum_custom/patches/v15_7/fix_system_settings_language.py` | `schema/ops` | `maybe` | manual_commit |
| `post_model_sync` | `ferum_custom.patches.v15_7.fix_workspaces_ferum_custom` | `ferum_custom/patches/v15_7/fix_workspaces_ferum_custom.py` | `ui` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_7.fix_workspaces_objects_shortcuts` | `ferum_custom/patches/v15_7/fix_workspaces_objects_shortcuts.py` | `ui` | `unknown` |  |
| `post_model_sync` | `ferum_custom.patches.v15_7.hide_legacy_service_project_fields` | `ferum_custom/patches/v15_7/hide_legacy_service_project_fields.py` | `permissions` | `maybe` | writes_update_modified |
| `post_model_sync` | `ferum_custom.patches.v15_7.hide_service_project_everywhere` | `ferum_custom/patches/v15_7/hide_service_project_everywhere.py` | `permissions` | `likely` | writes_update_modified |
| `post_model_sync` | `ferum_custom.patches.v15_7.hide_service_project_from_desk` | `ferum_custom/patches/v15_7/hide_service_project_from_desk.py` | `ui` | `maybe` | raw_sql, writes_update_modified |
| `post_model_sync` | `ferum_custom.patches.v15_7.migrate_service_project_to_contracts` | `ferum_custom/patches/v15_7/migrate_service_project_to_contracts.py` | `data/legacy` | `likely` | raw_sql, manual_commit, writes_update_modified |
| `post_model_sync` | `ferum_custom.patches.v15_7.migrate_service_project_to_contracts_retry` | `ferum_custom/patches/v15_7/migrate_service_project_to_contracts_retry.py` | `data/legacy` | `likely` | manual_commit |
| `post_model_sync` | `ferum_custom.patches.v15_7.sync_service_object_from_project` | `ferum_custom/patches/v15_7/sync_service_object_from_project.py` | `data/legacy` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_7.transition_legacy_service_doctypes_to_contract_project` | `ferum_custom/patches/v15_7/transition_legacy_service_doctypes_to_contract_project.py` | `data/legacy` | `maybe` | custom_fields, writes_update_modified |
| `post_model_sync` | `ferum_custom.patches.v15_8.fix_query_reports_service_requests_and_invoices` | `ferum_custom/patches/v15_8/fix_query_reports_service_requests_and_invoices.py` | `ui` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_ferum_p0_roles_and_users` | `ferum_custom/patches/v15_9/add_ferum_p0_roles_and_users.py` | `schema/ops` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_client_script_p0` | `ferum_custom/patches/v15_9/add_project_client_script_p0.py` | `ui` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_custom_docperms_for_ferum_roles` | `ferum_custom/patches/v15_9/add_project_custom_docperms_for_ferum_roles.py` | `permissions` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_documents_file_meta` | `ferum_custom/patches/v15_9/add_project_documents_file_meta.py` | `schema/ops` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_documents_ui` | `ferum_custom/patches/v15_9/add_project_documents_ui.py` | `ui` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_full_cycle_p0` | `ferum_custom/patches/v15_9/add_project_full_cycle_p0.py` | `schema/ops` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_full_cycle_p0_extras` | `ferum_custom/patches/v15_9/add_project_full_cycle_p0_extras.py` | `schema/ops` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_p0_enabled_flag` | `ferum_custom/patches/v15_9/add_project_p0_enabled_flag.py` | `schema/ops` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_p0_settings_fields` | `ferum_custom/patches/v15_9/add_project_p0_settings_fields.py` | `schema/ops` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_project_manager_field` | `ferum_custom/patches/v15_9/add_project_project_manager_field.py` | `schema/ops` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_telegram_users_field` | `ferum_custom/patches/v15_9/add_project_telegram_users_field.py` | `schema/ops` | `likely` | custom_fields |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_project_workflow_p0` | `ferum_custom/patches/v15_9/add_project_workflow_p0.py` | `schema/ops` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_report_project_sites` | `ferum_custom/patches/v15_9/add_report_project_sites.py` | `ui` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.add_rusakov_to_all_projects` | `ferum_custom/patches/v15_9/add_rusakov_to_all_projects.py` | `schema/ops` | `unknown` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.backfill_project_sites_from_service_objects` | `ferum_custom/patches/v15_9/backfill_project_sites_from_service_objects.py` | `data/legacy` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.backfill_project_sites_from_service_objects_rerun` | `ferum_custom/patches/v15_9/backfill_project_sites_from_service_objects_rerun.py` | `data/legacy` | `unknown` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.cleanup_service_request_custom_fields` | `ferum_custom/patches/v15_9/cleanup_service_request_custom_fields.py` | `schema/ops` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.convert_query_reports_to_script_reports` | `ferum_custom/patches/v15_9/convert_query_reports_to_script_reports.py` | `ui` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.disable_broken_reports` | `ferum_custom/patches/v15_9/disable_broken_reports.py` | `ui` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.disable_legacy_service_object_mutations` | `ferum_custom/patches/v15_9/disable_legacy_service_object_mutations.py` | `permissions` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.disable_p0_for_incomplete_projects` | `ferum_custom/patches/v15_9/disable_p0_for_incomplete_projects.py` | `permissions` | `likely` | raw_sql, manual_commit |
| `post_model_sync` | `ferum_custom.patches.v15_9.ensure_file_home_folder` | `ferum_custom/patches/v15_9/ensure_file_home_folder.py` | `schema/ops` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.fix_workspaces_objects_shortcuts_project_sites` | `ferum_custom/patches/v15_9/fix_workspaces_objects_shortcuts_project_sites.py` | `ui` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.hide_unused_project_fields_p0` | `ferum_custom/patches/v15_9/hide_unused_project_fields_p0.py` | `permissions` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.optimize_workspaces_p0_minimal` | `ferum_custom/patches/v15_9/optimize_workspaces_p0_minimal.py` | `ui` | `likely` | raw_sql |
| `post_model_sync` | `ferum_custom.patches.v15_9.update_ferum_p0_users_real_emails` | `ferum_custom/patches/v15_9/update_ferum_p0_users_real_emails.py` | `other` | `maybe` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.update_file_doc_type_options_project_documents` | `ferum_custom/patches/v15_9/update_file_doc_type_options_project_documents.py` | `other` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.update_project_client_script_p0_buttons` | `ferum_custom/patches/v15_9/update_project_client_script_p0_buttons.py` | `ui` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.update_project_documents_ui_contract_upload` | `ferum_custom/patches/v15_9/update_project_documents_ui_contract_upload.py` | `ui` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.update_project_p0_custom_field_labels_ru` | `ferum_custom/patches/v15_9/update_project_p0_custom_field_labels_ru.py` | `ui` | `likely` |  |
| `post_model_sync` | `ferum_custom.patches.v15_9.update_project_workflow_p0_roles` | `ferum_custom/patches/v15_9/update_project_workflow_p0_roles.py` | `other` | `likely` |  |

## Grouped by purpose

### permissions

- `ferum_custom.patches.v15_7.hide_legacy_service_project_fields` — `post_model_sync` (ferum_custom/patches/v15_7/hide_legacy_service_project_fields.py)
- `ferum_custom.patches.v15_7.hide_service_project_everywhere` — `post_model_sync` (ferum_custom/patches/v15_7/hide_service_project_everywhere.py)
- `ferum_custom.patches.v15_9.add_project_custom_docperms_for_ferum_roles` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_custom_docperms_for_ferum_roles.py)
- `ferum_custom.patches.v15_9.disable_legacy_service_object_mutations` — `post_model_sync` (ferum_custom/patches/v15_9/disable_legacy_service_object_mutations.py)
- `ferum_custom.patches.v15_9.disable_p0_for_incomplete_projects` — `post_model_sync` (ferum_custom/patches/v15_9/disable_p0_for_incomplete_projects.py)
- `ferum_custom.patches.v15_9.hide_unused_project_fields_p0` — `post_model_sync` (ferum_custom/patches/v15_9/hide_unused_project_fields_p0.py)

### data/legacy

- `ferum_custom.patches.v15_10.rename_legacy_project_site_doctype` — `pre_model_sync` (ferum_custom/patches/v15_10/rename_legacy_project_site_doctype.py)
- `ferum_custom.patches.v15_10.migrate_project_site_row_to_truth` — `post_model_sync` (ferum_custom/patches/v15_10/migrate_project_site_row_to_truth.py)
- `ferum_custom.patches.v15_10.repair_project_site_truth_names` — `post_model_sync` (ferum_custom/patches/v15_10/repair_project_site_truth_names.py)
- `ferum_custom.patches.v15_7.backfill_contract_project_links` — `post_model_sync` (ferum_custom/patches/v15_7/backfill_contract_project_links.py)
- `ferum_custom.patches.v15_7.backfill_contract_service_objects_from_requests` — `post_model_sync` (ferum_custom/patches/v15_7/backfill_contract_service_objects_from_requests.py)
- `ferum_custom.patches.v15_7.migrate_service_project_to_contracts` — `post_model_sync` (ferum_custom/patches/v15_7/migrate_service_project_to_contracts.py)
- `ferum_custom.patches.v15_7.migrate_service_project_to_contracts_retry` — `post_model_sync` (ferum_custom/patches/v15_7/migrate_service_project_to_contracts_retry.py)
- `ferum_custom.patches.v15_7.sync_service_object_from_project` — `post_model_sync` (ferum_custom/patches/v15_7/sync_service_object_from_project.py)
- `ferum_custom.patches.v15_7.transition_legacy_service_doctypes_to_contract_project` — `post_model_sync` (ferum_custom/patches/v15_7/transition_legacy_service_doctypes_to_contract_project.py)
- `ferum_custom.patches.v15_9.backfill_project_sites_from_service_objects` — `post_model_sync` (ferum_custom/patches/v15_9/backfill_project_sites_from_service_objects.py)
- `ferum_custom.patches.v15_9.backfill_project_sites_from_service_objects_rerun` — `post_model_sync` (ferum_custom/patches/v15_9/backfill_project_sites_from_service_objects_rerun.py)

### ui

- `ferum_custom.patches.v15_7.fix_report_invoices_by_project` — `post_model_sync` (ferum_custom/patches/v15_7/fix_report_invoices_by_project.py)
- `ferum_custom.patches.v15_7.fix_report_service_requests_by_project` — `post_model_sync` (ferum_custom/patches/v15_7/fix_report_service_requests_by_project.py)
- `ferum_custom.patches.v15_7.fix_workspaces_ferum_custom` — `post_model_sync` (ferum_custom/patches/v15_7/fix_workspaces_ferum_custom.py)
- `ferum_custom.patches.v15_7.fix_workspaces_objects_shortcuts` — `post_model_sync` (ferum_custom/patches/v15_7/fix_workspaces_objects_shortcuts.py)
- `ferum_custom.patches.v15_7.hide_service_project_from_desk` — `post_model_sync` (ferum_custom/patches/v15_7/hide_service_project_from_desk.py)
- `ferum_custom.patches.v15_8.fix_query_reports_service_requests_and_invoices` — `post_model_sync` (ferum_custom/patches/v15_8/fix_query_reports_service_requests_and_invoices.py)
- `ferum_custom.patches.v15_9.add_project_client_script_p0` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_client_script_p0.py)
- `ferum_custom.patches.v15_9.add_project_documents_ui` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_documents_ui.py)
- `ferum_custom.patches.v15_9.add_report_project_sites` — `post_model_sync` (ferum_custom/patches/v15_9/add_report_project_sites.py)
- `ferum_custom.patches.v15_9.convert_query_reports_to_script_reports` — `post_model_sync` (ferum_custom/patches/v15_9/convert_query_reports_to_script_reports.py)
- `ferum_custom.patches.v15_9.disable_broken_reports` — `post_model_sync` (ferum_custom/patches/v15_9/disable_broken_reports.py)
- `ferum_custom.patches.v15_9.fix_workspaces_objects_shortcuts_project_sites` — `post_model_sync` (ferum_custom/patches/v15_9/fix_workspaces_objects_shortcuts_project_sites.py)
- `ferum_custom.patches.v15_9.optimize_workspaces_p0_minimal` — `post_model_sync` (ferum_custom/patches/v15_9/optimize_workspaces_p0_minimal.py)
- `ferum_custom.patches.v15_9.update_project_client_script_p0_buttons` — `post_model_sync` (ferum_custom/patches/v15_9/update_project_client_script_p0_buttons.py)
- `ferum_custom.patches.v15_9.update_project_documents_ui_contract_upload` — `post_model_sync` (ferum_custom/patches/v15_9/update_project_documents_ui_contract_upload.py)
- `ferum_custom.patches.v15_9.update_project_p0_custom_field_labels_ru` — `post_model_sync` (ferum_custom/patches/v15_9/update_project_p0_custom_field_labels_ru.py)

### schema/ops

- `ferum_custom.patches.v15_7.add_contract_project_objects_acts_model` — `post_model_sync` (ferum_custom/patches/v15_7/add_contract_project_objects_acts_model.py)
- `ferum_custom.patches.v15_7.cleanup_ferum_custom_module_defs` — `post_model_sync` (ferum_custom/patches/v15_7/cleanup_ferum_custom_module_defs.py)
- `ferum_custom.patches.v15_7.create_contract_objects_acts_doctypes` — `post_model_sync` (ferum_custom/patches/v15_7/create_contract_objects_acts_doctypes.py)
- `ferum_custom.patches.v15_7.ensure_contract_year_field` — `post_model_sync` (ferum_custom/patches/v15_7/ensure_contract_year_field.py)
- `ferum_custom.patches.v15_7.export_missing_doctype_files` — `post_model_sync` (ferum_custom/patches/v15_7/export_missing_doctype_files.py)
- `ferum_custom.patches.v15_7.fix_accounts_settings_exchange_rate` — `post_model_sync` (ferum_custom/patches/v15_7/fix_accounts_settings_exchange_rate.py)
- `ferum_custom.patches.v15_7.fix_settings_invoice_notification_roles` — `post_model_sync` (ferum_custom/patches/v15_7/fix_settings_invoice_notification_roles.py)
- `ferum_custom.patches.v15_7.fix_system_settings_language` — `post_model_sync` (ferum_custom/patches/v15_7/fix_system_settings_language.py)
- `ferum_custom.patches.v15_9.add_ferum_p0_roles_and_users` — `post_model_sync` (ferum_custom/patches/v15_9/add_ferum_p0_roles_and_users.py)
- `ferum_custom.patches.v15_9.add_project_documents_file_meta` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_documents_file_meta.py)
- `ferum_custom.patches.v15_9.add_project_full_cycle_p0` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_full_cycle_p0.py)
- `ferum_custom.patches.v15_9.add_project_full_cycle_p0_extras` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_full_cycle_p0_extras.py)
- `ferum_custom.patches.v15_9.add_project_p0_enabled_flag` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_p0_enabled_flag.py)
- `ferum_custom.patches.v15_9.add_project_p0_settings_fields` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_p0_settings_fields.py)
- `ferum_custom.patches.v15_9.add_project_project_manager_field` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_project_manager_field.py)
- `ferum_custom.patches.v15_9.add_project_telegram_users_field` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_telegram_users_field.py)
- `ferum_custom.patches.v15_9.add_project_workflow_p0` — `post_model_sync` (ferum_custom/patches/v15_9/add_project_workflow_p0.py)
- `ferum_custom.patches.v15_9.add_rusakov_to_all_projects` — `post_model_sync` (ferum_custom/patches/v15_9/add_rusakov_to_all_projects.py)
- `ferum_custom.patches.v15_9.cleanup_service_request_custom_fields` — `post_model_sync` (ferum_custom/patches/v15_9/cleanup_service_request_custom_fields.py)
- `ferum_custom.patches.v15_9.ensure_file_home_folder` — `post_model_sync` (ferum_custom/patches/v15_9/ensure_file_home_folder.py)

### other

- `ferum_custom.patches.v15_9.update_ferum_p0_users_real_emails` — `post_model_sync` (ferum_custom/patches/v15_9/update_ferum_p0_users_real_emails.py)
- `ferum_custom.patches.v15_9.update_file_doc_type_options_project_documents` — `post_model_sync` (ferum_custom/patches/v15_9/update_file_doc_type_options_project_documents.py)
- `ferum_custom.patches.v15_9.update_project_workflow_p0_roles` — `post_model_sync` (ferum_custom/patches/v15_9/update_project_workflow_p0_roles.py)
