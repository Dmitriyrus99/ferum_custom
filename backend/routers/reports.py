from fastapi import APIRouter, Depends, HTTPException
from frappe_client import FrappeClient

from ..config import settings
from ..auth import get_current_user, has_role

router = APIRouter()

# Initialize FrappeClient
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)

@router.get("/reports")
async def get_reports(current_user: str = Depends(has_role(["Project Manager", "Administrator", "Engineer", "Department Head", "Client"]))):
    try:
        # In a real scenario, you would filter reports based on the current_user's permissions
        reports = frappe_client.get_list("ServiceReport", fields=["name", "service_request", "status", "total_amount"])
        return {"reports": reports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/{report_name}")
async def get_report(report_name: str, current_user: str = Depends(has_role(["Project Manager", "Administrator", "Engineer", "Department Head", "Client"]))):
    try:
        report = frappe_client.get_doc("ServiceReport", report_name)
        # Add logic to ensure user has permission to view this specific report
        return {"report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports")
async def create_report(report_data: dict, current_user: str = Depends(has_role(["Project Manager", "Administrator", "Engineer"]))):
    try:
        new_report = frappe_client.insert("ServiceReport", report_data)
        return {"message": "Service Report created successfully", "report": new_report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
