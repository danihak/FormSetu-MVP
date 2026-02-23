# Contributing to FormSetu

FormSetu is designed for community contribution, especially through [C4GT's Dedicated Mentoring Program](https://codeforgovtech.in/).

## Good First Issues

These are tagged `good-first-issue` on GitHub:

- **Add a new validator** (e.g., Voter ID, Driving License, Ration Card)
- **Add multilingual prompts** to existing form schemas
- **Write tests** for the conversation engine edge cases
- **Add a new example form schema** (e.g., Ration Card application, Caste Certificate)

## Architecture Overview

```
formsetu/
├── packages/           # Independent, reusable packages
│   ├── schema-spec/    # GovForm Schema JSON specification
│   ├── validator/      # Indian data format validators (pip installable)
│   ├── engine/         # Conversation FSM engine
│   ├── adapters/       # Channel adapters (BHASHINI, WhatsApp, Web)
│   └── lookup/         # IFSC, LGD, PIN code lookups
├── services/
│   └── api/            # FastAPI REST server
├── tools/
│   ├── form-digitizer/ # PDF → schema converter
│   └── schema-builder/ # Visual schema editor
└── deploy/             # Docker, Kubernetes configs
```

## Development Setup

```bash
# Clone
git clone https://github.com/formsetu/formsetu.git
cd formsetu

# Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest packages/validator/tests/ -v

# Run full stack
cp .env.example .env
# Edit .env with your BHASHINI credentials
docker compose up
```

## Adding a New Validator

1. Create `packages/validator/src/validators/your_type.py`
2. Implement a class with `validate(self, raw_input: str) -> ValidationResult`
3. Register it in `packages/validator/src/__init__.py`
4. Add tests in `packages/validator/tests/test_your_type.py`
5. Add the field type to `packages/schema-spec/govform.schema.json` enum

## Adding a New Form Schema

1. Find the actual government form (PDF or web page)
2. Create `packages/schema-spec/examples/your-form.json`
3. Follow the GovForm Schema spec (see `govform.schema.json`)
4. Include voice prompts in at least English and Hindi
5. Test with: `python -m tools.schema-validator packages/schema-spec/examples/your-form.json`

## Code Style

- Python: Follow PEP 8, type hints encouraged
- All user-facing strings must be bilingual (en + hi minimum)
- Error codes: UPPERCASE_WITH_UNDERSCORES
- Tests: pytest, aim for >80% coverage on validators

## Pull Request Process

1. Fork → branch → implement → test → PR
2. PR title format: `[package] Brief description` (e.g., `[validator] Add Voter ID validator`)
3. Include tests for any new code
4. Update relevant documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
