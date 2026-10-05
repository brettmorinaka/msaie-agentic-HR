from typing import Dict, Any, List
from src.agents.state import HRAgentState, Citation
from src.mcp.client import MCPClient
from src.agents.llm_provider import LLMProvider

class PolicyRAGAgent:
    """
    Agent specialized in answering HR policy questions via semantic retrieval,
    extracting precise citations, and generating grounded responses with guardrails.
    """

    def __init__(self, mcp_client: MCPClient, llm: LLMProvider):
        self.mcp = mcp_client
        self.llm = llm

    def execute(self, state: HRAgentState) -> Dict[str, Any]:
        query = state["user_query"]
        updates: Dict[str, Any] = {
            "retrieved_chunks": [],
            "citations": [],
            "tool_calls": list(state.get("tool_calls", [])),
            "operational_trace": list(state.get("operational_trace", []))
        }

        # 1. Lookup active session employee profile if provided
        emp_id = state.get("employee_id")
        employee_context_str = ""

        if emp_id:
            profile_res = self.mcp.call_tool("lookup_employee_profile", {"employee_id": emp_id})
            updates["tool_calls"].append(profile_res)
            updates["operational_trace"].append({
                "agent": "PolicyRAGAgent",
                "action": "lookup_employee_profile",
                "arguments": {"employee_id": emp_id},
                "status": profile_res.get("status", "success")
            })

            profile = profile_res.get("output", {})
            if isinstance(profile, dict) and "employee_id" in profile and not profile.get("error"):
                tenure = profile.get("tenure_years", 0.0)
                if tenure < 2.0:
                    tier_str = "Tier 1 (0 to 2 years tenure): 15 days/year (120 hours, 5.0 hrs/pay period)"
                elif tenure <= 5.0:
                    tier_str = "Tier 2 (2 to 5 years tenure): 20 days/year (160 hours, 6.67 hrs/pay period)"
                else:
                    tier_str = "Tier 3 (5+ years tenure): 25 days/year (200 hours, 8.33 hrs/pay period)"

                benefits = profile.get("benefits_election", {})
                stipend_used = profile.get("equipment_stipend_used", 0.0)
                stipend_limit = profile.get("equipment_stipend_limit", 750.0)
                remaining_stipend = max(0.0, stipend_limit - stipend_used)

                employee_context_str = (
                    f"Employee ID: {profile.get('employee_id')}\n"
                    f"Full Name: {profile.get('full_name')}\n"
                    f"Role: {profile.get('role')} in {profile.get('department')} (Manager: {profile.get('manager_name')})\n"
                    f"Hire Date: {profile.get('hire_date')} (Tenure: {tenure} years, Probation Completed: {'Yes' if profile.get('probation_completed') else 'No'})\n"
                    f"Work Location: {profile.get('work_location_type')} ({profile.get('residence_state')})\n"
                    f"Current PTO Balance: {profile.get('pto_balance_days')} days (Paid Sick Leave: {profile.get('sick_balance_days')} days)\n"
                    f"PTO Accrual Tier: {tier_str}\n"
                    f"Health Benefits: Medical: {benefits.get('medical_plan', 'None')}, Dental: {benefits.get('dental_plan', 'None')}, Vision: {benefits.get('vision_plan', 'None')}\n"
                    f"Home Office Equipment Allowance: ${remaining_stipend:.2f} remaining out of ${stipend_limit:.2f}"
                )

        # 2. Query decomposition for multi-topic/multi-document queries
        subqueries = [query]
        q_lower = query.lower()
        if ("pto" in q_lower or "vacation" in q_lower) and ("expense" in q_lower or "meal" in q_lower) and ("remote" in q_lower or "workation" in q_lower):
            subqueries = [
                "temporary international remote work workation policy 30 days limit",
                "strictly non reimbursable expenditures travel expense meals"
            ]
        elif ("stipend" in q_lower or "allowance" in q_lower) and "remote" in q_lower:
            subqueries = ["home office equipment allowance stipend for remote work"]
        elif ("pto" in q_lower or "vacation" in q_lower) and not any(w in q_lower for w in ["international", "france", "rollover", "parental"]):
            subqueries = ["annual PTO accrual tiers rollover guidelines notice process"]

        retrieved_all = []
        for sq in subqueries:
            tool_res = self.mcp.call_tool("search_policy_documents", {"query": sq, "top_k": 3})
            updates["tool_calls"].append(tool_res)
            updates["operational_trace"].append({
                "agent": "PolicyRAGAgent",
                "action": "search_policy_documents",
                "arguments": {"query": sq, "top_k": 3},
                "status": tool_res["status"],
                "results_count": len(tool_res.get("output", [])) if isinstance(tool_res.get("output"), list) else 0
            })
            if isinstance(tool_res.get("output"), list):
                retrieved_all.extend(tool_res["output"])

        # Deduplicate chunks by chunk_id
        seen_chunks = set()
        deduped_chunks = []
        citations: List[Citation] = []

        for chk in retrieved_all:
            cid = chk.get("chunk_id")
            if cid and cid not in seen_chunks:
                seen_chunks.add(cid)
                deduped_chunks.append(chk)
                citations.append({
                    "document_id": chk.get("document_id", "UNKNOWN"),
                    "document_title": chk.get("document_title", "HR Policy"),
                    "section_title": chk.get("section_title", "General"),
                    "source_file": chk.get("source_file", ""),
                    "snippet": chk.get("snippet", ""),
                    "similarity_score": chk.get("similarity_score", 0.0)
                })

        updates["retrieved_chunks"] = deduped_chunks
        updates["citations"] = citations

        # Synthesize answer using retrieved context
        context_str = "\n\n".join([
            f"Document: {c['document_title']} ({c['document_id']})\n"
            f"Section: {c['section_title']}\n"
            f"Snippet: {c['snippet']}\n"
            f"Content: {c['text']}"
            for c in deduped_chunks[:4]
        ])

        if employee_context_str:
            system_prompt = (
                "You are the GlobalTech Senior HR Policy Advisor. Answer the employee's inquiry strictly based on "
                "the provided policy context. When an employee profile is provided from the active session, personalize "
                "the response specifically for this employee: address their situation directly (including their tenure, "
                "accrual tier, current balance, benefits plan, or work location as applicable), while citing document IDs "
                "and section titles for all factual statements. Separate verified policy facts from operational HR recommendations."
            )
            user_prompt = (
                f"Active Employee Profile:\n{employee_context_str}\n\n"
                f"User Question: {query}\n\n"
                f"Retrieved Policy Documents:\n{context_str}"
            )
        else:
            system_prompt = (
                "You are the GlobalTech Senior HR Policy Advisor. Answer the employee's inquiry strictly based on "
                "the provided policy context. Cite document IDs and section titles for all factual statements. "
                "Separate verified policy facts from operational HR recommendations."
            )
            user_prompt = f"User Question: {query}\n\nRetrieved Policy Documents:\n{context_str}"

        answer = self.llm.generate(user_prompt, system_prompt)
        updates["final_response"] = answer
        return updates
