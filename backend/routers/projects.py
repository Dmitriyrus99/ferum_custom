from fastapi import APIRouter, Depends, HTTPException, status
from frappe_client import FrappeClient

from ..config import settings
from ..auth import get_current_user, has_role

router = APIRouter()

# Initialize FrappeClient
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)

@router.get("/projects")
async def get_projects(current_user: dict = Depends(get_current_user)):
    filters = {}
    # Assuming current_user contains 'roles' and 'email' or 'name' (Frappe user ID)
    user_roles = current_user.get("roles", [])
    user_name = current_user.get("name")

    if "Administrator" in user_roles:
        # Admins see all projects
        pass
    elif "Project Manager" in user_roles:
        # Project Managers see projects they are associated with
        # This assumes a link field in ServiceProject to Project Manager (e.g., 'project_manager_email' or 'assigned_to')
        # For now, let's assume a custom field 'project_manager' in ServiceProject that stores the user's email or name
        filters["project_manager"] = user_name # Or current_user.get("email")
    elif "Client" in user_roles:
        # Clients see projects associated with their customer
        # This assumes the client user is linked to a Customer DocType, and ServiceProject has a 'customer' field
        # You would need to fetch the customer linked to the current_user
        # For simplicity, let's assume a direct link or a way to get customer from user
        # In a real Frappe setup, you'd query User or a custom DocType to get the customer_id
        # For now, a placeholder: 
        # customer_id = frappe_client.get_value("User", user_name, "customer_id") # Example if user has customer_id field
        # if customer_id: filters["customer"] = customer_id
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client role project filtering not fully implemented yet.")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view projects.")

    try:
        projects = frappe_client.get_list("ServiceProject", filters=filters, fields=["name", "project_name", "status", "customer"])
        return {"projects": projects}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/projects/{project_name}")
async def get_project(project_name: str, current_user: dict = Depends(get_current_user)):
    user_roles = current_user.get("roles", [])
    user_name = current_user.get("name")

    try:
        project = frappe_client.get_doc("ServiceProject", project_name)
        
        # Authorization logic for single project
        if "Administrator" in user_roles:
            pass # Admins can view any project
        elif "Project Manager" in user_roles:
            # PMs can view projects they manage
            if project.get("project_manager") != user_name: # Assuming 'project_manager' field in ServiceProject
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this project.")
        elif "Client" in user_roles:
            # Clients can view projects associated with their customer
            # This requires fetching the customer linked to the current_user and comparing with project.customer
            # For now, a placeholder:
            # customer_id = frappe_client.get_value("User", user_name, "customer_id")
            # if project.get("customer") != customer_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client role project filtering not fully implemented yet.")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this project.")

        return {"project": project}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/projects")
async def create_project(project_data: dict, current_user: str = Depends(has_role(["Project Manager", "Administrator"]))):
    try:
        new_project = frappe_client.insert("ServiceProject", project_data)
        return {"message": "Project created successfully", "project": new_project}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/projects/{project_name}")
async def update_project(project_name: str, project_data: dict, current_user: str = Depends(has_role(["Project Manager", "Administrator"]))):
    try:
        updated_project = frappe_client.update("ServiceProject", project_name, project_data)
        return {"message": "Project updated successfully", "project": updated_project}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
