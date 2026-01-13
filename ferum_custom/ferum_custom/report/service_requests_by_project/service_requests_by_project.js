/* global frappe */

frappe.query_reports["Service Requests by Project"] = {
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

