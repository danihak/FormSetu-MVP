# FormSetu: Technical RFC & Implementation Plan

**Version:** 0.1-draft  
**Author:** Danish  
**Date:** February 2026  
**Status:** Proposal for COSS Review  
**Reviewers:** Karthik (Principal Technical Architect, COSS), Manmeet (COSS)

---

## 1. Problem Statement (Technical)

India's voice DPI stack (BHASHINI + VoicERA) provides ASR, TTS, NMT, and conversational infrastructure. However, there is no **structured, machine-readable representation** of government forms that would allow these voice systems to:

1. Know what fields a form requires
2. Generate a conversational flow to collect those fields
3. Validate spoken inputs against Indian data format rules
4. Handle conditional logic (field X appears only if field Y = value Z)

**Current state:** Every department that wants voice-enabled form filling must build the entire logic from scratch. Pehchan (Rajasthan) did it for birth/death certificates. GHMC (Hyderabad) is doing it for grievances. Each is a silo.

**Proposed:** An open-source building block — a form schema standard + conversation engine + validator library — that any department can plug into VoicERA/BHASHINI to voice-enable their forms in days instead of months.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CHANNEL LAYER                         │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐ │
│  │ VoicERA/ │ │ WhatsApp │ │  IVR   │ │ Web Widget   │ │
│  │ BHASHINI │ │ Business │ │ DTMF+  │ │ (Embed in    │ │
│  │ Voice    │ │ API      │ │ Voice  │ │ govt portal) │ │
│  └────┬─────┘ └────┬─────┘ └───┬────┘ └──────┬───────┘ │
└───────┼─────────────┼───────────┼─────────────┼─────────┘
        │             │           │             │
        └─────────────┴─────┬─────┴─────────────┘
                            │
              ┌─────────────▼──────────────┐
              │   CHANNEL ADAPTER LAYER    │
              │   (Protocol translation)   │
              │   Audio ↔ Text ↔ Events    │
              └─────────────┬──────────────┘
                            │
        ┌───────────────────▼───────────────────┐
        │         FORMSETU CORE ENGINE          │
        │                                       │
        │  ┌─────────────┐  ┌────────────────┐  │
        │  │ Session      │  │ Conversation   │  │
        │  │ Manager      │  │ Flow Engine    │  │
        │  │ (state per   │  │ (walks the     │  │
        │  │  user call)  │  │  form schema)  │  │
        │  └──────┬───────┘  └───────┬────────┘  │
        │         │                  │            │
        │  ┌──────▼──────────────────▼─────────┐ │
        │  │         Field Processor            │ │
        │  │  ┌───────────┐  ┌──────────────┐  │ │
        │  │  │ Validator  │  │ Normalizer   │  │ │
        │  │  │ (Aadhaar,  │  │ (spoken num  │  │ │
        │  │  │  PAN, IFSC │  │  → digits,   │  │ │
        │  │  │  PIN, etc) │  │  translit)   │  │ │
        │  │  └───────────┘  └──────────────┘  │ │
        │  └───────────────────────────────────┘ │
        │                                       │
        └───────────────────┬───────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │     SCHEMA REGISTRY        │
              │  (PostgreSQL + Redis)      │
              │  Stores GovForm Schemas    │
              │  Versioned, searchable     │
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │     SUBMISSION LAYER       │
              │  API Setu / Dept portals   │
              │  DigiLocker (doc fetch)    │
              │  eSign (Aadhaar eSign)     │
              └────────────────────────────┘
