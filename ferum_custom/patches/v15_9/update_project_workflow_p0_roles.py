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


def execute() -> None:
	workflow_name = "Ferum Project Workflow (P0)"
	if not frappe.db.exists("Workflow", workflow_name):
		return
	if not frappe.db.exists("DocType", "Project"):
		return
	if not frappe.get_meta("Project").has_field("ferum_stage"):
		return

	doc = frappe.get_doc("Workflow", workflow_name)

	doc.document_type = "Project"
	doc.workflow_state_field = "ferum_stage"
	doc.is_active = 1
	doc.send_email_alert = 0

	# Allow edits for operational roles (custom + standard ERPNext roles).
	edit_roles = [
		"System Manager",
		"Projects Manager",
		"Project Manager",
		"Office Manager",
		"Ferum Office Manager",
		"Ferum Tender Specialist",
		"General Director",
		"Ferum Director",
	]

	# Reset states/transitions to keep deterministic.
	doc.states = []
	doc.transitions = []

	# Ensure Workflow State master docs exist.
	for state in STAGES:
		if not frappe.db.exists("Workflow State", state):
			ws = frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": "Primary"}
			)
			ws.insert(ignore_permissions=True)

	# Ensure workflow action exists.
	action_name = "Next Stage"
	if not frappe.db.exists("Workflow Action Master", action_name):
		frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action_name}).insert(
			ignore_permissions=True
		)

	for state in STAGES:
		for role in edit_roles:
			if role and frappe.db.exists("Role", role):
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
	transition_roles = [
		"System Manager",
		"Projects Manager",
		"Project Manager",
		"General Director",
		"Ferum Director",
	]
	for i in range(len(STAGES) - 1):
		for role in transition_roles:
			if role and frappe.db.exists("Role", role):
				doc.append(
					"transitions",
					{
						"state": STAGES[i],
						"action": action_name,
						"next_state": STAGES[i + 1],
						"allowed": role,
						"allow_self_approval": 1,
					},
				)

	doc.save(ignore_permissions=True)
	frappe.clear_cache()
