# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FinAudit is a personal finance audit tool that parses bank statements (CSV/PDF), categorizes transactions, detects anomalies, and visualizes spending patterns. Built with FastAPI backend and Streamlit UI.

**Tech Stack**: Python 3.13+, FastAPI, SQLAlchemy, Streamlit, OpenAI API (gpt-4o-mini), pdfplumber, uv (package manager)

## Development Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run backend API server (default: http://localhost:8000)
uv run uvicorn app.main:app --reload

# Run Streamlit UI (requires backend running)
uv run streamlit run ui/app.py

# Run all tests
uv run pytest

# Run specific test types
uv run pytest tests/unit/          # Unit tests only
uv run pytest tests/integration/   # Integration tests
uv run pytest tests/property/      # Property-based tests (Hypothesis)
uv run pytest tests/smoke/         # Smoke tests

# Run a single test file
uv run pytest tests/unit/test_pdf_parser.py

# Run tests with verbose output
uv run pytest -v
```

## Environment Setup

Requires `.env` file in project root with:
```
OPENAI_API_KEY=sk-...
```

The OpenAI API is used for LLM-based transaction categorization fallback when rule-based matching fails.

## Architecture

### Bank Adapter Pattern

The core design uses a **strategy pattern** for parsing different bank statement formats:

- **`app/adapters/base.py`**: Defines `BankAdapter` abstract base class and `AdapterRegistry`
  - Each adapter implements `header_signature` (CSV column detection) and `text_patterns` (PDF regex detection)
  - `parse_csv_rows()` and `parse_pdf_text()` return `list[RawTransaction]`
  - Registry auto-selects appropriate adapter based on file headers/content

- **Bank implementations**: `hdfc.py`, `icici.py`, `sbi.py`, `kotak.py`, `axis.py`, `credit_card.py`
  - Each adapter registers itself via `AdapterRegistry.register()` at module load
  - All adapters are imported in `app/adapters/__init__.py` to ensure registration

**Adding a new bank adapter**:
1. Create `app/adapters/new_bank.py` implementing `BankAdapter`
2. Define unique `header_signature` (CSV columns) and `text_patterns` (PDF regex)
3. Implement `parse_csv_rows()` and `parse_pdf_text()`
4. Register at module bottom: `AdapterRegistry.register(NewBankAdapter())`
5. Import in `app/adapters/__init__.py`

### Service Layer

- **`categorization.py`**: `CategorizationEngine` with rule-based matching (DB-stored patterns) → LLM fallback (OpenAI)
- **`duplicate_filter.py`**: Hash-based deduplication using `derive_id(date, description, amount)`
- **`pdf_parser.py`**: Wrapper around pdfplumber with error handling (password protection, OCR detection)
- **`anomaly_detector.py`**: Statistical anomaly detection (3-month rolling average, threshold-based alerts)
- **`rule_service.py`**: CRUD operations for categorization rules (pattern → category mappings)

### Database Layer

- **SQLite** (`finance.db`) with SQLAlchemy ORM
- **Models** (`app/models/db.py`): `TransactionModel`, `RuleModel`
- **Schemas** (`app/models/schemas.py`): Pydantic models for API contracts
- **Categories**: Fixed set: `["Food", "Transport", "Utilities", "Entertainment", "Investment", "Healthcare", "Shopping", "Other"]`
- **Transaction lifecycle**:
  1. Parsed → `RawTransaction` (date, description, amount)
  2. Deduplicated → hash-based ID generation
  3. Categorized → rule match or LLM fallback
  4. Persisted → `TransactionModel` with `is_reviewed=0`
  5. User reviews → updates category, sets `is_reviewed=1`

### API Routes

All routes prefixed with `/api/v1`:

- **`/upload`** (POST): Multi-file upload, returns `{transactions: [...], summary: {new, duplicates}}`
- **`/transactions`** (GET): List all transactions
- **`/transactions/{id}`** (PATCH): Update transaction (category, is_reviewed)
- **`/summary`** (GET): Spending breakdown by bucket (Needs/Wants/Investments) for date range
- **`/anomalies`** (GET): Anomaly detection results for specified month
- **`/rules`** (GET/POST/DELETE): Categorization rule management

### Streamlit UI (`ui/app.py`)

Multi-section UI that communicates with backend via HTTP:
- **Upload sidebar**: Multi-file upload with summary display
- **Needs Review**: List of unreviewed transactions with inline category editing
- **Anomaly Highlights**: Current month anomaly warnings
- **Spending Breakdown**: Pie chart visualization (Plotly or fallback bar chart)

**Note**: UI expects backend at `http://localhost:8000` — start backend first.

## Testing Strategy

- **Unit tests** (`tests/unit/`): Service layer, adapters, parsers in isolation
- **Integration tests** (`tests/integration/`): API endpoints with real database
- **Property-based tests** (`tests/property/`): Hypothesis for invariant checking (e.g., duplicate filter idempotence)
- **Smoke tests** (`tests/smoke/`): End-to-end happy path validation

Test configuration in `pyproject.toml`: `asyncio_mode = "auto"` for pytest-asyncio.

## Key Implementation Details

- **Date parsing**: Adapters handle multiple date formats (`"%d/%m/%y"`, `"%d/%m/%Y"`) with fallback
- **Amount convention**: Debit = positive (money out), Credit = negative (money in)
- **Transaction ID**: Deterministic hash from `(date, description, amount)` for deduplication
- **Error handling**: Custom exceptions (`UnrecognizedHeaderError`, `PasswordProtectedError`, `NoExtractableTextError`) mapped to 422 responses
- **Database session**: FastAPI dependency injection via `get_db()` generator
- **Categorization priority**: Rules ordered by `priority DESC` — first match wins
