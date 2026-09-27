import re
from typing import Dict, Any, List
from src.agents.state import HRAgentState, Citation
from src.mcp.client import MCPClient
from src.agents.llm_provider import LLMProvider

class OnboardingAgent:
    """
    Agent specialized in new hire onboarding workflows:
    - Inspecting onboarding checklist progress
    - Advising on home office equipment allowance and hardware setup
    - Guiding benefits enrollment deadlines
    - Drafting introductory emails and filing onboarding setup tickets
    """

    def __init__(self, mcp_client: MCPClient, llm: LLMProvider):
        self.mcp = mcp_client
        self.llm = llm

    def execute(self, state: HRAgentState) -> Dict[str, Any]:
        query = state["user_query"]
        updates: Dict[str, Any] = {
            "tool_calls": list(state.get("tool_calls", [])),
            "operational_trace": list(state.get("operational_trace", [])),
            "citations": list(state.get("citations", []))
        }

        # 1. Identify employee ID
        emp_id = state.get("employee_id")
        if not emp_id:
            emp_match = re.search(r"EMP-[A-Z0-9-]+", query, re.IGNORECASE)
            emp_id = emp_match.group(0).upper() if emp_match else "EMP-NEW-01"

        # 2. Lookup employee profile via MCP
        profile_res = self.mcp.call_tool("lookup_employee_profile", {"employee_id": emp_id})
        updates["tool_calls"].append(profile_res)
        updates["operational_trace"].append({
            "agent": "OnboardingAgent",
            "action": "lookup_employee_profile",
            "arguments": {"employee_id": emp_id},
            "status": profile_res["status"]
        })

        profile = profile_res.get("output", {})
        if "error" in profile:
            updates["final_response"] = (
                f"Could not locate an employee record for '{emp_id}'. "
                f"Please ensure you provide a valid Employee ID (e.g., EMP-NEW-01, EMP-102)."
            )
            return updates

        emp_name = profile.get("full_name", "Employee")
        role = profile.get("role", "New Hire")
        dept = profile.get("department", "General")
        checklist = profile.get("onboarding_checklist", {})

        # 3. Retrieve relevant onboarding policy rules via MCP
        policy_res = self.mcp.call_tool("search_policy_documents", {
            "query": "new hire onboarding equipment allowance benefits 30 days enrollment",
            "top_k": 2
        })
        updates["tool_calls"].append(policy_res)
        updates["operational_trace"].append({
            "agent": "OnboardingAgent",
            "action": "search_policy_documents",
            "arguments": {"query": "new hire onboarding equipment allowance benefits", "top_k": 2},
            "status": policy_res["status"]
        })

        if isinstance(policy_res.get("output"), list):
            for c in policy_res["output"]:
                updates["citations"].append({
                    "document_id": c.get("document_id", "POL-BEN-2024"),
                    "document_title": c.get("document_title", "HR Policy"),
                    "section_title": c.get("section_title", "Enrollment"),
                    "source_file": c.get("source_file", ""),
                    "snippet": c.get("snippet", ""),
                    "similarity_score": c.get("similarity_score", 0.0)
                })

        # 4. Check for drafting welcome email or filing setup ticket
        drafted_email = None
        if "email" in query.lower() or "welcome" in query.lower():
            email_res = self.mcp.call_tool("draft_hr_email", {
                "recipient": emp_name,
                "subject": f"Welcome to GlobalTech, {emp_name}! Your Onboarding Roadmap",
                "body_bullet_points": [
                    "Complete benefits election within 30 calendar days of hire (Day 1 coverage).",
                    "Submit home office equipment receipts up to $750 within 60 days via Concur.",
                    "Review and digitally sign the GlobalTech Code of Business Ethics.",
                    "Set up your direct deposit and security multi-factor authentication (MFA)."
                ]
            })
            updates["tool_calls"].append(email_res)
            drafted_email = email_res.get("output", {}).get("email_body")

        # 5. Format response
        pending_items = [k.replace("_", " ").title() for k, v in checklist.items() if v != "completed"]
        completed_items = [k.replace("_", " ").title() for k, v in checklist.items() if v == "completed"]

        response_parts = [
            f"### Onboarding Dossier & Status: {emp_name} ({emp_id})",
            f"**Role:** {role} | **Department:** {dept} | **Work Location:** {profile.get('work_location_type')}",
            "",
            "**Onboarding Progress Checklist:**",
            f"• **Completed ({len(completed_items)}):** {', '.join(completed_items) if completed_items else 'None'}",
            f"• **Pending Actions ({len(pending_items)}):** {', '.join(pending_items) if pending_items else 'All items completed!'}",
            "",
            "**Key Onboarding Policy Requirements:**",
            "1. **Benefits Enrollment Window:** New team members have **30 calendar days from start date** to finalize medical, dental, and vision elections ([POL-BEN-2024: 1. Enrollment Windows]).",
            "2. **Home Office Equipment Allowance:** Eligible for a one-time reimbursement of up to **$750 USD** for ergonomic office gear within 60 days of approval ([POL-REMOTE-2024: 3. Home Office Equipment Allowance]).",
            "3. **Code of Conduct:** Zero-tolerance anti-harassment policy requires digital signature ([POL-ETHICS-2024: 2. Equal Opportunity and Anti-Harassment]).",
            "4. **401(k) Match:** Immediate 100% vesting with up to 5% total employer matching ([POL-BEN-2024: 6. 401(k) Retirement Savings])."
        ]

        if drafted_email:
            response_parts.extend([
                "",
                "**Drafted Onboarding Welcome Email:**",
                "```text",
                drafted_email,
                "```"
            ])

        updates["final_response"] = "\n".join(response_parts)
        return updates
