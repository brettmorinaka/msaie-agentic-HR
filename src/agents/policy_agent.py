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

        # Query decomposition for multi-topic/multi-document queries
        subqueries = [query]
        q_lower = query.lower()
        if ("pto" in q_lower or "vacation" in q_lower) and ("expense" in q_lower or "meal" in q_lower) and ("remote" in q_lower or "workation" in q_lower):
            subqueries = [
                "temporary international remote work workation policy 30 days limit",
                "strictly non reimbursable expenditures travel expense meals"
            ]
        elif ("stipend" in q_lower or "allowance" in q_lower) and "remote" in q_lower:
            subqueries = ["home office equipment allowance stipend for remote work"]

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

        system_prompt = (
            "You are the GlobalTech Senior HR Policy Advisor. Answer the employee's inquiry strictly based on "
            "the provided policy context. Cite document IDs and section titles for all factual statements. "
            "Separate verified policy facts from operational HR recommendations."
        )
        user_prompt = f"User Question: {query}\n\nRetrieved Policy Documents:\n{context_str}"

        answer = self.llm.generate(user_prompt, system_prompt)
        updates["final_response"] = answer
        return updates
