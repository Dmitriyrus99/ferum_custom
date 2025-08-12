from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import has_role
from ..bot.telegram_bot import send_telegram_notification

router = APIRouter()

class NotificationPayload(BaseModel):
    chat_id: int
    text: str

@router.post("/send_telegram_notification")
async def send_telegram_notification_endpoint(payload: NotificationPayload, current_user: str = Depends(has_role(["Administrator", "Department Head"]))):
    try:
        await send_telegram_notification(payload.chat_id, payload.text)
        return {"message": "Notification sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {e}")
