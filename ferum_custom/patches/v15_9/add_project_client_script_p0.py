from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Client Script"):
		return

	name = "Ferum Project P0 Buttons"
	existing = frappe.db.get_value("Client Script", {"name": name}, "name")
	script = """
frappe.ui.form.on('Project', {
  refresh(frm) {
    if (!frm.doc || !frm.doc.ferum_stage) return;
    frm.add_custom_button(__('Send Welcome Email'), () => {
      frappe.call({
        method: 'ferum_custom.api.project_p0.send_welcome_email',
        type: 'POST',
        args: { project: frm.doc.name },
        freeze: true,
        freeze_message: __('Sending...'),
        callback(r) {
          frm.reload_doc();
        }
      });
    });
  }
});
""".strip()

	if existing:
		doc = frappe.get_doc("Client Script", name)
	else:
		doc = frappe.new_doc("Client Script")
		doc.dt = "Project"
		doc.script_type = "Client"
		doc.enabled = 1
		doc.name = name
		doc.__newname = name

	doc.script = script
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)

	frappe.clear_cache()

