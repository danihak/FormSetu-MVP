"""
FormSetu Conversation Engine
=============================
Finite State Machine that takes a GovForm Schema and walks a user
through filling it via sequential prompts, validation, and confirmation.

Design principle: DETERMINISTIC. No LLM in the critical path.
Every state transition is auditable and reproducible.
"""

import json
import uuid
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


class SessionState(Enum):
    CREATED = "created"
    GREETING = "greeting"
    COLLECTING = "collecting"         # Actively collecting a field
    CONFIRMING = "confirming"         # Asking user to confirm a field value
    RETRYING = "retrying"             # Field validation failed, asking again
    REVIEWING = "reviewing"           # All fields done, reviewing summary
    SUBMITTING = "submitting"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class FieldState:
    field_id: str
    attempts: int = 0
    max_attempts: int = 3
    value: Optional[str] = None
    normalized_value: Optional[str] = None
    confirmed: bool = False
    skipped: bool = False


@dataclass
class EngineResponse:
    """Response from engine to be sent to user via channel adapter."""
    session_id: str
    state: SessionState
    prompt_text: dict                 # i18n: {"en": "...", "hi": "..."}
    field_id: Optional[str] = None
    progress: dict = field(default_factory=dict)  # {"completed": 3, "total": 15}
    expects_input: bool = True
    confirmation_value: Optional[str] = None  # Value being confirmed
    error: Optional[dict] = None      # Error message from validation