```

---

## 3. Core Data Model: GovForm Schema Specification

This is the heart of FormSetu. A JSON-based schema format that can describe any government form.

### 3.1 Schema Structure

```json
{
  "$schema": "https://formsetu.gov.in/schema/v1",
  "form_id": "pm-kisan-v3",
  "version": "3.1",
  "metadata": {
    "name": { "en": "PM-KISAN Beneficiary Application", "hi": "पीएम-किसान लाभार्थी आवेदन" },
    "department": "Ministry of Agriculture & Farmers Welfare",
    "scheme_id": "myscheme:pm-kisan",
    "last_updated": "2025-11-15",
    "estimated_time_minutes": 8,
    "documents_required": ["aadhaar", "bank_passbook", "land_record"]
  },
  "sections": [
    {
      "id": "personal",
      "label": { "en": "Personal Details", "hi": "व्यक्तिगत विवरण" },
      "order": 1,
      "fields": ["full_name", "father_name", "dob", "gender", "aadhaar_number", "mobile"]
    },
    {
      "id": "bank",
      "label": { "en": "Bank Details", "hi": "बैंक विवरण" },
      "order": 2,
      "fields": ["account_number", "account_type", "ifsc_code", "bank_name"]
    },
    {
      "id": "land",
      "label": { "en": "Land Details", "hi": "भूमि विवरण" },
      "order": 3,
      "fields": ["state", "district", "sub_district", "village", "khasra_number", "land_area_hectares"]
    }
  ],
  "fields": {
    "full_name": {
      "type": "text",
      "label": { "en": "Full Name (as on Aadhaar)", "hi": "पूरा नाम (आधार अनुसार)" },
      "required": true,
      "validation": {
        "pattern": "^[\\p{L}\\p{M}\\s.]+$",
        "min_length": 2,
        "max_length": 100
      },
      "voice": {
        "prompt": {
          "en": "Please tell me your full name, exactly as it appears on your Aadhaar card.",
          "hi": "कृपया अपना पूरा नाम बताइए, जैसा आपके आधार कार्ड पर लिखा है।"
        },
        "confirm": true,
        "spell_mode": false,
        "example": { "en": "For example: Ramesh Kumar Singh", "hi": "जैसे: रमेश कुमार सिंह" }
      },
      "autofill": { "source": "aadhaar_ekyc", "field": "name" }
    },
    "aadhaar_number": {
      "type": "aadhaar",
      "label": { "en": "Aadhaar Number", "hi": "आधार संख्या" },
      "required": true,
      "validation": {
        "format": "aadhaar",
        "checksum": "verhoeff"
      },
      "voice": {
        "prompt": {
          "en": "Please tell me your 12-digit Aadhaar number, slowly.",
          "hi": "कृपया अपना 12 अंकों का आधार नंबर धीरे-धीरे बताइए।"
        },
        "confirm": true,
        "spell_mode": true,
        "chunk_size": 4,
        "chunk_prompt": {
          "en": "First 4 digits?... Next 4?... Last 4?",
          "hi": "पहले 4 अंक?... अगले 4?... आखिरी 4?"
        }
      }
    },
    "ifsc_code": {
      "type": "ifsc",
      "label": { "en": "IFSC Code", "hi": "IFSC कोड" },
      "required": true,
      "validation": {
        "format": "ifsc",
        "pattern": "^[A-Z]{4}0[A-Z0-9]{6}$"
      },
      "voice": {
        "prompt": {
          "en": "What is your bank's IFSC code? If you don't know it, tell me your bank name and branch.",
          "hi": "आपके बैंक का IFSC कोड क्या है? अगर नहीं पता तो बैंक का नाम और शाखा बताइए।"
        },
        "confirm": true,
        "fallback_strategy": "bank_branch_lookup"
      },
      "lookup": {
        "endpoint": "/api/v1/lookup/ifsc",
        "input_fields": ["bank_name", "branch_name"],
        "output_field": "ifsc_code"
      }
    },
    "account_type": {
      "type": "select",
      "label": { "en": "Account Type", "hi": "खाता प्रकार" },
      "required": true,
      "options": [
        { "value": "savings", "label": { "en": "Savings Account", "hi": "बचत खाता" } },
        { "value": "current", "label": { "en": "Current Account", "hi": "चालू खाता" } },
        { "value": "jan_dhan", "label": { "en": "Jan Dhan Account", "hi": "जन धन खाता" } }
      ],
      "voice": {
        "prompt": {
          "en": "Is your account a Savings account, Current account, or Jan Dhan account?",
          "hi": "आपका खाता बचत खाता है, चालू खाता है, या जन धन खाता है?"
        },
        "confirm": false
      }
    },
    "state": {
      "type": "geo_state",
      "label": { "en": "State", "hi": "राज्य" },
      "required": true,
      "validation": { "source": "lgd_state_codes" }
    },
    "district": {
      "type": "geo_district",
      "label": { "en": "District", "hi": "जिला" },
      "required": true,
      "validation": { "source": "lgd_district_codes" },
      "depends_on": { "field": "state", "filter_by": "state_code" }
    }
  },
  "conditionals": [
    {
      "id": "joint_account_details",
      "if": { "field": "account_type", "operator": "eq", "value": "joint" },
      "then": { "show_fields": ["joint_holder_name", "joint_holder_aadhaar"] }
    },
    {
      "id": "tribal_land_docs",
      "if": { "field": "category", "operator": "in", "value": ["ST"] },
      "then": { "show_fields": ["tribal_certificate_number"], "make_optional": ["khasra_number"] }
    }
  ],
  "submission": {
    "target": "api_setu",
    "endpoint": "/api/v1/schemes/pm-kisan/apply",
    "method": "POST",
    "auth": "aadhaar_esign",
    "documents": {
      "aadhaar_xml": { "source": "digilocker", "doc_type": "ADHAR" },
      "land_record": { "source": "manual_upload_or_digilocker" }
    }
  }
}
```

### 3.2 Design Decisions & Tradeoffs

| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| Schema format | JSON with custom `$schema` | JSON Schema draft-07 | Pure JSON Schema can't express voice prompts, conditional field visibility, or autofill hints. We extend it with `voice`, `lookup`, `autofill` sections. Validator layer still uses JSON Schema for field-level validation. |
| Multilingual labels | Inline `{ "en": "...", "hi": "..." }` | External i18n files | Government forms are small (10-30 fields). Inline keeps schema self-contained. No need for separate translation management for form labels. |
| Conditional logic | Declarative rules in schema | Code-based rules | Declarative = auditable, serializable, can be edited by non-developers via a form builder UI later. Code-based would be more powerful but kills reusability. |
| Field types | Domain-specific (`aadhaar`, `ifsc`, `pan`, `geo_state`) not just (`text`, `number`) | Generic types only | Domain types carry validation + voice behavior. `type: "aadhaar"` automatically implies Verhoeff checksum, 12-digit, chunk-by-4 voice strategy. Generic types would need this configured per-field. |
| Voice prompts | Part of schema, per-field | Generated dynamically by LLM | Deterministic > dynamic for government forms. Pre-written prompts ensure consistent citizen experience. LLM generation can be an optional enhancement layer, not the default. |

### 3.3 LGD Integration (Critical for Address Fields)

Government of India's Local Government Directory (LGD) provides the canonical hierarchy: State → District → Sub-District → Block → Panchayat → Village. FormSetu must use LGD codes, not free-text, for address fields. This ensures submitted forms use codes that government systems recognize.

**Implementation:** Cache LGD data locally (updated weekly). Voice flow uses fuzzy matching: user says "Udaipur" → match against LGD district list for selected state → confirm.

---

## 4. Conversation Flow Engine

### 4.1 State Machine Design

The engine is a **finite state machine (FSM)**, NOT an LLM-driven chatbot. This is a deliberate architectural choice.

**Why FSM over LLM:**
- Government forms need 100% field coverage. An LLM might skip fields.
- Validation must be deterministic. LLM can't reliably verify Verhoeff checksums.
- Audit trail: every state transition is logged. Reproducible.
- Cost: FSM runs on minimal compute. LLM would cost ₹2-5 per form session at scale.
- Latency: FSM responds in <50ms. LLM adds 1-3s per turn.

**Where LLM IS used (optional, not in critical path):**
- Intent disambiguation: if user says something unrelated to the current field
- Spoken number normalization (backup): "barah sau taintees" → 1233
- Error explanation generation in natural language

### 4.2 FSM States

```
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │  GREET   │──── Explain form, estimated time
                    └────┬─────┘
                         │
                    ┌────▼──────────┐
             ┌──────│  NEXT_FIELD   │◄────────────────┐
             │      └────┬──────────┘                  │
             │           │                             │
             │      ┌────▼─────┐                       │
             │      │  PROMPT  │──── Ask question       │
             │      └────┬─────┘                       │
             │           │                             │
             │      ┌────▼──────────┐                  │
             │      │  LISTEN       │──── Receive input │
             │      └────┬──────────┘                  │
             │           │                             │
             │      ┌────▼──────────┐      ┌────────┐  │
             │      │  VALIDATE     │─FAIL─▶│ RETRY  │──┘
             │      └────┬──────────┘      │ (max 3)│
             │           │ PASS            └────────┘
             │      ┌────▼──────────┐          │ max retries
             │      │  CONFIRM      │          ▼
             │      │  (if needed)  │     ┌─────────┐
             │      └────┬──────────┘     │  SKIP   │
             │           │                │ (mark   │
             │           │ YES            │ pending)│
             │           │                └─────────┘
             │      ┌────▼──────────┐
             │      │  STORE_FIELD  │───── Save to session
             │      └────┬──────────┘
             │           │
             │           └─── if more fields → NEXT_FIELD
             │                if all done ↓
             │      ┌────────────────┐
             │      │  REVIEW        │──── Read back all fields
             │      └────┬───────────┘
             │           │
             │      ┌────▼──────────┐
             │      │  SUBMIT       │──── Call submission API
             │      └────┬──────────┘
             │           │
             │      ┌────▼──────────┐
             └──NO──│  COMPLETE     │──── Provide reference number
                    └───────────────┘
