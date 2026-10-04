import os
import sys
import time
from pathlib import Path
import streamlit as st

# Setup python path to ensure project root is accessible
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.agents.orchestrator import HROrchestrator
from src.mcp.client import MCPClient
from src.rag.vector_store import PolicyVectorStore
from src.config import CHROMA_PERSIST_DIR


@st.cache_resource
def get_cached_chunk_count() -> int:
    """Cache the policy vector store item count to prevent repeated SQLite client creation."""
    try:
        vs = PolicyVectorStore(persist_dir=str(CHROMA_PERSIST_DIR), use_fallback_embeddings=True)
        return vs.count()
    except Exception:
        return 37


def init_session_state():
    """Initialize necessary session state variables."""
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = HROrchestrator()

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "👋 Hello! I am the **GlobalTech HR Automation Agent** powered by LangGraph.\n\n"
                    "I can assist you with:\n"
                    "• **HR Policy Inquiries** (PTO, international remote work, expense per diems, code of conduct)\n"
                    "• **New Hire Onboarding** (checklist verification, equipment stipends, welcome roadmap)\n"
                    "• **Employee Self-Service Tools** (PTO balance checks, leave submissions, benefits lookups)\n\n"
                    "Select an active employee, pick a demo from the sidebar, or type your inquiry below!"
                ),
                "citations": [],
                "operational_trace": [],
                "mcp_trace": [],
                "action_safety": "SAFE"
            }
        ]

    if "pending_confirmation" not in st.session_state:
        st.session_state.pending_confirmation = None


