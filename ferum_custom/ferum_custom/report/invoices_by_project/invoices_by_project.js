/* global frappe */

frappe.query_reports["Invoices by Project"] = {
	filters: [
		{
			fieldname: "project",
			label: "Project",
			fieldtype: "Link",
			options: "Service Project",
			reqd: 0,
		},
	],
};

