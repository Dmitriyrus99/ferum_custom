import frappe
import requests
import json

# Assuming FastAPI backend is running and accessible
FASTAPI_BACKEND_URL = "http://localhost:8000/api/v1"
# Replace with a valid JWT token for the FastAPI backend
# In a real system, this token would be securely managed (e.g., from a config DocType)
FASTAPI_AUTH_TOKEN = "YOUR_FASTAPI_JWT_TOKEN"

def send_telegram_notification_to_fastapi(chat_id, message):
    headers = {
        "Authorization": f"Bearer {FASTAPI_AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(f"{FASTAPI_BACKEND_URL}/send_telegram_notification", headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        frappe.log_by_page(f"Telegram notification sent via FastAPI for chat_id {chat_id}", "Notification Success")
    except requests.exceptions.RequestException as e:
        frappe.log_error(f"Failed to send Telegram notification via FastAPI to chat_id {chat_id}: {e}", "Notification Error")

def notify_new_service_request(doc, method):
    # Notify Project Managers and Office Managers about a new Service Request
    message = f"New Service Request created: {doc.name} - {doc.title}. Status: {doc.status}. Priority: {doc.priority}."
    
    # Example: Send to a specific Telegram chat ID (e.g., a group chat for PMs/Office Managers)
    # You would retrieve this chat_id from a Frappe setting or a dedicated DocType
    pm_office_chat_id = 123456789 # REPLACE WITH ACTUAL CHAT ID
    send_telegram_notification_to_fastapi(pm_office_chat_id, message)

    # Example: Send email notification
    # frappe.sendmail(
    #     recipients=["pm@example.com", "office@example.com"],
    #     subject=f"New Service Request: {doc.name}",
    #     content=message
    # )

def notify_service_request_status_change(doc, method):
    # Notify assigned engineer and client about status change
    message = f"Service Request {doc.name} status changed to {doc.status}. Title: {doc.title}."

    # Notify assigned engineer (if assigned and has Telegram ID linked)
    # You would need a way to map ERPNext user to Telegram chat_id
    if doc.assigned_to:
        engineer_chat_id = 987654321 # REPLACE WITH ACTUAL CHAT ID for assigned_to user
        send_telegram_notification_to_fastapi(engineer_chat_id, message)

    # Notify client (if client has Telegram ID linked or email)
    # You would need a way to map Customer to Telegram chat_id or get client email
    if doc.customer:
        client_chat_id = 1122334455 # REPLACE WITH ACTUAL CHAT ID for customer
        send_telegram_notification_to_fastapi(client_chat_id, message)

    # Example: Send email notification to client
    # frappe.sendmail(
    #     recipients=[frappe.db.get_value("Customer", doc.customer, "email_id")],
    #     subject=f"Service Request {doc.name} Update",
    #     content=message
    # )