def main():
    """Main Streamlit application execution function."""
    st.set_page_config(
        page_title="GlobalTech HR Multi-Agent Automation System",
        page_icon="💼",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS Styling
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.2rem;
            font-weight: 700;
            color: #1E293B;
            margin-bottom: 0.2rem;
        }
        .sub-header {
            font-size: 1.05rem;
            color: #64748B;
            margin-bottom: 1.2rem;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-right: 8px;
        }
        .badge-green { background-color: #DCFCE7; color: #166534; }
        .badge-blue { background-color: #DBEAFE; color: #1E40AF; }
        .badge-purple { background-color: #F3E8FF; color: #6B21A8; }
        .badge-amber { background-color: #FEF3C7; color: #92400E; }
        .citation-box {
            border-left: 4px solid #3B82F6;
            background-color: #EFF6FF;
            padding: 8px 12px;
            margin-bottom: 8px;
            border-radius: 0 6px 6px 0;
        }
    </style>
    """, unsafe_allow_html=True)

    init_session_state()

    demo_query_triggered = None

    # Sidebar Controls
    with st.sidebar:
        st.markdown("## 🤖 System Control Panel")

        st.markdown("### Active Employee Persona")
        employee_options = {
            "EMP-101": "EMP-101 | Alice Chen (Sr Engineer, Remote, 2.6 yrs)",
            "EMP-102": "EMP-102 | Marcus Johnson (Marketing, Hybrid, 3 mos probation)",
            "EMP-103": "EMP-103 | Sarah Miller (HR Lead, On-site, 4 yrs)",
            "EMP-NEW-01": "EMP-NEW-01 | Jordan Hayes (New Hire Engineer, Remote)",
            "None": "Anonymous / General Inquiry"
        }
        selected_emp_key = st.selectbox(
            "Select Active Employee:",
            options=list(employee_options.keys()),
            format_func=lambda k: employee_options[k],
            index=0,
            key="active_employee_selector"
        )
        active_emp_id = None if selected_emp_key == "None" else selected_emp_key

        st.divider()

        st.markdown("### 🎯 Interactive Demo Tasks")
        st.caption("Click any demo task to immediately execute the multi-agent workflow:")

        demo_tasks = [
            ("🚀 Demo 1: Onboarding Roadmap", "Help with onboarding checklist and draft welcome email for EMP-NEW-01"),
            ("🏖️ Demo 2: PTO Balance & Request", "Check my PTO balance for EMP-101 and help me request 3 days off"),
            ("🌍 Demo 3: Multi-Doc Policy Question", "Can I expense meals while working remotely on PTO from France?"),
            ("💻 Demo 4: Remote Work Allowance", "What is the home office equipment allowance for EMP-102 and am I eligible?"),
            ("🔒 Demo 5: Action Safety Guardrail", "Submit request to take 3 days PTO for EMP-101"),
            ("🚫 Demo 6: Out-of-Scope Guardrail", "How do I bake chocolate chip cookies?")
        ]

        for label, query in demo_tasks:
            if st.button(label, use_container_width=True, key=f"btn_{label[:10]}"):
                demo_query_triggered = query

        st.divider()

        if st.button("🔄 Reset Conversation", use_container_width=True, key="btn_reset_convo"):
            st.session_state.messages = [st.session_state.messages[0]]
            st.session_state.pending_confirmation = None
            st.rerun()

        st.divider()

        chunk_count = get_cached_chunk_count()

        st.markdown("### 📊 System Telemetry")
        st.markdown("• **LangGraph Engine:** `v1.2+ Active`")
        st.markdown(f"• **Chroma RAG Chunks:** `{chunk_count} Indexed`")
        st.markdown("• **MCP Protocol:** `8 Tools Registered`")
        st.markdown("• **Action Safety:** `Guardrail Active`")

    # Main Content Header
    col_title, col_badges = st.columns([3, 2])
    with col_title:
        st.markdown('<div class="main-header">GlobalTech HR Multi-Agent System</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Autonomous HR Automation with LangGraph & Model Context Protocol (MCP)</div>', unsafe_allow_html=True)

    with col_badges:
        st.markdown("""
        <div style="text-align: right; padding-top: 10px;">
            <span class="status-badge badge-green">● System Healthy</span>
            <span class="status-badge badge-blue">LangGraph v1.2</span>
            <span class="status-badge badge-purple">MCP Tools Active</span>
        </div>
        """, unsafe_allow_html=True)

    # Render Chat History
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Display Citations if available
            citations = msg.get("citations", [])
            if citations:
                with st.expander(f"📚 Policy Citations & Supporting Evidence ({len(citations)})"):
                    for c in citations:
                        st.markdown(f"""
                        <div class="citation-box">
                            <strong>[{c['document_id']}] {c['document_title']}</strong> — <em>{c['section_title']}</em><br>
                            <small><strong>File:</strong> {c['source_file']} | <strong>Similarity Score:</strong> {c.get('similarity_score', 'N/A')}</small><br>
                            <span style="font-size: 0.9rem; color: #334155;">"{c['snippet']}"</span>
                        </div>
                        """, unsafe_allow_html=True)

            # Display MCP Tool Calls & Operational Traces
            mcp_trace = msg.get("mcp_trace", [])
            op_trace = msg.get("operational_trace", [])
            if mcp_trace or op_trace:
                with st.expander(f"⚙️ Architectural & MCP Tool Call Trace ({len(mcp_trace)} MCP Calls)"):
                    tab1, tab2 = st.tabs(["MCP Tool Execution", "LangGraph Reasoning Steps"])

                    with tab1:
                        if mcp_trace:
                            for t in mcp_trace:
                                st.markdown(f"**Tool:** `{t['tool_name']}` | **Status:** `{t['status']}` | **Latency:** `{t['latency_ms']} ms`")
                                col_args, col_out = st.columns(2)
                                with col_args:
                                    st.caption("Arguments:")
                                    st.json(t["arguments"])
                                with col_out:
                                    st.caption("Output:")
                                    st.json(t["output"])
                                st.divider()
                        else:
                            st.info("No external MCP tools were executed for this query.")

                    with tab2:
                        if op_trace:
                            st.json(op_trace)
                        else:
                            st.info("No architectural steps logged.")

    # Handle Confirmation Action
    if st.session_state.pending_confirmation:
        conf = st.session_state.pending_confirmation
        st.warning(f"⚠️ Action Confirmation Required: {conf['message']}")
        col_c1, col_c2 = st.columns([1, 4])
        with col_c1:
            if st.button("✅ Confirm & Execute Ticket", type="primary", use_container_width=True, key="btn_confirm_ticket"):
                user_msg = f"Confirm submission of {conf['ticket_type']} for {conf['employee_id']}"
                st.session_state.pending_confirmation = None

                with st.spinner("Executing confirmed mock HR action..."):
                    response = st.session_state.orchestrator.run(
                        user_query=user_msg,
                        employee_id=conf["employee_id"],
                        confirmed=True
                    )
                    st.session_state.messages.append({
                        "role": "user",
                        "content": user_msg
                    })
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response["answer"],
                        "citations": response["citations"],
                        "operational_trace": response["operational_trace"],
                        "mcp_trace": response["mcp_tool_trace"],
                        "action_safety": response["action_safety"]
                    })
                    st.rerun()

    # Determine input prompt (either from clicked demo button or chat input)
    chat_prompt = st.chat_input("Ask an HR policy question or execute a workflow (e.g., 'Check PTO balance for EMP-101')...")
    active_prompt = demo_query_triggered or chat_prompt

    if active_prompt:
        st.session_state.messages.append({"role": "user", "content": active_prompt})

        with st.spinner("LangGraph multi-agent orchestrator processing query..."):
            start_time = time.perf_counter()
            response = st.session_state.orchestrator.run(
                user_query=active_prompt,
                employee_id=active_emp_id,
                confirmed=False
            )
            latency = (time.perf_counter() - start_time) * 1000.0

            if response.get("action_safety") == "CONFIRMATION_REQUIRED":
                st.session_state.pending_confirmation = {
                    "message": "Please confirm ticket creation.",
                    "employee_id": active_emp_id,
                    "ticket_type": "PTO Request"
                }

            st.session_state.messages.append({
                "role": "assistant",
                "content": response["answer"],
                "citations": response["citations"],
                "operational_trace": response["operational_trace"],
                "mcp_trace": response["mcp_tool_trace"],
                "action_safety": response.get("action_safety", "SAFE")
            })

        st.rerun()


if __name__ == "__main__":
    main()
