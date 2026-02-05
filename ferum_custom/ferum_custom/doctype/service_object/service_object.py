import frappe
from frappe.model.document import Document


class ServiceObject(Document):
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
			"Service Request",
			filters={"service_object": self.name, "status": ["in", ["Open", "In Progress"]]},
			pluck="name",
		)
		if active_requests:
			frappe.throw(
				f"Cannot delete Service Object. It is linked to active Service Requests: {', '.join(active_requests)}"
			)
