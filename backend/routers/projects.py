from fastapi import APIRouter, Depends, HTTPException
from frappe_client import FrappeClient

from ..config import settings
from ..auth import get_current_user, has_role

router = APIRouter()

# Initialize FrappeClient
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)

@router.get("/projects")
async def get_projects(current_user: str = Depends(has_role(["Project Manager", "Administrator"]))):
    try:
        # In a real scenario, you would filter projects based on the current_user's permissions
        # For now, fetching all projects
        projects = frappe_client.get_list("ServiceProject", fields=["name", "project_name", "status", "customer"])
        return {"projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_name}")
async def get_project(project_name: str, current_user: str = Depends(has_role(["Project Manager", "Administrator", "Director", "Client"]))):
    try:
        project = frappe_client.get_doc("ServiceProject", project_name)
        # Add logic to ensure user has permission to view this specific project
        return {"project": project}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects")
async def create_project(project_data: dict, current_user: str = Depends(has_role(["Project Manager", "Administrator"]))):
    try:
        new_project = frappe_client.insert("ServiceProject", project_data)
        return {"message": "Project created successfully", "project": new_project}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/projects/{project_name}")
async def update_project(project_name: str, project_data: dict, current_user: str = Depends(has_role(["Project Manager", "Administrator"]))):
    try:
        updated_project = frappe_client.update("ServiceProject", project_name, project_data)
        return {"message": "Project updated successfully", "project": updated_project}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))