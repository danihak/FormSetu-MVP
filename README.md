# FormSetu

**The Form Intelligence Layer for India's Voice DPI**

FormSetu is an open-source building block that converts any government form into a voice-enabled conversational experience. It sits between voice infrastructure (Voice Adapter) and government backends, providing the missing "form intelligence" layer in India's DPI stack.

> **One schema. Every channel. Every language.**

## The Problem

India has 740+ central sector schemes, each requiring citizens to fill forms. 5.34 lakh CSC kiosks handle 33.5M transactions/month because citizens cannot self-serve — due to language and literacy barriers. VoicERA (launched Feb 2026) provides voice infrastructure, but voice alone can't fill forms. It needs a layer that understands form structure, validates Indian data formats, and handles conversational flow.

## What FormSetu Does

1. **GovForm Schema** — A JSON standard for describing any government form (fields, validation, voice prompts, conditional logic, submission config)
2. **Conversation Engine** — A deterministic FSM that walks through a schema, collecting fields via voice/text conversation
3. **Validator Library** — Production-grade validators for Indian data formats (Aadhaar with Verhoeff checksum, PAN, IFSC, Mobile, PIN)
4. **Voice Adapter** — Integration with Open Source voice Adapter pipeline API for ASR, TTS, and translation in 22+ languages

## Architecture

See [docs/TECHNICAL_RFC.md](docs/TECHNICAL_RFC.md) for full technical specification.

### Packages (Modular, independently usable)

| Package | Description | Status |
|---------|-------------|--------|
| `@formsetu/schema-spec` | GovForm Schema specification + JSON Schema for validation | ✅ Complete |
| `@formsetu/validator` | Indian data format validators (Aadhaar, PAN, IFSC, Mobile, PIN) — 5 validators, 19 test cases | ✅ Complete |
| `@formsetu/engine` | Conversation flow engine (FSM-based, deterministic, auditable) | ✅ Complete |
| `@formsetu/voice-adapter` | Open Source Voice Adapter Pipeline API integration (ASR, TTS, NMT) | ✅ Complete |
| `@formsetu/lookup` | LGD, IFSC, PIN code lookup services | 🔴 Planned |

### Services

| Service | Description | Status |
|---------|-------------|--------|
| `formsetu-api` | REST API server (FastAPI) — schema registry, session management, validators | ✅ Complete |

### Tools

| Tool | Description | Status |
|------|-------------|--------|
| `form-digitizer` | PDF form → GovForm Schema using OCR + LLM | 🔴 Planned |
| `schema-builder` | Visual editor for creating GovForm Schemas | 🔴 Planned |

## Quick Start

```bash
# Clone
git clone https://github.com/danihak/FormSetu-MVP.git
cd FormSetu-MVP

# Run with Docker
cp .env.example .env
# Edit .env with your credentials 
docker compose up

# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Use the Validator Library Standalone

```python
from packages.validator.src.validators.aadhaar import AadhaarValidator

validator = AadhaarValidator()
result = validator.validate("4991 1866 5246")
print(result.valid)       # True
print(result.normalized)  # '499118665246'
```

### Start a Form-Filling Session

```bash
# Start PM-KISAN session
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"form_id": "pm-kisan-v3", "language": "hi"}'

# Respond to prompts
curl -X POST http://localhost:8000/api/v1/sessions/{session_id}/respond \
  -H "Content-Type: application/json" \
  -d '{"input": "Ramesh Kumar"}'
```

## Example: PM-KISAN Schema

The repo includes a complete PM-KISAN beneficiary registration schema ([pm-kisan.json](packages/schema-spec/examples/pm-kisan.json)) with:
- 18 fields across 3 sections (Personal, Bank, Land)
- Aadhaar validation with Verhoeff checksum and chunk-by-4 voice strategy
- IFSC lookup with bank name + branch fallback
- Cascading LGD hierarchy (State → District → Sub-District → Village)
- Conditional logic (ST category → tribal certificate, joint ownership → co-owner details)
- Bilingual prompts (English + Hindi)

## Why FSM, Not LLM?

The conversation engine is a **deterministic finite state machine**, not an LLM chatbot. This is deliberate:

| Concern | FSM | LLM Chatbot |
|---------|-----|-------------|
| Field coverage | 100% guaranteed | Might skip fields |
| Validation | Deterministic (Verhoeff checksum) | Cannot reliably verify checksums |
| Audit trail | Every state transition logged | Non-reproducible |
| Cost per session | ~₹0 (minimal compute) | ₹2-5 (API calls) |
| Latency per turn | <50ms | 1-3 seconds |

LLM is used **only at the edges** (optional): intent disambiguation, spoken number normalization fallback, natural language error explanations.

## Running Tests

```bash
# Validator tests (19 tests)
PYTHONPATH=packages/validator/src pytest packages/validator/tests/ -v

# All passing:
# 19 passed in 0.07s
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI (Python) |
| Session Storage | Redis |
| Schema Registry | PostgreSQL |
| Voice Integration |Voice Adapter API |
| Engine | Custom FSM (Python) |
| CI/CD | GitHub Actions |
| Deployment | Docker + Docker Compose |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. FormSetu is designed for community contribution, especially through [C4GT's Dedicated Mentoring Program](https://codeforgovtech.in/).

**Good first issues:** Add a new validator (Voter ID, Driving License), add a new form schema, add multilingual prompts.

## License

MIT — see [LICENSE](LICENSE)
