from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from frappe_client import FrappeClient

from ..config import settings
from ..auth import get_current_user, has_role

router = APIRouter()

# Initialize FrappeClient
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)

@router.get("/requests")
async def get_requests(current_user: dict = Depends(get_current_user)):
    filters = {}
    user_roles = current_user.get("roles", [])
    user_name = current_user.get("name")

    if "Administrator" in user_roles or "Office Manager" in user_roles:
        # Admins and Office Managers see all requests
        pass
    elif "Project Manager" in user_roles:
        # Project Managers see requests associated with their projects
        managed_projects = current_user.get("managed_projects")
        if managed_projects:
            filters["service_project"] = ["in", managed_projects]
        else:
            return {"requests": []}
    elif "Engineer" in user_roles:
        # Engineers see requests assigned to them
        filters["assigned_to"] = user_name
    elif "Client" in user_roles:
        # Clients see requests associated with their customer
        customer_id = current_user.get("customer_id")
        if customer_id:
            filters["customer"] = customer_id
        else:
            return {"requests": []}
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view requests.")

    try:
        requests = frappe_client.get_list("ServiceRequest", filters=filters, fields=["name", "title", "status", "assigned_to", "service_object"])
        return {"requests": requests}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/requests/{request_name}")
async def get_request(request_name: str, current_user: dict = Depends(get_current_user)):
    user_roles = current_user.get("roles", [])
    user_name = current_user.get("name")

    try:
        request = frappe_client.get_doc("ServiceRequest", request_name)
        
        # Authorization logic for single request
        if "Administrator" in user_roles or "Office Manager" in user_roles:
            pass # Admins and Office Managers can view any request
        elif "Project Manager" in user_roles:
            managed_projects = current_user.get("managed_projects", [])
            if request.get("service_project") not in managed_projects:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this request.")
        elif "Engineer" in user_roles:
            if request.get("assigned_to") != user_name:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this request.")
        elif "Client" in user_roles:
            customer_id = current_user.get("customer_id")
            if not customer_id or request.get("customer") != customer_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this request.")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this request.")

        return {"request": request}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

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

@router.post("/requests/{request_name}/attachments")
async def upload_request_attachment(request_name: str, file: UploadFile = File(...), current_user: str = Depends(has_role(["Project Manager", "Administrator", "Engineer", "Office Manager"]))):
    try:
        # Create a CustomAttachment DocType in ERPNext
        # The actual file content will be handled by CustomAttachment's before_insert hook (Google Drive integration)
        attachment_data = {
            "file_name": file.filename,
            "file_type": file.content_type,
            "uploaded_by": current_user,
            "linked_doctype": "ServiceRequest",
            "linked_docname": request_name
        }
        new_attachment = frappe_client.insert("CustomAttachment", attachment_data)

        # Link the CustomAttachment to the ServiceRequest via RequestPhotoAttachmentItem
        # First, get the ServiceRequest to update its child table
        service_request_doc = frappe_client.get_doc("ServiceRequest", request_name)
        
        # Add the new attachment to the 'photos' child table
        if not service_request_doc.photos:
            service_request_doc.photos = []
        service_request_doc.photos.append({"photo": new_attachment.name}) # Assuming 'photo' field in child table links to CustomAttachment name
        
        updated_service_request = frappe.client.update("ServiceRequest", service_request_doc.name, {"photos": service_request_doc.photos})

        return {"message": "Attachment uploaded and linked successfully", "attachment": new_attachment.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))