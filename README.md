# FinAudit

Personal Finance Audit Tool — Parse bank statements, categorize transactions, detect spending anomalies, and visualize financial patterns.

## Overview

FinAudit is a full-stack application that automates the tedious task of analyzing bank statements. Upload CSV or PDF bank statements from multiple banks, and the tool will:

- **Parse** transactions using bank-specific adapters
- **Categorize** spending using rule-based matching and LLM fallback
- **Deduplicate** transactions across multiple statement uploads
- **Detect anomalies** in spending patterns (3-month rolling average analysis)
- **Visualize** spending breakdown by Needs/Wants/Investments buckets

## Features

### Multi-Bank Support
- **Savings Accounts**: HDFC, ICICI, SBI, Kotak, Axis
- **Credit Cards**: Generic format support
- Extensible adapter pattern for adding new banks

### Intelligent Categorization
- Rule-based pattern matching (customizable via UI)
- OpenAI GPT-4o-mini fallback for unmatched transactions
- 8 predefined categories: Food, Transport, Utilities, Entertainment, Investment, Healthcare, Shopping, Other

### Transaction Management
- Automatic duplicate detection using content-based hashing
- Manual review and correction workflow
- Persistent storage in SQLite database

### Financial Insights
- Anomaly detection for unusual spending patterns
- Spending breakdown visualization (Needs/Wants/Investments)
- Date range filtering and monthly summaries

## Tech Stack

**Backend**:
- FastAPI (REST API)
- SQLAlchemy (ORM)
- SQLite (database)
- pdfplumber (PDF parsing)
- OpenAI API (LLM categorization)

**Frontend**:
- Streamlit (interactive UI)
- Plotly (charts)

**Testing**:
- pytest (test framework)
- Hypothesis (property-based testing)

**Package Management**:
- uv (fast Python package installer)

## Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- OpenAI API key (for LLM-based categorization)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd FinAudit
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the project root:
   ```env
   OPENAI_API_KEY=sk-your-api-key-here
   ```

4. **Initialize the database**
   
   The database (`finance.db`) is created automatically on first run.

## Usage

### Running the Application

1. **Start the backend API server**
   ```bash
   uv run uvicorn app.main:app --reload
   ```
   
   API will be available at: http://localhost:8000
   
   API documentation: http://localhost:8000/api/v1/docs

2. **Start the Streamlit UI** (in a separate terminal)
   ```bash
   uv run streamlit run ui/app.py
   ```
   
   UI will open in your browser at: http://localhost:8501

### Workflow

1. **Upload Statements**: Use the sidebar to upload CSV or PDF bank statements
2. **Review Transactions**: Check the "Needs Review" section for uncategorized transactions
3. **Correct Categories**: Use dropdown menus to assign correct categories
4. **View Insights**: Check anomaly highlights and spending breakdowns
5. **Manage Rules**: Add categorization rules to automate future uploads

## Project Structure

```
FinAudit/
├── app/
│   ├── adapters/          # Bank-specific parsers (HDFC, ICICI, SBI, etc.)
│   │   ├── base.py        # Adapter pattern base classes
│   │   └── *.py           # Individual bank adapters
│   ├── models/            # Database models and schemas
│   │   ├── database.py    # SQLAlchemy setup
│   │   ├── db.py          # ORM models
│   │   └── schemas.py     # Pydantic schemas
│   ├── routes/            # FastAPI route handlers
│   │   ├── upload.py      # File upload endpoint
│   │   ├── transactions.py
│   │   ├── analytics.py
│   │   └── rules.py
│   ├── services/          # Business logic
│   │   ├── categorization.py    # Rule + LLM categorization
│   │   ├── duplicate_filter.py  # Deduplication logic
│   │   ├── pdf_parser.py        # PDF text extraction
│   │   └── anomaly_detector.py  # Spending anomaly detection
│   └── main.py            # FastAPI application entry point
├── ui/
│   └── app.py             # Streamlit UI
├── tests/
│   ├── unit/              # Unit tests
│   ├── integration/       # API integration tests
│   ├── property/          # Hypothesis property tests
│   └── smoke/             # End-to-end smoke tests
├── finance.db             # SQLite database (auto-generated)
├── pyproject.toml         # Python project configuration
├── .env                   # Environment variables (not in git)
└── README.md
```

## API Endpoints

All endpoints are prefixed with `/api/v1`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload bank statement files (CSV/PDF) |
| GET | `/transactions` | List all transactions |
| PATCH | `/transactions/{id}` | Update transaction category/review status |
| GET | `/summary` | Get spending breakdown by date range |
| GET | `/anomalies` | Get spending anomalies for a month |
| GET | `/rules` | List categorization rules |
| POST | `/rules` | Create new categorization rule |
| DELETE | `/rules/{id}` | Delete categorization rule |

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test suites
uv run pytest tests/unit/          # Unit tests only
uv run pytest tests/integration/   # Integration tests
uv run pytest tests/property/      # Property-based tests
uv run pytest tests/smoke/         # Smoke tests

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/unit/test_pdf_parser.py
```

## Adding a New Bank Adapter

1. Create `app/adapters/new_bank.py`:
   ```python
   from app.adapters.base import BankAdapter, AdapterRegistry
   
   class NewBankAdapter(BankAdapter):
       @property
       def header_signature(self) -> frozenset[str]:
           return frozenset({"Date", "Description", "Amount"})
       
       @property
       def text_patterns(self) -> list[str]:
           return ["NEW BANK NAME"]
       
       def parse_csv_rows(self, reader):
           # Implementation
           pass
       
       def parse_pdf_text(self, text):
           # Implementation
           pass
   
   AdapterRegistry.register(NewBankAdapter())
   ```

2. Import in `app/adapters/__init__.py`

## Development Notes

- **Database**: SQLite with SQLAlchemy ORM. Schema auto-created on startup.
- **Transaction IDs**: Deterministic hash from `(date, description, amount)` for deduplication
- **Categorization**: Rules checked by priority DESC, then LLM fallback
- **Amount Convention**: Debit (money out) = positive, Credit (money in) = negative
- **Date Formats**: Adapters handle `DD/MM/YY` and `DD/MM/YYYY`

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
