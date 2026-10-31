"""Conservative org-chart inference from employee profile fields only.

The module intentionally does not load or inspect ground_truth.csv. Scores are evidence
scores (0..1), not calibrated probabilities. A relationship is emitted only when both the
score and the top-candidate margin clear configurable thresholds.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

import pandas as pd

DEPARTMENTS = [
    "Engineering", "Data & Analytics", "Security", "Product Management", "Sales",
    "Marketing", "Finance", "People & HR", "Operations", "Customer Success",
]

DEPT_ALIASES = {
    "Engineering": ["engineering", "eng", "technology", "software eng", "engineering & technology", "tech"],
    "Data & Analytics": ["data & analytics", "data", "analytics", "bi / data", "data eng", "business intelligence", "data science"],
    "Security": ["security", "infosec", "cybersecurity", "information security", "it security", "soc", "appsec"],
    "Product Management": ["product management", "product", "product & design", "pm", "user experience", "ux"],
    "Sales": ["sales", "revenue", "business development", "commercial", "account executive"],
    "Marketing": ["marketing", "growth", "marketing & comms", "demand generation", "content", "seo"],
    "Finance": ["finance", "finance & accounting", "fp&a", "accounting", "financial", "payroll"],
    "People & HR": ["people & hr", "human resources", "hr", "people", "talent", "recruiter", "compensation"],
    "Operations": ["operations", "ops", "business operations", "bizops", "supply chain", "fulfillment"],
    "Customer Success": ["customer success", "client services", "customer experience", "support", "onboarding", "implementation"],
}

SPONSOR_FOR_FUNCTION = {
    "Engineering": "CTO",
    "Data & Analytics": "CTO",
    "Security": "CTO",
    "Product Management": "CPO",
    "Sales": "CRO",
    "Marketing": "CRO",
    "Finance": "CFO",
    "People & HR": "CHRO",
    "Operations": "COO",
    "Customer Success": "COO",
}

TEAM_HINTS = sorted([
    "developer experience", "data platform", "demand generation", "technical support", "strategic accounts",
    "product security", "cloud security", "application", "applications", "infrastructure", "quality",
    "platform", "analytics", "reporting", "governance", "data quality", "ml platform", "soc", "identity",
    "appsec", "core product", "growth", "mobile", "enterprise", "user experience", "integrations",
    "mid-market", "smb", "public sector", "outbound", "content", "brand", "lifecycle", "seo", "field marketing",
    "fp&a", "accounting", "payroll", "revenue", "procurement", "compliance", "talent acquisition", "people operations",
    "learning", "compensation", "employee experience", "hr systems", "business operations", "fulfillment",
    "process improvement", "vendor operations", "planning", "workforce", "onboarding", "retention", "enablement",
], key=len, reverse=True)

EXEC_ROLE_PATTERNS = [
    ("CEO", [r"\bceo\b", r"chief executive officer", r"president\s*(?:and|&)\s*ceo"]),
    ("CTO", [r"\bcto\b", r"chief technology officer"]),
    ("CFO", [r"\bcfo\b", r"chief financial officer"]),
    ("COO", [r"\bcoo\b", r"chief operating officer", r"chief operations officer"]),
    ("CRO", [r"\bcro\b", r"chief revenue officer", r"chief commercial officer"]),
    ("CHRO", [r"\bchro\b", r"chief people officer", r"chief human resources officer"]),
    ("CPO", [r"\bcpo\b", r"chief product officer", r"chief product and strategy officer", r"chief product & strategy officer"]),
]


def _clean(value) -> str:
    if value is None or pd.isna(value):
        return ""
    value = str(value).lower().strip()
    value = value.replace("&", " and ").replace("/", " ")
    value = re.sub(r"[()\[\],.;:_-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def executive_role(title: str) -> str | None:
    t = _clean(title)
    for role, patterns in EXEC_ROLE_PATTERNS:
        if any(re.search(pattern, t) for pattern in patterns):
            return role
    # Less common chief titles can still be classified by their function.
    if "chief" in t and "officer" in t:
        if any(x in t for x in ["people", "human resources", "talent"]):
            return "CHRO"
        if any(x in t for x in ["product", "strategy"]):
            return "CPO"
        if any(x in t for x in ["revenue", "commercial", "sales"]):
            return "CRO"
    return None


def function_from_title(title: str) -> str | None:
    t = _clean(title)
    role = executive_role(title)
    if role:
        return {
            "CEO": None, "CTO": "Engineering", "CFO": "Finance", "COO": "Operations",
            "CRO": "Sales", "CHRO": "People & HR", "CPO": "Product Management",
        }[role]

    # Specific phrases first to reduce overlap between adjacent functions.
    rules = [
        ("Data & Analytics", ["data", "analytics", "business intelligence", "bi developer", "data science", "reporting", "ml platform"]),
        ("Security", ["security", "infosec", "cybersecurity", "soc analyst", "iam analyst", "appsec", "identity"]),
        ("Customer Success", ["customer success", "customer experience", "client services", "customer enablement", "technical support", "implementation consultant", "support specialist", "onboarding", "retention"]),
        ("Marketing", ["marketing", "content marketer", "demand generation", "seo specialist", "brand designer", "lifecycle", "field marketing"]),
        ("Finance", ["finance", "financial", "accountant", "fp&a", "accounts payable", "payroll", "revenue accountant", "procurement"]),
        ("People & HR", ["human resources", "people", "recruiter", "talent acquisition", "hr business partner", "learning specialist", "compensation", "hr systems"]),
        ("Product Management", ["product", "ux researcher", "ux designer", "user experience", "product designer", "business analyst"]),
        ("Sales", ["sales", "account executive", "business development", "solutions consultant", "revenue operations", "commercial", "strategic accounts", "mid market", "smb"]),
        ("Operations", ["operations", "business operations", "supply chain", "process analyst", "vendor", "fulfillment", "workforce"]),
        ("Engineering", ["engineering", "engineer", "eng ", "software", "devops", "cloud", "sre", "developer experience", "infrastructure", "platform", "quality engineer", "application engineer"]),
    ]
    for department, keywords in rules:
        if any(keyword in t for keyword in keywords):
            return department
    if re.search(r"\beng\b", t):
        return "Engineering"
    return None


def normalize_department(value: str) -> str | None:
    t = _clean(value)
    if not t:
        return None
    # Exact aliases first; only then use contained phrases.
    for department, aliases in DEPT_ALIASES.items():
        if t in {_clean(alias) for alias in aliases}:
            return department
    for department, aliases in DEPT_ALIASES.items():
        if any(_clean(alias) and _clean(alias) in t for alias in aliases):
            return department
    return None


def seniority(title: str) -> int | None:
    """Coarse seniority: CEO=10, C-suite=9, VP=7, Director=6, manager=4, IC=1-2."""
    t = _clean(title)
    if not t:
        return None
    role = executive_role(title)
    if role == "CEO":
        return 10
    if role:
        return 9
    if re.search(r"\b(svp|evp|senior vice president|executive vice president)\b", t):
        return 8
    if re.search(r"\b(vp|vice president|head of|global head)\b", t):
        return 7
    if re.search(r"\bdirector\b", t):
        return 6
    if re.search(r"\b(senior|sr)\b.*\bmanager\b", t) or re.search(r"\bgeneral manager\b", t):
        return 5
    # "Product Manager" and similar role titles are ambiguous in the real world; here this is
    # treated as manager-level evidence, but the confidence gate is designed to abstain if weak.
    if re.search(r"\bmanager\b", t):
        return 4
    if re.search(r"\b(team lead|tech lead|lead|principal lead)\b", t):
        return 3
    if re.search(r"\b(principal|staff|senior|sr|lead)\b", t):
        return 2
    return 1


def team_hint(title: str) -> str | None:
    t = _clean(title)
    if not t:
        return None
    # A team tag is deliberately extracted only from the title suffix, never from hidden labels.
    if "," not in str(title):
        return None
    suffix = _clean(str(title).split(",")[-1])
    for hint in TEAM_HINTS:
        if _clean(hint) == suffix or _clean(hint) in suffix:
            return _clean(hint)
    return None


def _role_group(title: str, level: int | None) -> str:
    role = executive_role(title)
    if role:
        return role
    if level in (6, 7, 8):
        return "FUNCTION_HEAD"
    if level in (4, 5):
        return "MANAGER"
    if level == 3:
        return "LEAD"
    if level in (1, 2):
        return "IC"
    return "UNKNOWN"


def _person_features(row: dict) -> dict:
    title = row.get("title", "")
    level = seniority(title)
    title_function = function_from_title(title)
    dept_function = normalize_department(row.get("department", ""))
    # The CEO is a root, not a functional employee, even if a raw department was populated.
    # Titles contain useful evidence, but department can rescue generic titles.
    function = None if executive_role(title) == "CEO" else (title_function or dept_function)
    return {
        **row,
        "_level": level,
        "_exec_role": executive_role(title),
        "_role_group": _role_group(title, level),
        "_title_function": title_function,
        "_dept_function": dept_function,
        "_function": function,
        "_team": team_hint(title),
        "_title_clean": _clean(title),
    }


def _score_pair(person: dict, candidate: dict) -> float:
    """Evidence score for candidate -> person; deliberately not presented as a probability."""
    person_level, candidate_level = person["_level"], candidate["_level"]
    if person_level is None or candidate_level is None or candidate_level <= person_level:
        return 0.0
    if not person["_function"] or not candidate["_function"]:
        return 0.0
    if person["_function"] != candidate["_function"]:
        return 0.0

    person_team, candidate_team = person["_team"], candidate["_team"]
    if person_team and candidate_team and person_team != candidate_team:
        return 0.0  # cross-team lateral reporting is not inferred from title alone

    score = 0.22
    score += 0.15  # same inferred function
    if person["_dept_function"] and candidate["_dept_function"] and person["_dept_function"] == candidate["_dept_function"]:
        score += 0.12
    if person_team and candidate_team and person_team == candidate_team:
        score += 0.28
    if candidate["_role_group"] in {"MANAGER", "LEAD", "FUNCTION_HEAD"}:
        score += 0.05
    gap = candidate_level - person_level
    score += {1: 0.13, 2: 0.11, 3: 0.075, 4: 0.04}.get(gap, 0.015)

    # Prefer the most plausible immediate layer rather than skipping an available supervisor.
    if person["_role_group"] == "MANAGER" and candidate["_role_group"] == "FUNCTION_HEAD":
        # A function head is the expected next management layer for a team manager.
        # This gets a strong boost only when same-function and seniority constraints already pass.
        score += 0.32
    if person["_role_group"] == "LEAD" and candidate["_role_group"] == "MANAGER":
        score += 0.06
    if person["_role_group"] == "IC" and candidate["_role_group"] == "LEAD" and person_team and person_team == candidate_team:
        score += 0.035
    if person["_role_group"] == "IC" and candidate["_role_group"] == "MANAGER" and person_team and person_team == candidate_team:
        score += 0.015
    return min(0.995, score)


def infer_org_chart(employees: pd.DataFrame, threshold: float = 0.62, min_margin: float = 0.035) -> pd.DataFrame:
    """Infer a manager for each row where evidence is strong enough.

    Returns one row per employee with inferred_manager_id/name, confidence, runner-up margin,
    status, and a human-readable reason. No ground-truth file is read by this function.
    """
    required = {"employee_id", "company_id", "name", "title", "department"}
    missing = required - set(employees.columns)
    if missing:
        raise ValueError(f"employees is missing required columns: {sorted(missing)}")

    raw_records = employees.fillna("").to_dict(orient="records")
    by_company: dict[str, list[dict]] = defaultdict(list)
    for row in raw_records:
        by_company[str(row["company_id"])].append(_person_features(row))

    results = []
    for company_id, people in by_company.items():
        by_id = {str(p["employee_id"]): p for p in people}
        ceos = [p for p in people if p["_exec_role"] == "CEO"]
        executives = {p["_exec_role"]: p for p in people if p["_exec_role"] and p["_exec_role"] != "CEO"}

        for person in people:
            emp_id = str(person["employee_id"])
            role = person["_exec_role"]
            inferred_id, confidence, margin, reason = "", 0.0, 0.0, "Insufficient title or hierarchy evidence"
            proposed_id = ""

            if role == "CEO":
                status = "root"
                reason = "Top executive; no manager inferred"
            elif role and role != "CEO":
                # C-suite reporting is usually clear from the unique CEO title.
                if len(ceos) == 1:
                    inferred_id = str(ceos[0]["employee_id"])
                    proposed_id = inferred_id
                    confidence = 0.985
                    margin = 1.0
                    reason = "Unique CEO candidate for C-suite role"
                    status = "inferred"
                else:
                    status = "unresolved"
                    reason = "No unique CEO candidate"
            elif person["_role_group"] == "FUNCTION_HEAD":
                function = person["_function"]
                sponsor_role = SPONSOR_FOR_FUNCTION.get(function or "")
                sponsor = executives.get(sponsor_role) if sponsor_role else None
                if sponsor:
                    inferred_id = str(sponsor["employee_id"])
                    proposed_id = inferred_id
                    confidence = 0.94
                    margin = 0.9
                    reason = f"Function head matched to expected {sponsor_role} sponsor"
                    status = "inferred"
                else:
                    status = "unresolved"
                    reason = "Function head found, but executive sponsor is unclear"
            elif person["_level"] is None or not person["_function"]:
                status = "unresolved"
            else:
                # Candidate pool is confined to the same company and inferred function.
                candidates = []
                for candidate in people:
                    if str(candidate["employee_id"]) == emp_id:
                        continue
                    if candidate["_exec_role"] == "CEO":
                        continue
                    # C-suite executives are only inferred as managers of function heads if explicitly mapped.
                    if candidate["_exec_role"]:
                        continue
                    if candidate["_role_group"] == "UNKNOWN":
                        continue
                    score = _score_pair(person, candidate)
                    if score > 0:
                        candidates.append((score, candidate))

                candidates.sort(key=lambda x: x[0], reverse=True)
                if not candidates:
                    status = "unresolved"
                    reason = "No plausible higher-seniority candidate in the same function"
                else:
                    best_score, best_candidate = candidates[0]
                    proposed_id = str(best_candidate["employee_id"])
                    second_score = candidates[1][0] if len(candidates) > 1 else 0.0
                    candidate_margin = best_score - second_score
                    # If multiple candidates are essentially tied, abstain instead of guessing.
                    if best_score >= threshold and candidate_margin >= min_margin:
                        inferred_id = str(best_candidate["employee_id"])
                        confidence = best_score
                        margin = candidate_margin
                        reason = _explain_pair(person, best_candidate)
                        status = "inferred"
                    else:
                        status = "unresolved"
                        reason = "Ambiguous manager candidates or evidence below threshold"
                        confidence = best_score
                        margin = candidate_margin

            manager = by_id.get(inferred_id) if inferred_id else None
            results.append({
                "employee_id": emp_id,
                "company_id": str(person["company_id"]),
                "name": person.get("name", ""),
                "title": person.get("title", ""),
                "department": person.get("department", ""),
                "inferred_function": person["_function"] or "",
                "inferred_manager_id": inferred_id,
                "inferred_manager_name": manager.get("name", "") if manager else "",
                "inferred_manager_title": manager.get("title", "") if manager else "",
                "proposed_manager_id": proposed_id,
                "confidence": round(float(confidence), 4),
                "candidate_margin": round(float(margin), 4),
                "status": status,
                "reason": reason,
            })

    return pd.DataFrame(results)


def _explain_pair(person: dict, candidate: dict) -> str:
    bits = []
    if person["_function"] and person["_function"] == candidate["_function"]:
        bits.append("same inferred function")
    if person["_dept_function"] and person["_dept_function"] == candidate["_dept_function"]:
        bits.append("department agrees")
    if person["_team"] and person["_team"] == candidate["_team"]:
        bits.append("team phrase matches in titles")
    gap = candidate["_level"] - person["_level"]
    bits.append(f"candidate is {gap} seniority level(s) above")
    return "; ".join(bits)


def add_tree_depth(inferred: pd.DataFrame) -> pd.DataFrame:
    """Add depth from each inferred root; only inferred links are traversed."""
    df = inferred.copy()
    manager_map = dict(zip(df["employee_id"].astype(str), df["inferred_manager_id"].fillna("").astype(str)))
    memo = {}

    def depth(emp_id, seen=None):
        if emp_id in memo:
            return memo[emp_id]
        seen = set() if seen is None else seen
        if emp_id in seen:
            return 0  # safety for malformed external inputs
        seen.add(emp_id)
        manager_id = manager_map.get(emp_id, "")
        if not manager_id or manager_id not in manager_map:
            memo[emp_id] = 0
        else:
            memo[emp_id] = depth(manager_id, seen) + 1
        return memo[emp_id]

    df["inferred_depth"] = [depth(str(emp_id)) for emp_id in df["employee_id"]]
    return df
