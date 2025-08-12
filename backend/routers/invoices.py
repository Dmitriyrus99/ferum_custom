from fastapi import APIRouter, Depends, HTTPException
from frappe_client import FrappeClient

from ..config import settings
from ..auth import get_current_user, has_role

router = APIRouter()

# Initialize FrappeClient
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)

@router.get("/invoices")
async def get_invoices(current_user: str = Depends(has_role(["Project Manager", "Administrator", "Accountant", "Office Manager", "Client"]))):
    try:
        # In a real scenario, you would filter invoices based on the current_user's permissions
        invoices = frappe_client.get_list("Invoice", fields=["name", "project", "amount", "status", "counterparty_type"])
        return {"invoices": invoices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/invoices/{invoice_name}")
async def get_invoice(invoice_name: str, current_user: str = Depends(has_role(["Project Manager", "Administrator", "Accountant", "Office Manager", "Client"]))):
    try:
        invoice = frappe_client.get_doc("Invoice", invoice_name)
        # Add logic to ensure user has permission to view this specific invoice
        return {"invoice": invoice}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/invoices")
async def create_invoice(invoice_data: dict, current_user: str = Depends(has_role(["Project Manager", "Administrator", "Office Manager"]))):
    try:
        new_invoice = frappe_client.insert("Invoice", invoice_data)
        return {"message": "Invoice created successfully", "invoice": new_invoice}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/invoices/{invoice_name}/status")
async def update_invoice_status(invoice_name: str, status_data: dict, current_user: str = Depends(has_role(["Administrator", "Accountant"]))):
    try:
        updated_invoice = frappe_client.set_value("Invoice", invoice_name, {"status": status_data.get("status")})
        return {"message": "Invoice status updated successfully", "invoice": updated_invoice}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
