# Requirements Document

## Introduction

The Automated Personal Finance Audit Tool is a data pipeline application that ingests raw CSV exports and PDF bank statements from multiple Indian banks and credit card providers, normalizes them into a unified transaction schema, auto-categorizes transactions using a rule-based engine augmented by an LLM, and surfaces spending trends and anomalies for user review. The system exposes a FastAPI backend with a strict JSON contract so that the Streamlit frontend can be replaced by a React frontend without backend changes.

## Glossary

- **Ingestion_Service**: The backend component responsible for parsing uploaded CSV and PDF files and mapping bank-specific fields to the unified schema.
- **PDF_Parser**: The component responsible for extracting raw text from uploaded PDF bank statements and identifying transaction rows within that text.
- **Transaction**: A single financial event conforming to the core data contract: `{ id, date, description, amount, category, is_reviewed }`.
- **Categorization_Engine**: The component that assigns a category to a Transaction using rule-based matching and an LLM fallback.
- **Audit_UI**: The Streamlit frontend that allows the user to upload files, review flagged transactions, and correct categories.
- **Anomaly_Detector**: The backend component that compares current-month category spending against a 3-month rolling average and flags outliers.
- **Rule_Store**: The persistent store of user-confirmed category corrections used to improve future categorization.
- **Bank_Adapter**: A per-bank mapping configuration that translates bank-specific CSV column names to the unified schema fields.
- **Duplicate_Filter**: The component that removes transactions sharing the same derived transaction ID before persistence.

---

## Requirements

### Requirement 1: Multi-Source File Ingestion

**User Story:** As a user, I want to upload CSV files and PDF bank statements from different banks in one step, so that I do not have to manually reformat each file before importing it.

#### Acceptance Criteria

1. WHEN a CSV file is uploaded, THE Ingestion_Service SHALL identify the source bank by inspecting the CSV header row and selecting the matching Bank_Adapter.
2. WHEN a Bank_Adapter is selected, THE Ingestion_Service SHALL map the source columns to the unified Transaction schema fields: `date`, `description`, and `amount`.
3. IF no Bank_Adapter matches the uploaded CSV header, THEN THE Ingestion_Service SHALL return an error response with a human-readable message identifying the unrecognized header columns.
4. THE Ingestion_Service SHALL support Bank_Adapters for at least HDFC savings account, ICICI savings account, SBI savings account, Kotak savings account, Axis savings account, and generic credit card statement formats at initial release.
5. WHEN multiple files are uploaded in a single request, THE Ingestion_Service SHALL process each file independently and merge the resulting Transactions into a single response payload.
6. WHEN a PDF file is uploaded, THE Ingestion_Service SHALL pass the file to the PDF_Parser to extract raw text before Bank_Adapter selection.
7. WHEN the PDF_Parser receives a PDF file, THE PDF_Parser SHALL extract all text content from every page and return it as a structured string for downstream parsing.
8. WHEN text has been extracted from a PDF, THE Ingestion_Service SHALL identify the source bank by matching recognizable header patterns in the extracted text and selecting the matching Bank_Adapter.
9. WHEN a Bank_Adapter processes extracted PDF text, THE Bank_Adapter SHALL parse transaction rows from the text and map each row to the unified Transaction schema fields: `date`, `description`, and `amount`.
10. IF a PDF file is password-protected or cannot be read, THEN THE PDF_Parser SHALL return an error response with a human-readable message indicating the file could not be parsed.
11. IF the extracted PDF text does not match any known Bank_Adapter pattern, THEN THE Ingestion_Service SHALL return an error response with a human-readable message indicating the bank format was not recognized.
12. IF a PDF file contains no extractable text (e.g., a scanned image-only PDF), THEN THE PDF_Parser SHALL return an error response indicating that the file requires OCR processing and is not supported.

---

### Requirement 2: Deduplication

**User Story:** As a user, I want duplicate transactions removed automatically, so that my spending totals are not inflated by re-uploaded data.

#### Acceptance Criteria

1. THE Ingestion_Service SHALL derive a deterministic `id` for each Transaction by hashing the combination of `date`, `description`, and `amount`.
2. WHEN a Transaction with a duplicate `id` already exists in the database, THE Duplicate_Filter SHALL discard the incoming Transaction and not persist it.
3. WHEN a batch upload is processed, THE Ingestion_Service SHALL return a summary indicating the count of new Transactions persisted and the count of duplicates discarded.

---

### Requirement 3: Rule-Based Auto-Categorization

**User Story:** As a user, I want transactions categorized automatically, so that I spend less time manually tagging each entry.

