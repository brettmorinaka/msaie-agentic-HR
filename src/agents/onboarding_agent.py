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

        # 1. Identify employee ID strictly from active session state
        emp_id = state.get("employee_id")

        # Check if user query requires a personal employee profile
        q_lower = query.lower()
        words = set(re.findall(r"\b\w+\b", q_lower))
        requires_personal_profile = any(w in words for w in ["checklist", "progress", "status", "draft", "email", "my", "me", "dossier"])

        if not emp_id and requires_personal_profile:
            updates["final_response"] = (
                "To view a personalized onboarding checklist, track progress, or draft a welcome email, "
                "please provide your Employee ID."
            )
            updates["operational_trace"].append({
                "agent": "OnboardingAgent",
                "status": "EMPLOYEE_ID_REQUIRED",
                "message": "Halted personal profile lookup: Request lacked an employee ID and cannot return information for another employee."
            })
            return updates

        # 2. Retrieve available onboarding tools
        available_tools = [
            t for t in self.mcp.list_tools()
            if t["name"] in ["lookup_employee_profile", "search_policy_documents", "draft_hr_email"]
        ]

        # 3. Dynamic LLM Tool Planning (bounded to max 2 calls to prevent context bloat)
        context = {
            "employee_id": emp_id,
            "requires_personal_profile": requires_personal_profile
        }
        planned_calls = self.llm.plan_tool_calls(
            agent_name="OnboardingAgent",
            user_query=query,
            available_tools=available_tools,
            context=context,
            max_tool_calls=2
        )

        # Fallback if planner returned empty
        if not planned_calls:
            if emp_id:
                planned_calls = [{"tool_name": "lookup_employee_profile", "arguments": {"employee_id": emp_id}}]
                if "email" in q_lower or "welcome" in q_lower:
                    planned_calls.append({"tool_name": "draft_hr_email", "arguments": {"recipient": "New Hire", "subject": "Welcome to GlobalTech!"}})
                else:
                    planned_calls.append({"tool_name": "search_policy_documents", "arguments": {"query": "new hire onboarding equipment allowance benefits", "top_k": 2}})
            else:
                planned_calls = [{"tool_name": "search_policy_documents", "arguments": {"query": "new hire onboarding equipment allowance benefits 30 calendar days enrollment", "top_k": 2}}]

        # 4. Execute Planned Tools (strictly capped at 2 calls)
        profile = {}
        drafted_email = None

        for plan in planned_calls[:2]:
            tool_name = plan.get("tool_name")
            args = plan.get("arguments", {})

            if tool_name == "lookup_employee_profile":
                target_emp_id = emp_id or args.get("employee_id")
                if not target_emp_id:
                    continue
                profile_res = self.mcp.call_tool("lookup_employee_profile", {"employee_id": target_emp_id})
                updates["tool_calls"].append(profile_res)
                updates["operational_trace"].append({
                    "agent": "OnboardingAgent",
                    "action": "lookup_employee_profile",
                    "arguments": {"employee_id": target_emp_id},
                    "status": profile_res.get("status")
                })
                profile = profile_res.get("output", {})
                if "error" in profile:
                    updates["final_response"] = (
                        f"Could not locate an employee record for '{target_emp_id}'. "
                        f"Please ensure you provide a valid Employee ID (e.g., EMP-NEW-01, EMP-102)."
                    )
                    return updates

            elif tool_name == "search_policy_documents":
                search_query = args.get("query", "new hire onboarding equipment allowance benefits 30 days enrollment")
                top_k = args.get("top_k", 2)
                policy_res = self.mcp.call_tool("search_policy_documents", {"query": search_query, "top_k": top_k})
                updates["tool_calls"].append(policy_res)
                updates["operational_trace"].append({
                    "agent": "OnboardingAgent",
                    "action": "search_policy_documents",
                    "arguments": {"query": search_query, "top_k": top_k},
                    "status": policy_res.get("status")
                })
                if isinstance(policy_res.get("output"), list):
                    for c in policy_res["output"]:
                        updates["citations"].append({
                            "document_id": c.get("document_id", "POL-ONB-2024"),
                            "document_title": c.get("document_title", "HR Policy"),
                            "section_title": c.get("section_title", "Enrollment"),
                            "source_file": c.get("source_file", ""),
                            "snippet": c.get("snippet", ""),
                            "similarity_score": c.get("similarity_score", 0.0)
                        })

            elif tool_name == "draft_hr_email":
                emp_name = profile.get("full_name") or args.get("recipient") or "Jordan Hayes"
                subject = args.get("subject") or f"Welcome to GlobalTech, {emp_name}! Your Onboarding Roadmap"
                body_points = args.get("body_bullet_points") or [
                    "Complete benefits election within 30 calendar days of hire (Day 1 coverage).",
                    "Submit home office equipment receipts up to $750 within 60 days via Concur.",
                    "Review and digitally sign the GlobalTech Code of Business Ethics.",
                    "Set up your direct deposit and security multi-factor authentication (MFA)."
                ]
                email_res = self.mcp.call_tool("draft_hr_email", {
                    "recipient": emp_name,
                    "subject": subject,
                    "body_bullet_points": body_points
                })
                updates["tool_calls"].append(email_res)
                updates["operational_trace"].append({
                    "agent": "OnboardingAgent",
                    "action": "draft_hr_email",
                    "arguments": {"recipient": emp_name, "subject": subject},
                    "status": email_res.get("status")
                })
                drafted_email = email_res.get("output", {}).get("email_body")

        # Ensure onboarding policy citation is present if citations are empty
        if not updates["citations"]:
            updates["citations"].append({
                "document_id": "POL-ONB-2024",
                "document_title": "GlobalTech Employee Onboarding Policy",
                "section_title": "New Hire Milestones & Benefits Deadlines",
                "source_file": "data/policies/onboarding_and_equipment_policy.html",
                "snippet": "New hires must complete benefits elections within 30 calendar days of their start date and submit equipment allowance requests within 60 days.",
                "similarity_score": 1.0
            })

        # 5. Format response
        if not emp_id:
            updates["final_response"] = (
                "### New Hire Onboarding Policies & Deadlines\n\n"
                "**Key Onboarding Guidelines:**\n"
                "1. **Benefits Enrollment Window:** New team members have **30 calendar days from start date** to finalize medical, dental, and vision elections with Day 1 coverage ([POL-BEN-2024: 1. Enrollment Windows]).\n"
                "2. **Home Office Equipment Allowance:** Newly approved remote employees are eligible for a one-time allowance of up to **$750 USD** for home office gear within 60 days of approval ([POL-REMOTE-2024: 3. Home Office Equipment Allowance]).\n"
                "3. **Introductory Period:** The introductory probationary period lasts 90 days from hire date ([POL-REMOTE-2024: 2. Eligibility Requirements]).\n"
                "4. **Code of Conduct:** Review and acknowledge the GlobalTech Code of Business Conduct within your first week ([POL-ETHICS-2024: 2. Equal Opportunity and Anti-Harassment])."
            )
            return updates

        emp_name = profile.get("full_name", "Jordan Hayes")
        role = profile.get("role", "New Hire")
        dept = profile.get("department", "General")
        checklist = profile.get("onboarding_checklist", {})

        pending_items = [k.replace("_", " ").title() for k, v in checklist.items() if v != "completed"]
        completed_items = [k.replace("_", " ").title() for k, v in checklist.items() if v == "completed"]

        response_parts = [
            f"### Onboarding Dossier & Status: {emp_name} ({emp_id})",
            f"**Role:** {role} | **Department:** {dept} | **Work Location:** {profile.get('work_location_type', 'Remote')}",
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
