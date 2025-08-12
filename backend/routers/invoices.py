from fastapi import APIRouter, Depends, HTTPException, status
from frappe_client import FrappeClient

from ..config import settings
from ..auth import get_current_user, has_role

router = APIRouter()

# Initialize FrappeClient
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)

@router.get("/invoices")
async def get_invoices(current_user: dict = Depends(get_current_user)):
    filters = {}
    user_roles = current_user.get("roles", [])
    user_name = current_user.get("name")

    if "Administrator" in user_roles or "Accountant" in user_roles or "Office Manager" in user_roles:
        # Admins, Accountants, and Office Managers see all invoices
        pass
    elif "Project Manager" in user_roles:
        # Project Managers see invoices associated with their projects
        # This requires fetching projects managed by this user and then filtering invoices by those projects
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project Manager role invoice filtering not fully implemented yet.")
    elif "Client" in user_roles:
        # Clients see invoices where they are the counterparty
        # This requires linking client user to customer, then filtering invoices by counterparty_name or customer ID
        # For now, a placeholder:
        # customer_id = frappe_client.get_value("User", user_name, "customer_id")
        # if customer_id: filters["counterparty_name"] = frappe_client.get_value("Customer", customer_id, "customer_name")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client role invoice filtering not fully implemented yet.")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view invoices.")

    try:
        invoices = frappe_client.get_list("Invoice", filters=filters, fields=["name", "project", "amount", "status", "counterparty_type"])
        return {"invoices": invoices}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/invoices/{invoice_name}")
async def get_invoice(invoice_name: str, current_user: dict = Depends(get_current_user)):
    user_roles = current_user.get("roles", [])
    user_name = current_user.get("name")

    try:
        invoice = frappe_client.get_doc("Invoice", invoice_name)
        
        # Authorization logic for single invoice
        if "Administrator" in user_roles or "Accountant" in user_roles or "Office Manager" in user_roles:
            pass # Admins, Accountants, and Office Managers can view any invoice
        elif "Project Manager" in user_roles:
            # PMs can view invoices associated with their projects
            # Need to check if invoice.project is one of the projects managed by the PM
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project Manager role invoice filtering not fully implemented yet.")
        elif "Client" in user_roles:
            # Clients can view invoices where they are the counterparty
            # Need to check if invoice.counterparty_name matches the client's customer_name
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client role invoice filtering not fully implemented yet.")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this invoice.")

        return {"invoice": invoice}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

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