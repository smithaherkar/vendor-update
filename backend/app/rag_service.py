"""
RAG Service: Pure-Python audit engine (discrepancy math & rules RULE-101..106)
and LangChain + Gemini integration for audit reports & Vendor AI Assistant.
"""
import logging
from typing import Any
from sqlalchemy.orm import Session

from app.config import settings
from app import ml_models

logger = logging.getLogger(__name__)


# =====================================================================
# 1. AUDIT EXPLANATION ENGINE (Pure Math + Rules + Gemini Fallback)
# =====================================================================

def evaluate_audit_rules(payload: dict, predicted_flag: int, risk_probability: float) -> tuple[dict, list[str]]:
    """
    Pure-Python discrepancy math and rules evaluation.
    No LLM required for math or rule triggering.
    """
    inv_qty = float(payload.get("invoice_quantity", 0.0))
    inv_dollars = float(payload.get("invoice_dollars", 0.0))
    freight = float(payload.get("Freight", 0.0))
    po_qty = float(payload.get("total_item_quantity", 0.0))
    po_dollars = float(payload.get("total_item_dollars", 0.0))

    qty_diff = inv_qty - po_qty
    dollar_diff = inv_dollars - po_dollars
    inv_unit_price = (inv_dollars / inv_qty) if inv_qty > 0 else 0.0
    po_unit_price = (po_dollars / po_qty) if po_qty > 0 else 0.0

    if po_unit_price > 0:
        unit_price_escalation = ((inv_unit_price - po_unit_price) / po_unit_price) * 100.0
    else:
        unit_price_escalation = 0.0

    freight_pct = (freight / inv_dollars * 100.0) if inv_dollars > 0 else 0.0

    discrepancies = {
        "qty_diff": round(qty_diff, 2),
        "dollar_diff": round(dollar_diff, 2),
        "invoice_unit_price": round(inv_unit_price, 2),
        "po_unit_price": round(po_unit_price, 2),
        "unit_price_escalation_pct": round(unit_price_escalation, 2),
        "freight_pct": round(freight_pct, 2),
    }

    triggered_rules = []

    # RULE-101: Billed quantity exceeds or differs from PO received quantity
    if abs(qty_diff) > 0.01:
        triggered_rules.append(
            f"RULE-101: Quantity Discrepancy (Invoice billed {inv_qty} units vs PO received {po_qty} units)"
        )

    # RULE-102: Billed dollar amount exceeds or differs from PO total amount
    if abs(dollar_diff) > 0.01:
        triggered_rules.append(
            f"RULE-102: Total Cost Mismatch (Invoice billed ${inv_dollars:,.2f} vs PO expected ${po_dollars:,.2f})"
        )

    # RULE-103: Unit price escalation over PO unit price
    if unit_price_escalation > 2.0:
        triggered_rules.append(
            f"RULE-103: Unit Price Escalation (+{unit_price_escalation:.1f}% higher unit price than PO baseline)"
        )

    # RULE-104: Excessive Freight Ratio (> 8% of total invoice)
    if freight_pct > 8.0:
        triggered_rules.append(
            f"RULE-104: High Freight Ratio (Freight represents {freight_pct:.1f}% of total invoice cost)"
        )

    # RULE-105: ML Risk Model Flag / High Probability
    if predicted_flag == 1 or risk_probability >= 0.50:
        triggered_rules.append(
            f"RULE-105: ML Model Fraud/Error Flag (Confidence: {risk_probability * 100.0:.1f}%)"
        )

    # RULE-106: Zero quantity billed or freight charged with zero item cost
    if inv_qty <= 0 or (freight > 0 and inv_dollars <= 0):
        triggered_rules.append(
            "RULE-106: Irregular Line Item (Zero quantity billed or standalone freight without item total)"
        )

    return discrepancies, triggered_rules


