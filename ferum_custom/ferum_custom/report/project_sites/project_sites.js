frappe.query_reports["Project Sites"] = {
	filters: [
		{
			fieldname: "project",
			label: "Project",
			fieldtype: "Link",
			options: "Project",
			reqd: 0,
		},
		{
			fieldname: "engineer",
			label: "Engineer",
			fieldtype: "Link",
			options: "User",
			reqd: 0,
		},
	],
};
