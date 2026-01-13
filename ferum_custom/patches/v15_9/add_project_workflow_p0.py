from __future__ import annotations

import frappe
STAGES: list[str] = [
	"Tender Won",
	"Contact Established",
	"Contract Signed",
	"Contractor Selected/Contracted",
	"Initial Document Package Sent",
	"Primary Survey Completed",
	"Act & Defects Sent",
	"Invoice/Act Sent",
	"Customer Received Docs Confirmed",
	"Payment Received",
]


def _ensure_workflow_state_field() -> None:
	# The field itself is created by add_project_full_cycle_p0 patch. If it doesn't exist, skip.
	if not frappe.db.exists("DocType", "Project"):
		return
	meta = frappe.get_meta("Project")
	if not meta.has_field("ferum_stage"):
		return


def _upsert_workflow() -> None:
	workflow_name = "Ferum Project Workflow (P0)"
	existing = frappe.db.exists("Workflow", workflow_name)
	if existing:
		doc = frappe.get_doc("Workflow", workflow_name)
	else:
		doc = frappe.new_doc("Workflow")
		doc.workflow_name = workflow_name

	doc.document_type = "Project"
	doc.workflow_state_field = "ferum_stage"
	doc.is_active = 1
	doc.send_email_alert = 0

	# Reset states/transitions to keep it deterministic.
	doc.states = []
	doc.transitions = []

	# Allow edits for core operational roles.
	edit_roles = ["System Manager", "Project Manager", "Office Manager"]

	# Ensure Workflow State master docs exist.
	for state in STAGES:
		if not frappe.db.exists("Workflow State", state):
			ws = frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state, "style": "Primary"})
			ws.insert(ignore_permissions=True)

	# Ensure workflow action exists.
	action_name = "Next Stage"
	if not frappe.db.exists("Workflow Action Master", action_name):
		frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action_name}).insert(
			ignore_permissions=True
		)

	for state in STAGES:
		for role in edit_roles:
			doc.append(
				"states",
				{
					"state": state,
					"allow_edit": role,
					"update_field": "ferum_stage",
					"update_value": state,
				},
			)

	# Transitions: sequential stage updates.
	transition_roles = ["System Manager", "Project Manager"]
	for i in range(len(STAGES) - 1):
		doc.append(
			"transitions",
			{
				"state": STAGES[i],
				"action": action_name,
				"next_state": STAGES[i + 1],
				"allowed": transition_roles[0],
				"allow_self_approval": 1,
			},
		)
		# Add PM separately (WorkflowTransition is role-based per row)
		doc.append(
			"transitions",
			{
				"state": STAGES[i],
				"action": action_name,
				"next_state": STAGES[i + 1],
				"allowed": transition_roles[1],
				"allow_self_approval": 1,
			},
		)

	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)


def execute() -> None:
	_ensure_workflow_state_field()
	# If field isn't present yet (migration order), skip.
	if not frappe.get_meta("Project").has_field("ferum_stage"):
		return
	_upsert_workflow()
	frappe.clear_cache()
