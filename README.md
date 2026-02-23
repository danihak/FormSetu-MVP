# FormSetu

**The Form Intelligence Layer for India's Voice DPI**

FormSetu is an open-source building block that sits between India's voice infrastructure (VoicERA/BHASHINI) and government application portals. It provides the missing "form brain" — a standard way to describe government forms, a conversation engine to collect data via voice, and validators for Indian data formats.

```
┌──────────────────────┐
│  Voice/Chat Channel  │  ← VoicERA, BHASHINI, WhatsApp, IVR, Web
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│      FormSetu        │  ← THIS PROJECT
│  Schema + Engine +   │
│  Validator + Adapters│
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  Government Backend  │  ← API Setu, Department Portals, DigiLocker
└──────────────────────┘
```

## Why

- **VoicERA** can hear and speak in 700+ dialects. It does NOT know what a PM-KISAN form needs.
- **Pehchan** (Rajasthan) does voice form-filling for birth certificates. It is NOT reusable for any other form.
- **Nobody** has a machine-readable standard for government form structure.

FormSetu fills this gap.

## Architecture

See [docs/TECHNICAL_RFC.md](docs/TECHNICAL_RFC.md) for full technical specification.

### Packages (Modular, independently usable)

| Package | Description | Status |
|---------|-------------|--------|
| `@formsetu/schema-spec` | GovForm Schema specification + JSON Schema for validation | 🟡 Draft |
| `@formsetu/validator` | Indian data format validators (Aadhaar, PAN, IFSC, etc.) | 🟡 In Progress |
| `@formsetu/engine` | Conversation flow engine (FSM-based) | 🔴 Planned |
| `@formsetu/adapter-bhashini` | BHASHINI pipeline API integration | 🔴 Planned |
| `@formsetu/lookup` | LGD, IFSC, PIN code lookup services | 🔴 Planned |

### Services

| Service | Description | Status |
|---------|-------------|--------|
| `formsetu-api` | REST API server (FastAPI) | 🔴 Planned |

### Tools

| Tool | Description | Status |
|------|-------------|--------|
| `form-digitizer` | PDF form → GovForm Schema using OCR + LLM | 🔴 Planned |
| `schema-builder` | Visual editor for creating GovForm Schemas | 🔴 Planned |

## Quick Start

```bash
# Install validator library
pip install formsetu-validator

# Validate an Aadhaar number
from formsetu_validator import AadhaarValidator
result = AadhaarValidator().validate("2234 5678 9012")
print(result.valid)  # True/False
print(result.error)  # Error details if invalid

# Run the full stack locally
docker compose up
```

## GovForm Schema (Example)

A PM-KISAN application form described as machine-readable JSON:

```json
{
  "form_id": "pm-kisan-v3",
  "metadata": {
    "name": { "en": "PM-KISAN Application", "hi": "पीएम-किसान आवेदन" },
    "department": "Ministry of Agriculture"
  },
  "fields": {
    "aadhaar_number": {
      "type": "aadhaar",
      "required": true,
      "voice": {
        "prompt": { "hi": "कृपया अपना 12 अंकों का आधार नंबर बताइए।" },
        "confirm": true,
        "spell_mode": true,
        "chunk_size": 4
      }
    }
  }
}
```

See [packages/schema-spec/examples/](packages/schema-spec/examples/) for complete form schemas.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). This project is designed for C4GT community contributions.

## License

MIT

## Acknowledgments

Built to work with [BHASHINI](https://bhashini.gov.in) and [VoicERA](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2229732), India's national language and voice infrastructure.