#### Acceptance Criteria

1. WHEN a Transaction is ingested, THE Categorization_Engine SHALL evaluate the `description` field against all rules in the Rule_Store in priority order.
2. WHEN a rule matches the `description`, THE Categorization_Engine SHALL assign the rule's associated category to the Transaction and set `is_reviewed` to `false`.
3. THE Categorization_Engine SHALL support the top-level categories: `Food`, `Transport`, `Utilities`, `Entertainment`, `Investment`, `Healthcare`, `Shopping`, and `Other`.
4. WHEN no rule in the Rule_Store matches the `description`, THE Categorization_Engine SHALL invoke the LLM fallback to infer a category from the `description` text.
5. WHEN the LLM fallback is invoked, THE Categorization_Engine SHALL assign the returned category to the Transaction and set `is_reviewed` to `false`.
6. IF the LLM service is unavailable, THEN THE Categorization_Engine SHALL assign the category `Other` to the Transaction and set `is_reviewed` to `false`.

---

### Requirement 4: Human-in-the-Loop Audit

**User Story:** As a user, I want to correct miscategorized transactions from the UI, so that the system improves over time and my reports stay accurate.

#### Acceptance Criteria

1. THE Audit_UI SHALL display a "Needs Review" section containing all Transactions where `is_reviewed` is `false`.
2. WHEN a user selects a new category for a Transaction in the Audit_UI, THE Audit_UI SHALL send a correction request to the backend with the Transaction `id` and the new category.
3. WHEN a correction request is received, THE Categorization_Engine SHALL update the Transaction's `category` field and set `is_reviewed` to `true`.
4. WHEN a correction request is received, THE Rule_Store SHALL persist a new rule mapping the Transaction's `description` to the corrected category so that future Transactions with the same description are categorized correctly without LLM invocation.
5. WHEN a correction is saved, THE Audit_UI SHALL remove the corrected Transaction from the "Needs Review" section without requiring a full page reload.

---

### Requirement 5: Trend and Anomaly Detection

**User Story:** As a user, I want to be alerted when my spending in a category is unusually high, so that I can investigate and adjust my behavior.

#### Acceptance Criteria

1. WHEN the dashboard is loaded, THE Anomaly_Detector SHALL compute a 3-month rolling average spend per category using all Transactions dated within the 3 calendar months preceding the current month.
2. WHEN the current month's total spend in a category exceeds the 3-month rolling average for that category by more than 30%, THE Anomaly_Detector SHALL flag that category as anomalous.
3. WHEN a category is flagged as anomalous, THE Audit_UI SHALL highlight the category and display the percentage deviation from the rolling average.
4. IF fewer than 3 months of Transaction data exist for a category, THEN THE Anomaly_Detector SHALL skip anomaly detection for that category and not flag it.

---

### Requirement 6: Spending Breakdown Visualization

**User Story:** As a user, I want a visual breakdown of my spending by Needs, Wants, and Investments, so that I can assess my financial health at a glance.

#### Acceptance Criteria

1. THE Audit_UI SHALL map each category to one of three buckets: `Needs` (Utilities, Healthcare, Transport), `Wants` (Food, Entertainment, Shopping), or `Investments` (Investment).
2. WHEN all Transactions for the selected period have `is_reviewed` set to `true`, THE Audit_UI SHALL render a chart showing the percentage and absolute amount for each bucket.
3. WHILE unreviewed Transactions exist, THE Audit_UI SHALL display a prompt indicating the count of unreviewed Transactions and encouraging the user to complete the audit before viewing the breakdown.
4. THE Audit_UI SHALL allow the user to filter the breakdown by a selectable date range with a minimum granularity of one calendar month.

---

### Requirement 7: Strict API Data Contract

**User Story:** As a developer, I want the backend to expose a versioned REST API with a fixed Transaction schema, so that the Streamlit frontend can be replaced by a React frontend without backend changes.

#### Acceptance Criteria

1. THE Ingestion_Service SHALL expose all Transaction endpoints under the `/api/v1/` path prefix.
2. WHEN a Transaction is returned by any API endpoint, THE Ingestion_Service SHALL serialize it using the schema: `{ "id": "<uuid>", "date": "<YYYY-MM-DD>", "description": "<string>", "amount": <number>, "category": "<string>", "is_reviewed": <boolean> }`.
3. WHEN an API request contains a malformed Transaction payload, THE Ingestion_Service SHALL return an HTTP 422 response with a structured validation error body.
4. THE Ingestion_Service SHALL include an OpenAPI specification document accessible at `/api/v1/docs` describing all endpoints and the Transaction schema.
