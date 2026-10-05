# AI Tooling & Development Retrospective

This document details the AI-assisted engineering tools utilized during the design, implementation, debugging, and evaluation of the **GlobalTech HR Multi-Agent Automation System**. It describes how each tool was used, what worked well, the architectural failure modes and pitfalls encountered throughout development (and resolved via today's commits), and key takeaways for AI-assisted agentic software development.

---

## 1. Overview of AI Code Tools Employed

| Tool / Technology | Role in Project | Modality of Use |
| :--- | :--- | :--- |
| **Google Antigravity IDE (Gemini Agentic Assistant)** | Primary pair-programming assistant, system architecture design, multi-file code generation, refactoring, and automated testing execution. | Autonomous agentic workflow with direct filesystem access, terminal execution, and subagent orchestration. |
| **Python Static & Dynamic Analysis Tools** | AST parsing, linting, type validation (`TypedDict`, `typing`), and test verification. | Executed via Antigravity terminal actions during continuous testing. |
| **Streamlit `AppTest` Framework (`streamlit.testing.v1`)** | Headless automated simulation of Streamlit UI interactions, state transitions, and widget clicks. | Programmatic headless testing integrated into `pytest`. |
| **Git & GitHub Actions CI/CD** | Automated continuous integration, regression testing, and code lifecycle tracking. | Git commits, automated test matrix, and workflow automation. |

---

## 2. How AI Tooling Was Applied Across System Layers

### 2.1 Multi-Format Policy Ingestion & Heading-Aware Chunker
- **Application:** The assistant designed format-specific parsers for Markdown frontmatter, semantic HTML DOM elements, and plain text sections (`src/rag/parser.py`).
- **Heading-Aware Strategy:** AI generated regex patterns matching both Markdown headers (`#` to `####`) and uppercase numbered section delimiters (`1. PURPOSE`), ensuring policy boundaries were preserved with prepended document and section context tokens.
- **Outcome:** Successfully indexed 152 self-contained semantic chunks across 11 comprehensive corporate policy documents (16,538 words, ~55 standard pages) without manual segmentation.

### 2.2 Model Context Protocol (MCP) with FastMCP & langchain-mcp-adapters
- **Application:** Refactored tool definitions using **FastMCP** (`mcp.server.fastmcp`) with `@mcp.tool()` decorators in `src/mcp/tools.py`.
- **Client Integration:** Implemented **langchain-mcp-adapters** and **MultiServerMCPClient** (`src/mcp/client.py`), allowing seamless tool discovery and LangChain `BaseTool` conversion across SSE, Stdio, and in-process execution.
- **Dual Transport Integration:** Implemented FastMCP SSE mounting (`/sse`, `/messages`) and standalone stdio subprocess execution (`python -m src.mcp.server --stdio`) with full operational telemetry (tool arguments, return values, and latency).

### 2.3 LangGraph Multi-Agent Orchestration & Dynamic LLM Intent Classification
- **Application:** Structured the `StateGraph` state machine (`src/agents/orchestrator.py`) using a centralized `HRAgentState` TypedDict.
- **Semantic Intent Classification:** Replaced brittle keyword heuristics in `_router_node` with dynamic LLM intent classification (`LLMProvider.classify_intent`), enabling the model to categorize queries into structured schemas (`policy_rag`, `onboarding`, `employee_workflow`, `out_of_scope`, `clarification`) with extracted entities and routing rationale.
- **Workflow Routing:** Defined conditional edges routing between:
  - LLM Intent classification (`_router_node`)
  - Scope and ambiguity guardrails (`_guardrails_node`)
  - Sub-agents: `PolicyRAGAgent`, `OnboardingAgent`, `EmployeeToolAgent`
  - Post-execution synthesis and citation audit (`_synthesizer_node`)

### 2.4 Autonomous LLM Tool Planning & Context Bloat Prevention
- **Application:** Built an autonomous tool planning engine (`LLMProvider.plan_tool_calls`) across `PolicyRAGAgent`, `EmployeeToolAgent`, and `OnboardingAgent`.
- **Bounded Tool Calling:** Replaced hardcoded subquery and tool selection ladders with dynamic JSON tool planning strictly capped at **at most 2 tool calls per subagent turn**, eliminating recursive multi-turn back-and-forth loops and preventing context bloat.

### 2.5 Interactive Streamlit Frontend & Session Persona Management
- **Application:** Generated an interactive UI with employee persona selection, sidebar demo buttons, expandable citation cards, and real-time operational execution traces.
- **Session-Scoped Privacy:** Bound all personal lookups and workflow actions to the active session profile selected in the UI dropdown rather than unverified prompt text mentions.

### 2.6 Benchmark Evaluation Harness & CI/CD
- **Application:** Generated 25 comprehensive evaluation test cases (`evaluation/eval_dataset.json`) and an automated benchmark runner (`evaluation/run_eval.py`) that computes groundedness recall, citation accuracy, tool selection fidelity, and latency percentiles (p50/p90/p95).

---

## 3. What Worked Well

### 3.1 Rapid Scaffolding of Typed Agent States & Graph Topologies
- Writing LangGraph graph definitions and TypedDict models by hand is verbose and error-prone. The AI assistant quickly generated complete, type-safe graph declarations with conditional branches, input validation, and clear node responsibilities.
- The separation of sub-agents (`PolicyRAGAgent`, `OnboardingAgent`, `EmployeeToolAgent`) into clean modular classes allowed incremental unit testing of individual agent logic before end-to-end graph compilation.

### 3.2 Standard-Conforming FastMCP Tooling & MultiServerMCPClient
- Defining 8 distinct MCP tools with `@mcp.tool()` decorators in FastMCP automatically derived standard JSON Schemas from Python type hints and docstrings without manual schema boilerplate.
- `MultiServerMCPClient` from `langchain-mcp-adapters` streamlined multi-server connectivity, enabling LangChain agents to bind MCP tools directly via `get_langchain_tools()` with support for both synchronous and asynchronous invocations.

### 3.3 Synthetic Data & Policy Corpus Realism
- The AI created and expanded 11 realistic corporate policy documents (`POL-REMOTE-2024`, `POL-PTO-2024`, `POL-BEN-2024`, `POL-EXP-2024`, `POL-ETHICS-2024`, `POL-SEC-2024`, `POL-ONB-2024`, `POL-HOL-2024`, `POL-REL-2024`, `POL-FAC-2024`, `POL-EMP-2024`) containing nuanced rules across PTO, holidays, remote work, expenses, data security, benefits, onboarding, equipment, leave, workplace conduct, manager relationships, office locations, and employment classifications.
- This enabled rigorous testing of cross-document RAG queries (e.g. asking whether one can expense meals while working remotely on PTO from France, or how fiscal close blackouts affect client entertainment travel).

### 3.4 Automated Evaluation & Benchmark Automation
- The AI generated the 25-case evaluation dataset and the automated runner script.
- The runner executed all test cases in seconds, validating that groundedness recall reached **93.7%**, citation accuracy reached **100%**, tool selection reached **100%**, and action safety achieved **100%**.

---

## 4. What Did Not Work Well & How Issues Were Overcome (Today's Retrospective)

Reviewing the code lifecycle and the series of commits from today reveals several critical architectural assumptions, subtle bugs, and design flaws that failed during initial implementation and required explicit intervention to fix.

### 4.1 Brittle Keyword-Based Routing & Subagent Tool Selection (Commits `85d764d`, `42e1c3a`)
- **What Went Wrong:**
  - The AI assistant initially defaulted to brittle `if/elif` string and keyword checks:
    - `HROrchestrator._router_node` checked for literal words (`"pto" in query`, `"onboard" in query`).
    - Subagents (`PolicyRAGAgent`, `EmployeeToolAgent`, `OnboardingAgent`) used hardcoded `if "pto"... elif "benefit"... elif "remote"...` branches to choose which tools to call.
  - As a result, naturally phrased queries (e.g. *"I need a few days off to visit family"*, *"Can I work from a different city?"*, *"What equipment can I order?"*) frequently misrouted or failed to trigger the necessary tools.
- **Resolution:**
  - Replaced router keyword matching with LLM-based intent classification (`LLMProvider.classify_intent`), categorizing queries into structured schemas with routing rationale and entity extraction.
  - Implemented dynamic tool planning via `LLMProvider.plan_tool_calls`, allowing subagents to inspect available tool JSON schemas and generate structured tool calls dynamically based on query semantics.

### 4.2 Privacy Leakage on Anonymous Requests & Missing Employee IDs (Commit `349af9d`)
- **What Went Wrong:**
  - In initial implementations, requests without an employee ID (e.g., an anonymous user asking *"Show my onboarding checklist"* or *"Check my PTO balance"*) defaulted to pulling sample records from `employees.json` (such as Jordan Hayes or Alice Chen).
  - This constituted a critical data leakage vulnerability where an unauthenticated or anonymous user received another employee's private profile, balances, and checklist status.
- **Resolution:**
  - Implemented strict privacy guardrails in `HROrchestrator`, `EmployeeToolAgent`, and `OnboardingAgent`:
  - When personal profile data or action execution is requested without an active session employee ID, the agents immediately halt execution, log an `EMPLOYEE_ID_REQUIRED` trace, and respond:
    > *"To access employee records, check your personal balances, or submit requests, please provide your Employee ID."*
  - Anonymous users can only query general company policy information.

### 4.3 Query Text Entity Extraction vs. Session-Scoped Privacy (Commits `f107790`, `78020ce`)
- **What Went Wrong:**
  - The AI initially extracted employee IDs directly from query text using regular expressions (`r"\b(EMP-\d+|EMP-[A-Z]+-\d+)\b"`).
  - This created two severe vulnerabilities:
    1. **Cross-Employee Profile Spoofing:** An employee logged in as `EMP-101` could ask *"What is the PTO policy for EMP-102?"*, causing the system to override the session and look up `EMP-102`'s private records.
    2. **Unauthenticated Query Snooping:** An unauthenticated user could extract another employee's profile simply by mentioning their ID in the text.
    3. **Demo Inconsistency:** Sidebar demo buttons contained hardcoded employee IDs in prompt text, contradicting the requirement that the active session persona determines context.
- **Resolution:**
  - Completely decoupled employee identification from prompt text: profile lookups are **strictly bound to the active session state** (`state.get("employee_id")`).
  - Text mentions of employee IDs are deliberately ignored during profile lookup. If session `EMP-101` queries about `EMP-102`, only `EMP-101`'s profile is looked up.
  - Streamlined Streamlit demo tasks (Commit `78020ce`), removing hardcoded IDs from prompt text so that prompts execute against the user's selected session persona.

### 4.4 Over-Zealous Scope Guardrails & False Out-of-Scope Rejections (Commit `42e1c3a`)
- **What Went Wrong:**
  - The initial implementation of `HRGuardrails.check_scope()` utilized a rigid lexical domain whitelist (`HR_DOMAINS`) that omitted common work mobility terms such as `"work"`, `"working"`, `"city"`, `"state"`, `"country"`, `"relocate"`, and `"location"`.
  - When an employee asked *"Can an employee work in another city?"*, the guardrail intercepted the query before routing, declared it out-of-scope, and returned a canned refusal (*"I cannot assist with questions outside our HR scope"*).
  - Furthermore, the guardrail did not consult the LLM intent classification result.
- **Resolution:**
  - Expanded `HR_DOMAINS` with comprehensive geographic and mobility keywords (`"relocate"`, `"relocation"`, `"location"`, `"transfer"`, `"abroad"`, `"city"`, `"country"`).
  - Updated `check_scope()` to defer to the LLM classifier: if the classifier categorizes the query as an in-scope workflow (`policy_rag`, `employee_workflow`, `onboarding`), the guardrail accepts it.
  - Added policy synthesis handling for [POL-REMOTE-2024: 5](file:///Users/2015mbp16gb256gb/Documents/repos/msaie-agentic-HR/data/policies/remote_work_policy.md) (30-day workation limit) and Section 8 (60-day relocation notice).

### 4.5 Tool Call Proliferation, Context Bloat, and Redundant Upfront Lookups (Commit `42e1c3a`)
- **What Went Wrong:**
  - In `EmployeeToolAgent`, the assistant initially hardcoded a `lookup_employee_profile` call at the start of `execute()` before calling the tool planner.
  - When the tool planner then planned two tools (e.g. `check_pto_balance` and `check_policy_compliance`), the agent ended up executing **3 tool calls per turn**.
  - This caused test assertions to fail (`assert 3 <= 2`), violated single-turn bounded execution, bloated prompt context, and introduced unnecessary latency.
- **Resolution:**
  - Removed the hardcoded upfront profile lookup from `EmployeeToolAgent`.
  - Bounded tool execution across all subagents to strictly `max_tool_calls <= 2` in a single planning turn.
  - Dynamically resolved employee names and profile metadata from whichever tool outputs were returned by the planned calls.

### 4.6 Deployment Architecture Mismatch: Single-Port SPA vs. Multi-Service API (Commits `47efa79`, `bb6ba7d`)
- **What Went Wrong:**
  - The AI assistant initially assumed that all services (`FastAPI` on 8000, `MCP` on 8001, and `Streamlit` on 8501) could be simultaneously reached on the single public URL assigned by Render (`https://msaie-agentic-hr.onrender.com`).
  - In reality, Render's free tier runs a single container web process bound to `$PORT` executing `streamlit run app.py`. Because Streamlit is a Single Page Application (SPA), requests sent to subpaths like `/health`, `/chat`, or `/docs` were intercepted by Streamlit's Tornado router and returned the Streamlit frontend HTML application instead of REST API JSON.
  - Additionally, free-tier containers automatically spun down after 15 minutes of inactivity, causing unannounced 50+ second cold-start delays that caused external API clients to time out.
- **Resolution:**
  - Updated documentation (`deployed.md`, `README.md`) to explicitly delineate service availability:
    - **Deployed URL:** Dedicated exclusively to the interactive Streamlit UI.
    - **Local Deployment (`./run.sh`):** Exposes the full multi-service architecture including the FastAPI REST endpoints (`/health`, `/chat`, `/docs`) and the FastMCP server (`/mcp`).
  - Documented free-tier dormancy characteristics (50–90 second spin-up delay) and mitigation strategies (uptime pingers or local execution).

### 4.7 Streamlit Re-Import Caching Crash (Empty DOM Bug)
- **What Went Wrong:**
  - In initial development, changing the employee dropdown or clicking a demo task button caused the Streamlit app to wipe its DOM and appear blank.
  - The entrypoint `app.py` previously contained `from src.app.streamlit_app import *`. Because Streamlit re-executes the entrypoint on every widget change, Python's `import` mechanism saw the module in `sys.modules`, skipped executing its body, and Streamlit cleared the UI.
- **Resolution:**
  - Refactored `src/app/streamlit_app.py` into an explicit `main()` function invoked directly by `app.py`:
    ```python
    from src.app.streamlit_app import main
    main()
    ```
  - Added `@st.cache_resource` for the ChromaDB client connection to prevent SQLite reconnect overhead on reactive reruns.
  - Created automated regression tests using `streamlit.testing.v1.AppTest` (`tests/test_streamlit_app.py`).

---

## 5. Key Takeaways & Recommendations

1. **Autonomous Tool Planning Must Be Strictly Bounded:** Agentic tool planning must be constrained with hard tool-call limits (`max_tool_calls <= 2`) and single-pass planning to prevent runaway ReAct loops, context bloat, and escalating inference costs.
2. **Session Context Over Text-Extracted Entities for Authorization:** Never rely on regex extraction of sensitive identifiers (such as employee IDs or account numbers) from freeform user queries. Identity and access control must be strictly anchored to verified session state to prevent prompt spoofing.
3. **Semantic Classifiers Must Coordinate with Lexical Guardrails:** Keyword-based input guardrails frequently reject valid user inquiries that use synonyms or natural language. Lexical checks should either be sufficiently comprehensive or defer to the semantic LLM intent classifier for domain determination.
4. **Explicit Function Calls Over Module Imports in Streamlit:** Always encapsulate Streamlit UI logic in an explicit `main()` function and call it directly from entrypoint scripts to prevent Python's import cache from silencing reactive reruns.
5. **Acknowledge Platform Topology Constraints in Distributed Multi-Agent Systems:** Deploying a multi-agent system composed of multiple distinct services (UI, REST API, FastMCP server) on single-port free hosting platforms requires clear architectural separation between single-process frontend deployments and multi-service local/orchestrated stacks.
6. **Deterministic Fallbacks Enable Bulletproof CI/CD:** Pairing local vector databases (ChromaDB) and tool planners with deterministic offline fallback modes guarantees fast, reliable, zero-cost continuous integration testing without external API dependencies.
