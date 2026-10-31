from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"

st.set_page_config(page_title="Org Chart Inference", page_icon="🌳", layout="wide")


@st.cache_data(show_spinner="Loading synthetic benchmark…")
def load_data():
    companies = pd.read_csv(DATA_DIR / "companies.csv", keep_default_na=False)
    employees = pd.read_csv(DATA_DIR / "employees.csv", keep_default_na=False)
    inferred = pd.read_csv(DATA_DIR / "inferred_edges.csv", keep_default_na=False)
    return companies, employees, inferred


def make_effective_edges(inferred: pd.DataFrame, threshold: float, min_margin: float) -> pd.DataFrame:
    """Apply user-selected confidence and ambiguity cutoffs to the stored top proposals."""
    out = inferred.copy()
    proposal = out["proposed_manager_id"].fillna("").astype(str)
    score = pd.to_numeric(out["confidence"], errors="coerce").fillna(0)
    margin = pd.to_numeric(out["candidate_margin"], errors="coerce").fillna(0)
    keep = proposal.ne("") & score.ge(threshold) & margin.ge(min_margin)
    out["effective_manager_id"] = proposal.where(keep, "")
    out["effective_status"] = out["status"].astype(str)
    out.loc[keep, "effective_status"] = "inferred"
    out.loc[~keep & out["status"].ne("root"), "effective_status"] = "unresolved"
    return out


def calculate_depths(manager_map: dict[str, str]) -> dict[str, int]:
    depths: dict[str, int] = {}

    def depth(node: str, seen=None) -> int:
        if node in depths:
            return depths[node]
        seen = set() if seen is None else set(seen)
        if node in seen:
            return 0
        seen.add(node)
        parent = manager_map.get(node, "")
        if not parent or parent not in manager_map:
            depths[node] = 0
        else:
            depths[node] = depth(parent, seen) + 1
        return depths[node]

    for node in manager_map:
        depth(node)
    return depths


def connected_from_root(company_df: pd.DataFrame, manager_map: dict[str, str]) -> tuple[str | None, set[str], dict[str, int]]:
    roots = company_df[company_df["status"].eq("root")]["employee_id"].astype(str).tolist()
    if not roots:
        # Fall back only when exactly one employee has an unambiguous CEO-like title.
        title_candidates = company_df[company_df["title"].astype(str).str.contains(r"\bCEO\b|Chief Executive Officer", case=False, regex=True)]["employee_id"].astype(str).tolist()
        roots = title_candidates if len(title_candidates) == 1 else []
    if len(roots) != 1:
        return None, set(), {}
    root = roots[0]
    children: dict[str, list[str]] = defaultdict(list)
    for employee_id, manager_id in manager_map.items():
        if manager_id and manager_id in manager_map:
            children[manager_id].append(employee_id)
    depths = {root: 0}
    queue = deque([root])
    while queue:
        parent = queue.popleft()
        for child in children.get(parent, []):
            if child not in depths:
                depths[child] = depths[parent] + 1
                queue.append(child)
    return root, set(depths), depths