```

### 4.3 Sequence Diagram: Single Field Collection via Voice

```
Citizen          VoicERA/BHASHINI       FormSetu Engine       Validator         Schema Registry
  │                    │                      │                   │                    │
  │ speaks in Hindi    │                      │                   │                    │
  │───────────────────▶│                      │                   │                    │
  │                    │ ASR: Hindi→Text      │                   │                    │
  │                    │─────────────────────▶│                   │                    │
  │                    │                      │ get_current_field()│                    │
  │                    │                      │──────────────────────────────────────▶│
  │                    │                      │◄─ field: aadhaar_number ──────────────│
  │                    │                      │                   │                    │
  │                    │                      │ normalize_input() │                    │
  │                    │                      │ "mera Aadhaar hai │                    │
  │                    │                      │  barah so chauwan │                    │
  │                    │                      │  saat hazaar paanch│                   │
  │                    │                      │  sau baees"       │                    │
  │                    │                      │ → extract: 1254 7522 ????              │
  │                    │                      │   (incomplete)    │                    │
  │                    │                      │                   │                    │
  │                    │                      │ validate()        │                    │
  │                    │                      │──────────────────▶│                    │
  │                    │                      │◄── FAIL: need 12  │                    │
  │                    │                      │    digits, got 8  │                    │
  │                    │                      │                   │                    │
  │                    │  TTS: "I heard 1254  │                   │                    │
  │                    │  7522. I need 4 more │                   │                    │
  │                    │  digits. Last 4?"    │                   │                    │
  │                    │◄─────────────────────│                   │                    │
  │◄───────────────────│                      │                   │                    │
  │ "teen nau chaar    │                      │                   │                    │
  │  paanch"           │                      │                   │                    │
  │───────────────────▶│                      │                   │                    │
  │                    │ ASR → "3945"         │                   │                    │
  │                    │─────────────────────▶│                   │                    │
  │                    │                      │ combine: 125475223945                  │
  │                    │                      │ validate()        │                    │
  │                    │                      │──────────────────▶│                    │
  │                    │                      │◄── FAIL: Verhoeff │                    │
  │                    │                      │    checksum fail  │                    │
  │                    │                      │    (last digit    │                    │
  │                    │                      │    should be 6?)  │                    │
  │                    │                      │                   │                    │
  │                    │ TTS: "The number     │                   │                    │
  │                    │ doesn't seem right.  │                   │                    │
  │                    │ Can you check and    │                   │                    │
  │                    │ repeat all 12 digits?│                   │                    │
  │                    │◄─────────────────────│                   │                    │
  │◄───────────────────│                      │                   │                    │
  │                    │                      │                   │                    │
  │ (repeats correctly)│                      │                   │                    │
  │  ... → validated   │                      │                   │                    │
