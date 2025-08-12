## Development Notes

This document outlines areas that require further development or manual configuration beyond the initial setup.

### 1. Google Sheets Integration

The `sync_to_google_sheets` method in `ferum_custom/ferum_custom/doctype/Invoice/invoice.py` has been updated with a more detailed placeholder. To enable actual synchronization with Google Sheets, you need to:

*   **Install `gspread`:** Add `gspread` to your ERPNext bench's `requirements.txt` or install it directly in your Frappe environment.
    ```bash
    # Example for bench
    cd /path/to/your/frappe-bench
    pip install gspread
    bench restart
    ```
*   **Refer to `backend/google_integration_notes.md`** for detailed instructions on setting up Google Cloud Project, enabling APIs, creating credentials (Service Account recommended), and configuring environment variables (`GOOGLE_APPLICATION_CREDENTIALS` or similar).
*   **Ensure Service Account access:** Share your Google Sheet (`Ferum Invoices Tracker` or your chosen name) with the email address of your Google Service Account.

### 2. Google Drive Integration

The `before_insert` and `on_trash` methods in `ferum_custom/ferum_custom/doctype/CustomAttachment/custom_attachment.py` have been updated with more detailed placeholders for Google Drive integration. To enable actual synchronization with Google Drive, you need to:

*   **Install `google-api-python-client`:** Add `google-api-python-client` to your ERPNext bench's `requirements.txt` or install it directly in your Frappe environment.
    ```bash
    # Example for bench
    cd /path/to/your/frappe-bench
    pip install google-api-python-client
    bench restart
    ```
*   **Refer to `backend/google_integration_notes.md`** for detailed instructions on setting up Google Cloud Project, enabling APIs, creating credentials (Service Account recommended), and configuring environment variables (`GOOGLE_APPLICATION_CREDENTIALS` or similar).
*   **Ensure Service Account access:** Share the relevant Google Drive folders with the email address of your Google Service Account.

### 3. RBAC Role-Checker in FastAPI Backend

The `has_role` function in `backend/auth.py` is currently a placeholder that uses mock roles. For a production environment, this function needs to be replaced with actual logic to fetch user roles from ERPNext.

*   **Implement logic to query ERPNext:** Use the `frappe_client` (already initialized in `backend/auth.py`) to fetch the roles of the `current_user` from your ERPNext instance.
*   **Example (conceptual):**
    ```python
    # In auth.py, inside has_role function
    # from frappe_client import FrappeClient
    # frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)
    # user_doc = frappe_client.get_doc("User", current_user)
    # actual_user_roles = [role.role for role in user_doc.roles] # Assuming roles are in a child table
    # if not any(role in actual_user_roles for role in required_roles):
    # #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    ```
    *Note: You might need to adjust the ERPNext API calls based on your specific ERPNext setup and how roles are exposed via its API.*