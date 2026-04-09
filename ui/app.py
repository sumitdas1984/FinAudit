"""
Personal Finance Audit Tool — Streamlit UI
==========================================
Calls the FastAPI backend at http://localhost:8000 over HTTP.
Layout based on FinAudit mockup: sidebar nav with Dashboard, Audit Queue, Import Data pages.
"""

import datetime
import requests
import streamlit as st
import plotly.express as px

API_BASE = "http://localhost:8000/api/v1"

CATEGORIES = ["Food", "Transport", "Utilities", "Entertainment", "Investment", "Healthcare", "Shopping", "Other"]

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="FinAudit | Personal Finance Auditor",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "upload_summary" not in st.session_state:
    st.session_state.upload_summary = None

if "unreviewed" not in st.session_state:
    st.session_state.unreviewed: list[dict] = []

if "unreviewed_loaded" not in st.session_state:
    st.session_state.unreviewed_loaded = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_unreviewed() -> None:
    try:
        resp = requests.get(f"{API_BASE}/transactions", timeout=10)
        if resp.status_code == 200:
            all_txns = resp.json()
            st.session_state.unreviewed = [t for t in all_txns if not t.get("is_reviewed", True)]
            st.session_state.unreviewed_loaded = True
        else:
            st.error(f"Failed to load transactions ({resp.status_code})")
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the backend at http://localhost:8000.")
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")


