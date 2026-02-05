from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user, has_role
from ..frappe_client import get_frappe_client

router = APIRouter()


@router.get("/projects")
async def get_projects(current_user: dict = Depends(get_current_user)):
	frappe_client = get_frappe_client()
	filters = {}
	user_roles = current_user.get("roles", [])

	if "Administrator" in user_roles:
		# Admins see all projects
		pass
	elif "Project Manager" in user_roles:
		# Project Managers see projects they are associated with
		# Assuming 'current_user' dict contains 'managed_projects' list for PMs
		managed_projects = current_user.get("managed_projects")
		if managed_projects:
			filters["name"] = ["in", managed_projects]
		else:
			# If PM manages no projects, return empty list
			return {"projects": []}
	elif "Client" in user_roles:
		# Clients see projects associated with their customer
		# Assuming 'current_user' dict contains 'customer_id' for Clients
		customer_id = current_user.get("customer_id")
		if customer_id:
			filters["customer"] = customer_id
		else:
			# If client is not linked to a customer, return empty list
			return {"projects": []}
	else:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Not authorized to view projects.",
		)

	try:
		projects = frappe_client.get_list(
			"ServiceProject",
			filters=filters,
			fields=["name", "project_name", "status", "customer"],
		)
		return {"projects": projects}
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/projects/{project_name}")
async def get_project(project_name: str, current_user: dict = Depends(get_current_user)):
	frappe_client = get_frappe_client()
	user_roles = current_user.get("roles", [])

	try:
		project = frappe_client.get_doc("ServiceProject", project_name)

		# Authorization logic for single project
		if "Administrator" in user_roles:
			pass  # Admins can view any project
		elif "Project Manager" in user_roles:
			# PMs can view projects they manage
			managed_projects = current_user.get("managed_projects", [])
			if project_name not in managed_projects:
				raise HTTPException(
					status_code=status.HTTP_403_FORBIDDEN,
					detail="Not authorized to view this project.",
				)
		elif "Client" in user_roles:
			# Clients can view projects associated with their customer
			customer_id = current_user.get("customer_id")
			if not customer_id or project.get("customer") != customer_id:
				raise HTTPException(
					status_code=status.HTTP_403_FORBIDDEN,
					detail="Not authorized to view this project.",
				)
		else:
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="Not authorized to view this project.",
			)

		return {"project": project}
	except HTTPException as e:
		raise e
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/projects")
async def create_project(
	project_data: dict,
	current_user: str = Depends(has_role(["Project Manager", "Administrator"])),
):
	frappe_client = get_frappe_client()
	try:
		new_project = frappe_client.insert("ServiceProject", project_data)
		return {"message": "Project created successfully", "project": new_project}
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/projects/{project_name}")
async def update_project(
	project_name: str,
	project_data: dict,
	current_user: str = Depends(has_role(["Project Manager", "Administrator"])),
):
	frappe_client = get_frappe_client()
	try:
		updated_project = frappe_client.update("ServiceProject", project_name, project_data)
		return {"message": "Project updated successfully", "project": updated_project}
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
