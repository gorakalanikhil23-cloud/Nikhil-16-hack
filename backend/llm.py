"""Optional local Ollama explanations with deterministic fallbacks."""

import json
import os
import re
from typing import Any

import requests

from backend.metrics import forecast_metrics, today_metrics


MODEL = "gemma2:2b"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
_EXPLANATION_CACHE: dict[str, dict[str, Any]] = {}
_MEDICAL_TERMS = re.compile(
    r"\b(diagnos(?:e|is|ing)|symptom|treatment|medication|medicine|prescription|"
    r"disease|patient|clinical|prognosis|dosage|therapy|medical|health|illness|"
    r"diabetes|cancer|infection|injury|pain|fever|allergy|surgery|vaccine)\b|"
    r"\bblood pressure\b",
    re.IGNORECASE,
)


def ollama_available(timeout: float = 2.0) -> bool:
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        response.raise_for_status()
        models = response.json().get("models", [])
        return any(model.get("name", "").split(":")[0] == MODEL.split(":")[0] for model in models)
    except (requests.RequestException, ValueError, AttributeError):
        return False


def _evidence(row: Any) -> dict[str, Any]:
    return {
        "appointments": int(round(row.appointments)),
        "staff": int(round(row.staff_available)),
        "avg_task_minutes": round(float(row.avg_task_minutes), 1),
        "utilization_percent": round(float(row.utilization) * 100, 1),
        "emergency_cases": int(round(row.emergency_cases)),
    }


def fallback_explanation(department: str, risk: str, evidence: dict[str, Any]) -> dict[str, Any]:
    utilization = evidence["utilization_percent"]
    if risk == "Critical":
        problem = (
            f"{department} demand exceeds available shift capacity "
            f"({utilization:.1f}% utilization)."
        )
        window = "Current shift; review coverage and workload now."
        actions = [
            "Rebalance available staff to the highest-demand tasks.",
            "Review appointment scheduling and defer non-urgent work.",
            "Escalate capacity constraints to the operations lead.",
        ]
    else:
        problem = (
            f"{department} is approaching capacity "
            f"({utilization:.1f}% utilization)."
        )
        window = "Current shift; monitor workload through the day."
        actions = [
            "Review the roster for short-term coverage options.",
            "Spread appointments across available time slots.",
            "Monitor workload and reassess staffing during the shift.",
        ]
    return {"problem": problem, "risk_window": window, "actions": actions}


def explain_department(department: str, risk: str, evidence: dict[str, Any]) -> dict[str, Any]:
    cache_key = json.dumps([department, risk, evidence], sort_keys=True)
    if cache_key in _EXPLANATION_CACHE:
        return _EXPLANATION_CACHE[cache_key]

    fallback = fallback_explanation(department, risk, evidence)
    if not ollama_available():
        _EXPLANATION_CACHE[cache_key] = fallback
        return fallback

    prompt = f"""You explain hospital operational bottlenecks, not clinical care.
Use only the evidence numbers below. Do not calculate or invent numbers.
Do not give medical advice. Each action must be under 15 words.
Return valid JSON only with keys "problem", "risk_window", and "actions".
"actions" must contain exactly 3 short strings.
Department: {department}
Risk: {risk}
Evidence: {json.dumps(evidence)}
"""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False, "format": "json"},
            timeout=60,
        )
        response.raise_for_status()
        text = response.json().get("response", "")
        text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.IGNORECASE)
        parsed = json.loads(text)
        if (
            isinstance(parsed, dict)
            and isinstance(parsed.get("problem"), str)
            and isinstance(parsed.get("risk_window"), str)
            and isinstance(parsed.get("actions"), list)
            and len(parsed["actions"]) == 3
            and all(isinstance(action, str) and len(action.split()) < 15 for action in parsed["actions"])
        ):
            result = {
                "problem": parsed["problem"],
                "risk_window": parsed["risk_window"],
                "actions": parsed["actions"],
            }
            _EXPLANATION_CACHE[cache_key] = result
            return result
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        pass

    _EXPLANATION_CACHE[cache_key] = fallback
    return fallback


def _format_context() -> tuple[str, Any, Any]:
    today = today_metrics()
    forecast = forecast_metrics()
    fields = ["department", "risk", "appointments", "staff_available", "avg_task_minutes",
              "emergency_cases", "demand_minutes", "capacity_minutes", "utilization"]
    return today[fields].to_string(index=False), today, forecast


def _question_fallback(question: str, today: Any, forecast: Any) -> str:
    query = question.lower()
    if "forecast" in query or "tomorrow" in query:
        rows = forecast.sort_values("utilization", ascending=False)
        return "Tomorrow's forecast utilization: " + "; ".join(
            f"{row.department}: {row.utilization * 100:.1f}% ({row.risk})"
            for row in rows.itertuples()
        )
    if "critical" in query or "warning" in query:
        selected = today.loc[today["risk"].isin(["Critical", "Warning"])]
        if selected.empty:
            return "There are no Warning or Critical departments today."
        return "Flagged departments: " + "; ".join(
            f"{row.department}: {row.risk} at {row.utilization * 100:.1f}% utilization"
            for row in selected.itertuples()
        )
    if "most overloaded" in query or "highest utilization" in query or "busiest" in query:
        row = today.sort_values("utilization", ascending=False).iloc[0]
        return (
            f"{row['department']} has the highest current utilization at "
            f"{row['utilization'] * 100:.1f}% ({row['risk']})."
        )

    department = next(
        (name for name in today["department"] if name.lower() in query),
        None,
    )
    if department:
        row = today.loc[today["department"] == department].iloc[0]
        forecast_row = forecast.loc[forecast["department"] == department].iloc[0]
        return (
            f"{department} today: {row['risk']} risk, {row['utilization'] * 100:.1f}% "
            f"utilization, {int(row['appointments'])} appointments, "
            f"{int(row['staff_available'])} staff, and {int(row['emergency_cases'])} "
            f"emergency cases. Tomorrow's forecast is {forecast_row['utilization'] * 100:.1f}%."
        )
    return (
        "Try: “Which department is most overloaded?”, “What is the forecast tomorrow?”, "
        "or “How is Radiology doing?”"
    )


def answer_question(question: str, context: str | None = None) -> dict[str, str]:
    clean_question = question.strip()
    if len(clean_question) > 300:
        raise ValueError("Questions must be 300 characters or fewer.")
    if _MEDICAL_TERMS.search(clean_question):
        return {"answer": "This tool covers operational data only.", "mode": "fallback"}

    computed_context, today, forecast = _format_context()
    if ollama_available():
        prompt = f"""Answer the user's question using only the operational data context.
Do not calculate or introduce numbers not present in the context.
Do not provide diagnosis or medical advice. If the answer is absent, say so.
Context:
{context or computed_context}
Question: {clean_question}
"""
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": MODEL, "prompt": prompt, "stream": False},
                timeout=60,
            )
            response.raise_for_status()
            answer = response.json().get("response", "").strip()
            if answer:
                return {"answer": answer, "mode": "local"}
        except (requests.RequestException, ValueError, AttributeError):
            pass
    return {"answer": _question_fallback(clean_question, today, forecast), "mode": "fallback"}
