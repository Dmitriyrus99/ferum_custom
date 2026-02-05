frappe.query_reports["Service Requests by Project"] = {
	filters: [
		{
			fieldname: "project",
			label: "Project",
			fieldtype: "Link",
			options: "Project",
			reqd: 0,
		},
	],
};