def _get_all_transactions() -> list[dict]:
    try:
        resp = requests.get(f"{API_BASE}/transactions", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def _get_anomalies(month: str) -> list[dict]:
    try:
        resp = requests.get(f"{API_BASE}/anomalies", params={"month": month}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def _get_summary(start: str, end: str) -> dict | None:
    try:
        resp = requests.get(f"{API_BASE}/summary", params={"start": start, "end": end}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> str:
    with st.sidebar:
        st.title("💰 FinAudit")
        st.markdown("---")
        st.caption("Navigation")
        nav = st.radio(
            "nav",
            ["📊 Dashboard", "🔍 Audit Queue", "📥 Import Data"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.info("**Audit Tip:** High-confidence matches (80%+) are auto-processed. Focus on low-confidence rows.")
        if st.button("Reset Session Data", type="secondary"):
            st.session_state.clear()
            st.rerun()
    return nav


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------

def show_dashboard():
    st.header("Financial Health Overview")

    today = datetime.date.today()
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    month_end = next_month - datetime.timedelta(days=1)
    current_month = today.strftime("%Y-%m")

    all_txns = _get_all_transactions()
    anomalies = _get_anomalies(current_month)
    summary = _get_summary(month_start.isoformat(), month_end.isoformat())

    # --- Metrics ---
    col1, col2, col3 = st.columns(3)

    if summary:
        buckets = summary.get("buckets", {})
        total_spent = sum(buckets.values())
        unreviewed_count = summary.get("unreviewed_count", 0)
        total_txns = len(all_txns)
        reviewed = total_txns - unreviewed_count
        audit_pct = (reviewed / total_txns * 100) if total_txns else 0
    else:
        total_spent = 0.0
        audit_pct = 0.0
        unreviewed_count = 0

    col1.metric("Total Spent", f"₹{total_spent:,.2f}", f"Month of {current_month}")
    col2.metric("Audit Completion", f"{audit_pct:.0f}%", "Target: 100%")
    col3.metric(
        "Anomalies Flagged",
        f"{len(anomalies):02d}",
        "Requires Action" if anomalies else "All Clear",
        delta_color="inverse" if anomalies else "normal",
    )

    st.markdown("### Spending Analysis")
    chart_col, anomaly_col = st.columns([2, 1])

    with chart_col:
        if summary and sum(summary.get("buckets", {}).values()) > 0:
            buckets = summary["buckets"]
            if summary.get("unreviewed_count", 0) > 0:
                st.warning(f"{summary['unreviewed_count']} transactions still need review. Complete the audit for an accurate breakdown.")
            else:
                fig = px.pie(
                    names=list(buckets.keys()),
                    values=list(buckets.values()),
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Safe,
                )
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
        elif all_txns:
            # Fall back to category breakdown from transactions
            import pandas as pd
            df = pd.DataFrame(all_txns)
            df_spend = df[df["amount"] > 0]
            if not df_spend.empty:
                fig = px.pie(
                    df_spend,
                    values="amount",
                    names="category",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Safe,
                )
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No spending data available yet. Upload a statement to get started.")
        else:
            st.info("No data yet. Upload a bank statement from the Import Data page.")

    with anomaly_col:
        st.markdown("#### Potential Issues")
        if anomalies:
            for a in anomalies:
                st.warning(
                    f"**{a['category']}** — ₹{a['current_month_spend']:,.2f} this month "
                    f"(+{a['deviation_pct']:.1f}% above avg)"
                )
        else:
            st.success("No anomalies detected for this month.")


# ---------------------------------------------------------------------------
# Page: Audit Queue
# ---------------------------------------------------------------------------

def show_audit_queue():
    st.header("Transaction Audit Queue")
    st.write("Review AI-suggested categories and finalize your records.")

    if not st.session_state.unreviewed_loaded:
        _load_unreviewed()

    unreviewed = st.session_state.unreviewed

    if not unreviewed:
        st.success("All transactions have been reviewed.")
        if st.button("Refresh"):
            _load_unreviewed()
            st.rerun()
        return

    # Table header
    hcols = st.columns([2, 4, 2, 3, 2, 2])
    for col, label in zip(hcols, ["Date", "Merchant", "Amount (₹)", "Final Category", "AI Match", "Audit Status"]):
        col.markdown(f"**{label}**")
    st.markdown("---")

    for txn in list(unreviewed):
        txn_id = txn["id"]
        current_cat = txn.get("category", CATEGORIES[0])
        default_idx = CATEGORIES.index(current_cat) if current_cat in CATEGORIES else 0

        row = st.columns([2, 4, 2, 3, 2, 2])
        row[0].write(txn.get("date", ""))
        row[1].write(txn.get("description", ""))
        row[2].write(f"₹{txn.get('amount', 0):,.2f}")

        new_cat = row[3].selectbox(
            "cat",
            options=CATEGORIES,
            index=default_idx,
            key=f"cat_{txn_id}",
            label_visibility="collapsed",
        )
        row[4].progress(0.5, text="—")   # placeholder; real confidence not in schema
        row[5].write("Pending")

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
                    st.error(f"Failed to update ({patch_resp.status_code})")
            except requests.exceptions.ConnectionError:
                st.error("Cannot reach the backend.")
            except Exception as exc:
                st.error(f"Error: {exc}")

    if st.button("Save Audit Progress", type="primary"):
        st.success("Audit records updated successfully!")
        st.session_state.unreviewed_loaded = False
        st.rerun()


# ---------------------------------------------------------------------------
# Page: Import Data
# ---------------------------------------------------------------------------

def show_import():
    st.header("Import Financial Statements")
    st.write("Upload your bank statements in CSV or PDF format.")

    uploaded_files = st.file_uploader(
        "Choose a file",
        type=["csv", "pdf"],
        accept_multiple_files=True,
        help="Supports HDFC, ICICI, SBI, Kotak, Axis savings accounts and generic credit card formats.",
    )

    if uploaded_files:
        if st.button("Start AI Audit Process", type="primary"):
            files_payload = [
                ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
                for f in uploaded_files
            ]
            with st.status("Analyzing file structure and categorizing...", expanded=True) as status:
                st.write("Identifying bank format...")
                st.write("Extracting transaction list...")
                st.write("Running AI categorization engine...")
                try:
                    response = requests.post(f"{API_BASE}/upload", files=files_payload, timeout=120)
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.upload_summary = data.get("summary", {})
                        st.session_state.unreviewed_loaded = False
                        status.update(label="Import complete!", state="complete", expanded=False)
                        summary = st.session_state.upload_summary
                        st.success(
                            f"Done — {summary.get('new', 0)} new transactions added, "
                            f"{summary.get('duplicates', 0)} duplicates skipped."
                        )
                        st.balloons()
                    else:
                        detail = response.json()
                        status.update(label="Import failed", state="error")
                        st.error(f"Upload failed ({response.status_code}): {detail}")
                except requests.exceptions.ConnectionError:
                    status.update(label="Connection error", state="error")
                    st.error("Cannot reach the backend at http://localhost:8000.")
                except Exception as exc:
                    status.update(label="Error", state="error")
                    st.error(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    nav = render_sidebar()

    if nav == "📊 Dashboard":
        show_dashboard()
    elif nav == "🔍 Audit Queue":
        show_audit_queue()
    elif nav == "📥 Import Data":
        show_import()


if __name__ == "__main__":
    main()
