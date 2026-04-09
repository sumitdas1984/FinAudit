# Implementation Plan: Personal Finance Audit Tool

## Overview

Implement a FastAPI backend with SQLAlchemy/SQLite persistence, bank-specific CSV/PDF adapters (HDFC, ICICI, SBI, Kotak, Axis, generic credit card), rule-based categorization with GPT-4o-mini fallback, anomaly detection, and a Streamlit frontend. Property-based tests use Hypothesis for all 17 correctness properties.

## Tasks

- [x] 1. Project setup and dependencies
  - Add FastAPI, uvicorn, SQLAlchemy, pdfplumber, hypothesis, streamlit, openai, fpdf2, httpx, pytest, pytest-asyncio to `pyproject.toml` dependencies
  - Create directory structure: `app/`, `app/adapters/`, `app/models/`, `app/services/`, `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/smoke/`
  - Create `app/__init__.py`, `app/adapters/__init__.py`, `app/models/__init__.py`, `app/services/__init__.py`
  - _Requirements: 7.1, 7.4_

- [x] 2. Database models and schema
  - [x] 2.1 Define SQLAlchemy ORM models in `app/models/db.py`
    - `TransactionModel` table: `id TEXT PK`, `date TEXT`, `description TEXT`, `amount REAL`, `category TEXT`, `is_reviewed INTEGER DEFAULT 0`
    - `RuleModel` table: `id INTEGER PK AUTOINCREMENT`, `pattern TEXT UNIQUE`, `category TEXT`, `priority INTEGER DEFAULT 0`, `created_at TEXT`
    - Database engine + `SessionLocal` factory + `Base.metadata.create_all()` in `app/models/database.py`
    - _Requirements: 2.1, 3.1, 4.4_

  - [x] 2.2 Define Pydantic schemas in `app/models/schemas.py`
    - `RawTransaction` dataclass: `date`, `description`, `amount`
    - `Transaction` Pydantic model matching the API contract schema
    - `Rule`, `AnomalyResult`, `UploadSummary` Pydantic models
    - `CATEGORIES` constant list and `CATEGORY_BUCKET` mapping dict
    - _Requirements: 7.2, 3.3, 6.1_

  - [x] 2.3 Write property test for Transaction serialization round-trip
    - **Property 16: Transaction serialization round-trip**
    - Use `st.builds(Transaction, ...)` to generate arbitrary Transaction objects, serialize to JSON and deserialize back, assert equality
    - **Validates: Requirements 7.2**

  - [x] 2.4 Write property test for malformed payload → HTTP 422
    - **Property 17: Malformed payloads always yield HTTP 422**
    - Use `st.fixed_dictionaries(...)` with missing/wrong-type fields against FastAPI test client
    - **Validates: Requirements 7.3**

- [x] 3. ID derivation and Duplicate_Filter
  - [x] 3.1 Implement `derive_id()` in `app/services/duplicate_filter.py`
    - `sha256(f"{date}|{description}|{amount}".encode()).hexdigest()[:16]`
    - Implement `DuplicateFilter.filter(transactions, db_session)` returning `(new_list, duplicate_count)`
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.2 Write property test for ID determinism
    - **Property 5: Transaction ID derivation is deterministic**
    - Use `st.tuples(st.dates(), st.text(), st.floats(allow_nan=False, allow_infinity=False))` — call `derive_id()` twice, assert equal; generate two differing triples, assert IDs differ
    - **Validates: Requirements 2.1**

  - [x] 3.3 Write property test for deduplication idempotency
    - **Property 6: Deduplication is idempotent**
    - Use `st.lists(raw_transaction_strategy())` with in-memory SQLite — insert set once, then again; assert `new == 0` and `duplicates == total` on second pass
    - **Validates: Requirements 2.2, 2.3**

  - [x] 3.4 Write property test for batch summary consistency
    - **Property 7: Batch summary counts are consistent**
    - Assert `summary.new + summary.duplicates == total_parsed` for any generated batch
    - **Validates: Requirements 2.3**

