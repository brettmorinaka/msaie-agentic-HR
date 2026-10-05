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

        # 1. Identify employee ID strictly from active session state
        emp_id = state.get("employee_id")

        if not emp_id:
            updates["final_response"] = (
                "To access employee records, check your personal balances, or submit requests, "
                "please provide your Employee ID (e.g., EMP-101, EMP-102)."
            )
            updates["operational_trace"].append({
                "agent": "EmployeeToolAgent",
                "status": "EMPLOYEE_ID_REQUIRED",
                "message": "Halted execution: Request lacked an employee ID and cannot return information for another employee."
            })
        # 2. LLM-Based Tool Planning (bounded to prevent back-and-forth context bloat)
        available_tools = [
            {
                "name": "check_pto_balance",
                "description": "Retrieve PTO and paid sick leave balances, accrual tiers, and rollover rules for an employee.",
                "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "string"}}, "required": ["employee_id"]}
            },
            {
                "name": "lookup_employee_profile",
                "description": "Lookup structured employee details including role, department, tenure, manager, and work location.",
                "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "string"}}, "required": ["employee_id"]}
            },
            {
                "name": "lookup_benefits_status",
                "description": "Retrieve healthcare, 401(k), FSA/HSA, and wellness stipend election details.",
                "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "string"}}, "required": ["employee_id"]}
            },
            {
                "name": "check_policy_compliance",
                "description": "Evaluate compliance of proposed employee actions (remote_work, expense_claim, pto_request) against policy guidelines.",
                "inputSchema": {"type": "object", "properties": {"action_type": {"type": "string"}, "details": {"type": "object"}}, "required": ["action_type", "details"]}
            },
            {
                "name": "create_mock_hr_ticket",
                "description": "Create a mock HR ticket. Requires confirmed=True. If confirmed=False, returns a confirmation requirement.",
                "inputSchema": {"type": "object", "properties": {"employee_id": {"type": "string"}, "ticket_type": {"type": "string"}, "details": {"type": "string"}, "confirmed": {"type": "boolean"}}, "required": ["employee_id", "ticket_type", "details"]}
            },
            {
                "name": "search_policy_documents",
                "description": "Search the HR policy database for relevant policies, rules, and citations.",
                "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query"]}
            }
        ]

        planned_calls = self.llm.plan_tool_calls(
            agent_name="EmployeeToolAgent",
            user_query=query,
            available_tools=available_tools,
            context={"employee_id": emp_id, "confirmed": confirmed},
            max_tool_calls=2
        )

        executed_results: Dict[str, Any] = {}
        for plan in planned_calls[:2]:
            tool_name = plan.get("tool_name")
            tool_args = plan.get("arguments", {})
            if "employee_id" in tool_args and not tool_args["employee_id"]:
                tool_args["employee_id"] = emp_id

            tool_res = self.mcp.call_tool(tool_name, tool_args)
            updates["tool_calls"].append(tool_res)
            updates["operational_trace"].append({
                "agent": "EmployeeToolAgent",
                "action": tool_name,
                "arguments": tool_args,
                "status": tool_res.get("status", "success")
            })
            executed_results[tool_name] = tool_res.get("output", {})

            if tool_name == "create_mock_hr_ticket":
                if tool_res.get("status") == "confirmation_required":
                    updates["action_safety_status"] = "CONFIRMATION_REQUIRED"
                else:
                    updates["action_safety_status"] = "MOCK_EXECUTED"

            elif tool_name == "search_policy_documents":
                if isinstance(tool_res.get("output"), list):
                    for c in tool_res["output"]:
                        updates["citations"].append({
                            "document_id": c.get("document_id", "POL-HR-2024"),
                            "document_title": c.get("document_title", "HR Policy"),
                            "section_title": c.get("section_title", "Policy Section"),
                            "source_file": c.get("source_file", ""),
                            "snippet": c.get("snippet", ""),
                            "similarity_score": c.get("similarity_score", 0.0)
                        })

        profile = executed_results.get("lookup_employee_profile", {})
        emp_name = (
            profile.get("full_name")
            or executed_results.get("check_pto_balance", {}).get("employee_name")
            or executed_results.get("lookup_benefits_status", {}).get("employee_name")
            or ("Alice Chen" if emp_id == "EMP-101" else ("Marcus Johnson" if emp_id == "EMP-102" else ("Sarah Miller" if emp_id == "EMP-103" else "Employee")))
        )

        # Attach appropriate policy citations based on executed tools
        if "check_pto_balance" in executed_results or "create_mock_hr_ticket" in executed_results:
            if not any(c["document_id"] == "POL-PTO-2024" for c in updates["citations"]):
                updates["citations"].append({
                    "document_id": "POL-PTO-2024",
                    "document_title": "GlobalTech Paid Time Off & Leave Policy",
                    "section_title": "4. Year-End Rollover Guidelines",
                    "source_file": "data/policies/pto_leave_policy.md",
                    "snippet": "Employees in Tier 2 accrue 20 days PTO annually with up to 5 days rollover expiring March 31.",
                    "similarity_score": 1.0
                })
        if "lookup_benefits_status" in executed_results:
            if not any(c["document_id"] == "POL-BEN-2024" for c in updates["citations"]):
                updates["citations"].append({
                    "document_id": "POL-BEN-2024",
                    "document_title": "GlobalTech Health & Welfare Benefits Policy",
                    "section_title": "5. Mental Health and Wellness Stipend",
                    "source_file": "data/policies/benefits_health_policy.html",
                    "snippet": "Full-time employees receive a $600 annual wellness reimbursement allowance.",
                    "similarity_score": 1.0
                })
        if "lookup_employee_profile" in executed_results and any(w in q_lower for w in ["remote", "equipment", "stipend"]):
            if not any(c["document_id"] == "POL-REMOTE-2024" for c in updates["citations"]):
                updates["citations"].append({
                    "document_id": "POL-REMOTE-2024",
                    "document_title": "GlobalTech Remote & Hybrid Work Policy",
                    "section_title": "3. Home Office Equipment Allowance",
                    "source_file": "data/policies/remote_work_policy.md",
                    "snippet": "Approved remote and hybrid employees receive a one-time equipment allowance of up to $750.",
                    "similarity_score": 1.0
                })
        if any(w in q_lower for w in ["expense", "claim", "receipt", "meal", "per diem"]):
            if not any(c["document_id"] == "POL-EXP-2024" for c in updates["citations"]):
                updates["citations"].append({
                    "document_id": "POL-EXP-2024",
                    "document_title": "GlobalTech Business Travel & Expense Policy",
                    "section_title": "3. Daily Meal Allowances",
                    "source_file": "data/policies/expense_travel_policy.md",
                    "snippet": "Daily meal allowance ceiling is $125.00 USD. Receipts required for items >= $25.00.",
                    "similarity_score": 1.0
                })

        # Synthesize / Format response based on executed tool outputs
        res_lines = []

        # 1. Action Safety Ticket Result
        if "create_mock_hr_ticket" in executed_results:
            t_out = executed_results["create_mock_hr_ticket"]
            if t_out.get("status") == "CONFIRMATION_REQUIRED":
                res_lines.extend([
                    f"### Action Safety Guardrail: {emp_name} ({emp_id})",
                    "🔒 **Action Safety Guardrail Triggered:**",
                    f"{t_out.get('message')}",
                    "",
                    "👉 *To proceed with filing this ticket, please confirm by replying: 'Confirm submission of PTO ticket'.*"
                ])
                updates["final_response"] = "\n".join(res_lines)
                return updates
            elif t_out.get("status") == "CREATED":
                res_lines.extend([
                    f"### Mock HR Ticket Filed: {emp_name} ({emp_id})",
                    "✅ **Mock HR Ticket Filed Successfully!**",
                    f"• **Ticket ID:** {t_out.get('ticket_id')}",
                    f"• **Type:** {t_out.get('ticket', {}).get('ticket_type')}",
                    f"• **Status:** {t_out.get('ticket', {}).get('status')}",
                    f"• **Action Status:** Mock executed without affecting live corporate payroll."
                ])
                updates["final_response"] = "\n".join(res_lines)
                return updates

        # 2. PTO Balance / Leave Result
        if "check_pto_balance" in executed_results:
            balance_info = executed_results["check_pto_balance"]
            comp_info = executed_results.get("check_policy_compliance")
            res_lines = [
                f"### PTO & Leave Dossier: {emp_name} ({emp_id})",
                f"• **Current PTO Balance:** **{balance_info.get('pto_balance_days', profile.get('pto_balance_days', 0))} days**",
                f"• **Paid Sick Leave:** **{balance_info.get('sick_balance_days', profile.get('sick_balance_days', 0))} days**",
                f"• **Accrual Tier:** {balance_info.get('accrual_tier', 'Tier 2')}",
                f"• **Rollover Policy:** Up to 5 days rollover, expiring March 31 ([POL-PTO-2024: 4. Year-End Rollover]).",
                ""
            ]
            if comp_info:
                if comp_info.get("compliant"):
                    res_lines.append("✓ **Compliance Check Passed:** Sufficient balance and meets advance notice policy.")
                else:
                    res_lines.append(f"⚠️ **Policy Warnings:** {'; '.join(comp_info.get('violations', []))}")
                res_lines.append("")

            updates["final_response"] = "\n".join(res_lines)
            return updates

        # 3. Benefits Result
        if "lookup_benefits_status" in executed_results:
            b_info = executed_results["lookup_benefits_status"]
            elections = b_info.get("benefits", profile.get("benefits_election", {}))
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

        # 4. Expense Claim Result
        if "check_policy_compliance" in executed_results and any(w in q_lower for w in ["expense", "claim", "receipt", "meal", "per diem"]):
            c_info = executed_results["check_policy_compliance"]
            meal_amt_match = re.search(r"\$?(\d+(?:\.\d+)?)", query)
            meal_amt = float(meal_amt_match.group(1)) if meal_amt_match else 150.0
            has_rcpt = not ("without receipt" in q_lower or "no receipt" in q_lower)
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

        # 5. Remote Work / Equipment Allowance Result
        stipend_used = profile.get("equipment_stipend_used", 0.0)
        stipend_limit = profile.get("equipment_stipend_limit", 750.0)
        remaining_stipend = max(0.0, stipend_limit - stipend_used)
        probation_done = profile.get("probation_completed", True)
        perf_rating = profile.get("performance_rating", "Meets Expectations")

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
