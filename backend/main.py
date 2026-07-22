"""
API HTTP pour le frontend React. Reutilise le moteur existant (agents/,
tools/, core/) sans le modifier: ce fichier ne fait qu'orchestrer les
appels HTTP -> ingestion_agent / translator_agent et serialiser
l'EngineState en JSON (backend/serialize.py).

Etat: un seul diagnostic actif a la fois, garde en memoire process (pas de
base de donnees, pas de multi-utilisateur) - meme perimetre que la demo
Streamlit d'origine, qui gardait tout dans st.session_state.
"""
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from agents import ingestion_agent, translator_agent
from backend.serialize import state_to_dict
from core.llm import llm_is_available
from core.state import EngineState
from tools import data_loader, retrieval
from tools.export import build_export_markdown
from tools.schema_mapping import ROLE_SCHEMAS, classify_and_normalize

PROCESS_ID = "P01"

app = FastAPI(title="SOS Redemarrage API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_state: EngineState | None = None


def _read_csv_bytes(raw: bytes) -> pd.DataFrame | None:
    import io
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding=encoding)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception:
            continue
    return None


@app.post("/api/diagnose")
async def diagnose(
    message: str = Form(""),
    site_visible: bool = Form(False),
    can_pay: bool = Form(False),
    incident_dt: str = Form("2026-06-08 08:15"),
    csv_files: list[UploadFile] = File(default=[]),
    docx_files: list[UploadFile] = File(default=[]),
):
    global _state

    report = []
    if csv_files:
        uploads = {}
        for f in csv_files:
            raw = await f.read()
            df = _read_csv_bytes(raw)
            if df is not None:
                uploads[f.filename] = df
        tables, results = classify_and_normalize(uploads)
        data_loader.set_active_tables(tables)
        try:
            data_loader.set_incident_time(pd.Timestamp(incident_dt))
        except (ValueError, TypeError):
            pass
        found_roles = {r.role for r in results if r.role}
        report = [
            {"filename": r.filename, "role": r.role, "score": r.score}
            for r in results
        ] + [
            {"filename": None, "role": role, "score": None, "missing": True}
            for role in sorted(set(ROLE_SCHEMAS.keys()) - found_roles)
        ]
    else:
        data_loader.clear_active_tables()

    if docx_files:
        docs = {f.filename: await f.read() for f in docx_files}
        retrieval.set_active_docs(docs)
    else:
        retrieval.clear_active_docs()

    _state = ingestion_agent.run(PROCESS_ID)

    return {
        "classification_report": report,
        "dashboard": state_to_dict(_state, llm_is_available()),
    }


@app.get("/api/dashboard")
async def dashboard():
    if _state is None:
        return {"dashboard": None}
    return {"dashboard": state_to_dict(_state, llm_is_available())}


@app.post("/api/ask")
async def ask(payload: dict):
    if _state is None:
        return {"answer": "Aucun diagnostic en memoire — lancez-en un depuis la page de depot."}
    question = payload.get("question", "")
    answer = translator_agent.answer_question(_state, question)
    return {"answer": answer}


@app.get("/api/export", response_class=PlainTextResponse)
async def export():
    if _state is None:
        return PlainTextResponse("Aucun diagnostic en memoire.", status_code=404)
    md = build_export_markdown(_state)
    return PlainTextResponse(
        md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="plan_redemarrage_{_state.process_id}.md"'},
    )


# En production, sert le build Vite (frontend/dist) depuis le meme process
# uvicorn - evite d'avoir un second serveur a exposer pour la demo.
_dist_dir = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _dist_dir.exists():
    app.mount("/", StaticFiles(directory=_dist_dir, html=True), name="frontend")