- [ ] 4. PDF_Parser
  - [x] 4.1 Implement `PDF_Parser` in `app/services/pdf_parser.py`
    - `extract_text(file: BinaryIO) -> str` using `pdfplumber.open()`; join all page text
    - Raise `PasswordProtectedError` for encrypted PDFs, `NoExtractableTextError` when all pages yield empty text, `ParseError` for other failures
    - Define custom exception classes in `app/services/exceptions.py`
    - _Requirements: 1.6, 1.7, 1.10, 1.12_

  - [x] 4.2 Write property test for PDF full-page coverage
    - **Property 4: PDF text extraction covers all pages**
    - Generate multi-page PDFs programmatically with `fpdf2`, each page containing a unique token; assert all tokens appear in extracted text
    - **Validates: Requirements 1.7**

  - [x] 4.3 Write unit tests for PDF_Parser edge cases
    - Test password-protected PDF raises `PasswordProtectedError`
    - Test image-only PDF raises `NoExtractableTextError`
    - _Requirements: 1.10, 1.12_

- [x] 5. Bank_Adapter base class and concrete implementations
  - [x] 5.1 Implement `BankAdapter` ABC and `AdapterRegistry` in `app/adapters/base.py`
    - Abstract properties: `header_signature: frozenset[str]`, `text_patterns: list[str]`
    - Abstract methods: `parse_csv_rows(reader) -> list[RawTransaction]`, `parse_pdf_text(text) -> list[RawTransaction]`
    - `AdapterRegistry.select_for_csv(headers: frozenset[str]) -> BankAdapter` — raise `UnrecognizedHeaderError` if no match
    - `AdapterRegistry.select_for_pdf(text: str) -> BankAdapter` — raise `UnrecognizedBankFormatError` if no match
    - _Requirements: 1.1, 1.3, 1.4, 1.8_

  - [x] 5.2 Implement `HDFCSavingsAdapter` in `app/adapters/hdfc.py`
    - Define `header_signature` matching HDFC savings CSV columns
    - Implement `parse_csv_rows()` mapping date/narration/amount columns to `RawTransaction`
    - Implement `parse_pdf_text()` using regex to extract transaction rows from HDFC PDF text
    - _Requirements: 1.2, 1.4, 1.9_

  - [x] 5.3 Implement `ICICISavingsAdapter` in `app/adapters/icici.py`
    - Define `header_signature` matching ICICI savings CSV columns
    - Implement `parse_csv_rows()` and `parse_pdf_text()` for ICICI format
    - _Requirements: 1.2, 1.4, 1.9_

  - [x] 5.4 Implement `GenericCreditCardAdapter` in `app/adapters/credit_card.py`
    - Define `header_signature` for generic credit card CSV format
    - Implement `parse_csv_rows()` and `parse_pdf_text()`
    - _Requirements: 1.2, 1.4, 1.9_

  - [x] 5.5 Implement `SBISavingsAdapter` in `app/adapters/sbi.py`
    - Define `header_signature` matching SBI savings CSV columns
    - Implement `parse_csv_rows()` and `parse_pdf_text()` for SBI format
    - _Requirements: 1.2, 1.4, 1.9_

  - [x] 5.6 Implement `KotakSavingsAdapter` in `app/adapters/kotak.py`
    - Define `header_signature` matching Kotak savings CSV columns
    - Implement `parse_csv_rows()` and `parse_pdf_text()` for Kotak format
    - _Requirements: 1.2, 1.4, 1.9_

  - [x] 5.7 Implement `AxisSavingsAdapter` in `app/adapters/axis.py`
    - Define `header_signature` matching Axis savings CSV columns
    - Implement `parse_csv_rows()` and `parse_pdf_text()` for Axis format
    - Register all six adapters in `app/adapters/__init__.py` via `AdapterRegistry`
    - _Requirements: 1.2, 1.4, 1.9_

  - [x] 5.8 Write property test for adapter selection exhaustiveness
    - **Property 1: Bank adapter selection is exhaustive and exclusive**
    - Use `st.frozensets(st.text())` — assert known signatures return exactly one adapter; assert unknown headers raise error; assert no header matches two adapters
    - **Validates: Requirements 1.1, 1.3**

  - [x] 5.9 Write property test for adapter field mapping
    - **Property 2: Bank adapter field mapping preserves all data**
    - Use `st.fixed_dictionaries(...)` per bank schema — assert `date`, `description`, `amount` are non-null and amount is finite for every generated row
    - **Validates: Requirements 1.2, 1.9**

  - [x] 5.10 Write unit tests for Bank_Adapters with fixture files
    - One example-based test per adapter using a sample CSV fixture in `tests/fixtures/`
    - _Requirements: 1.2, 1.4_

