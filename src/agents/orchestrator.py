import re
import datetime
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from src.agents.state import HRAgentState
from src.agents.guardrails import HRGuardrails
from src.agents.llm_provider import LLMProvider
from src.agents.policy_agent import PolicyRAGAgent
from src.agents.onboarding_agent import OnboardingAgent
from src.agents.employee_agent import EmployeeToolAgent
from src.mcp.client import MCPClient


class HROrchestrator:
    """
    LangGraph Multi-Agent Orchestrator for HR Automation.
    Manages routing, safety guardrails, specialized sub-agents, and operational traces.
    """

    def __init__(self, mcp_client: Optional[MCPClient] = None, llm_provider: Optional[LLMProvider] = None):
        self.mcp = mcp_client or MCPClient()
        self.llm = llm_provider or LLMProvider()

        # Initialize sub-agents
        self.policy_agent = PolicyRAGAgent(self.mcp, self.llm)
        self.onboarding_agent = OnboardingAgent(self.mcp, self.llm)
        self.employee_agent = EmployeeToolAgent(self.mcp, self.llm)

        # Build LangGraph workflow
        self.workflow_graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(HRAgentState)

        # 1. Define nodes
        graph.add_node("router", self._router_node)
        graph.add_node("guardrails", self._guardrails_node)
        graph.add_node("policy_agent", self._policy_agent_node)
        graph.add_node("onboarding_agent", self._onboarding_agent_node)
        graph.add_node("employee_agent", self._employee_agent_node)
        graph.add_node("synthesizer", self._synthesizer_node)

        # 2. Define edges & conditional branches
        graph.set_entry_point("router")
        graph.add_edge("router", "guardrails")

        def route_after_guardrails(state: HRAgentState) -> str:
            wf = state.get("workflow", "policy_rag")
            if wf in ["out_of_scope", "clarification"]:
                return "synthesizer"
            elif wf == "onboarding":
                return "onboarding_agent"
            elif wf == "employee_workflow":
                return "employee_agent"
            else:
                return "policy_agent"

        graph.add_conditional_edges(
            "guardrails",
            route_after_guardrails,
            {
                "synthesizer": "synthesizer",
                "onboarding_agent": "onboarding_agent",
                "employee_agent": "employee_agent",
                "policy_agent": "policy_agent"
            }
        )

        graph.add_edge("policy_agent", "synthesizer")
        graph.add_edge("onboarding_agent", "synthesizer")
        graph.add_edge("employee_agent", "synthesizer")
        graph.add_edge("synthesizer", END)

        return graph.compile()

    # --- Node Implementations ---

    def _router_node(self, state: HRAgentState) -> Dict[str, Any]:
        """Interprets intent and extracts context."""
        query = state["user_query"].strip()
        q_lower = query.lower()

        # Extract employee ID if present in query
        emp_match = re.search(r"EMP-[A-Z0-9-]+", query, re.IGNORECASE)
        emp_id = state.get("employee_id") or (emp_match.group(0).upper() if emp_match else None)

        trace = list(state.get("operational_trace", []))

        # Intent classification heuristics
        if any(w in q_lower for w in ["recipe", "bake", "cook", "quantum physics", "write python", "debug code", "capital of", "two sum"]):
            workflow = "out_of_scope"
            reasoning = "Query outside HR domain."
        elif any(w in q_lower for w in ["onboard", "new hire", "checklist", "first day", "roadmap"]):
            workflow = "onboarding"
            reasoning = "Query pertains to new hire onboarding, checklist milestones, or orientation."
        elif (
            ("pto" in q_lower or "vacation" in q_lower or "time off" in q_lower or "leave" in q_lower) and
            any(w in q_lower for w in ["balance", "submit", "take", "book", "file", "confirm"]) and
            not any(w in q_lower for w in ["how do", "rollover", "interact", "what is the annual", "accrual tier"])
        ):
            workflow = "employee_workflow"
            reasoning = "Query requests employee PTO balance check or leave ticket action."
        elif (
            ("stipend" in q_lower or "equipment" in q_lower or "allowance" in q_lower or "profile" in q_lower or "benefits" in q_lower or "expense" in q_lower) and
            (emp_id is not None or any(w in q_lower for w in ["my", "check", "remaining", "used", "complies", "compliance"])) and
            not any(w in q_lower for w in ["am i eligible", "what are the deductible", "daily maximum allowance"])
        ):
            workflow = "employee_workflow"
            reasoning = "Query requires employee tool execution (equipment balance, profile lookup, benefits election, expense check)."
        elif "confirm" in q_lower and "ticket" in q_lower:
            workflow = "employee_workflow"
            reasoning = "User confirming pending ticket creation."
        else:
            workflow = "policy_rag"
            reasoning = "Query requests HR policy guidance, compliance rules, or benefits information."

        trace.append({
            "step": "intent_routing",
            "detected_workflow": workflow,
            "employee_id": emp_id,
            "reasoning": reasoning,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })

        return {
            "workflow": workflow,
            "employee_id": emp_id,
            "intent_reasoning": reasoning,
            "operational_trace": trace
        }

    def _guardrails_node(self, state: HRAgentState) -> Dict[str, Any]:
        """Validates scope and detects ambiguity."""
        query = state["user_query"]
        workflow = state.get("workflow", "policy_rag")
        trace = list(state.get("operational_trace", []))

        # Check scope
        in_scope, refusal = HRGuardrails.check_scope(query)
        if not in_scope:
            trace.append({
                "step": "guardrail_scope_check",
                "status": "REFUSED_OUT_OF_SCOPE",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })
            return {
                "workflow": "out_of_scope",
                "final_response": refusal,
                "operational_trace": trace
            }

        # Check ambiguity
        is_ambiguous, clarification = HRGuardrails.check_ambiguity(query, workflow)
        if is_ambiguous:
            trace.append({
                "step": "guardrail_ambiguity_check",
                "status": "CLARIFICATION_REQUIRED",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })
            return {
                "workflow": "clarification",
                "final_response": clarification,
                "operational_trace": trace
            }

        trace.append({
            "step": "guardrail_check",
            "status": "PASSED",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        return {"operational_trace": trace}

    def _policy_agent_node(self, state: HRAgentState) -> Dict[str, Any]:
        res = self.policy_agent.execute(state)
        return res

    def _onboarding_agent_node(self, state: HRAgentState) -> Dict[str, Any]:
        res = self.onboarding_agent.execute(state)
        return res

    def _employee_agent_node(self, state: HRAgentState) -> Dict[str, Any]:
        res = self.employee_agent.execute(state)
        return res

    def _synthesizer_node(self, state: HRAgentState) -> Dict[str, Any]:
        """Attaches final operational traces, safety metadata, and formats output."""
        trace = list(state.get("operational_trace", []))
        citations = state.get("citations", [])
        tool_calls = state.get("tool_calls", [])

        trace.append({
            "step": "synthesis_and_citation_audit",
            "total_mcp_tools_called": len(tool_calls),
            "total_citations": len(citations),
            "action_safety": state.get("action_safety_status", "SAFE"),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })

        return {
            "operational_trace": trace
        }

    def run(self, user_query: str, employee_id: Optional[str] = None, session_id: str = "default-session", confirmed: bool = False) -> Dict[str, Any]:
        """Execute the LangGraph multi-agent HR workflow."""
        self.mcp.clear_trace()

        initial_state: HRAgentState = {
            "user_query": user_query,
            "employee_id": employee_id,
            "session_id": session_id,
            "confirmed": confirmed,
            "workflow": "undetermined",
            "intent_reasoning": "",
            "retrieved_chunks": [],
            "citations": [],
            "query_rewrites": [],
            "tool_calls": [],
            "operational_trace": [],
            "facts": [],
            "recommendations": [],
            "action_safety_status": "SAFE",
            "final_response": "",
            "error": None
        }

        final_state = self.workflow_graph.invoke(initial_state)
        mcp_trace = self.mcp.get_trace()

        return {
            "query": user_query,
            "answer": final_state.get("final_response", ""),
            "citations": final_state.get("citations", []),
            "action_safety": final_state.get("action_safety_status", "SAFE"),
            "workflow": final_state.get("workflow", "general"),
            "operational_trace": final_state.get("operational_trace", []),
            "mcp_tool_trace": mcp_trace
        }