def tree_figure(nodes: pd.DataFrame, manager_map: dict[str, str], confidence_map: dict[str, float], reason_map: dict[str, str]):
    if nodes.empty:
        return None
    node_ids = set(nodes["employee_id"].astype(str))
    children: dict[str, list[str]] = defaultdict(list)
    roots = []
    for row in nodes.to_dict(orient="records"):
        emp_id = str(row["employee_id"])
        parent = manager_map.get(emp_id, "")
        if parent and parent in node_ids:
            children[parent].append(emp_id)
        else:
            roots.append(emp_id)

    row_by_id = {str(row["employee_id"]): row for row in nodes.to_dict(orient="records")}
    for parent in children:
        children[parent].sort(key=lambda i: (str(row_by_id[i].get("title", "")), str(row_by_id[i].get("name", ""))))
    roots.sort(key=lambda i: (str(row_by_id[i].get("title", "")), str(row_by_id[i].get("name", ""))))

    positions: dict[str, tuple[float, float]] = {}
    cursor = [0.0]

    def place(node: str, d: int):
        kids = children.get(node, [])
        if not kids:
            x = cursor[0]
            cursor[0] += 1.0
        else:
            child_x = [place(child, d + 1) for child in kids]
            x = sum(child_x) / len(child_x)
        positions[node] = (x, -float(d))
        return x

    for root in roots:
        place(root, 0)
        cursor[0] += 0.7

    edge_x, edge_y = [], []
    for child, parent in manager_map.items():
        if child in positions and parent in positions:
            x0, y0 = positions[parent]
            x1, y1 = positions[child]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    node_x, node_y, labels, hover, colors, sizes = [], [], [], [], [], []
    for emp_id, row in row_by_id.items():
        x, y = positions[emp_id]
        node_x.append(x); node_y.append(y)
        name = str(row.get("name", "Unknown"))
        title = str(row.get("title", "Title missing")) or "Title missing"
        labels.append(name)
        conf = confidence_map.get(emp_id, 0.0)
        reason = reason_map.get(emp_id, "")
        hover.append(
            f"<b>{name}</b><br>{title}<br>Department: {row.get('inferred_function', '')}"
            f"<br>Confidence score: {conf:.3f}<br>Evidence: {reason}<extra></extra>"
        )
        colors.append("#176B87" if manager_map.get(emp_id) else "#8A94A6")
        sizes.append(14 if manager_map.get(emp_id) else 12)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(width=1, color="#A8B3C2"), hoverinfo="skip", name="Inferred reporting line"))
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text", text=labels, textposition="bottom center",
        textfont=dict(size=9), marker=dict(size=sizes, color=colors, line=dict(width=0.6, color="white")),
        hovertext=hover, hovertemplate="%{hovertext}", name="Employees",
    ))
    fig.update_layout(
        height=max(580, min(1000, 420 + len(nodes) * 3)),
        margin=dict(l=15, r=15, t=35, b=40),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
        title=dict(text="Inferred reporting lines", x=0.02, y=0.98),
    )
    return fig


try:
    companies, employees, all_inferred = load_data()
except FileNotFoundError as exc:
    st.error(f"Required data file is missing: {exc}. Run `python build.py` first.")
    st.stop()

st.title("🌳 Org Chart Inference")
st.caption("Synthetic benchmark · conservative manager inference · confidence scores are evidence scores, not calibrated probabilities")

with st.sidebar:
    st.header("Explore a company")
    display_options = {
        f"{row.company_name} · {row.company_id}": row.company_id
        for row in companies.sort_values("company_name").itertuples(index=False)
    }
    selected_label = st.selectbox("Company", list(display_options.keys()), index=0)
    company_id = display_options[selected_label]
    threshold = st.slider("Minimum confidence score", min_value=0.50, max_value=0.99, value=0.93, step=0.01,
                          help="An edge is shown only when its score meets this threshold.")
    min_margin = st.slider("Minimum lead over next candidate", min_value=0.00, max_value=0.20, value=0.035, step=0.005,
                           help="Higher margins suppress cases where two possible managers look similarly plausible.")

company = companies[companies["company_id"].eq(company_id)].iloc[0]
company_employees = employees[employees["company_id"].eq(company_id)].copy()
company_inferred_raw = all_inferred[all_inferred["company_id"].eq(company_id)].copy()
company_inferred = make_effective_edges(company_inferred_raw, threshold, min_margin)

id_to_name = dict(zip(company_employees["employee_id"].astype(str), company_employees["name"].astype(str)))
id_to_title = dict(zip(company_employees["employee_id"].astype(str), company_employees["title"].astype(str)))
manager_map = dict(zip(company_inferred["employee_id"].astype(str), company_inferred["effective_manager_id"].astype(str)))
confidence_map = dict(zip(company_inferred["employee_id"].astype(str), pd.to_numeric(company_inferred["confidence"], errors="coerce").fillna(0).astype(float)))
reason_map = dict(zip(company_inferred["employee_id"].astype(str), company_inferred["reason"].astype(str)))
company_inferred["effective_manager_name"] = company_inferred["effective_manager_id"].map(id_to_name).fillna("")
company_inferred["effective_manager_title"] = company_inferred["effective_manager_id"].map(id_to_title).fillna("")

