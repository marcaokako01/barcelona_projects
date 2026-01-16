from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def list_leads():
    return [{"name": "Lead Teste", "status": "Quente"}]
