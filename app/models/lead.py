from sqlalchemy import Column, Integer, String, DateTime, Enum
from app.db.base import Base
import enum
from datetime import datetime

class LeadStatus(str, enum.Enum):
    FRIO = "frio"
    MORNO = "morno"
    QUENTE = "quente"
    AGENDADO = "agendado"

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    phone = Column(String, unique=True, index=True)
    status = Column(Enum(LeadStatus), default=LeadStatus.FRIO)
    summary = Column(String, nullable=True) # Resumo da conversa
    created_at = Column(DateTime, default=datetime.utcnow)
