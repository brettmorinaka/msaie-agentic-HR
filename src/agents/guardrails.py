import re
from typing import Tuple, Optional, Dict, Any, List

HR_DOMAINS = [
    "pto", "vacation", "leave", "sick", "holiday", "time off", "absence", "bereavement", "parental",
    "remote", "hybrid", "work from home", "wfh", "office", "stipend", "equipment", "allowance", "workation",
    "benefit", "insurance", "health", "dental", "vision", "fsa", "hsa", "wellness", "401k", "retirement", "pension",
    "expense", "travel", "reimburse", "per diem", "hotel", "flight", "mileage", "meal",
    "conduct", "harassment", "ethics", "reporting", "whistleblower", "conflict of interest", "moonlighting", "gift",
    "onboard", "new hire", "checklist", "training", "profile", "ticket", "manager", "probation", "performance",
    "payroll", "salary", "compensation", "hr", "policy", "employee"
]

OUT_OF_SCOPE_TRIGGERS = [
    "recipe", "bake", "cook", "quantum physics", "write python", "debug code",
    "weather tomorrow", "capital of", "who won the super bowl", "movie recommendation",
    "cryptocurrency trading", "stock market prediction", "essay on shakespeare", "two sum"
]


class HRGuardrails:
    """
    Safety, Scope, and Compliance Guardrails for HR Multi-Agent System.
    """

    @staticmethod
    def check_scope(query: str, workflow: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Determines whether a user query falls within HR company policies and workflows.
        Returns: (is_in_scope, refusal_reason_if_out_of_scope)
        """
        if workflow == "out_of_scope":
            return False, (
                "I am the GlobalTech HR Assistant, specialized strictly in internal company policies, "
                "benefits, onboarding, time-off requests, and employee workflows. "
                "I cannot assist with questions outside our HR scope."
            )

        q_lower = query.lower()

        # Check explicit out of scope triggers
        for trigger in OUT_OF_SCOPE_TRIGGERS:
            if trigger in q_lower:
                return False, (
                    "I am the GlobalTech HR Assistant, specialized strictly in internal company policies, "
                    "benefits, onboarding, time-off requests, and employee workflows. "
                    "I cannot assist with questions outside our HR scope."
                )

        has_hr_keyword = any(kw in q_lower for kw in HR_DOMAINS)
        has_emp_id = bool(re.search(r"EMP-\w+", query, re.IGNORECASE))

        if not has_hr_keyword and not has_emp_id:
            words = q_lower.split()
            if len(words) > 3 and not any(w in ["hello", "hi", "help", "who", "what", "can you", "good morning"] for w in words):
                return False, (
                    "Your question does not appear to relate to GlobalTech HR policies, employee benefits, "
                    "onboarding, or workplace guidelines. Please ask an HR-related question, or contact "
                    "People Operations at people-ops@globaltech.internal."
                )

        return True, None

    @staticmethod
    def check_ambiguity(query: str, workflow: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Checks whether a requested workflow is missing necessary information.
        """
        if workflow == "clarification":
            return True, (
                "To assist with your time off request, please provide your Employee ID (e.g., EMP-101) "
                "and the target dates or number of days you plan to take."
            )

        q_lower = query.lower()

        # Check if user is asking to book or request time off without dates or employee ID
        is_requesting_time_off = (
            any(w in q_lower for w in ["time off", "pto", "vacation", "leave"]) and
            (bool(re.search(r"\b(?:book|request|take)\b", q_lower)) or "want to take" in q_lower)
        )

        # But if it's an informational question ("how many days", "how do pto", "what is"), it's not ambiguous
        is_info_question = bool(re.search(r"^(?:how|what|can|when|who|where)\b", q_lower.strip()))

        if is_requesting_time_off and not is_info_question:
            has_emp_id = bool(re.search(r"EMP-\w+", query, re.IGNORECASE))
            has_days_or_dates = bool(re.search(r"\d+\s*(?:day|days|week|weeks|hours)", q_lower)) or bool(re.search(r"\d{4}-\d{2}-\d{2}", query))
            if not has_emp_id and not has_days_or_dates:
                return True, (
                    "To assist with your time off request, please provide your Employee ID (e.g., EMP-101) "
                    "and the target dates or number of days you plan to take."
                )

        return False, None

    @staticmethod
    def enforce_action_safety(action: str, params: Dict[str, Any], confirmed: bool) -> Tuple[bool, str]:
        """
        Validates safety for state-changing actions (e.g. creating tickets or modifying records).
        """
        if action in ["create_ticket", "create_mock_hr_ticket", "submit_request"]:
            if not confirmed:
                return False, "CONFIRMATION_REQUIRED"
            return True, "MOCK_EXECUTED"
        return True, "SAFE"
