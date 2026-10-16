# CareOps — Hospital Operations Dashboard

CareOps is a small dashboard that highlights synthetic hospital workload and capacity bottlenecks, explains operational risks, forecasts tomorrow's utilization, and answers questions about the data. It uses no patient data, real names, diagnosis, or clinical recommendations.

## Architecture

- **Backend:** FastAPI, pandas, requests, and Uvicorn.
- **Frontend:** Plain HTML, CSS, and JavaScript served by FastAPI; no frontend build step.
- **AI:** Optional local Ollama `gemma2:2b` for explanations and answers. When unavailable, the dashboard remains fully usable with rule-based explanations and keyword answers. No cloud AI services are used.
- **Metrics:** All arithmetic, risk classification, and forecasts are computed in Python before any evidence is sent to the model.
- **Data:** Reproducible synthetic data in `data/operations.csv`.

## Local setup

Requires Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python backend\generate_data.py
# Optional: install Ollama, then pull the local model
ollama pull gemma2:2b
uvicorn backend.main:app --reload
```

Open http://localhost:8000. Without Ollama the app runs in fallback mode; with the model available locally it uses AI-written operational explanations.

## Render deployment

1. Push this repository to GitHub.
2. In Render, choose **New +** → **Blueprint** and connect the repository.
3. Confirm the `careops-dashboard` free web service from `render.yaml`.
4. Deploy; the public service runs in fallback mode without Ollama.

The app works fully offline locally in fallback mode and switches to rule-based fallback whenever Ollama is unavailable, including on public deployment. The only permitted network service for AI is the configured local Ollama endpoint (`OLLAMA_URL`).

## Operational assumptions

Capacity is modeled as 480 minutes per staff member per shift, with each emergency case weighted at 45 minutes. Utilization below 80% is Normal, 80% through 100% is Warning, and above 100% is Critical. Tomorrow's forecast averages the prior seven days' appointments, emergency cases, staffing, and average task time per department.

**Operational data only. Not for clinical decisions.**