```

---

## 5. Validator Library (Standalone, Reusable)

This is designed as an **independent npm/pip package** — usable even without FormSetu engine.

### 5.1 Supported Indian Data Formats

```python
# formsetu-validator: standalone library

class AadhaarValidator:
    """
    12-digit number with Verhoeff checksum.
    Handles spoken input normalization.
    """
    VERHOEFF_TABLE_D = [
        [0,1,2,3,4,5,6,7,8,9],
        [1,2,3,4,0,6,7,8,9,5],
        # ... full Verhoeff tables
    ]

    def validate(self, raw_input: str) -> ValidationResult:
        digits = self.extract_digits(raw_input)  # handles "1234 5678 9012" or "123456789012"
        if len(digits) != 12:
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_LENGTH",
                message={"en": f"Aadhaar must be 12 digits, got {len(digits)}"},
                partial=digits
            )
        if not self.verhoeff_check(digits):
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_CHECKSUM",
                message={"en": "Aadhaar number checksum failed. Please verify."}
            )
        if digits.startswith(('0', '1')):
            return ValidationResult(
                valid=False,
                error_code="AADHAAR_RANGE",
                message={"en": "Aadhaar numbers don't start with 0 or 1."}
            )
        return ValidationResult(valid=True, normalized=digits)


class IFSCValidator:
    """
    Format: AAAA0BBBBBB (4 alpha + 0 + 6 alphanum)
    Validates against RBI IFSC master list.
    """
    PATTERN = r'^[A-Z]{4}0[A-Z0-9]{6}$'

    def validate(self, raw_input: str) -> ValidationResult:
        cleaned = raw_input.upper().replace(' ', '').replace('-', '')
        if not re.match(self.PATTERN, cleaned):
            return ValidationResult(valid=False, error_code="IFSC_FORMAT")
        # Optional: check against cached RBI IFSC list
        if self.rbi_lookup_enabled and cleaned not in self.ifsc_cache:
            return ValidationResult(valid=False, error_code="IFSC_NOT_FOUND")
        return ValidationResult(valid=True, normalized=cleaned)

    def lookup_by_bank_branch(self, bank_name: str, branch_name: str) -> list[str]:
        """Fuzzy match bank+branch → return candidate IFSC codes"""
        ...