class ConversationEngine:
    """
    Core FSM engine. Stateless — all state is in the Session object.
    
    Usage:
        engine = ConversationEngine()
        session = engine.start_session(schema, language="hi")
        response = engine.get_next_prompt(session)
        # ... send prompt to user, get input ...
        response = engine.process_input(session, user_input="रमेश कुमार")
        # ... continue until session.state == COMPLETED
    """

    def __init__(self, validator_registry=None):
        """
        Args:
            validator_registry: ValidatorRegistry instance for field validation.
                                If None, validation is skipped (useful for testing).
        """
        self.validators = validator_registry

    def start_session(self, schema: dict, language: str = "en", channel: str = "voice") -> dict:
        """
        Initialize a new form-filling session.

        Args:
            schema: Parsed GovForm Schema dict
            language: ISO-639-1 language code for prompts
            channel: "voice", "whatsapp", "web", "ivr"

        Returns:
            Session dict containing all state for this form-filling session.
        """
        # Flatten sections into ordered field list
        ordered_fields = []
        for section in sorted(schema["sections"], key=lambda s: s["order"]):
            for field_id in section["fields"]:
                if field_id in schema["fields"]:
                    ordered_fields.append(field_id)

        session = {
            "session_id": str(uuid.uuid4()),
            "form_id": schema["form_id"],
            "schema": schema,
            "language": language,
            "channel": channel,
            "state": SessionState.GREETING.value,
            "ordered_fields": ordered_fields,
            "current_field_index": 0,
            "field_states": {fid: {"attempts": 0, "value": None, "confirmed": False, "skipped": False} for fid in ordered_fields},
            "conditionally_hidden": set(),  # Fields hidden due to conditional logic
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": [],
        }

        return session

    def get_next_prompt(self, session: dict) -> EngineResponse:
        """
        Get the next prompt to send to the user.
        Called after start_session() or after process_input().
        """
        state = SessionState(session["state"])
        schema = session["schema"]
        lang = session["language"]

        if state == SessionState.GREETING:
            form_name = schema["metadata"]["name"].get(lang, schema["metadata"]["name"]["en"])
            est_time = schema["metadata"].get("estimated_time_minutes", 10)
            total = self._count_active_fields(session)

            session["state"] = SessionState.COLLECTING.value
            self._log(session, "greeting_shown")

            return EngineResponse(
                session_id=session["session_id"],
                state=SessionState.GREETING,
                prompt_text={
                    "en": f"Welcome! I'll help you fill the {schema['metadata']['name']['en']}. "
                          f"This has about {total} questions and should take about {est_time} minutes. "
                          f"Let's start. You can say 'skip' for any optional question, or 'back' to go to the previous question.",
                    "hi": f"नमस्ते! मैं आपकी {schema['metadata']['name'].get('hi', '')} भरने में मदद करूंगा। "
                          f"इसमें करीब {total} सवाल हैं और लगभग {est_time} मिनट लगेंगे। "
                          f"चलिए शुरू करते हैं। किसी वैकल्पिक सवाल के लिए 'छोड़ो' बोल सकते हैं।"
                },
                progress={"completed": 0, "total": total},
            )

        if state == SessionState.COLLECTING:
            return self._prompt_current_field(session)

        if state == SessionState.REVIEWING:
            return self._generate_review(session)

        return EngineResponse(
            session_id=session["session_id"],
            state=state,
            prompt_text={"en": "Session is in an unexpected state."},
            expects_input=False,
        )

    def process_input(self, session: dict, user_input: str) -> EngineResponse:
        """
        Process user's response to the current prompt.

        Args:
            session: Session dict (will be mutated)
            user_input: Raw text from ASR/chat

        Returns:
            EngineResponse with next prompt, validation result, or completion
        """
        state = SessionState(session["state"])
        cleaned = user_input.strip()

        # Handle meta-commands
        if self._is_command(cleaned, "skip"):
            return self._handle_skip(session)
        if self._is_command(cleaned, "back"):
            return self._handle_back(session)

        if state == SessionState.COLLECTING:
            return self._handle_field_input(session, cleaned)

        if state == SessionState.CONFIRMING:
            return self._handle_confirmation(session, cleaned)

        if state == SessionState.REVIEWING:
            return self._handle_review_response(session, cleaned)

        return self.get_next_prompt(session)

    # ---- Internal Methods ----

    def _prompt_current_field(self, session: dict) -> EngineResponse:
        """Generate prompt for the current field."""
        field_id = self._get_current_field_id(session)
        if field_id is None:
            # All fields done → review
            session["state"] = SessionState.REVIEWING.value
            return self._generate_review(session)

        field_def = session["schema"]["fields"][field_id]
        lang = session["language"]

        # Get voice prompt or fall back to label
        if "voice" in field_def and "prompt" in field_def["voice"]:
            prompt = field_def["voice"]["prompt"]
        else:
            label = field_def["label"].get(lang, field_def["label"]["en"])
            prompt = {"en": f"Please provide: {field_def['label']['en']}", "hi": f"कृपया बताइए: {label}"}

        # Add example if first attempt
        fs = session["field_states"][field_id]
        if fs["attempts"] == 0 and "voice" in field_def and "example" in field_def.get("voice", {}):
            example = field_def["voice"]["example"]
            for lang_code in prompt:
                if lang_code in example:
                    prompt[lang_code] += f" {example[lang_code]}"

        total = self._count_active_fields(session)
        completed = self._count_completed_fields(session)

        return EngineResponse(
            session_id=session["session_id"],
            state=SessionState.COLLECTING,
            prompt_text=prompt,
            field_id=field_id,
            progress={"completed": completed, "total": total},
        )

    def _handle_field_input(self, session: dict, user_input: str) -> EngineResponse:
        """Validate input for current field and advance or retry."""
        field_id = self._get_current_field_id(session)
        field_def = session["schema"]["fields"][field_id]
        fs = session["field_states"][field_id]
        fs["attempts"] += 1
        lang = session["language"]

        # Validate
        validation = self._validate_field(field_def, user_input)

        if not validation["valid"]:
            self._log(session, "validation_failed", field_id=field_id, input=user_input, error=validation["error_code"])

            if fs["attempts"] >= 3:
                # Max retries — skip if optional, mark pending if required
                if not field_def.get("required", True):
                    return self._handle_skip(session)
                return EngineResponse(
                    session_id=session["session_id"],
                    state=SessionState.COLLECTING,
                    prompt_text={
                        "en": f"I'm having trouble with this field. Let me ask again more carefully. {validation['message'].get('en', '')}",
                        "hi": f"इस जानकारी में कुछ दिक्कत हो रही है। मैं दोबारा पूछता हूं। {validation['message'].get('hi', '')}",
                    },
                    field_id=field_id,
                    error=validation["message"],
                )

            return EngineResponse(
                session_id=session["session_id"],
                state=SessionState.COLLECTING,
                prompt_text=validation["message"],
                field_id=field_id,
                error=validation["message"],
            )

        # Valid — store and maybe confirm
        normalized = validation.get("normalized", user_input)
        fs["value"] = user_input
        fs["normalized_value"] = normalized

        needs_confirm = field_def.get("voice", {}).get("confirm", False)
        if needs_confirm and session["channel"] == "voice":
            session["state"] = SessionState.CONFIRMING.value
            return EngineResponse(
                session_id=session["session_id"],
                state=SessionState.CONFIRMING,
                prompt_text={
                    "en": f"I heard: {normalized}. Is that correct? Say yes or no.",
                    "hi": f"मैंने सुना: {normalized}। क्या यह सही है? हां या ना बोलिए।",
                },
                field_id=field_id,
                confirmation_value=normalized,
            )

        # No confirmation needed — advance
        fs["confirmed"] = True
        self._log(session, "field_collected", field_id=field_id, value=normalized)
        self._evaluate_conditionals(session)
        session["current_field_index"] += 1
        session["state"] = SessionState.COLLECTING.value
        return self.get_next_prompt(session)

    def _handle_confirmation(self, session: dict, user_input: str) -> EngineResponse:
        """Handle yes/no confirmation of a field value."""
        field_id = self._get_current_field_id(session)
        fs = session["field_states"][field_id]

        if self._is_affirmative(user_input):
            fs["confirmed"] = True
            self._log(session, "field_confirmed", field_id=field_id)
            self._evaluate_conditionals(session)
            session["current_field_index"] += 1
            session["state"] = SessionState.COLLECTING.value
            return self.get_next_prompt(session)
        else:
            # Re-ask
            fs["value"] = None
            fs["normalized_value"] = None
            session["state"] = SessionState.COLLECTING.value
            return EngineResponse(
                session_id=session["session_id"],
                state=SessionState.COLLECTING,
                prompt_text={
                    "en": "OK, let me ask again.",
                    "hi": "ठीक है, मैं दोबारा पूछता हूं।",
                },
                field_id=field_id,
            )

    def _validate_field(self, field_def: dict, user_input: str) -> dict:
        """Run validation for a field. Returns {"valid": bool, "error_code": str, "message": dict, "normalized": str}"""
        field_type = field_def["type"]

        # Use registered validator if available
        if self.validators and field_type in self.validators._validators:
            result = self.validators.validate(field_type, user_input)
            return {
                "valid": result.valid,
                "error_code": result.error_code,
                "message": result.message,
                "normalized": result.normalized or user_input,
            }

        # Fallback: basic validation from schema
        validation = field_def.get("validation", {})

        if "pattern" in validation:
            import re
            if not re.match(validation["pattern"], user_input):
                return {
                    "valid": False,
                    "error_code": "PATTERN_MISMATCH",
                    "message": {"en": "The format doesn't look right. Please try again."},
                }

        if "min_length" in validation and len(user_input) < validation["min_length"]:
            return {
                "valid": False,
                "error_code": "TOO_SHORT",
                "message": {"en": f"This needs at least {validation['min_length']} characters."},
            }

        return {"valid": True, "normalized": user_input}

    def _evaluate_conditionals(self, session: dict):
        """After a field is set, re-evaluate conditional rules."""
        schema = session["schema"]
        conditionals = schema.get("conditionals", [])
        hidden = set()

        for rule in conditionals:
            field_id = rule["if"]["field"]
            fs = session["field_states"].get(field_id, {})
            value = fs.get("normalized_value") or fs.get("value")

            condition_met = False
            op = rule["if"]["operator"]
            expected = rule["if"]["value"]

            if value is not None:
                if op == "eq":
                    condition_met = (value == expected)
                elif op == "neq":
                    condition_met = (value != expected)
                elif op == "in":
                    condition_met = (value in expected)

            if not condition_met:
                # Hide fields that should only show when condition is met
                for fid in rule["then"].get("show_fields", []):
                    hidden.add(fid)

        session["conditionally_hidden"] = hidden

    def _get_current_field_id(self, session: dict) -> Optional[str]:
        """Get ID of the current field to collect, skipping hidden/completed fields."""
        idx = session["current_field_index"]
        fields = session["ordered_fields"]
        hidden = session.get("conditionally_hidden", set())

        while idx < len(fields):
            fid = fields[idx]
            fs = session["field_states"][fid]
            if fid not in hidden and not fs["confirmed"] and not fs["skipped"]:
                session["current_field_index"] = idx
                return fid
            idx += 1

        return None  # All done

    def _handle_skip(self, session: dict) -> EngineResponse:
        field_id = self._get_current_field_id(session)
        field_def = session["schema"]["fields"][field_id]
        if field_def.get("required", True):
            return EngineResponse(
                session_id=session["session_id"],
                state=SessionState.COLLECTING,
                prompt_text={"en": "This field is required and cannot be skipped.", "hi": "यह जानकारी जरूरी है, छोड़ नहीं सकते।"},
                field_id=field_id,
            )
        session["field_states"][field_id]["skipped"] = True
        self._log(session, "field_skipped", field_id=field_id)
        session["current_field_index"] += 1
        session["state"] = SessionState.COLLECTING.value
        return self.get_next_prompt(session)

    def _handle_back(self, session: dict) -> EngineResponse:
        if session["current_field_index"] > 0:
            session["current_field_index"] -= 1
            # Reset previous field
            fid = session["ordered_fields"][session["current_field_index"]]
            session["field_states"][fid]["confirmed"] = False
            session["field_states"][fid]["value"] = None
            session["field_states"][fid]["attempts"] = 0
        session["state"] = SessionState.COLLECTING.value
        return self.get_next_prompt(session)

    def _generate_review(self, session: dict) -> EngineResponse:
        """Generate summary of all collected fields for review."""
        lang = session["language"]
        lines = []
        for fid in session["ordered_fields"]:
            fs = session["field_states"][fid]
            if fs["skipped"]:
                continue
            field_def = session["schema"]["fields"][fid]
            label = field_def["label"].get(lang, field_def["label"]["en"])
            value = fs.get("normalized_value") or fs.get("value") or "-"
            lines.append(f"{label}: {value}")

        summary = "\n".join(lines)
        return EngineResponse(
            session_id=session["session_id"],
            state=SessionState.REVIEWING,
            prompt_text={
                "en": f"Here's what I've collected:\n\n{summary}\n\nIs everything correct? Say 'yes' to submit or tell me which field to change.",
                "hi": f"यह रहा सारांश:\n\n{summary}\n\nक्या सब सही है? 'हां' बोलिए या बताइए क्या बदलना है।",
            },
        )

    def _count_active_fields(self, session: dict) -> int:
        hidden = session.get("conditionally_hidden", set())
        return sum(1 for f in session["ordered_fields"] if f not in hidden)

    def _count_completed_fields(self, session: dict) -> int:
        return sum(1 for f in session["ordered_fields"]
                   if session["field_states"][f]["confirmed"] or session["field_states"][f]["skipped"])

    def _is_affirmative(self, text: str) -> bool:
        affirmatives = {"yes", "ya", "yep", "correct", "sahi", "haan", "ha", "ji", "ji haan", "theek", "theek hai", "sahi hai"}
        return text.lower().strip() in affirmatives

    def _is_command(self, text: str, command: str) -> bool:
        commands = {
            "skip": {"skip", "chhodo", "chhod do", "छोड़ो", "छोड़ दो", "next"},
            "back": {"back", "pichla", "peeche", "पीछे", "पिछला", "previous"},
        }
        return text.lower().strip() in commands.get(command, set())

    def _log(self, session: dict, event: str, **kwargs):
        session["audit_log"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            **kwargs,
        })
        session["updated_at"] = datetime.utcnow().isoformat()
