import pandas as pd

from inference import infer_org_chart, seniority, function_from_title, team_hint


def tiny_company():
    return pd.DataFrame([
        {"employee_id": "E1", "company_id": "C1", "name": "A CEO", "title": "Chief Executive Officer", "department": "Operations"},
        {"employee_id": "E2", "company_id": "C1", "name": "A CTO", "title": "Chief Technology Officer", "department": "Engineering"},
        {"employee_id": "E3", "company_id": "C1", "name": "A VP", "title": "VP of Engineering", "department": "Eng"},
        {"employee_id": "E4", "company_id": "C1", "name": "A Manager", "title": "Engineering Manager, Platform", "department": "Engineering"},
        {"employee_id": "E5", "company_id": "C1", "name": "A Lead", "title": "Tech Lead, Platform", "department": "Engineering"},
        {"employee_id": "E6", "company_id": "C1", "name": "A Engineer", "title": "Senior Software Engineer, Platform", "department": "Engineering"},
    ])


def test_title_features():
    assert seniority("Chief Executive Officer") == 10
    assert seniority("CTO") == 9
    assert seniority("Senior Engineering Manager, Platform") == 5
    assert function_from_title("Senior Data Eng., Data Platform") == "Data & Analytics"
    assert team_hint("Senior Software Engineer, Platform") == "platform"


def test_infers_plausible_hierarchy_without_ground_truth():
    out = infer_org_chart(tiny_company(), threshold=0.62, min_margin=0.035).set_index("employee_id")
    assert out.loc["E1", "inferred_manager_id"] == ""
    assert out.loc["E2", "inferred_manager_id"] == "E1"
    assert out.loc["E3", "inferred_manager_id"] == "E2"
    assert out.loc["E4", "inferred_manager_id"] == "E3"
    assert out.loc["E5", "inferred_manager_id"] == "E4"
    assert out.loc["E6", "inferred_manager_id"] == "E5"


def test_no_self_edges_and_required_output_fields():
    out = infer_org_chart(tiny_company())
    assert not (out["employee_id"] == out["inferred_manager_id"]).any()
    assert {"confidence", "candidate_margin", "status", "reason", "proposed_manager_id"}.issubset(out.columns)
    assert "manager_id" not in out.columns
