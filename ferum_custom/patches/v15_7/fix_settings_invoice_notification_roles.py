import frappe


def execute() -> None:
    """Fix broken Table MultiSelect definition in Ferum Custom Settings.

    Some sites ended up with `invoice_notification_roles.options = "Role"` which makes
    Frappe treat `Role` as a child table and fails while loading settings with:
    OperationalError: (1054, "Unknown column 'parent' in 'WHERE'")
    """

    doctype = "Ferum Custom Settings"
    fieldname = "invoice_notification_roles"
    expected_options = "Ferum Invoice Notification Role"

    if not frappe.db.exists("DocType", doctype):
        return

    if frappe.db.exists("DocType", expected_options):
        frappe.db.set_value("DocType", expected_options, "istable", 1)

    docfield_name = frappe.db.get_value(
        "DocField",
        {"parent": doctype, "parenttype": "DocType", "fieldname": fieldname},
        "name",
    )
    if not docfield_name:
        return

    current_options = frappe.db.get_value("DocField", docfield_name, "options")
    if current_options == expected_options:
        return

    frappe.db.set_value("DocField", docfield_name, "options", expected_options)
    frappe.db.commit()

    frappe.clear_cache(doctype=doctype)

