"""FastAPI application for the synthetic hospital operations dashboard."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.llm import answer_question, explain_department, ollama_available, MODEL
from backend.metrics import forecast_metrics, load_data, today_metrics


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
app = FastAPI(title="Hospital Operations Dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300)


def _records(frame: Any) -> list[dict[str, Any]]:
    records = frame.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if hasattr(value, "isoformat"):
                record[key] = value.isoformat()
            elif hasattr(value, "item"):
                record[key] = value.item()
    return records


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Any, _exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Unable to process the request."})


@app.get("/api/status")
def status() -> dict[str, str]:
    local = ollama_available()
    return {"mode": "local" if local else "fallback", "model": MODEL}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    today = today_metrics(load_data())
    counts = today["risk"].value_counts()
    return {
        "counts": {
            "normal": int(counts.get("Normal", 0)),
            "warning": int(counts.get("Warning", 0)),
            "critical": int(counts.get("Critical", 0)),
        },
        "departments": _records(today),
    }


@app.get("/api/bottlenecks")
def bottlenecks() -> dict[str, Any]:
    today = today_metrics(load_data())
    flagged = today.loc[today["risk"].isin(["Warning", "Critical"])]
    results = []
    for row in flagged.itertuples():
        evidence = {
            "appointments": int(row.appointments),
            "staff": int(row.staff_available),
            "avg_task_minutes": int(row.avg_task_minutes),
            "utilization_percent": round(float(row.utilization) * 100, 1),
            "emergency_cases": int(row.emergency_cases),
        }
        results.append(
            {
                "department": row.department,
                "evidence": evidence,
                "risk": row.risk,
                "explanation": explain_department(row.department, row.risk, evidence),
            }
        )
    return {"bottlenecks": results}


@app.get("/api/forecast")
def forecast() -> dict[str, Any]:
    return {"departments": _records(forecast_metrics(load_data()))}


@app.post("/api/ask")
def ask(request: QuestionRequest) -> dict[str, str]:
    try:
        return answer_question(request.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
