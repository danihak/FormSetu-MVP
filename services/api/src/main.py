"""
FormSetu API Server
====================
REST API for schema registry, form-filling sessions, and validation.

Run: uvicorn services.api.src.main:app --reload
Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import os

app = FastAPI(
    title="FormSetu API",
    description="Form Intelligence Layer for India's Voice DPI. "
                "Schema registry, conversation engine, and Indian data validators.",
    version="0.1.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Health Check ----

@app.get("/health")
async def health():
    return {"status": "ok", "service": "formsetu-api", "version": "0.1.0"}


# ---- Schema Registry ----

# In-memory for MVP. Replace with PostgreSQL in production.
_schemas: dict = {}

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "../../../packages/schema-spec/examples")


@app.on_event("startup")
async def load_example_schemas():
    """Load example schemas on startup."""
    if os.path.exists(EXAMPLES_DIR):
        for filename in os.listdir(EXAMPLES_DIR):
            if filename.endswith(".json"):
                with open(os.path.join(EXAMPLES_DIR, filename)) as f:
                    schema = json.load(f)
                    _schemas[schema["form_id"]] = schema


class SchemaCreate(BaseModel):
    schema_data: dict


@app.get("/api/v1/schemas")
async def list_schemas(department: Optional[str] = None):
    """List all registered form schemas."""
    schemas = list(_schemas.values())
    if department:
        schemas = [s for s in schemas if s.get("metadata", {}).get("department", "").lower() == department.lower()]
    return {
        "count": len(schemas),
        "schemas": [
            {
                "form_id": s["form_id"],
                "name": s["metadata"]["name"],
                "department": s["metadata"].get("department"),
                "version": s.get("version"),
                "field_count": len(s.get("fields", {})),
            }
            for s in schemas
        ],
    }


@app.get("/api/v1/schemas/{form_id}")
async def get_schema(form_id: str):
    """Get a form schema by ID."""
    if form_id not in _schemas:
        raise HTTPException(404, f"Schema '{form_id}' not found")
    return _schemas[form_id]


@app.post("/api/v1/schemas", status_code=201)
async def create_schema(body: SchemaCreate):
    """Register a new form schema."""
    schema = body.schema_data
    form_id = schema.get("form_id")
    if not form_id:
        raise HTTPException(400, "schema_data must contain 'form_id'")
    if form_id in _schemas:
        raise HTTPException(409, f"Schema '{form_id}' already exists. Use PUT to update.")
    _schemas[form_id] = schema
    return {"form_id": form_id, "status": "created"}


# ---- Session Management ----

_sessions: dict = {}


class SessionStart(BaseModel):
    form_id: str
    language: str = "hi"
    channel: str = "voice"


class SessionRespond(BaseModel):
    input: str
    input_type: str = "text"  # "text" or "audio_base64"


@app.post("/api/v1/sessions")
async def start_session(body: SessionStart):
    """Start a new form-filling session."""
    if body.form_id not in _schemas:
        raise HTTPException(404, f"Schema '{body.form_id}' not found")

    # Lazy import to avoid circular deps during startup
    from packages.engine.src.conversation_engine import ConversationEngine

    engine = ConversationEngine()
    session = engine.start_session(_schemas[body.form_id], body.language, body.channel)
    _sessions[session["session_id"]] = {"session": session, "engine": engine}

    response = engine.get_next_prompt(session)
    return {
        "session_id": session["session_id"],
        "state": response.state.value,
        "prompt": response.prompt_text,
        "progress": response.progress,
    }


@app.post("/api/v1/sessions/{session_id}/respond")
async def session_respond(session_id: str, body: SessionRespond):
    """Submit user response for current field."""
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found")

    ctx = _sessions[session_id]
    response = ctx["engine"].process_input(ctx["session"], body.input)

    return {
        "session_id": session_id,
        "state": response.state.value,
        "prompt": response.prompt_text,
        "field_id": response.field_id,
        "progress": response.progress,
        "confirmation_value": response.confirmation_value,
        "error": response.error,
    }


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    """Get current session state."""
    if session_id not in _sessions:
        raise HTTPException(404, "Session not found")
    session = _sessions[session_id]["session"]
    return {
        "session_id": session_id,
        "form_id": session["form_id"],
        "state": session["state"],
        "language": session["language"],
        "fields": {
            fid: {
                "value": fs.get("normalized_value") or fs.get("value"),
                "confirmed": fs["confirmed"],
                "skipped": fs["skipped"],
            }
            for fid, fs in session["field_states"].items()
            if fs["confirmed"] or fs["skipped"]
        },
    }


# ---- Standalone Validators ----

class ValidateRequest(BaseModel):
    value: str


@app.post("/api/v1/validate/aadhaar")
async def validate_aadhaar(body: ValidateRequest):
    """Validate an Aadhaar number."""
    from packages.validator.src.validators.aadhaar import AadhaarValidator
    result = AadhaarValidator().validate(body.value)
    return {"valid": result.valid, "normalized": result.normalized,
            "error_code": result.error_code, "message": result.message}


@app.post("/api/v1/validate/pan")
async def validate_pan(body: ValidateRequest):
    """Validate a PAN number."""
    from packages.validator.src.validators.pan import PANValidator
    result = PANValidator().validate(body.value)
    return {"valid": result.valid, "normalized": result.normalized,
            "error_code": result.error_code, "message": result.message}