def _generate_fallback_explanation(
    payload: dict,
    predicted_flag: int,
    risk_probability: float,
    discrepancies: dict,
    triggered_rules: list[str],
) -> str:
    """Deterministic Markdown explanation fallback when Gemini is unavailable."""
    verdict = "FLAGGED FOR AUDIT" if predicted_flag == 1 else "CLEARED / LOW RISK"
    rules_block = "\n".join([f"- **{r}**" for r in triggered_rules]) if triggered_rules else "- *No rule violations detected.*"

    return f"""### Audit Explanation Report
**Overall Status:** `{verdict}` (ML Risk Probability: **{risk_probability * 100.0:.1f}%**)

#### Discrepancy Analysis
- **Quantity Variance:** `{discrepancies['qty_diff']:+g}` units (Billed: {payload['invoice_quantity']}, Received: {payload['total_item_quantity']})
- **Financial Variance:** `${discrepancies['dollar_diff']:+,.2f}` (Billed: ${payload['invoice_dollars']:,.2f}, PO: ${payload['total_item_dollars']:,.2f})
- **Unit Price Shift:** `{discrepancies['unit_price_escalation_pct']:+.1f}%` (Billed: ${discrepancies['invoice_unit_price']:.2f}/unit vs PO: ${discrepancies['po_unit_price']:.2f}/unit)
- **Freight Allocation:** `${payload['Freight']:,.2f}` (**{discrepancies['freight_pct']:.1f}%** of total invoice)

#### Triggered Business Rules
{rules_block}

---
*Note: Configured fallback engine generated this audit summary. Set `GEMINI_API_KEY` in backend `.env` for AI-generated narrative summaries.*"""


def explain_invoice_flag(payload: dict, predicted_flag: int, risk_probability: float) -> dict[str, Any]:
    """
    Computes discrepancy math, evaluates rules RULE-101..106, and generates
    a LangChain + Gemini audit report (or deterministic fallback if key is missing/invalid).
    """
    discrepancies, triggered_rules = evaluate_audit_rules(payload, predicted_flag, risk_probability)

    api_key = settings.gemini_api_key.strip() if settings.gemini_api_key else ""
    if not api_key:
        markdown_output = _generate_fallback_explanation(
            payload, predicted_flag, risk_probability, discrepancies, triggered_rules
        )
        return {
            "discrepancies": discrepancies,
            "triggered_rules": triggered_rules,
            "explanation_markdown": markdown_output,
            "used_fallback": True,
        }

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.2,
        )

        sys_msg = SystemMessage(
            content=(
                "You are an expert Forensic Vendor Auditor. Analyze the provided invoice discrepancy metrics "
                "and triggered business rules. Write a clear, professional Markdown audit summary detailing "
                "why this invoice was flagged or cleared, highlighting specific monetary variances and risk factors."
            )
        )

        user_content = f"""
Invoice Data:
- Billed Qty: {payload['invoice_quantity']}, Billed Dollars: ${payload['invoice_dollars']}, Freight: ${payload['Freight']}
- PO Received Qty: {payload['total_item_quantity']}, PO Received Dollars: ${payload['total_item_dollars']}

Discrepancy Metrics:
{discrepancies}

ML Model Verdict:
- Flagged: {predicted_flag == 1}
- Risk Probability: {risk_probability * 100:.1f}%

Triggered Rules:
{triggered_rules}
"""
        human_msg = HumanMessage(content=user_content)
        response = llm.invoke([sys_msg, human_msg])
        markdown_output = str(response.content)

        return {
            "discrepancies": discrepancies,
            "triggered_rules": triggered_rules,
            "explanation_markdown": markdown_output,
            "used_fallback": False,
        }

    except Exception as exc:
        logger.warning(f"Gemini API call failed for audit explanation: {exc}. Using fallback template.")
        markdown_output = _generate_fallback_explanation(
            payload, predicted_flag, risk_probability, discrepancies, triggered_rules
        )
        return {
            "discrepancies": discrepancies,
            "triggered_rules": triggered_rules,
            "explanation_markdown": markdown_output,
            "used_fallback": True,
        }


# =====================================================================
# 2. VENDOR AI ASSISTANT (LangChain Tool-Calling Agent)
# =====================================================================

