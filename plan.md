### Core Requirements and system architecture
1. Environment and Reproducibility
    - Create a virtual environment, such as venv.
    - List dependencies in requirements.txt.
    - Provide a README.md with setup, local run, deployment, and evaluation instructions.
    - Set fixed seeds where applicable, such as deterministic chunking or evaluation sampling.
    - Ensure secrets such as API keys are read from environment variables and are not committed to the repository.
2. Policy Corpus Ingestion and Indexing
    - Parse and clean policy documents, handling at least two supported source formats where feasible, such as markdown, HTML, PDF, or TXT.
    - Chunk documents using a justified strategy, such as heading-aware chunking or token windows with overlap.
    - Embed chunks using a free embedding model, local model, or free-tier API.
    - Store embedded chunks in a local or lightweight vector database such as Chroma.
    - Persist enough document metadata to support citations, including document title or ID, section, and source snippet.
3. Retrieval Augmented Generation (RAG)
    - Implement top-k retrieval with optional filtering, query rewriting, or reranking.
    - Build a prompting strategy that injects retrieved chunks and source metadata into the LLM context.
    - Generate answers that cite source document IDs, titles, or sections and include supporting snippets where appropriate.
    - Add guardrails that refuse or redirect out-of-corpus policy questions, limit unsupported claims, and distinguish policy facts from recommendations.
    - Include at least one complex question requiring retrieval from multiple policy documents.
4. Agentic System Design
    - Build an agent orchestrator that can interpret user intent, decide whether RAG alone is sufficient, select tools, call MCP-exposed tools, and synthesize final responses.
    - Support at least two multi-step HR workflows, such as remote work eligibility, PTO request guidance, benefits question handling, expense compliance, onboarding checklist creation, or HR case triage.
    - Implement a visible or logged trace of agent reasoning steps at the architectural level: selected tools, tool arguments, tool outputs, retrieved policy sources, final answer basis, and any escalation decision. Do not expose hidden chain-of-thought; provide concise operational traces instead.
    - Handle failures gracefully, such as unavailable MCP tools, missing employee IDs, incomplete policy evidence, or ambiguous requests that require clarification.
    - Prevent irreversible actions. Actions such as creating HR tickets, drafting manager messages, or updating case records must be mock actions or require explicit user confirmation.
5. MCP Server and Tool Integration
    - Implement one or more MCP servers that expose tools for the agent. The MCP server may run as a local process using stdio, a localhost HTTP service, a Streamable HTTP service, or another MCP-compatible approach supported by your system’s architecture.
    - Expose at least five MCP tools. At least one tool must use the RAG index or retrieve policy evidence, and at least one tool must use mock structured data or perform a mock operation.
    - Tools should include tools such as the following: search_policy_documents, get_policy_section, lookup_employee_profile, check_pto_balance, lookup_benefits_status, create_mock_hr_ticket, draft_hr_email, and check_policy_compliance.
    - The agent must actually call MCP-exposed tools during execution; hard-coded direct function calls are not sufficient unless they are wrapped and invoked through the MCP layer.
    - Document the MCP architecture, transport choice, tool schemas, and how the agent client discovers and calls tools.
6. Web Application
    - Use Streamlit for the web application.
    - The web app should include a chat interface where users can ask HR policy and workflow questions.
    - Provide a /chat endpoint, or equivalent, that receives user requests and returns the final answer, citations, snippets, and a concise tool-call trace.
    - Provide a /health endpoint, or equivalent, that returns a simple JSON status including app status and, where feasible, MCP connectivity status.
    - Provide a way for an outside observer to reproduce at least two agentic demo tasks from the UI or an API client.
7. Deployment to Render, Railway, or Equivalent
    - Deploy the application to Render, Railway, or an equivalent free-tier or zero-cost host. The deployed application must be accessible at a shareable URL unless the student documents a platform outage or exceptional deployment issue.
    - To remain free-tier compatible, a single-service deployment is acceptable: the web app, agent orchestrator, local vector store, mock JSON data, and MCP server process may all run in one deployed service.
    - Deploy the MCP server as a separate service and call it via HTTP. Configure the MCP server URL with environment variables.
    - The application should not require a paid database. Acceptable storage includes committed synthetic data files or a hosted free-tier option.
    - If the free-tier service spins down after inactivity, the README and demo should explain the expected cold-start behavior.
8. CI/CD
    - Create a GitHub Actions workflow, or equivalent CI/CD pipeline, that runs on push or pull request.
    - The workflow should install dependencies, run a build/start/import check, and successfully execute some automated tests such as unit or smoke tests before deploying.
    - Include at least one automated test that verifies the app can start and at least one test or script that verifies MCP tool discovery or a simple MCP tool call.
    - Deployment must only occur if tests pass.
9. Evaluation of the Agentic RAG Application
    - Provide an evaluation set of 20-30 questions or tasks covering policy Q&A and agentic workflows. Include straightforward policy questions, multi-document questions, tool-requiring tasks, ambiguous requests, and out-of-scope requests – with correct or gold answers.
    - Report answer quality metrics: groundedness, citation accuracy, and optionally exact or partial match against short gold answers.
    - Report agent behavior metrics: tool selection accuracy, workflow completion rate, escalation or clarification accuracy, and action-safety pass rate.
    - Report system metrics: latency p50/p95 for 10-20 representative queries or tasks. If free-tier cold starts affect latency, report cold-start and warm-start behavior separately where possible.
    - Include at least one ablation or comparison, such as different retrieval k values, chunk sizes, prompt variants, or agent tool availability.
10. Design Documentation
    - Briefly justify design choices, including agent framework or manual orchestration approach, MCP server design, transport choice, tool schemas, embedding model, chunking strategy, retrieval k, vector store, deployment architecture, and safety guardrails.
    - Include an architecture diagram or text-based architecture showing the web app, agent orchestrator, MCP client, MCP server or servers, RAG index, mock structured data, and LLM provider.
    - Describe the two required agentic demo tasks and the expected sequence of MCP tool calls for each task.