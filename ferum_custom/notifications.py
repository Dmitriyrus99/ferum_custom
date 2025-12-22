import json
import os
from pathlib import Path

import frappe
import requests

REQUEST_TIMEOUT_SECONDS = 20
_DOTENV_LOADED = False


def _ensure_dotenv_loaded() -> None:
    """Load bench `.env` for non-web processes (workers/scheduler) where supervisor doesn't pass env vars."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return

    # notifications.py -> ferum_custom -> ferum_custom -> ferum_custom -> apps/ferum_custom -> apps -> bench root
    bench_root = Path(__file__).resolve().parents[5]
    dotenv_path = bench_root / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=str(dotenv_path), override=False)


def _get_setting(*keys: str) -> str | None:
    _ensure_dotenv_loaded()
    for key in keys:
        val = frappe.conf.get(key) if hasattr(frappe, "conf") else None
        if val:
            return str(val).strip()
        val = os.getenv(key)
        if val:
            return str(val).strip()
    return None


def _get_int_setting(*keys: str) -> int | None:
    val = _get_setting(*keys)
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _fastapi_backend_url() -> str | None:
    return _get_setting(
        "ferum_fastapi_base_url",
        "FERUM_FASTAPI_BASE_URL",
        "ferum_fastapi_backend_url",
        "FERUM_FASTAPI_BACKEND_URL",
        "FASTAPI_BACKEND_URL",
    )


def _fastapi_auth_token() -> str | None:
    return _get_setting(
        "ferum_fastapi_auth_token",
        "FERUM_FASTAPI_AUTH_TOKEN",
        "FASTAPI_AUTH_TOKEN",
    )


def _default_chat_id() -> int | None:
    return _get_int_setting(
        "ferum_telegram_default_chat_id",
        "FERUM_TELEGRAM_DEFAULT_CHAT_ID",
    )


def _telegram_bot_token() -> str | None:
    return _get_setting("ferum_telegram_bot_token", "FERUM_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")


def _send_telegram_direct(chat_id: int, message: str) -> None:
    token = _telegram_bot_token()
    if not token:
        frappe.log_error("Missing FERUM_TELEGRAM_BOT_TOKEN; can't send Telegram message.", "Telegram Config Error")
        return

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        frappe.log_error(f"Telegram sendMessage failed for chat_id {chat_id}: {e}", "Telegram Send Error")


def send_telegram_notification_to_fastapi(chat_id: int, message: str) -> None:
    """Compatibility wrapper: try FastAPI if configured, else send directly via Telegram API."""
    base_url = _fastapi_backend_url()
    token = _fastapi_auth_token()
    if not base_url or not token:
        _send_telegram_direct(int(chat_id), message)
        return

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"chat_id": int(chat_id), "text": message}
    try:
        response = requests.post(
            f"{base_url}/send_telegram_notification",
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        frappe.log_error(f"FastAPI telegram notification failed for chat_id {chat_id}: {e}", "Notification Error")
        # Fallback to direct send so notifications don't silently die.
        _send_telegram_direct(int(chat_id), message)


def notify_new_service_request(doc, method):
    # Notify Project Managers and Office Managers about a new Service Request
    message = f"New Service Request created: {doc.name} - {doc.title}. Status: {doc.status}. Priority: {doc.priority}."

    # Example: Send to a specific Telegram chat ID (e.g., a group chat for PMs/Office Managers)
    # You would retrieve this chat_id from a Frappe setting or a dedicated DocType
    chat_id = (
        _get_int_setting("ferum_telegram_pm_office_chat_id", "FERUM_TELEGRAM_PM_OFFICE_CHAT_ID")
        or _default_chat_id()
    )
    if chat_id:
        send_telegram_notification_to_fastapi(chat_id, message)

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
    chat_id = (
        _get_int_setting("ferum_telegram_pm_office_chat_id", "FERUM_TELEGRAM_PM_OFFICE_CHAT_ID")
        or _default_chat_id()
    )
    if chat_id:
        send_telegram_notification_to_fastapi(chat_id, message)

    # Example: Send email notification to client
    # frappe.sendmail(
    #     recipients=[frappe.db.get_value("Customer", doc.customer, "email_id")],
    #     subject=f"Service Request {doc.name} Update",
    #     content=message
    # )


def notify_new_service_report(doc, method):
    # Notify relevant parties (e.g., Project Manager, Admin) about a new Service Report
    message = f"New Service Report created: {doc.name} for Service Request {doc.service_request}. Status: {doc.status}."

    # Example: Send to a specific Telegram chat ID
    chat_id = _get_int_setting("ferum_telegram_pm_admin_chat_id", "FERUM_TELEGRAM_PM_ADMIN_CHAT_ID") or _default_chat_id()
    if chat_id:
        send_telegram_notification_to_fastapi(chat_id, message)

    # Example: Send email notification
    # frappe.sendmail(
    #     recipients=["pm@example.com", "admin@example.com"],
    #     subject=f"New Service Report: {doc.name}",
    #     content=message
    # )


def notify_service_report_status_change(doc, method):
    # Notify relevant parties about Service Report status change (e.g., Submitted, Approved)
    message = f"Service Report {doc.name} status changed to {doc.status}. For Service Request {doc.service_request}."

    # Example: Send to a specific Telegram chat ID
    chat_id = _get_int_setting("ferum_telegram_pm_admin_chat_id", "FERUM_TELEGRAM_PM_ADMIN_CHAT_ID") or _default_chat_id()
    if chat_id:
        send_telegram_notification_to_fastapi(chat_id, message)

    # Example: Send email notification
    # frappe.sendmail(
    #     recipients=["pm@example.com", "admin@example.com"],
    #     subject=f"Service Report {doc.name} Status Update",
    #     content=message
    # )


def notify_new_invoice(doc, method):
    # Notify relevant parties (e.g., Accountant, Admin) about a new Invoice
    message = f"New Invoice created: {doc.name} for {doc.counterparty_name}. Amount: {doc.amount}. Status: {doc.status}."

    # Example: Send to a specific Telegram chat ID
    chat_id = _get_int_setting("ferum_telegram_accountant_chat_id", "FERUM_TELEGRAM_ACCOUNTANT_CHAT_ID") or _default_chat_id()
    if chat_id:
        send_telegram_notification_to_fastapi(chat_id, message)

    # Example: Send email notification
    # frappe.sendmail(
    #     recipients=["accountant@example.com", "admin@example.com"],
    #     subject=f"New Invoice: {doc.name}",
    #     content=message
    # )


def notify_invoice_status_change(doc, method):
    # Notify relevant parties about Invoice status change (e.g., Paid, Overdue)
    message = f"Invoice {doc.name} status changed to {doc.status}. For {doc.counterparty_name}. Amount: {doc.amount}."

    # Example: Send to a specific Telegram chat ID
    chat_id = _get_int_setting("ferum_telegram_accountant_chat_id", "FERUM_TELEGRAM_ACCOUNTANT_CHAT_ID") or _default_chat_id()
    if chat_id:
        send_telegram_notification_to_fastapi(chat_id, message)

    # Example: Send email notification
    # frappe.sendmail(
    #     recipients=["accountant@example.com", "admin@example.com"],
    #     subject=f"Invoice {doc.name} Status Update",
    #     content=message
    # )