class PANValidator:
    """Format: AAAAA1111A — 5 alpha + 4 digit + 1 alpha"""
    ...

class PINCodeValidator:
    """6-digit, first digit 1-9. Cross-validates with state if provided."""
    ...

class MobileValidator:
    """10-digit, starts with 6/7/8/9."""
    ...

class VoterIDValidator:
    """3 alpha + 7 digits"""
    ...

class VehicleRegistrationValidator:
    """State code + district code + series + number"""
    ...
```

### 5.2 Spoken Number Normalizer

This is a critical sub-component. Indian citizens dictate numbers in mixed ways:

```python
class SpokenNumberNormalizer:
    """
    Handles:
    - "barah sau taintees" → 1233 (Hindi number words)
    - "twelve thirty-four" → 1234 (English)
    - "one two three four" → 1234 (digit-by-digit)
    - "double five" → 55
    - "triple zero" → 000
    - Mixed: "SBIN zero four double five two three" → SBIN0045523 (IFSC-like)
    """

    # Language-specific number word maps
    HINDI_NUMBERS = {
        "शून्य": 0, "एक": 1, "दो": 2, "तीन": 3, "चार": 4,
        "पांच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9,
        "दस": 10, "ग्यारह": 11, "बारह": 12, "तेरह": 13,
        # ... complete Hindi number system
        "सौ": 100, "हज़ार": 1000, "लाख": 100000,
    }

    def normalize(self, text: str, expected_type: str = "digits") -> str:
        """
        expected_type:
          "digits" → always return individual digits: "barah" → "12"
          "number" → return numeric value: "barah sau" → "1200"
          "alphanumeric" → handle mixed: "SBIN zero four five" → "SBIN045"
        """
        ...
