from fastapi import APIRouter

reminder_router = APIRouter(prefix="/reminders", tags=["Reminders"])

@reminder_router.get("/")
async def read_reminders():
    return [{"message": "Placeholder for reminder list"}]
