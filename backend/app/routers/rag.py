from fastapi import APIRouter

from app import schemas, rag_service

router = APIRouter(prefix="/api/rag", tags=["Vendor AI Assistant"])


@router.post("/ask", response_model=schemas.AssistantReply)
def ask_assistant(payload: schemas.AssistantAsk):
    """
    Natural-language endpoint for MANIFEST 03 (Vendor AI Assistant).
    A LangChain tool-calling agent decides which internal function to call
    (freight estimate, invoice risk score, recent flagged invoices) based on
    the question, then answers using the real results.
    """
    reply = rag_service.ask_assistant(payload.message)
    return schemas.AssistantReply(reply=reply)
