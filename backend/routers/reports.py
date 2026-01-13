from fastapi import APIRouter, Depends, HTTPException, status
from frappeclient import FrappeClient

from ..auth import get_current_user, has_role
from ..config import settings

router = APIRouter()

# Initialize FrappeClient
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)


@router.get("/reports")
async def get_reports(current_user: dict = Depends(get_current_user)):
	filters: dict[str, object] = {}
	user_roles = current_user.get("roles", [])

	if "Administrator" in user_roles or "Department Head" in user_roles:
		# Admins and Department Heads see all reports
		pass
	elif "Project Manager" in user_roles:
		# Project Managers see reports associated with their projects
		managed_projects = current_user.get("managed_projects")
		if managed_projects:
			# Reports are linked to ServiceRequest, which is linked to ServiceProject
			# This requires a more complex query or fetching all relevant ServiceRequests first
			# For now, a placeholder:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Project Manager role report filtering not fully implemented yet.",
			)
		else:
			return {"reports": []}
	elif "Engineer" in user_roles:
		# Engineers see reports linked to service requests they were assigned to
		# This requires fetching service requests assigned to the engineer, then filtering reports by those requests
		# For now, a placeholder:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Engineer role report filtering not fully implemented yet.",
		)
	elif "Client" in user_roles:
		# Clients see reports associated with their customer's projects
		# This requires linking client user to customer, then filtering reports by customer's projects
		# For now, a placeholder:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Client role report filtering not fully implemented yet.",
		)
	else:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Not authorized to view reports.",
		)

	try:
		reports = frappe_client.get_list(
			"ServiceReport",
			filters=filters,
			fields=["name", "service_request", "status", "total_amount"],
		)
		return {"reports": reports}
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/reports/{report_name}")
async def get_report(report_name: str, current_user: dict = Depends(get_current_user)):
	user_roles = current_user.get("roles", [])

	try:
		report = frappe_client.get_doc("ServiceReport", report_name)

		# Authorization logic for single report
		if "Administrator" in user_roles or "Department Head" in user_roles:
			pass  # Admins and Department Heads can view any report
		elif "Project Manager" in user_roles:
			# PMs can view reports associated with their projects
			# Need to check if report.service_request.service_project is one of the projects managed by the PM
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Project Manager role report filtering not fully implemented yet.",
			)
		elif "Engineer" in user_roles:
			# Engineers can view reports linked to service requests they were assigned to
			# Need to check if report.service_request.assigned_to matches the engineer
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Engineer role report filtering not fully implemented yet.",
			)
		elif "Client" in user_roles:
			# Clients can view reports associated with their customer's projects
			# Need to check if report.service_request.service_project.customer matches the client's customer_id
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Client role report filtering not fully implemented yet.",
			)
		else:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Not authorized to view this report.",
			)

		return {"report": report}
	except HTTPException as e:
		raise e
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/reports")
async def create_report(
	report_data: dict,
	current_user: str = Depends(has_role(["Project Manager", "Administrator", "Engineer"])),
):
	try:
		new_report = frappe_client.insert("ServiceReport", report_data)
		return {"message": "Service Report created successfully", "report": new_report}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