```

---

## 6. Integration with BHASHINI/VoicERA

### 6.1 BHASHINI Pipeline Integration

FormSetu uses BHASHINI's standard pipeline API, NOT a custom integration. This is important for COSS alignment — we use existing DPI, we don't rebuild it.

```python
class BhashiniAdapter:
    """
    Wraps BHASHINI Pipeline API for FormSetu's needs.
    Uses: ASR (speech→text), NMT (translate to engine language), TTS (text→speech)
    """

    ULCA_BASE = "https://meity-auth.ulcacontrib.org"
    PIPELINE_ENDPOINT = "/ulca/apis/v0/model/getModelsPipeline"

    def __init__(self, user_id: str, api_key: str, pipeline_id: str):
        self.user_id = user_id
        self.api_key = api_key
        self.pipeline_id = pipeline_id
        self._configure_pipeline()

    def _configure_pipeline(self):
        """Fetch pipeline config and extract callback URL + service IDs"""
        body = {
            "pipelineTasks": [
                {"taskType": "asr"},
                {"taskType": "translation"},
                {"taskType": "tts"}
            ],
            "pipelineRequestConfig": {
                "pipelineId": self.pipeline_id
            }
        }
        resp = requests.post(
            f"{self.ULCA_BASE}{self.PIPELINE_ENDPOINT}",
            json=body,
            headers={"userID": self.user_id, "ulcaApiKey": self.api_key}
        )
        config = resp.json()
        self.callback_url = config["pipelineInferenceAPIEndPoint"]["callbackUrl"]
        self.inference_key = config["pipelineInferenceAPIEndPoint"]["inferenceApiKey"]["value"]
        # Extract service IDs per language
        self.asr_services = {}  # lang_code → service_id
        self.tts_services = {}
        self.nmt_services = {}
        for cfg in config["pipelineResponseConfig"]:
            ...

    async def speech_to_text(self, audio_base64: str, source_lang: str) -> str:
        """ASR: audio → text in source language"""
        payload = {
            "pipelineTasks": [{
                "taskType": "asr",
                "config": {
                    "language": {"sourceLanguage": source_lang},
                    "serviceId": self.asr_services[source_lang],
                    "audioFormat": "wav",
                    "samplingRate": 16000
                }
            }],
            "inputData": {
                "audio": [{"audioContent": audio_base64}]
            }
        }
        resp = await self._call_pipeline(payload)
        return resp["pipelineResponse"][0]["output"][0]["source"]

    async def text_to_speech(self, text: str, lang: str, gender: str = "female") -> str:
        """TTS: text → audio base64"""
        payload = {
            "pipelineTasks": [{
                "taskType": "tts",
                "config": {
                    "language": {"sourceLanguage": lang},
                    "serviceId": self.tts_services[lang],
                    "gender": gender
                }
            }],
            "inputData": {
                "input": [{"source": text}]
            }
        }
        resp = await self._call_pipeline(payload)
        return resp["pipelineResponse"][0]["audio"][0]["audioContent"]

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """NMT: translate text between languages"""
        ...

    async def _call_pipeline(self, payload: dict) -> dict:
        """Make inference call to BHASHINI pipeline"""
        resp = requests.post(
            self.callback_url,
            json=payload,
            headers={"Authorization": self.inference_key}
        )
        return resp.json()
```

### 6.2 VoicERA Integration (When SDK Available)

VoicERA is freshly launched (Feb 17, 2026). Its developer SDK is not yet publicly documented. FormSetu's channel adapter architecture means we can add a VoicERA-native adapter once their SDK stabilizes, without changing the core engine.

**Current plan:** Use BHASHINI pipeline APIs directly (they work today). Migrate to VoicERA-specific integration when available.

### 6.3 WebSocket Support for Real-Time Voice

For low-latency voice interaction, FormSetu supports BHASHINI's streaming WebSocket API:

```python
class BhashiniStreamingAdapter:
    """
    Uses bhashini.ai WebSocket API for streaming ASR.
    Enables real-time voice with interim results.
    """
    WS_URL = "wss://api.bhashini.ai/v1/streaming/asr"

    async def stream_asr(self, websocket_client, source_lang: str):
        """
        Streams audio chunks → receives interim + final transcriptions.
        Allows FormSetu to show/act on partial results.
        """
        ...
