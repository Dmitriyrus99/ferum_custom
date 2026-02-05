frappe.query_reports["Invoices by Project"] = {
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
