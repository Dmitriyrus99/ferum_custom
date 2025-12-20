import frappe
from frappe.model.document import Document


class ServiceObject(Document):
    def validate(self):
        if self.is_new() or self.has_changed("object_name"):
            if (
                frappe.db.exists("ServiceObject", {"object_name": self.object_name})
                and frappe.db.get_value("ServiceObject", {"object_name": self.object_name}, "name")
                != self.name
            ):
                frappe.throw(f"Service Object with name '{self.object_name}' already exists.")

    def on_trash(self):
        active_contract_links = frappe.get_all(
            "ContractServiceObject",
            filters={"service_object": self.name, "status": "Active"},
            pluck="contract",
        )
        if active_contract_links:
            frappe.throw(
                f"Cannot delete Service Object. It is linked to active Contracts: {', '.join(active_contract_links)}"
            )

        active_requests = frappe.get_all(
            "ServiceRequest",
            filters={"service_object": self.name, "status": ["in", ["Open", "In Progress"]]},
            pluck="name",
        )
        if active_requests:
            frappe.throw(
                f"Cannot delete Service Object. It is linked to active Service Requests: {', '.join(active_requests)}"
            )