```

---

## 7. API Design

### 7.1 Schema Registry APIs

```
POST   /api/v1/schemas                    # Create new form schema
GET    /api/v1/schemas                    # List schemas (filterable by department, scheme)
GET    /api/v1/schemas/{form_id}          # Get schema by ID
GET    /api/v1/schemas/{form_id}/versions # Get version history
PUT    /api/v1/schemas/{form_id}          # Update schema (creates new version)
DELETE /api/v1/schemas/{form_id}          # Soft delete

# Schema validation
POST   /api/v1/schemas/validate           # Validate a schema draft against spec

# Discovery
GET    /api/v1/schemas/search?q=kisan&department=agriculture
```

### 7.2 Session/Conversation APIs

```
POST   /api/v1/sessions                   # Start new form-filling session
  Request:  { "form_id": "pm-kisan-v3", "language": "hi", "channel": "voice" }
  Response: { "session_id": "uuid", "first_prompt": {...}, "total_fields": 15 }

POST   /api/v1/sessions/{id}/respond      # Submit user response for current field
  Request:  { "input": "रमेश कुमार सिंह", "input_type": "text" }
  Response: {
    "field_status": "accepted",       # or "rejected", "needs_confirmation"
    "next_prompt": {...},             # prompt for next field (or confirmation)
    "progress": { "completed": 3, "total": 15, "percent": 20 }
  }

GET    /api/v1/sessions/{id}              # Get session state (all collected fields)
POST   /api/v1/sessions/{id}/back         # Go back to previous field
POST   /api/v1/sessions/{id}/skip         # Skip current field (if optional)
POST   /api/v1/sessions/{id}/submit       # Submit completed form
DELETE /api/v1/sessions/{id}              # Abandon session
```

### 7.3 Validator APIs (Standalone)

```
POST   /api/v1/validate/aadhaar    { "value": "123456789012" }
POST   /api/v1/validate/pan        { "value": "ABCDE1234F" }
POST   /api/v1/validate/ifsc       { "value": "SBIN0004567" }
POST   /api/v1/validate/pincode    { "value": "313001", "state": "Rajasthan" }
POST   /api/v1/validate/mobile     { "value": "9876543210" }

# Bulk validate
POST   /api/v1/validate/batch
  Request: [
    { "type": "aadhaar", "value": "..." },
    { "type": "pan", "value": "..." }
  ]