- [x] 6. Categorization_Engine and Rule_Store
  - [x] 6.1 Implement `CategorizationEngine` in `app/services/categorization.py`
    - `categorize(description: str, db: Session) -> str` — query rules ordered by `priority DESC`, return first match
    - If no match: call OpenAI `gpt-4o-mini` with zero-shot prompt constrained to `CATEGORIES`; on failure return `"Other"`
    - Wrap LLM call in try/except; log warning on failure
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6_

  - [x] 6.2 Implement rule CRUD helpers in `app/services/rule_service.py`
    - `create_rule(pattern, category, priority, db)`, `list_rules(db)`, `delete_rule(id, db)`
    - `upsert_rule_for_correction(description, category, db)` — used by correction endpoint
    - _Requirements: 4.4_

  - [x] 6.3 Write property test for highest-priority rule wins
    - **Property 8: Highest-priority matching rule wins categorization**
    - Use `st.lists(rule_strategy(), min_size=1)` + `st.text()` — insert rules into in-memory DB, assert engine returns category of highest-priority matching rule
    - **Validates: Requirements 3.1, 3.2**

  - [x] 6.4 Write property test for LLM fallback invocation
    - **Property 9: LLM fallback is invoked iff no rule matches**
    - Use `st.text()` with mocked LLM — assert LLM called exactly once when no rule matches; assert LLM not called when rule matches; assert `"Other"` returned when LLM raises exception
    - **Validates: Requirements 3.4, 3.5, 3.6**

- [x] 7. Anomaly_Detector
  - [x] 7.1 Implement `AnomalyDetector` in `app/services/anomaly_detector.py`
    - `compute_anomalies(reference_date: date, db: Session) -> list[AnomalyResult]`
    - Compute rolling average per category over 3 calendar months before `reference_date`
    - Flag category if `current > rolling_avg * 1.30` AND at least 3 months of data exist
    - `deviation_pct = round((current - avg) / avg * 100, 2)`
    - `compute_summary(start: date, end: date, db: Session) -> dict` — bucket totals + `unreviewed_count`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.4_

  - [x] 7.2 Write property test for anomaly threshold exactness
    - **Property 12: Anomaly flagging threshold is exact**
    - Use `st.floats(min_value=0, allow_nan=False, allow_infinity=False)` for spend values — assert flagged iff `current > avg * 1.30` AND >= 3 months history; assert not flagged otherwise
    - **Validates: Requirements 5.1, 5.2, 5.4**

  - [x] 7.3 Write property test for deviation percentage correctness
    - **Property 13: Deviation percentage is computed correctly**
    - Use `st.floats(min_value=0.01, allow_nan=False, allow_infinity=False)` — assert `deviation_pct == round((current - avg) / avg * 100, 2)` for all flagged anomalies
    - **Validates: Requirements 5.3**

  - [x] 7.4 Write property test for bucket mapping totality
    - **Property 14: Category-to-bucket mapping is total and correct**
    - Use `st.sampled_from(CATEGORIES)` — assert every non-Other category maps to exactly the bucket defined in `CATEGORY_BUCKET`
    - **Validates: Requirements 6.1**

  - [x] 7.5 Write property test for bucket totals correctness
    - **Property 15: Bucket totals are the sum of constituent transactions**
    - Use `st.lists(transaction_strategy())` — assert each bucket total equals sum of amounts for transactions in that bucket within the date range
    - **Validates: Requirements 6.2, 6.4**

