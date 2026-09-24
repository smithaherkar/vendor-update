from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, rag_service

router = APIRouter(prefix="/api/rag", tags=["Vendor AI Assistant"])


@router.post("/ask", response_model=schemas.AssistantReply)
def ask_assistant(payload: schemas.AssistantAsk, db: Session = Depends(get_db)):
    """
    Deterministic SQL-backed analytics assistant.
    Routes user query to one of 17 fixed retrievable fact queries, evaluates
    low-sample-size confidence guards, and minimizes LLM usage to pure formatting.
    """
    reply = rag_service.ask_assistant(payload.message, db=db)
    return schemas.AssistantReply(reply=reply)