def ask_assistant(message: str) -> str:
    """
    Tool-calling assistant for MANIFEST 03.
    Uses tools: estimate_freight_tool, check_invoice_risk_tool, get_recent_flagged_invoices_tool.
    Returns clear message if GEMINI_API_KEY is missing/invalid.
    """
    api_key = settings.gemini_api_key.strip() if settings.gemini_api_key else ""
    if not api_key:
        return (
            "⚠️ **`GEMINI_API_KEY` is not configured.**\n\n"
            "To activate the Vendor AI Assistant (MANIFEST 03):\n"
            "1. Add your key to `backend/.env`: `GEMINI_API_KEY=your_actual_key`\n"
            "2. Restart the backend server (`uvicorn app.main:app --reload`)\n\n"
            "You can still use MANIFEST 01 (Invoice Risk Check) and MANIFEST 02 (Freight Cost Estimate) in deterministic mode."
        )

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.tools import tool
        try:
            from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
        except ImportError:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from app.database import SessionLocal
        from app import models_db

        @tool
        def estimate_freight_tool(dollars: float) -> str:
            """Estimates physical freight cost for a given invoice dollar amount."""
            est = ml_models.predict_freight(dollars)
            return f"Projected freight for ${dollars:,.2f} invoice is ${est:,.2f}."

        @tool
        def check_invoice_risk_tool(
            invoice_quantity: float,
            invoice_dollars: float,
            freight: float,
            total_item_quantity: float,
            total_item_dollars: float,
        ) -> str:
            """Scores fraud/error risk for invoice metrics against PO data."""
            payload = {
                "invoice_quantity": invoice_quantity,
                "invoice_dollars": invoice_dollars,
                "Freight": freight,
                "total_item_quantity": total_item_quantity,
                "total_item_dollars": total_item_dollars,
            }
            flag, prob = ml_models.predict_invoice_flag(payload)
            verdict = "FLAGGED" if flag == 1 else "CLEARED"
            return f"Invoice risk verdict: {verdict} (Risk Probability: {prob * 100:.1f}%)."

        @tool
        def get_recent_flagged_invoices_tool(limit: int = 5) -> str:
            """Retrieves the most recent flagged invoices logged in database history."""
            db: Session = SessionLocal()
            try:
                records = (
                    db.query(models_db.InvoicePrediction)
                    .filter(models_db.InvoicePrediction.predicted_flag == 1)
                    .order_by(models_db.InvoicePrediction.created_at.desc())
                    .limit(limit)
                    .all()
                )
                if not records:
                    return "No flagged invoices found in recent history."
                results = [
                    f"- **Entry #{r.id}**: Billed ${r.invoice_dollars:,.2f}, Freight ${r.freight:,.2f}, Risk Confidence: {r.risk_probability * 100:.1f}% ({r.created_at.strftime('%b %d, %H:%M')})"
                    for r in records
                ]
                return "\n".join(results)
            finally:
                db.close()

        tools = [estimate_freight_tool, check_invoice_risk_tool, get_recent_flagged_invoices_tool]

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.1,
        )

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are Vendor Intelligence Assistant, an AI expert assisting procurement and audit teams. "
                "Use your tools (estimate_freight_tool, check_invoice_risk_tool, get_recent_flagged_invoices_tool) "
                "to retrieve real data before answering. Never invent or hallucinate financial numbers."
            ),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

        res = executor.invoke({"input": message})
        return str(res["output"])

    except Exception as exc:
        logger.error(f"Error in ask_assistant agent: {exc}")
        # Smart fallback for common queries if API key is invalid or fails
        msg_lower = message.lower()
        if "flag" in msg_lower or "invoice" in msg_lower or "which" in msg_lower or "show" in msg_lower or "list" in msg_lower:
            try:
                flagged_info = get_recent_flagged_invoices_tool.invoke({})
                return f"📋 **Audit History Lookup:**\n\n{flagged_info}\n\n*(Note: Gemini LLM API call encountered: `{exc}`)*"
            except Exception:
                pass
        return f"Could not process assistant query: {exc}"