- [x] 8. FastAPI routes
  - [x] 8.1 Implement `POST /api/v1/upload` in `app/routes/upload.py`
    - Accept `multipart/form-data` with one or more files
    - Route each file through PDF_Parser (if PDF) or direct CSV read, then AdapterRegistry, DuplicateFilter, CategorizationEngine
    - Persist new transactions; return `{ "transactions": [...], "summary": { "new": int, "duplicates": int } }`
    - Return HTTP 422 with structured error body for unrecognized headers, password-protected PDFs, image-only PDFs, unrecognized bank formats
    - _Requirements: 1.1–1.12, 2.1–2.3, 3.1–3.6_

  - [x] 8.2 Write property test for multi-file merge
    - **Property 3: Multi-file merge is the union of individual results**
    - Use `st.lists(st.binary())` of synthetic CSVs — assert combined upload transaction count equals sum of individual upload counts (before dedup)
    - **Validates: Requirements 1.5**

  - [x] 8.3 Implement `GET /api/v1/transactions` in `app/routes/transactions.py`
    - Query all transactions from DB; serialize using `Transaction` schema
    - _Requirements: 7.1, 7.2_

  - [x] 8.4 Implement `PATCH /api/v1/transactions/:id` in `app/routes/transactions.py`
    - Accept `{ "category": str }` body; validate category is in `CATEGORIES`
    - Update `category` and set `is_reviewed = true`; call `upsert_rule_for_correction()`
    - Return HTTP 404 if transaction not found
    - _Requirements: 4.3, 4.4_

  - [x] 8.5 Write property test for correction updates fields
    - **Property 10: Correction updates category and marks reviewed**
    - Use `st.sampled_from(CATEGORIES)` — assert PATCH sets `category` to new value and `is_reviewed` to `true`
    - **Validates: Requirements 4.3**

  - [x] 8.6 Write property test for correction persists rule
    - **Property 11: Correction persists a rule for future use**
    - Use `st.text()` descriptions + `st.sampled_from(CATEGORIES)` — after PATCH, assert Rule_Store contains rule mapping description → category; assert next categorization of same description uses rule without LLM
    - **Validates: Requirements 4.4**

  - [x] 8.7 Implement `GET /api/v1/anomalies` and `GET /api/v1/summary` in `app/routes/analytics.py`
    - `/api/v1/anomalies?month=YYYY-MM` → call `AnomalyDetector.compute_anomalies()`
    - `/api/v1/summary?start=YYYY-MM-DD&end=YYYY-MM-DD` → call `compute_summary()`
    - _Requirements: 5.1–5.4, 6.1–6.4_

  - [x] 8.8 Implement `GET/POST/DELETE /api/v1/rules` in `app/routes/rules.py`
    - Wire to `rule_service` CRUD helpers
    - _Requirements: 4.4_

  - [x] 8.9 Wire all routers in `app/main.py`
    - Create FastAPI app with prefix `/api/v1`, include all routers
    - Configure `docs_url="/api/v1/docs"`
    - Initialize DB on startup via `Base.metadata.create_all()`
    - _Requirements: 7.1, 7.4_

- [x] 9. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Streamlit Audit_UI
  - [x] 10.1 Implement upload sidebar in `ui/app.py`
    - File uploader widget accepting CSV and PDF; POST to `POST /api/v1/upload`; display summary of new/duplicate counts
    - _Requirements: 1.5_

  - [x] 10.2 Implement "Needs Review" section
    - Fetch `GET /api/v1/transactions`; filter `is_reviewed == false`; display count prompt while unreviewed exist
    - Render each unreviewed transaction with a category dropdown; on change send `PATCH /api/v1/transactions/:id`; remove row from list on success without full reload
    - _Requirements: 4.1, 4.2, 4.5, 6.3_

  - [x] 10.3 Implement anomaly highlights
    - Fetch `GET /api/v1/anomalies?month=<current_month>`; highlight flagged categories with deviation percentage
    - _Requirements: 5.2, 5.3_

  - [x] 10.4 Implement spending breakdown visualization
    - Fetch `GET /api/v1/summary` with date range selector (month granularity); render bar/pie chart for Needs/Wants/Investments buckets showing percentage and absolute amounts
    - Only render chart when `unreviewed_count == 0`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 11. Integration and smoke tests
  - [x] 11.1 Write integration test for full upload → categorize → retrieve flow
    - Use in-memory SQLite; POST a synthetic CSV; assert transactions returned with correct categories
    - `tests/integration/test_api_upload.py`
    - _Requirements: 1.1, 2.1, 3.1_

  - [x] 11.2 Write integration tests for correction flow
    - POST upload, PATCH correction, GET transactions — assert state changes; assert rule persisted
    - `tests/integration/test_api_corrections.py`
    - _Requirements: 4.3, 4.4_

  - [x] 11.3 Write integration tests for anomaly detection flow
    - Seed DB with 4 months of transactions; call GET /api/v1/anomalies; assert correct flags
    - `tests/integration/test_api_anomalies.py`
    - _Requirements: 5.1, 5.2, 5.4_

  - [x] 11.4 Write smoke tests in `tests/smoke/test_smoke.py`
    - Assert all 6 adapters are registered in AdapterRegistry
    - Assert all 8 categories are defined in `CATEGORIES`
    - Assert `GET /api/v1/docs` returns HTTP 200
    - _Requirements: 1.4, 3.3, 7.4_

- [x] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `settings(max_examples=100)` and are tagged `# Feature: personal-finance-audit, Property N: <text>`
- Unit tests and property tests are complementary — both are needed for full coverage
- All property tests live in `tests/property/test_properties.py`
