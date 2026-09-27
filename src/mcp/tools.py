import json
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.config import EMPLOYEES_FILE, TICKETS_FILE, CHROMA_PERSIST_DIR
from src.rag.vector_store import PolicyVectorStore

_vector_store: Optional[PolicyVectorStore] = None

def get_vector_store() -> PolicyVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = PolicyVectorStore(persist_dir=str(CHROMA_PERSIST_DIR), use_fallback_embeddings=True)
    return _vector_store


def search_policy_documents(query: str, top_k: int = 3, filter_category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search the HR policy database using semantic retrieval.
    Returns matching policy sections with citations, snippets, and similarity scores.
    """
    vs = get_vector_store()
    return vs.search(query=query, top_k=top_k, filter_category=filter_category)


def get_policy_section(document_id: str, section_title: str) -> Dict[str, Any]:
    """
    Retrieve full text and metadata for a specific section within an HR policy document.
    """
    vs = get_vector_store()
    res = vs.get_section(document_id=document_id, section_title=section_title)
    if res:
        return res
    return {
        "error": f"Section '{section_title}' not found in document '{document_id}'",
        "document_id": document_id,
        "section_title": section_title
    }


def lookup_employee_profile(employee_id: str) -> Dict[str, Any]:
    """
    Lookup structured employee details including role, department, tenure, manager,
    work location, and onboarding checklist status.
    """
    clean_id = employee_id.strip().upper()
    if not EMPLOYEES_FILE.exists():
        return {"error": "Employee database not found", "employee_id": clean_id}

    with open(EMPLOYEES_FILE, "r", encoding="utf-8") as f:
        employees = json.load(f)

    if clean_id in employees:
        return employees[clean_id]
    return {"error": f"Employee with ID '{clean_id}' was not found in directory", "employee_id": clean_id}


def check_pto_balance(employee_id: str) -> Dict[str, Any]:
    """
    Retrieve PTO and paid sick leave balances, tenure tier, and rollover rules for an employee.
    """
    profile = lookup_employee_profile(employee_id)
    if "error" in profile:
        return profile

    tenure = profile.get("tenure_years", 0.0)
    if tenure < 2.0:
        tier_info = "Tier 1 (0-2 yrs): 15 days/year (120 hrs)"
    elif tenure <= 5.0:
        tier_info = "Tier 2 (2-5 yrs): 20 days/year (160 hrs)"
    else:
        tier_info = "Tier 3 (5+ yrs): 25 days/year (200 hrs)"

    return {
        "employee_id": profile["employee_id"],
        "employee_name": profile["full_name"],
        "pto_balance_days": profile.get("pto_balance_days", 0.0),
        "sick_balance_days": profile.get("sick_balance_days", 0.0),
        "accrual_tier": tier_info,
        "max_rollover_days": 5,
        "rollover_deadline": "March 31 of following year"
    }


def lookup_benefits_status(employee_id: str) -> Dict[str, Any]:
    """
    Retrieve healthcare, retirement 401(k), FSA/HSA, and wellness stipend election details.
    """
    profile = lookup_employee_profile(employee_id)
    if "error" in profile:
        return profile

    elections = profile.get("benefits_election", {})
    return {
        "employee_id": profile["employee_id"],
        "employee_name": profile["full_name"],
        "department": profile.get("department"),
        "benefits": elections,
        "wellness_stipend_remaining": round(600.0 - elections.get("wellness_stipend_claimed_ytd", 0.0), 2),
        "401k_match_policy": "100% match on first 4%, 50% on next 2% (max 5%)"
    }


def create_mock_hr_ticket(employee_id: str, ticket_type: str, details: str, confirmed: bool = False) -> Dict[str, Any]:
    """
    Create a mock HR ticket or workflow request.
    SAFETY GUARDRAIL: Requires confirmed=True. If confirmed=False, returns a confirmation requirement.
    """
    profile = lookup_employee_profile(employee_id)
    if "error" in profile:
        return profile

    if not confirmed:
        return {
            "status": "CONFIRMATION_REQUIRED",
            "action_safety": "GUARDRAIL_TRIGGERED",
            "message": f"Action requires explicit user confirmation before creating a ticket of type '{ticket_type}' for {profile['full_name']} ({employee_id}).",
            "pending_ticket": {
                "employee_id": employee_id,
                "ticket_type": ticket_type,
                "details": details
            }
        }

    # Save mock ticket
    tickets = []
    if TICKETS_FILE.exists():
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                tickets = json.load(f)
        except Exception:
            tickets = []

    new_id = f"TCK-{1000 + len(tickets) + 1}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ticket_entry = {
        "ticket_id": new_id,
        "employee_id": employee_id,
        "employee_name": profile["full_name"],
        "ticket_type": ticket_type,
        "details": details,
        "status": "PENDING_MANAGER_APPROVAL",
        "created_at": now_iso,
        "action_safety": "MOCK_EXECUTED"
    }
    tickets.append(ticket_entry)

    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, indent=2)

    return {
        "status": "CREATED",
        "action_safety": "MOCK_EXECUTED",
        "ticket_id": new_id,
        "message": f"Mock HR ticket {new_id} successfully filed for {profile['full_name']} ({ticket_type}).",
        "ticket": ticket_entry
    }


def check_policy_compliance(action_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate compliance of proposed employee actions against policy guidelines:
    - 'remote_work': verifies probationary status, performance, workation <= 30 days.
    - 'expense_claim': checks meal daily limits ($125/day), receipts for >= $25.
    - 'pto_request': checks advance notice guidelines and balance sufficiency.
    """
    action_type = action_type.lower().strip()

    if action_type == "remote_work":
        emp_id = details.get("employee_id")
        emp = lookup_employee_profile(emp_id) if emp_id else {}
        workation_days = details.get("workation_days", 0)

        violations = []
        if emp and not emp.get("probation_completed", True):
            violations.append("Employee has not completed the 90-day probationary period.")
        if emp and "Improvement" in emp.get("performance_rating", ""):
            violations.append("Employee on PIP is not eligible for remote work.")
        if workation_days > 30:
            violations.append(f"Requested {workation_days} days exceeds the 30-day annual international workation cap.")
        if details.get("country", "").lower() in ["cuba", "iran", "north korea", "syria"]:
            violations.append(f"Work from {details.get('country')} is strictly prohibited under US sanctions.")

        return {
            "compliant": len(violations) == 0,
            "action_type": action_type,
            "violations": violations,
            "policy_reference": "POL-REMOTE-2024"
        }

    elif action_type == "expense_claim":
        meal_total = float(details.get("daily_meal_total", 0.0))
        has_receipt = details.get("has_itemized_receipt", True)
        is_during_pto = details.get("during_pto_or_workation", False)

        violations = []
        if is_during_pto:
            violations.append("Meals or travel during PTO or workations are strictly non-reimbursable.")
        if meal_total > 125.0:
            violations.append(f"Daily meal total of ${meal_total:.2f} exceeds the $125.00 daily limit.")
        if meal_total >= 25.0 and not has_receipt:
            violations.append("Itemized receipt is mandatory for expenses equal to or exceeding $25.00.")

        return {
            "compliant": len(violations) == 0,
            "action_type": action_type,
            "violations": violations,
            "policy_reference": "POL-EXP-2024"
        }

    elif action_type == "pto_request":
        days_requested = float(details.get("days_requested", 1.0))
        advance_notice_days = int(details.get("advance_notice_days", 0))
        emp_id = details.get("employee_id")
        balance = check_pto_balance(emp_id) if emp_id else {}

        violations = []
        if emp_id and "pto_balance_days" in balance and balance["pto_balance_days"] < days_requested:
            violations.append(f"Insufficient PTO balance ({balance['pto_balance_days']} days available vs {days_requested} requested).")
        if days_requested <= 2 and advance_notice_days < 2:
            violations.append("1-2 day PTO requires at least 48 hours (2 days) advance notice.")
        elif 3 <= days_requested <= 5 and advance_notice_days < 14:
            violations.append("3-5 day PTO requires at least 14 days advance notice.")
        elif days_requested > 5 and advance_notice_days < 30:
            violations.append("Leaves longer than 5 consecutive days require 30 days advance notice.")

        return {
            "compliant": len(violations) == 0,
            "action_type": action_type,
            "violations": violations,
            "policy_reference": "POL-PTO-2024"
        }

    return {
        "compliant": True,
        "action_type": action_type,
        "violations": [],
        "note": "No automated compliance rules defined for this action type."
    }


def draft_hr_email(recipient: str, subject: str, body_bullet_points: List[str]) -> Dict[str, Any]:
    """
    Draft a professional HR communication email to an employee or manager.
    """
    points = "\n".join([f"• {pt}" for pt in body_bullet_points])
    body = (
        f"Dear {recipient},\n\n"
        f"Thank you for contacting People Operations. Below is the summary of your inquiry and next steps:\n\n"
        f"{points}\n\n"
        f"If you have further questions, please reply directly to this message or contact HR at people-ops@globaltech.internal.\n\n"
        f"Best regards,\n"
        f"GlobalTech People Operations Team"
    )
    return {
        "recipient": recipient,
        "subject": subject,
        "email_body": body,
        "status": "DRAFTED"
    }


# Tool Definitions for MCP Registry
MCP_TOOL_DEFINITIONS = [
    {
        "name": "search_policy_documents",
        "description": "Search HR policy corpus using semantic retrieval. Returns matching policy sections with citations and snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or question about HR policies"},
                "top_k": {"type": "integer", "description": "Number of relevant chunks to retrieve", "default": 3},
                "filter_category": {"type": "string", "description": "Optional category filter"}
            },
            "required": ["query"]
        },
        "handler": search_policy_documents
    },
    {
        "name": "get_policy_section",
        "description": "Retrieve full text and metadata for a specific section within an HR policy document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "Document ID (e.g. POL-REMOTE-2024)"},
                "section_title": {"type": "string", "description": "Title or keyword of the section"}
            },
            "required": ["document_id", "section_title"]
        },
        "handler": get_policy_section
    },
    {
        "name": "lookup_employee_profile",
        "description": "Lookup structured employee details including role, department, tenure, manager, and onboarding status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID (e.g. EMP-101, EMP-102)"}
            },
            "required": ["employee_id"]
        },
        "handler": lookup_employee_profile
    },
    {
        "name": "check_pto_balance",
        "description": "Retrieve PTO and sick leave balances, accrual tiers, and rollover deadlines for an employee.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID (e.g. EMP-101)"}
            },
            "required": ["employee_id"]
        },
        "handler": check_pto_balance
    },
    {
        "name": "lookup_benefits_status",
        "description": "Retrieve employee healthcare, retirement 401(k), HSA/FSA, and wellness stipend election details.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID (e.g. EMP-101)"}
            },
            "required": ["employee_id"]
        },
        "handler": lookup_benefits_status
    },
    {
        "name": "create_mock_hr_ticket",
        "description": "Create a mock HR ticket. Action safety: requires explicit user confirmation (confirmed=True).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
                "ticket_type": {"type": "string", "description": "Type of ticket (e.g. PTO Request, Equipment Stipend)"},
                "details": {"type": "string", "description": "Description of the request"},
                "confirmed": {"type": "boolean", "description": "Explicit confirmation flag", "default": False}
            },
            "required": ["employee_id", "ticket_type", "details"]
        },
        "handler": create_mock_hr_ticket
    },
    {
        "name": "check_policy_compliance",
        "description": "Evaluate compliance of an employee action against policy rules (remote_work, expense_claim, pto_request).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "enum": ["remote_work", "expense_claim", "pto_request"]},
                "details": {"type": "object", "description": "Action specific attributes to validate"}
            },
            "required": ["action_type", "details"]
        },
        "handler": check_policy_compliance
    },
    {
        "name": "draft_hr_email",
        "description": "Draft a formal HR communication email to an employee or manager.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Recipient name or email"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body_bullet_points": {"type": "array", "items": {"type": "string"}, "description": "Key bullet points to include"}
            },
            "required": ["recipient", "subject", "body_bullet_points"]
        },
        "handler": draft_hr_email
    }
]

TOOL_MAP = {t["name"]: t["handler"] for t in MCP_TOOL_DEFINITIONS}
