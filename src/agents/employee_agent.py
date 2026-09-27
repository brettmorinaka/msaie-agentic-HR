import re
from typing import Dict, Any, List
from src.agents.state import HRAgentState, Citation
from src.mcp.client import MCPClient
from src.agents.llm_provider import LLMProvider

class EmployeeToolAgent:
    """
    Agent specialized in employee self-service and tool execution workflows:
    - Checking PTO balances and leave compliance
    - Evaluating remote work eligibility and equipment allowances
    - Validating expense compliance against per diem limits
    - Safe ticket creation with guardrails requiring explicit user confirmation
    """

    def __init__(self, mcp_client: MCPClient, llm: LLMProvider):
        self.mcp = mcp_client
        self.llm = llm

    def execute(self, state: HRAgentState) -> Dict[str, Any]:
        query = state["user_query"]
        q_lower = query.lower()
        confirmed = state.get("confirmed", False)

        updates: Dict[str, Any] = {
            "tool_calls": list(state.get("tool_calls", [])),
            "operational_trace": list(state.get("operational_trace", [])),
            "citations": list(state.get("citations", [])),
            "action_safety_status": "SAFE"
        }

        # 1. Identify employee ID
        emp_id = state.get("employee_id")
        if not emp_id:
            emp_match = re.search(r"EMP-[A-Z0-9-]+", query, re.IGNORECASE)
            emp_id = emp_match.group(0).upper() if emp_match else "EMP-101"

        # Lookup employee profile
        profile_res = self.mcp.call_tool("lookup_employee_profile", {"employee_id": emp_id})
        updates["tool_calls"].append(profile_res)
        profile = profile_res.get("output", {})
        emp_name = profile.get("full_name", "Employee")

        # Workflow 1: PTO Balance Check & Leave Request Guidance
        if "pto" in q_lower or "vacation" in q_lower or "time off" in q_lower:
            balance_res = self.mcp.call_tool("check_pto_balance", {"employee_id": emp_id})
            updates["tool_calls"].append(balance_res)
            balance_info = balance_res.get("output", {})

            # Extract requested days if present
            days_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:day|days)", q_lower)
            days_requested = float(days_match.group(1)) if days_match else 0.0

            # Check compliance if days requested
            compliance_info = None
            if days_requested > 0:
                comp_res = self.mcp.call_tool("check_policy_compliance", {
                    "action_type": "pto_request",
                    "details": {
                        "employee_id": emp_id,
                        "days_requested": days_requested,
                        "advance_notice_days": 14
                    }
                })
                updates["tool_calls"].append(comp_res)
                compliance_info = comp_res.get("output", {})

            # Check if user wants to file/submit a ticket or confirms it
            ticket_res = None
            should_file = confirmed or any(w in q_lower for w in ["submit", "submission", "book", "request", "file", "create ticket", "confirm"])
            if should_file and days_requested > 0:
                ticket_res = self.mcp.call_tool("create_mock_hr_ticket", {
                    "employee_id": emp_id,
                    "ticket_type": "PTO Request",
                    "details": f"Requesting {days_requested} days PTO",
                    "confirmed": confirmed
                })
                updates["tool_calls"].append(ticket_res)
                if ticket_res.get("status") == "confirmation_required":
                    updates["action_safety_status"] = "CONFIRMATION_REQUIRED"
                else:
                    updates["action_safety_status"] = "MOCK_EXECUTED"

            # Retrieve citation
            policy_res = self.mcp.call_tool("search_policy_documents", {"query": "PTO advance notice rollover rules", "top_k": 2})
            updates["tool_calls"].append(policy_res)
            if isinstance(policy_res.get("output"), list):
                for c in policy_res["output"]:
                    updates["citations"].append({
                        "document_id": c.get("document_id", "POL-PTO-2024"),
                        "document_title": c.get("document_title", "HR Policy"),
                        "section_title": c.get("section_title", "PTO Policy"),
                        "source_file": c.get("source_file", ""),
                        "snippet": c.get("snippet", ""),
                        "similarity_score": c.get("similarity_score", 0.0)
                    })

            # Format PTO response
            res_lines = [
                f"### PTO & Leave Dossier: {emp_name} ({emp_id})",
                f"• **Current PTO Balance:** **{balance_info.get('pto_balance_days', 0)} days**",
                f"• **Paid Sick Leave:** **{balance_info.get('sick_balance_days', 0)} days**",
                f"• **Accrual Tier:** {balance_info.get('accrual_tier', 'Tier 1')}",
                f"• **Rollover Policy:** Up to 5 days rollover, expiring March 31 ([POL-PTO-2024: 4. Year-End Rollover]).",
                ""
            ]

            if days_requested > 0:
                res_lines.append(f"**Requested Leave Evaluation ({days_requested} days):**")
                if compliance_info and compliance_info.get("compliant"):
                    res_lines.append("✓ **Compliance Check Passed:** Sufficient balance and meets advance notice policy.")
                elif compliance_info:
                    res_lines.append(f"⚠️ **Policy Warnings:** {'; '.join(compliance_info.get('violations', []))}")
                res_lines.append("")

            if ticket_res:
                t_out = ticket_res.get("output", {})
                if t_out.get("status") == "CONFIRMATION_REQUIRED":
                    res_lines.extend([
                        "🔒 **Action Safety Guardrail Triggered:**",
                        f"{t_out.get('message')}",
                        "",
                        "👉 *To proceed with filing this ticket, please confirm by replying: 'Confirm submission of PTO ticket'.*"
                    ])
                elif t_out.get("status") == "CREATED":
                    res_lines.extend([
                        "✅ **Mock HR Ticket Filed Successfully!**",
                        f"• **Ticket ID:** {t_out.get('ticket_id')}",
                        f"• **Type:** {t_out.get('ticket', {}).get('ticket_type')}",
                        f"• **Status:** {t_out.get('ticket', {}).get('status')}",
                        f"• **Action Status:** Mock executed without affecting live corporate payroll."
                    ])

            updates["final_response"] = "\n".join(res_lines)
            return updates

        # Workflow 2: Remote Work & Equipment Allowance Check
        elif "remote" in q_lower or "equipment" in q_lower or "stipend" in q_lower:
            stipend_used = profile.get("equipment_stipend_used", 0.0)
            stipend_limit = profile.get("equipment_stipend_limit", 750.0)
            remaining_stipend = max(0.0, stipend_limit - stipend_used)
            probation_done = profile.get("probation_completed", True)
            perf_rating = profile.get("performance_rating", "Meets Expectations")

            # Check compliance
            comp_res = self.mcp.call_tool("check_policy_compliance", {
                "action_type": "remote_work",
                "details": {
                    "employee_id": emp_id,
                    "workation_days": 10
                }
            })
            updates["tool_calls"].append(comp_res)
            comp_info = comp_res.get("output", {})

            # Citations
            policy_res = self.mcp.call_tool("search_policy_documents", {"query": "equipment stipend allowance remote eligibility", "top_k": 2})
            updates["tool_calls"].append(policy_res)
            if isinstance(policy_res.get("output"), list):
                for c in policy_res["output"]:
                    updates["citations"].append({
                        "document_id": c.get("document_id", "POL-REMOTE-2024"),
                        "document_title": c.get("document_title", "HR Policy"),
                        "section_title": c.get("section_title", "Equipment Allowance"),
                        "source_file": c.get("source_file", ""),
                        "snippet": c.get("snippet", ""),
                        "similarity_score": c.get("similarity_score", 0.0)
                    })

            res_lines = [
                f"### Remote Work & Equipment Status: {emp_name} ({emp_id})",
                f"• **Current Location Type:** {profile.get('work_location_type', 'Hybrid')}",
                f"• **Probation Completed:** {'Yes' if probation_done else 'No (in 90-day probationary period)'}",
                f"• **Performance Rating:** {perf_rating}",
                f"• **Home Office Equipment Allowance:** **${remaining_stipend:.2f} remaining** (out of ${stipend_limit:.2f} max allowance)",
                f"• **Monthly Internet Subsidy:** $50/month active in payroll",
                "",
                "**Policy Evaluation:**",
                f"• **Eligibility:** {'Eligible for full remote arrangement' if probation_done and 'Improvement' not in perf_rating else 'Requires manager exception/probation completion'} ([POL-REMOTE-2024: 2. Eligibility Requirements]).",
                f"• **Expense Claim Rules:** Equipment must be submitted with itemized receipts via Concur within 60 days of approval ([POL-REMOTE-2024: 3.1])."
            ]

            updates["final_response"] = "\n".join(res_lines)
            return updates

        # Workflow 3: Benefits Lookup
        elif "benefit" in q_lower or "insurance" in q_lower or "wellness" in q_lower or "401k" in q_lower:
            ben_res = self.mcp.call_tool("lookup_benefits_status", {"employee_id": emp_id})
            updates["tool_calls"].append(ben_res)
            b_info = ben_res.get("output", {})
            elections = b_info.get("benefits", {})

            res_lines = [
                f"### Benefits Status Dossier: {emp_name} ({emp_id})",
                f"• **Medical Insurance:** {elections.get('medical_plan', 'Not Enrolled')}",
                f"• **Dental:** {elections.get('dental_plan', 'Not Enrolled')}",
                f"• **Vision:** {elections.get('vision_plan', 'Not Enrolled')}",
                f"• **401(k) Contribution:** {elections.get('retirement_401k_contribution_pct', 0.0)}% (Employer matches up to 5% with immediate vesting)",
                f"• **Wellness Subsidy Remaining:** **${b_info.get('wellness_stipend_remaining', 600.0):.2f}** for current year ([POL-BEN-2024: 5. Mental Health and Wellness Stipend])"
            ]
            updates["final_response"] = "\n".join(res_lines)
            return updates

        # Workflow 4: Expense Compliance Evaluation
        elif "expense" in q_lower or "per diem" in q_lower or "claim" in q_lower:
            meal_amt_match = re.search(r"\$?(\d+(?:\.\d+)?)", query)
            meal_amt = float(meal_amt_match.group(1)) if meal_amt_match else 150.0
            has_rcpt = not ("without receipt" in q_lower or "no receipt" in q_lower)

            comp_res = self.mcp.call_tool("check_policy_compliance", {
                "action_type": "expense_claim",
                "details": {
                    "daily_meal_total": meal_amt,
                    "has_itemized_receipt": has_rcpt,
                    "during_pto_or_workation": False
                }
            })
            updates["tool_calls"].append(comp_res)
            c_info = comp_res.get("output", {})

            policy_res = self.mcp.call_tool("search_policy_documents", {"query": "daily meal allowance per diem receipt limit", "top_k": 2})
            updates["tool_calls"].append(policy_res)
            if isinstance(policy_res.get("output"), list):
                for c in policy_res["output"]:
                    updates["citations"].append({
                        "document_id": c.get("document_id", "POL-EXP-2024"),
                        "document_title": c.get("document_title", "HR Policy"),
                        "section_title": c.get("section_title", "Daily Meal Allowances"),
                        "source_file": c.get("source_file", ""),
                        "snippet": c.get("snippet", ""),
                        "similarity_score": c.get("similarity_score", 0.0)
                    })

            res_lines = [
                f"### Expense Policy Compliance Evaluation: {emp_name} ({emp_id})",
                f"• **Proposed Daily Meal Claim:** ${meal_amt:.2f}",
                f"• **Receipt Attached:** {'Yes' if has_rcpt else 'No (Missing itemized receipt)'}",
                "",
                "**Compliance Audit Findings:**"
            ]
            if c_info.get("compliant"):
                res_lines.append("✓ **Status: Fully Compliant** with GlobalTech Travel & Expense Reimbursement Policy.")
            else:
                res_lines.append("❌ **Status: Non-Compliant with Policy**")
                for v in c_info.get("violations", []):
                    res_lines.append(f"• ⚠️ {v}")

            res_lines.extend([
                "",
                "**Policy References:**",
                "• Daily meal allowance ceiling is **$125.00 USD** ([POL-EXP-2024: 3. Daily Meal Allowances]).",
                "• Itemized receipts are mandatory for all transactions equal to or exceeding **$25.00 USD** ([POL-EXP-2024: 5. Expense Submission Deadlines])."
            ])
            updates["final_response"] = "\n".join(res_lines)
            return updates

        # Generic employee lookup fallback
        res_lines = [
            f"### Employee Directory Record: {emp_name} ({emp_id})",
            f"• **Role:** {profile.get('role')}",
            f"• **Department:** {profile.get('department')}",
            f"• **Manager:** {profile.get('manager_name')}",
            f"• **Work Location:** {profile.get('work_location_type')}",
            f"• **PTO Balance:** {profile.get('pto_balance_days')} days"
        ]
        updates["final_response"] = "\n".join(res_lines)
        return updates
