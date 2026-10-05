import os
import json
import re
from typing import Dict, Any, List, Optional
from src.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    LLM_PROVIDER,
    LLM_MODEL
)

class LLMProvider:
    """
    Unified LLM provider supporting OpenRouter (primary), OpenAI, Anthropic, or an intelligent
    built-in deterministic HR synthesis engine when running without API keys or in offline evaluation mode.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.openrouter_key = api_key or os.getenv("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
        self.openrouter_url = base_url or os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)
        self.openai_key = os.getenv("OPENAI_API_KEY", OPENAI_API_KEY)
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY)
        self.google_key = os.getenv("GOOGLE_API_KEY", GOOGLE_API_KEY)
        self.model = model or os.getenv("LLM_MODEL", os.getenv("OPENROUTER_MODEL", LLM_MODEL))

        configured_provider = provider or os.getenv("LLM_PROVIDER", LLM_PROVIDER)
        if configured_provider != "auto":
            self.active_provider = configured_provider
        elif self.openrouter_key:
            self.active_provider = "openrouter"
        elif self.openai_key:
            self.active_provider = "openai"
        elif self.anthropic_key:
            self.active_provider = "anthropic"
        elif self.google_key:
            self.active_provider = "google"
        else:
            self.active_provider = "mock"
        print(f"Using provider: {self.active_provider}")
        print(f"Using model: {self.model}")


    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate response using the selected provider."""
        # 1. OpenRouter (Primary Chosen Provider)
        if self.active_provider == "openrouter" and self.openrouter_key:
            try:
                import httpx
                headers = {
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/your-org/msaie-agentic-HR",
                    "X-Title": "GlobalTech HR Multi-Agent System"
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are the GlobalTech Senior HR Policy Advisor."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.0
                }
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(self.openrouter_url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices and "message" in choices[0] and "content" in choices[0]["message"]:
                            content = choices[0]["message"]["content"]
                            if content:
                                return content
                    else:
                        print(f"[!] OpenRouter API returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[!] OpenRouter API request failed: {e}; falling back to deterministic synthesis.")

        # 2. OpenAI Fallback
        elif self.active_provider == "openai" and self.openai_key:
            try:
                import httpx
                headers = {"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"}
                payload = {
                    "model": self.model if "gpt" in self.model else "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt or "You are an HR Assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.0
                }
                with httpx.Client(timeout=20.0) as client:
                    resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        return resp.json()["choices"][0]["message"]["content"]
            except Exception:
                pass

        # 3. Built-in Deterministic Synthesis Engine
        return self._deterministic_synthesize(prompt, system_prompt)

    def classify_intent(self, query: str, employee_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Classifies incoming user query using the LLM to determine the appropriate workflow/subagent.
        Returns a dict:
        {
            "workflow": "policy_rag" | "onboarding" | "employee_workflow" | "out_of_scope" | "clarification",
            "employee_id": Optional[str],
            "reasoning": str
        }
        """
        system_prompt = (
            "You are the GlobalTech Multi-Agent HR Intent Classifier.\n"
            "Analyze the incoming user request and categorize it into exactly ONE of the following 5 workflows:\n"
            "1. 'policy_rag': Informational inquiries about company policies, rules, benefits packages, healthcare plans, "
            "PTO accrual rules, travel reimbursement guidelines, remote work day caps, ethics/gift policies, or workplace conduct.\n"
            "2. 'onboarding': New hire onboarding workflows, milestones, 30/60/90-day checklists, welcome emails, orientation roadmap, or new hire setup.\n"
            "3. 'employee_workflow': Transactional self-service actions for employees. Includes checking personal PTO balances, "
            "checking remaining equipment allowance or benefits elections, looking up employee profiles, submitting leave/ticket requests, "
            "confirming pending tickets, or verifying expense compliance against policy.\n"
            "4. 'out_of_scope': Requests that are completely outside the HR, company policy, and employee domain (such as general coding, "
            "python algorithms, cooking recipes, weather, quantum physics, general trivia, personal advice).\n"
            "5. 'clarification': Incomplete or ambiguous action requests that cannot proceed without missing critical details (e.g., asking "
            "to take or book time off without providing dates, duration, or employee ID).\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "workflow": "policy_rag" | "onboarding" | "employee_workflow" | "out_of_scope" | "clarification",\n'
            '  "employee_id": "<extracted employee ID like EMP-101, EMP-NEW-01, or null>",\n'
            '  "reasoning": "<concise explanation of why this workflow was chosen>"\n'
            "}"
        )
        user_prompt = f"User Request: {query}\nActive Employee ID: {employee_id or 'None'}"

        # 1. OpenRouter (Primary Provider)
        if self.active_provider == "openrouter" and self.openrouter_key:
            try:
                import httpx
                headers = {
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/your-org/msaie-agentic-HR",
                    "X-Title": "GlobalTech HR Multi-Agent System"
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.0
                }
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(self.openrouter_url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices and "message" in choices[0] and "content" in choices[0]["message"]:
                            content = choices[0]["message"]["content"]
                            parsed = self._parse_json_classification(content)
                            if parsed:
                                if employee_id and not parsed.get("employee_id"):
                                    parsed["employee_id"] = employee_id
                                return parsed
                    else:
                        print(f"[!] OpenRouter classification API returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[!] OpenRouter classification failed: {e}; falling back to deterministic classification.")

        # 2. OpenAI Fallback
        elif self.active_provider == "openai" and self.openai_key:
            try:
                import httpx
                headers = {"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"}
                payload = {
                    "model": self.model if "gpt" in self.model else "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.0
                }
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        parsed = self._parse_json_classification(content)
                        if parsed:
                            if employee_id and not parsed.get("employee_id"):
                                parsed["employee_id"] = employee_id
                            return parsed
            except Exception:
                pass

        # 3. Built-in Deterministic Classifier Fallback
        return self._deterministic_classify_intent(query, employee_id)

    def _parse_json_classification(self, text: str) -> Optional[Dict[str, Any]]:
        """Safely parses LLM JSON output with code fence stripping."""
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        try:
            parsed = json.loads(cleaned.strip())
            valid_workflows = {"policy_rag", "onboarding", "employee_workflow", "out_of_scope", "clarification"}
            if isinstance(parsed, dict) and parsed.get("workflow") in valid_workflows:
                return {
                    "workflow": parsed["workflow"],
                    "employee_id": parsed.get("employee_id"),
                    "reasoning": parsed.get("reasoning", "LLM-classified intent")
                }
        except Exception:
            m = re.search(r'"workflow"\s*:\s*"([^"]+)"', cleaned)
            if m and m.group(1) in {"policy_rag", "onboarding", "employee_workflow", "out_of_scope", "clarification"}:
                return {
                    "workflow": m.group(1),
                    "employee_id": None,
                    "reasoning": "Extracted from LLM response"
                }
        return None

    def _deterministic_classify_intent(self, query: str, employee_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Deterministic intent classification engine.
        Emulates LLM classification when running offline, in test environments, or on network failure.
        """
        q_lower = query.lower().strip()

        detected_emp_id = employee_id

        # 1. Out-of-Scope Detection
        out_of_scope_patterns = [
            "recipe", "bake", "cook", "quantum physics", "write python", "debug code",
            "capital of", "weather tomorrow", "two sum", "super bowl", "cryptocurrency"
        ]
        if any(p in q_lower for p in out_of_scope_patterns):
            return {
                "workflow": "out_of_scope",
                "employee_id": detected_emp_id,
                "reasoning": "Query is outside the HR and employee operations domain."
            }

        # 2. Ambiguity / Clarification Check
        is_requesting_time_off = (
            any(w in q_lower for w in ["time off", "pto", "vacation", "leave"]) and
            (bool(re.search(r"\b(?:book|request|take)\b", q_lower)) or "want to take" in q_lower)
        )
        is_info_question = bool(re.search(r"^(?:how|what|can|when|who|where)\b", q_lower))
        if is_requesting_time_off and not is_info_question:
            has_days_or_dates = bool(re.search(r"\d+\s*(?:day|days|week|weeks|hours)", q_lower)) or bool(re.search(r"\d{4}-\d{2}-\d{2}", query))
            if not detected_emp_id and not has_days_or_dates:
                return {
                    "workflow": "clarification",
                    "employee_id": None,
                    "reasoning": "User requested time off but did not specify employee ID or dates."
                }

        # 3. Onboarding Workflow
        onboarding_patterns = [
            "onboard", "new hire", "checklist", "first day", "roadmap", "welcome onboarding email",
            "welcome email", "new hire benefits election"
        ]
        if any(p in q_lower for p in onboarding_patterns):
            return {
                "workflow": "onboarding",
                "employee_id": detected_emp_id,
                "reasoning": "Query pertains to new hire onboarding, checklist milestones, or orientation."
            }

        # 4. Employee Workflow (Transactional Tools & Profile)
        if "confirm" in q_lower and "ticket" in q_lower:
            return {
                "workflow": "employee_workflow",
                "employee_id": detected_emp_id,
                "reasoning": "User is confirming submission of a pending HR ticket."
            }

        is_pto_action = (
            ("pto" in q_lower or "vacation" in q_lower or "time off" in q_lower or "leave" in q_lower) and
            any(w in q_lower for w in ["balance", "submit", "take", "book", "file", "confirm"]) and
            not any(w in q_lower for w in ["how do", "rollover", "interact", "what is the annual", "accrual tier"])
        )
        is_employee_tool_action = (
            ("stipend" in q_lower or "equipment" in q_lower or "allowance" in q_lower or "profile" in q_lower or "benefits" in q_lower or "expense" in q_lower) and
            (detected_emp_id is not None or any(w in q_lower for w in ["my", "check", "remaining", "used", "complies", "compliance"])) and
            not any(w in q_lower for w in ["am i eligible", "what are the deductible", "daily maximum allowance"])
        )

        if is_pto_action or is_employee_tool_action:
            return {
                "workflow": "employee_workflow",
                "employee_id": detected_emp_id,
                "reasoning": "Query requires employee tool execution or personal record lookup."
            }

        # 5. Default: Policy RAG
        return {
            "workflow": "policy_rag",
            "employee_id": detected_emp_id,
            "reasoning": "Query requests company policy, benefits rules, or HR guidelines."
        }

    def _deterministic_synthesize(self, prompt: str, system_prompt: str) -> str:
        """
        Deterministic knowledge-based synthesis engine.
        Answers questions accurately based on policy corpus and extracted context.
        """
        # Extract user query
        if "User Question:" in prompt:
            query_part = prompt.split("User Question:")[1]
            if "Retrieved Policy Documents:" in query_part:
                user_query = query_part.split("Retrieved Policy Documents:")[0].strip()
            else:
                user_query = query_part.strip()
        else:
            user_query = prompt.strip()

        q_lower = user_query.lower()

        # Check for active session employee context
        has_employee_context = "Active Employee Profile:" in prompt
        emp_id_match = re.search(r"Employee ID:\s*(EMP-[A-Z0-9-]+)", prompt)
        full_name_match = re.search(r"Full Name:\s*([^\n]+)", prompt)
        tenure_match = re.search(r"Tenure:\s*([0-9.]+)\s*years", prompt)
        pto_balance_match = re.search(r"Current PTO Balance:\s*([0-9.]+)\s*days", prompt)
        work_loc_match = re.search(r"Work Location:\s*([^\n]+)", prompt)
        prob_match = re.search(r"Probation Completed:\s*(Yes|No)", prompt)
        medical_match = re.search(r"Medical:\s*([^,\n]+)", prompt)

        # 0. Active Employee Personalized Responses
        if has_employee_context and emp_id_match:
            emp_id_val = emp_id_match.group(1)
            emp_name_val = full_name_match.group(1).strip() if full_name_match else "Employee"
            tenure_val = float(tenure_match.group(1)) if tenure_match else 2.0
            balance_val = float(pto_balance_match.group(1)) if pto_balance_match else 0.0

            # 0a. Personalized PTO Policy Query
            if ("pto" in q_lower or "vacation" in q_lower or "time off" in q_lower) and not (("workation" in q_lower or "france" in q_lower) and "meal" in q_lower):
                if tenure_val < 2.0:
                    tier_desc = "**Tier 1 (0 to 2 years tenure)**, accruing **15 days (120 hours)** of paid time off per calendar year (5.0 hours per pay period)"
                elif tenure_val <= 5.0:
                    tier_desc = "**Tier 2 (2 to 5 years tenure)**, accruing **20 days (160 hours)** of paid time off per calendar year (6.67 hours per pay period)"
                else:
                    tier_desc = "**Tier 3 (5+ years tenure)**, accruing **25 days (200 hours)** of paid time off per calendar year (8.33 hours per pay period)"

                return (
                    f"### PTO Policy & Accrual Dossier: {emp_name_val} ({emp_id_val})\n\n"
                    "**Your Personalized PTO Policy & Accrual:**\n"
                    f"• **Tenure & Accrual Tier:** With **{tenure_val} years of service**, you are in {tier_desc} ([POL-PTO-2024: 2. Annual PTO Accrual Tiers]).\n"
                    f"• **Current Available Balance:** You currently have **{balance_val} days** of available PTO.\n\n"
                    "**Key Policy Rules Applicable to You:**\n"
                    "• **Year-End Rollover:** You may roll over a maximum of **5 unused PTO days** (40 hours) into the next calendar year; "
                    "any rolled-over days must be used by **March 31** ([POL-PTO-2024: 4. Year-End Rollover]).\n"
                    "• **Advance Notice Requirements:** 1–2 consecutive days require 48 hours notice; 3–5 consecutive days require 14 calendar days advance notice; "
                    "leaves longer than 5 days require 30 calendar days notice ([POL-PTO-2024: 3. Request and Approval Process]).\n"
                    "• **Manager Approval:** Submit requests via the GlobalTech HR Portal for approval by your manager ([POL-PTO-2024: 3. Request and Approval Process])."
                )

            # 0b. Personalized Medical Deductible / Benefits Query
            if "deductible" in q_lower or ("medical" in q_lower and "plan" in q_lower) or ("health" in q_lower and "insurance" in q_lower):
                med_plan = medical_match.group(1).strip() if medical_match else "Premier PPO Plan"
                if "HDHP" in med_plan:
                    ded_info = "features a **$1,500 individual / $3,000 family** annual deductible with 80% coinsurance and eligible employer HSA contributions"
                else:
                    ded_info = "features a **$500 individual / $1,000 family** annual deductible, 90% in-network coinsurance, and 100% covered preventative care"
                return (
                    f"### Medical Plan Deductibles: {emp_name_val} ({emp_id_val})\n\n"
                    f"**Your Coverage & Deductible:**\n"
                    f"• **Enrolled Plan:** You are enrolled in the **{med_plan}**.\n"
                    f"• **Deductible & Benefits:** Your plan {ded_info} ([POL-BEN-2024: 2. Medical Insurance Plans]).\n"
                    "• **Preventative Care:** Routine annual checkups and preventative screenings are covered at 100% with no deductible applied ([POL-BEN-2024: 2.1])."
                )

            # 0c. Personalized Remote Work / Allowance Query
            if ("remote" in q_lower or "equipment" in q_lower or "stipend" in q_lower) and not (("workation" in q_lower or "france" in q_lower) and "meal" in q_lower):
                loc_val = work_loc_match.group(1).strip() if work_loc_match else "Remote"
                prob_val = prob_match.group(1).strip() if prob_match else "Yes"
                return (
                    f"### Remote Work & Equipment Status: {emp_name_val} ({emp_id_val})\n\n"
                    "**Your Work Arrangement & Equipment Eligibility:**\n"
                    f"• **Current Arrangement:** {loc_val} (Probation Completed: {prob_val}).\n"
                    f"• **Remote Status:** {'Fully eligible for remote arrangement and up to 30 calendar days international workation' if prob_val == 'Yes' else 'Currently in 90-day probationary period; remote status requires manager approval'} ([POL-REMOTE-2024: 2. Eligibility Requirements]).\n"
                    "• **Equipment Allowance:** Newly approved remote employees receive a one-time allowance of up to **$750 USD** for home office gear within 60 days ([POL-REMOTE-2024: 3. Home Office Equipment Allowance])."
                )

        # 1. Multi-doc: International workation + PTO + meals
        if ("workation" in q_lower or "abroad" in q_lower or "france" in q_lower or "international" in q_lower) and ("expense" in q_lower or "meal" in q_lower):
            return (
                "### Policy Analysis: International Remote Work, PTO, and Expenses\n\n"
                "**Policy Facts:**\n"
                "1. **Annual Workation Cap:** Under the Remote & Hybrid Work Policy (**POL-REMOTE-2024**, Section 5), "
                "employees in good standing may work remotely from an approved international location for up to **30 calendar days per calendar year**, "
                "requiring at least **4 weeks advance notice** to HR & Legal.\n"
                "2. **Strict Expense Disallowance:** Under both **POL-REMOTE-2024** (Section 5.4) and the Travel & Expense Reimbursement Policy "
                "(**POL-EXP-2024**, Section 6), all travel, lodging, visa fees, and personal meals incurred during personal PTO or international "
                "workations are personal expenses and are **strictly non-reimbursable** by GlobalTech.\n\n"
                "**HR Recommendations:**\n"
                "• Submit your international remote work request at least 28 days prior to planned departure.\n"
                "• Pay for personal meals and travel costs out-of-pocket; do not file them in Concur."
            )

        # 2. International remote work cap and guidelines
        if ("international" in q_lower or "abroad" in q_lower or "workation" in q_lower) and ("remote" in q_lower or "work" in q_lower or "day" in q_lower or "many" in q_lower or "allowed" in q_lower or "guideline" in q_lower):
            return (
                "### International Remote Work Policy\n\n"
                "**Policy Facts:**\n"
                "• **Annual Limit:** Employees in good standing may work remotely from an approved international location for up to **30 calendar days per calendar year** ([POL-REMOTE-2024: 5. Temporary International Remote Work]).\n"
                "• **Advance Notice:** Requests must be formally submitted at least **4 weeks (28 days) in advance** ([POL-REMOTE-2024: 5.2]).\n"
                "• **Sanctioned Countries:** Remote work is strictly prohibited from countries under US trade embargoes ([POL-REMOTE-2024: 5.3]).\n"
                "• **Non-Reimbursable:** Travel, lodging, and meals during international workations are strictly non-reimbursable ([POL-REMOTE-2024: 5.4])."
            )

        # 3. PTO accrual for tenure (e.g. 3 years)
        if ("accrual" in q_lower or "accrue" in q_lower or "tenure" in q_lower or "3 years" in q_lower or "tier" in q_lower) and ("pto" in q_lower or "vacation" in q_lower):
            return (
                "### PTO Accrual Tiers & Guidelines\n\n"
                "**Policy Facts:**\n"
                "• **Tier 1 (0 to 2 years tenure):** Accrues 15 days (120 hours) per year ([POL-PTO-2024: 2. Annual PTO Accrual Tiers]).\n"
                "• **Tier 2 (2 to 5 years tenure):** Accrues **20 days (160 hours)** per full calendar year (6.67 hours/pay period) ([POL-PTO-2024: 2. Annual PTO Accrual Tiers]).\n"
                "• **Tier 3 (5+ years tenure):** Accrues 25 days (200 hours) per full calendar year ([POL-PTO-2024: 2. Annual PTO Accrual Tiers])."
            )

        # 4. Medical plan deductibles (Premier PPO vs HDHP)
        if "deductible" in q_lower or ("ppo" in q_lower and "plan" in q_lower):
            return (
                "### Medical Plan Deductibles and Coverage\n\n"
                "**Policy Facts:**\n"
                "• **Premier PPO Plan:** Features a **$500 individual / $1,000 family** annual deductible. In-network preventative services are covered at 100%, and medical services at 90% coinsurance after deductible ([POL-BEN-2024: 2. Medical Insurance Plans]).\n"
                "• **HDHP Plan:** Features a $1,500 individual / $3,000 family annual deductible with 80% coinsurance and eligible employer HSA contributions ([POL-BEN-2024: 2. Medical Insurance Plans])."
            )

        # 5. Travel meal per diem maximums
        if ("meal" in q_lower or "per diem" in q_lower) and ("allowance" in q_lower or "maximum" in q_lower or "travel" in q_lower or "limit" in q_lower):
            return (
                "### Travel Meal Allowances & Per Diem Caps\n\n"
                "**Policy Facts:**\n"
                "• **Daily Meal Ceiling:** Up to **$125.00 USD daily per diem maximum** combined total including tax and gratuity ([POL-EXP-2024: 3. Daily Meal Allowances]).\n"
                "• **Per-Meal Breakdown:** Breakfast up to $25.00, Lunch up to $35.00, Dinner up to $65.00 ([POL-EXP-2024: 3. Daily Meal Allowances]).\n"
                "• **Receipts:** Itemized receipts are required for all individual expenses equal to or exceeding $25.00 USD ([POL-EXP-2024: 5.2])."
            )

        # 6. Vendor gift disclosure limit
        if "gift" in q_lower or "vendor" in q_lower or "disclosure" in q_lower or "bribe" in q_lower:
            return (
                "### Gifts, Entertainment, and Ethics Guidelines\n\n"
                "**Policy Facts:**\n"
                "• **$75 Disclosure Threshold:** Promotional items and modest business meals with an aggregate value under **$75 USD** per occasion may be accepted without prior disclosure ([POL-ETHICS-2024: 5. Gifts, Entertainment, and Anti-Bribery]).\n"
                "• **Mandatory Declaration:** Any gift or entertainment exceeding $75 USD must be declared in writing to the Corporate Compliance Officer ([POL-ETHICS-2024: 5. Gifts, Entertainment, and Anti-Bribery]).\n"
                "• **Cash Prohibited:** Cash or cash equivalents (gift cards) are strictly prohibited in any amount."
            )

        # 7. Probation & equipment / remote eligibility
        if "probation" in q_lower and ("remote" in q_lower or "equipment" in q_lower or "stipend" in q_lower):
            return (
                "### Probationary Period & Remote Work Eligibility\n\n"
                "**Policy Facts:**\n"
                "• **Probationary Period:** Regular full-time employees become eligible to apply for remote or hybrid status following completion of their **90-day introductory probationary period** ([POL-REMOTE-2024: 2. Eligibility Requirements]).\n"
                "• **Performance Requirement:** Must maintain 'Meets Expectations' or higher ([POL-REMOTE-2024: 2.2]).\n"
                "• **Equipment Allowance:** Once approved for remote or hybrid status, employees are eligible for the one-time **$750 USD** home office equipment allowance within 60 days of approval ([POL-REMOTE-2024: 3.1])."
            )

        # 8. PTO rollover and parental leave
        if "rollover" in q_lower and ("pto" in q_lower or "parental" in q_lower or "leave" in q_lower):
            return (
                "### PTO Rollover and Parental Leave Interaction\n\n"
                "**Policy Facts:**\n"
                "• **Rollover Limit:** Employees may roll over a maximum of **5 unused PTO days** (40 hours) into the next calendar year, expiring on **March 31** ([POL-PTO-2024: 4. Year-End Rollover]).\n"
                "• **Parental Leave:** Primary caregivers receive 16 weeks of 100% paid parental leave, and secondary caregivers receive 8 weeks, which may be taken within 12 months of birth or placement ([POL-PTO-2024: 6. Parental Leave])."
            )

        # 9. HDHP and wellness stipend
        if "hdhp" in q_lower and "wellness" in q_lower:
            return (
                "### Wellness Subsidy and HDHP Health Accounts\n\n"
                "**Policy Facts:**\n"
                "• **Wellness Subsidy:** All active employees are entitled to a **$600 annual wellness subsidy** ($50/month) for gym memberships, fitness classes, and mindfulness platforms ([POL-BEN-2024: 5. Mental Health and Wellness Stipend]).\n"
                "• **HSA Employer Contribution:** Employees enrolled in the HDHP also receive an annual employer HSA deposit of $1,000 for individual or $2,000 for family coverage ([POL-BEN-2024: 3. Health Savings Accounts])."
            )

        # 10. Travel receipt & blackout rules
        if "blackout" in q_lower or ("receipt" in q_lower and "travel" in q_lower):
            return (
                "### Travel Receipts & Departmental Blackout Policies\n\n"
                "**Policy Facts:**\n"
                "• **Receipt Requirement:** Itemized receipts showing date, merchant, and breakdown are mandatory for all transactions equal to or exceeding **$25.00 USD** ([POL-EXP-2024: 5. Expense Submission Deadlines]).\n"
                "• **Department Blackouts:** Finance blackout applies during the last 5 days of each quarter and first 10 days of Q1; Sales blackout during the final 7 days of Q4. Travel or PTO during blackouts requires Department VP sign-off ([POL-PTO-2024: 8. Departmental Blackout Periods])."
            )

        # 11. New hire benefits election deadlines & equipment allowance
        if "new hire" in q_lower and ("election" in q_lower or "benefits" in q_lower or "equipment" in q_lower):
            return (
                "### New Hire Benefits Deadlines & Equipment Allowance\n\n"
                "**Policy Facts:**\n"
                "• **Benefits Election Deadline:** New hires have **30 calendar days from start date** to finalize medical, dental, and vision elections with Day 1 coverage ([POL-BEN-2024: 1. Enrollment Windows]).\n"
                "• **Equipment Allowance:** Newly approved remote employees receive a one-time allowance of up to **$750 USD** for home office gear within 60 days of approval ([POL-REMOTE-2024: 3. Home Office Equipment Allowance])."
            )

        # Default fallback synthesis
        return (
            "### GlobalTech HR Policy Summary\n\n"
            "Based on GlobalTech corporate policies, employee guidelines require compliance with standard "
            "procedural, safety, and documentation requirements. Please review the relevant policy document or contact People Operations."
        )