```

### 7.4 Lookup APIs

```
GET    /api/v1/lookup/ifsc?bank=SBI&branch=Udaipur+Main
GET    /api/v1/lookup/pincode?code=313001          # Returns state, district, area
GET    /api/v1/lookup/lgd/states
GET    /api/v1/lookup/lgd/districts?state_code=08
GET    /api/v1/lookup/lgd/subdistricts?district_code=0821
GET    /api/v1/lookup/lgd/villages?subdistrict_code=082101
```

---

## 8. Deployment Architecture

```
┌─────────────────────────────────────────────────┐
│                  Kubernetes Cluster               │
│                                                   │
│  ┌──────────────┐  ┌──────────────┐              │
│  │ formsetu-api │  │ formsetu-api │  (2+ replicas)│
│  │ (FastAPI)    │  │ (FastAPI)    │              │
│  └──────┬───────┘  └──────┬───────┘              │
│         └────────┬─────────┘                      │
│                  │                                │
│  ┌───────────────▼────────────────┐              │
│  │        Redis                    │              │
│  │  - Session state (TTL: 1hr)    │              │
│  │  - Schema cache                │              │
│  │  - IFSC/LGD lookup cache      │              │
│  └────────────────────────────────┘              │
│                                                   │
│  ┌────────────────────────────────┐              │
│  │        PostgreSQL               │              │
│  │  - Schema registry             │              │
│  │  - Session audit logs          │              │
│  │  - IFSC master data            │              │
│  │  - LGD master data             │              │
│  └────────────────────────────────┘              │
│                                                   │
│  External:                                        │
│  ├── BHASHINI Pipeline API (ASR/NMT/TTS)         │
│  ├── API Setu (form submission)                   │
│  └── DigiLocker API (document fetch)             │
└───────────────────────────────────────────────────┘
```

**Resource estimates (MVP):**
- API server: 2 vCPU, 4GB RAM per replica (2 replicas)
- Redis: 2GB (session data is ephemeral)
- PostgreSQL: 10GB (schema registry + audit logs)
- No GPU needed — all ML inference is on BHASHINI's side

---

## 9. MVP Scope (What to Build First)

### Phase 1: Weeks 1-4 — Foundation

| Week | Deliverable | Concrete Output |
|------|-------------|-----------------|
| 1 | GovForm Schema spec v0.1 | JSON schema definition + 2 example schemas (PM-KISAN, Birth Certificate) |
| 2 | Validator library v0.1 | `formsetu-validator` Python package: Aadhaar, PAN, IFSC, PIN, Mobile validators + tests |
| 3 | Conversation engine v0.1 | FSM engine that reads schema → generates prompts → collects → validates. Text-only (no voice yet) |
| 4 | BHASHINI adapter v0.1 | Voice integration: ASR input → engine → TTS output. End-to-end voice demo for PM-KISAN |

### Phase 2: Weeks 5-8 — Hardening

| Week | Deliverable |
|------|-------------|
| 5 | Spoken number normalizer (Hindi + English). LGD lookup integration. |
| 6 | Session management (Redis). API server (FastAPI). Multi-language support (add 2 more languages). |
| 7 | Schema registry with versioning. Schema validation tooling. |
| 8 | Web demo UI. Docker compose for full stack. Documentation. |

### Phase 3: Weeks 9-12 — Ecosystem

| Week | Deliverable |
|------|-------------|
| 9-10 | Form digitizer (PDF → schema draft using OCR + LLM classification) |
| 11-12 | WhatsApp adapter. IVR adapter. C4GT-ready contribution guide. |

---

## 10. What This is NOT

Being explicit about boundaries, because overpromising kills credibility:

1. **Not a form submission platform.** FormSetu helps COLLECT form data via voice. Actual submission goes through existing portals / API Setu. We don't replace department backends.

2. **Not an LLM chatbot.** The core is a deterministic state machine. LLM is used only at edges (disambiguation, number normalization fallback). A form session should work even if the LLM is down.

3. **Not a replacement for CSC/eMitra.** CSC operators can USE FormSetu to speed up their work. We augment, not replace.

4. **Not another Pehchan/GHMC.** Those are apps for specific use cases. FormSetu is the building block they SHOULD have been built on.

5. **Not competing with VoicERA.** FormSetu sits ON TOP of VoicERA. VoicERA is the voice pipe. FormSetu is the form brain.

---

## 11. Open Questions for Discussion

1. **Schema governance:** Who owns the "official" schema for a form? Department? NIC? Should FormSetu maintain a community-contributed registry, or only department-authorized schemas?

2. **Aadhaar consent flow:** Voice-based eKYC requires consent. How does this work in a voice-only flow? OTP on registered mobile? This needs UIDAI alignment.

3. **Offline/low-connectivity mode:** Rural India has patchy connectivity. Should FormSetu support a "collect offline, submit later" mode? This complicates the architecture significantly.

4. **VoicERA SDK timeline:** We're building on BHASHINI pipeline APIs today. When VoicERA releases its developer SDK, what's the migration path? Need to coordinate with DIBD/EkStep.

5. **Testing at scale:** How do we load-test voice form filling? Synthetic audio generation in multiple languages/dialects?

---

## 12. Success Metrics

| Metric | Target (6 months) |
|--------|-------------------|
| Form schemas published | 10+ (across 3 departments) |
| Average form completion time (voice) | < 10 minutes for a 15-field form |
| Validation accuracy | > 99% (no invalid Aadhaar/PAN accepted) |
| Voice recognition → field mapping accuracy | > 95% (correct field gets filled) |
| State adoptions | 2+ states piloting |
| GitHub stars | 200+ (community traction signal) |
| C4GT DMP tickets picked up | 5+ contributors |

---

*This document is a living RFC. Feedback from Karthik and Manmeet will shape v0.2.*