root_id, reachable, depths = connected_from_root(company_inferred, manager_map)
connected_count = len(reachable)
predicted_count = int(company_inferred["effective_manager_id"].ne("").sum())
unresolved_count = int((company_inferred["effective_status"].eq("unresolved")).sum())
root_count = int(company_inferred["effective_status"].eq("root").sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Employees", f"{len(company_employees):,}")
m2.metric("Inferred reporting lines", f"{predicted_count:,}")
m3.metric("Connected to CEO", f"{connected_count:,}" if root_id else "CEO unresolved")
m4.metric("Unresolved managers", f"{unresolved_count:,}")
st.write(f"**Industry:** {company['industry']}  ·  **Headquarters region:** {company['hq_region']}  ·  **Company ID:** `{company_id}`")

if root_id is None:
    st.warning("A unique CEO/root could not be identified from the available titles. The chart is partial; review unresolved titles before treating the hierarchy as complete.")

# The function filter keeps the hierarchy readable while showing its path to the executive layer.
functions = sorted([f for f in company_inferred["inferred_function"].dropna().astype(str).unique() if f])
function_options = ["Company overview"] + functions
selected_function = st.selectbox("View", function_options, index=0)

if root_id:
    if selected_function == "Company overview":
        depth_limit = st.slider("Maximum displayed depth", min_value=1, max_value=6, value=3, step=1,
                                help="CEO is depth 0; each inferred reporting line adds one level.")
        target_ids = {emp_id for emp_id, depth in depths.items() if depth <= depth_limit}
        chart_note = f"Showing the CEO-connected hierarchy through depth {depth_limit}."
    else:
        function_ids = set(company_inferred.loc[company_inferred["inferred_function"].eq(selected_function), "employee_id"].astype(str))
        connected_function_ids = function_ids & reachable
        target_ids = set(connected_function_ids)
        # Add every inferred ancestor so the chart preserves the context for this function.
        for emp_id in list(connected_function_ids):
            current = manager_map.get(emp_id, "")
            seen = set()
            while current and current in manager_map and current not in seen:
                target_ids.add(current)
                seen.add(current)
                current = manager_map.get(current, "")
        chart_note = f"Showing {len(connected_function_ids):,} of {len(function_ids):,} employees assigned to {selected_function} that connect to the CEO through inferred edges."

    chart_nodes = company_inferred[company_inferred["employee_id"].astype(str).isin(target_ids)].copy()
    st.caption(chart_note)
    if chart_nodes.empty:
        st.info("No connected edges meet the current confidence and ambiguity thresholds. Lower the threshold to explore more proposed lines, or review unresolved employees below.")
    else:
        fig = tree_figure(chart_nodes, manager_map, confidence_map, reason_map)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No chart root available. Use the reporting-line and unresolved tabs to inspect the available evidence.")

lines_tab, unresolved_tab, data_tab = st.tabs(["Reporting lines", "Unresolved / abstained", "Company data"])
with lines_tab:
    accepted = company_inferred[company_inferred["effective_manager_id"].ne("")].copy()
    accepted = accepted.sort_values(["confidence", "name"], ascending=[False, True])
    view_cols = ["name", "title", "inferred_function", "effective_manager_name", "effective_manager_title", "confidence", "candidate_margin", "reason"]
    if accepted.empty:
        st.info("No reporting lines pass the current thresholds.")
    else:
        st.dataframe(accepted[view_cols].rename(columns={
            "name": "Employee", "title": "Job title", "inferred_function": "Inferred function",
            "effective_manager_name": "Inferred manager", "effective_manager_title": "Manager title",
            "confidence": "Confidence score", "candidate_margin": "Candidate margin", "reason": "Evidence",
        }), use_container_width=True, hide_index=True)
        csv_bytes = accepted[view_cols].to_csv(index=False).encode("utf-8")
        st.download_button("Download inferred reporting lines (CSV)", csv_bytes, file_name=f"{company_id}_inferred_reporting_lines.csv", mime="text/csv")
with unresolved_tab:
    unresolved = company_inferred[company_inferred["effective_status"].eq("unresolved")].copy()
    st.write("These employees are intentionally left without a manager because the candidate score, margin, or title evidence is insufficient. An empty edge is preferable to an unsupported guess.")
    st.metric("Unresolved employees", f"{len(unresolved):,}")
    if not unresolved.empty:
        unresolved = unresolved.sort_values(["confidence", "name"], ascending=[False, True])
        st.dataframe(unresolved[["name", "title", "department", "inferred_function", "confidence", "candidate_margin", "reason"]].rename(columns={
            "name": "Employee", "title": "Job title", "department": "Raw department", "inferred_function": "Inferred function",
            "confidence": "Best candidate score", "candidate_margin": "Candidate margin", "reason": "Why no edge was emitted",
        }), use_container_width=True, hide_index=True)
with data_tab:
    st.write("The inference input is a flat employee table. The manager ground truth is stored separately and is used only by the evaluation script, not by this app.")
    st.dataframe(company_employees, use_container_width=True, hide_index=True)

st.divider()
st.caption("Method note: inference combines title seniority, inferred function, department aliases, title-embedded team hints, candidate uniqueness, and an abstention threshold. Synthetic ground truth enables repeatable evaluation; real-world org charts require validation against a labelled sample.")
