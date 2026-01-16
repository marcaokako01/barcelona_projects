from fastapi import APIRouter
from app.api.v1.endpoints import webhook, leads

api_router = APIRouter()
api_router.include_router(webhook.router, prefix="/webhook", tags=["voice-ai"])
api_router.include_router(leads.router, prefix="/leads", tags=["crm"])
