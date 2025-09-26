from fastapi import APIRouter

ai_router = APIRouter(prefix="/ai", tags=["AI Assist"])

@ai_router.get("/")
async def read_ai_status():
    return [{"message": "Placeholder for AI assist status"}]
