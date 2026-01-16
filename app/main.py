from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Inclui as rotas da API (Webhook e Leads)
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def health_check():
    return {"status": "active", "environment": settings.ENV}