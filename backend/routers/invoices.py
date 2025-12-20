from fastapi import APIRouter, Depends, HTTPException, status
from frappeclient import FrappeClient

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
        managed_projects = current_user.get("managed_projects")
        if managed_projects:
            filters["project"] = ["in", managed_projects]
        else:
            return {"invoices": []}
    elif "Client" in user_roles:
        # Clients see invoices where they are the counterparty
        customer_id = current_user.get("customer_id")
        if customer_id:
            # Assuming Invoice has a 'customer' field or 'counterparty_name' can be mapped to customer
            # For simplicity, let's assume 'counterparty_name' directly matches the customer name
            customer_name = frappe_client.get_value("Customer", customer_id, "customer_name")
            if customer_name:
                filters["counterparty_name"] = customer_name
            else:
                return {"invoices": []}
        else:
            return {"invoices": []}
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
            managed_projects = current_user.get("managed_projects", [])
            if invoice.get("project") not in managed_projects:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this invoice.")
        elif "Client" in user_roles:
            customer_id = current_user.get("customer_id")
            if not customer_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this invoice.")
            
            customer_name = frappe_client.get_value("Customer", customer_id, "customer_name")
            if invoice.get("counterparty_name") != customer_name:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this invoice.")
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
