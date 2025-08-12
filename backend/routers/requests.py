from fastapi import APIRouter, Depends, HTTPException
from frappe_client import FrappeClient

from ..config import settings
from ..auth import get_current_user, has_role

router = APIRouter()

# Initialize FrappeClient
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)

@router.get("/requests")
async def get_requests(current_user: str = Depends(has_role(["Project Manager", "Administrator", "Engineer", "Office Manager", "Client"]))):
    try:
        # In a real scenario, you would filter requests based on the current_user's permissions
        requests = frappe_client.get_list("ServiceRequest", fields=["name", "title", "status", "assigned_to", "service_object"])
        return {"requests": requests}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/requests/{request_name}")
async def get_request(request_name: str, current_user: str = Depends(has_role(["Project Manager", "Administrator", "Engineer", "Office Manager", "Client"]))):
    try:
        request = frappe_client.get_doc("ServiceRequest", request_name)
        # Add logic to ensure user has permission to view this specific request
        return {"request": request}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/requests")
async def create_request(request_data: dict, current_user: str = Depends(has_role(["Project Manager", "Administrator", "Office Manager", "Client"]))):
    try:
        new_request = frappe_client.insert("ServiceRequest", request_data)
        return {"message": "Service Request created successfully", "request": new_request}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/requests/{request_name}/status")
async def update_request_status(request_name: str, status_data: dict, current_user: str = Depends(has_role(["Project Manager", "Administrator", "Engineer", "Department Head"]))):
    try:
        # This endpoint would enforce workflow rules defined in ERPNext
        updated_request = frappe_client.set_value("ServiceRequest", request_name, {"status": status_data.get("status")})
        return {"message": "Service Request status updated successfully", "request": updated_request}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
