"""
Personal Finance Audit Tool — Streamlit UI
==========================================
Calls the FastAPI backend at http://localhost:8000 over HTTP.

Sections (added across tasks 10.1 – 10.4):
  10.1  Upload sidebar          ← implemented here
  10.2  Needs Review section
  10.3  Anomaly highlights
  10.4  Spending breakdown visualization
"""

import datetime

import streamlit as st
import requests

API_BASE = "http://localhost:8000/api/v1"

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------

if "transactions" not in st.session_state:
    st.session_state.transactions: list[dict] = []

if "upload_summary" not in st.session_state:
    st.session_state.upload_summary: dict | None = None

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Personal Finance Audit", layout="wide")
st.title("Personal Finance Audit Tool")

# ---------------------------------------------------------------------------
# 10.1  Upload sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Upload Statements")

    uploaded_files = st.file_uploader(
        "Select CSV or PDF bank statements",
        type=["csv", "pdf"],
        accept_multiple_files=True,
        help="Supports HDFC, ICICI, SBI, Kotak, Axis savings accounts and generic credit card formats.",
    )

    if st.button("Upload", disabled=not uploaded_files):
        files_payload = [
            ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
            for f in uploaded_files
        ]
        try:
            response = requests.post(f"{API_BASE}/upload", files=files_payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                st.session_state.transactions = data.get("transactions", [])
                st.session_state.upload_summary = data.get("summary", {})
                st.session_state.unreviewed_loaded = False  # trigger reload in 10.2
            else:
                detail = response.json()
                st.error(f"Upload failed ({response.status_code}): {detail}")
        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the backend. Make sure the server is running on http://localhost:8000.")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")

    # Display upload summary
    if st.session_state.upload_summary is not None:
        summary = st.session_state.upload_summary
        st.success("Upload complete")
        col1, col2 = st.columns(2)
        col1.metric("New transactions", summary.get("new", 0))
        col2.metric("Duplicates skipped", summary.get("duplicates", 0))

# ---------------------------------------------------------------------------
# 10.2  Needs Review section
# ---------------------------------------------------------------------------

CATEGORIES = ["Food", "Transport", "Utilities", "Entertainment", "Investment", "Healthcare", "Shopping", "Other"]

# Initialise unreviewed list in session state (populated on first load / after upload)
if "unreviewed" not in st.session_state:
    st.session_state.unreviewed: list[dict] = []

if "unreviewed_loaded" not in st.session_state:
    st.session_state.unreviewed_loaded = False

def _load_unreviewed() -> None:
    """Fetch all transactions from the API and populate session state with unreviewed ones."""
    try:
        resp = requests.get(f"{API_BASE}/transactions", timeout=10)
        if resp.status_code == 200:
            all_txns = resp.json()
            st.session_state.unreviewed = [t for t in all_txns if not t.get("is_reviewed", True)]
            st.session_state.unreviewed_loaded = True
        else:
            st.error(f"Failed to load transactions ({resp.status_code})")
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the backend. Make sure the server is running on http://localhost:8000.")
    except Exception as exc:
        st.error(f"Unexpected error loading transactions: {exc}")

# Reload unreviewed list whenever a new upload completes (upload_summary changes)
if st.session_state.upload_summary is not None and not st.session_state.unreviewed_loaded:
    _load_unreviewed()

st.header("Needs Review")

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("Refresh list"):
        _load_unreviewed()

if not st.session_state.unreviewed_loaded:
    st.info("Upload a statement or click **Refresh list** to load transactions.")
elif len(st.session_state.unreviewed) == 0:
    st.success("All transactions have been reviewed.")
else:
    count = len(st.session_state.unreviewed)
    st.warning(f"{count} transaction{'s' if count != 1 else ''} need{'s' if count == 1 else ''} review")

    # Render one row per unreviewed transaction
    for txn in list(st.session_state.unreviewed):
        txn_id = txn["id"]
        cols = st.columns([2, 4, 2, 3])
        cols[0].write(txn.get("date", ""))
        cols[1].write(txn.get("description", ""))
        cols[2].write(f"₹{txn.get('amount', 0):,.2f}")

        current_cat = txn.get("category", CATEGORIES[0])
        default_idx = CATEGORIES.index(current_cat) if current_cat in CATEGORIES else 0

        new_cat = cols[3].selectbox(
            "Category",
            options=CATEGORIES,
            index=default_idx,
            key=f"cat_{txn_id}",
            label_visibility="collapsed",
        )

        if new_cat != current_cat:
            try:
                patch_resp = requests.patch(
                    f"{API_BASE}/transactions/{txn_id}",
                    json={"category": new_cat},
                    timeout=10,
                )
                if patch_resp.status_code == 200:
                    st.session_state.unreviewed = [
                        t for t in st.session_state.unreviewed if t["id"] != txn_id
                    ]
                    st.rerun()
                else:
                    st.error(f"Failed to update transaction {txn_id} ({patch_resp.status_code})")
            except requests.exceptions.ConnectionError:
                st.error("Cannot reach the backend.")
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")

# ---------------------------------------------------------------------------
# 10.3  Anomaly highlights
# ---------------------------------------------------------------------------

st.header("Anomaly Highlights")

current_month = datetime.date.today().strftime("%Y-%m")

try:
    anomaly_resp = requests.get(f"{API_BASE}/anomalies", params={"month": current_month}, timeout=10)
    if anomaly_resp.status_code == 200:
        anomalies: list[dict] = anomaly_resp.json()
        if not anomalies:
            st.success("No spending anomalies detected for this month.")
        else:
            st.warning(f"{len(anomalies)} spending anomal{'y' if len(anomalies) == 1 else 'ies'} detected for {current_month}")
            cols = st.columns(min(len(anomalies), 3))
            for i, anomaly in enumerate(anomalies):
                category = anomaly.get("category", "Unknown")
                current_spend = anomaly.get("current_month_spend", 0.0)
                rolling_avg = anomaly.get("rolling_avg", 0.0)
                deviation_pct = anomaly.get("deviation_pct", 0.0)
                col = cols[i % len(cols)]
                with col:
                    st.warning(
                        f"**{category}**\n\n"
                        f"This month: ₹{current_spend:,.2f}\n\n"
                        f"3-month avg: ₹{rolling_avg:,.2f}\n\n"
                        f"⚠ +{deviation_pct:.1f}% above average"
                    )
    else:
        st.error(f"Failed to load anomalies ({anomaly_resp.status_code})")
except requests.exceptions.ConnectionError:
    st.error("Cannot reach the backend. Make sure the server is running on http://localhost:8000.")
except Exception as exc:
    st.error(f"Unexpected error loading anomalies: {exc}")

# ---------------------------------------------------------------------------
# 10.4  Spending breakdown visualization
# ---------------------------------------------------------------------------

st.header("Spending Breakdown")

# Date range selector — default to current month
_today = datetime.date.today()
_month_start = _today.replace(day=1)
# Last day of current month
_next_month = (_month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
_month_end = _next_month - datetime.timedelta(days=1)

date_range = st.date_input(
    "Select date range",
    value=(_month_start, _month_end),
    min_value=datetime.date(2000, 1, 1),
    max_value=datetime.date(2100, 12, 31),
    format="YYYY-MM-DD",
)

# Ensure we have a valid two-element range before fetching
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date, end_date = date_range
    try:
        summary_resp = requests.get(
            f"{API_BASE}/summary",
            params={"start": start_date.isoformat(), "end": end_date.isoformat()},
            timeout=10,
        )
        if summary_resp.status_code == 200:
            summary_data = summary_resp.json()
            unreviewed_count: int = summary_data.get("unreviewed_count", 0)
            buckets: dict = summary_data.get("buckets", {})

            if unreviewed_count > 0:
                st.warning(
                    f"{unreviewed_count} transaction{'s' if unreviewed_count != 1 else ''} "
                    f"need{'s' if unreviewed_count == 1 else ''} review before viewing the breakdown."
                )
            else:
                # Build chart data
                bucket_names = ["Needs", "Wants", "Investments"]
                amounts = [buckets.get(b, 0.0) for b in bucket_names]
                total = sum(amounts)

                if total == 0:
                    st.info("No spending data available for the selected period.")
                else:
                    percentages = [(a / total * 100) for a in amounts]

                    # Try plotly first, fall back to st.bar_chart
                    try:
                        import plotly.graph_objects as go  # type: ignore

                        labels = [
                            f"{name}<br>₹{amt:,.2f} ({pct:.1f}%)"
                            for name, amt, pct in zip(bucket_names, amounts, percentages)
                        ]
                        fig = go.Figure(
                            data=[
                                go.Pie(
                                    labels=bucket_names,
                                    values=amounts,
                                    text=labels,
                                    hovertemplate="%{label}<br>₹%{value:,.2f}<br>%{percent}<extra></extra>",
                                    textinfo="label+percent",
                                )
                            ]
                        )
                        fig.update_layout(
                            title=f"Spending Breakdown: {start_date} → {end_date}",
                            showlegend=True,
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except ImportError:
                        import pandas as pd  # type: ignore

                        chart_data = pd.DataFrame(
                            {"Amount (₹)": amounts},
                            index=bucket_names,
                        )
                        st.bar_chart(chart_data)

                    # Summary table below the chart
                    st.subheader("Bucket Summary")
                    cols = st.columns(len(bucket_names))
                    for col, name, amt, pct in zip(cols, bucket_names, amounts, percentages):
                        col.metric(name, f"₹{amt:,.2f}", f"{pct:.1f}%")
        else:
            st.error(f"Failed to load spending summary ({summary_resp.status_code})")
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the backend. Make sure the server is running on http://localhost:8000.")
    except Exception as exc:
        st.error(f"Unexpected error loading spending summary: {exc}")
else:
    st.info("Select a start and end date to view the spending breakdown.")
