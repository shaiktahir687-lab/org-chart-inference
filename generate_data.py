"""Generate a reproducible synthetic org-chart benchmark.

The employee table deliberately excludes manager_id. Ground-truth reporting lines are
written separately for evaluation only, which prevents the inference code from leaking labels.
"""
from __future__ import annotations

import argparse
import csv
import random
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED = 20261029

DEPARTMENTS = {
    "Engineering": {
        "sponsor": "CTO",
        "head_names": ["Engineering", "Software Engineering", "Technology"],
        "manager_label": "Engineering Manager",
        "lead_label": "Tech Lead",
        "ic_titles": ["Software Engineer", "Backend Engineer", "QA Engineer", "SRE", "DevOps Engineer", "Cloud Engineer", "Application Engineer"],
        "teams": ["Platform", "Applications", "Infrastructure", "Quality", "Developer Experience", "Cloud"],
    },
    "Data & Analytics": {
        "sponsor": "CTO",
        "head_names": ["Data", "Data & Analytics", "Analytics"],
        "manager_label": "Data Engineering Manager",
        "lead_label": "Data Lead",
        "ic_titles": ["Data Engineer", "Analytics Engineer", "Data Analyst", "BI Developer", "Data Quality Analyst", "Data Scientist"],
        "teams": ["Data Platform", "Analytics", "Reporting", "Governance", "Data Quality", "ML Platform"],
    },
    "Security": {
        "sponsor": "CTO",
        "head_names": ["Security", "Information Security", "Cybersecurity"],
        "manager_label": "Security Manager",
        "lead_label": "Security Lead",
        "ic_titles": ["Security Analyst", "Security Engineer", "SOC Analyst", "IAM Analyst", "Application Security Engineer", "GRC Analyst"],
        "teams": ["Product Security", "Cloud Security", "SOC", "Identity", "Governance", "AppSec"],
    },
    "Product Management": {
        "sponsor": "CPO",
        "head_names": ["Product", "Product Management"],
        "manager_label": "Product Manager",
        "lead_label": "Product Lead",
        "ic_titles": ["Product Analyst", "Product Designer", "UX Researcher", "Product Operations Analyst", "Business Analyst", "UX Designer"],
        "teams": ["Core Product", "Growth", "Mobile", "Enterprise", "User Experience", "Integrations"],
    },
    "Sales": {
        "sponsor": "CRO",
        "head_names": ["Sales", "Revenue", "Business Development"],
        "manager_label": "Sales Manager",
        "lead_label": "Sales Team Lead",
        "ic_titles": ["Account Executive", "Sales Development Representative", "Sales Engineer", "Business Development Representative", "Revenue Operations Analyst", "Solutions Consultant"],
        "teams": ["Enterprise", "Mid-Market", "SMB", "Public Sector", "Strategic Accounts", "Outbound"],
    },
    "Marketing": {
        "sponsor": "CRO",
        "head_names": ["Marketing", "Growth Marketing", "Marketing & Communications"],
        "manager_label": "Marketing Manager",
        "lead_label": "Marketing Lead",
        "ic_titles": ["Marketing Specialist", "Content Marketer", "Demand Generation Specialist", "Marketing Analyst", "SEO Specialist", "Brand Designer"],
        "teams": ["Demand Generation", "Content", "Brand", "Lifecycle", "SEO", "Field Marketing"],
    },
    "Finance": {
        "sponsor": "CFO",
        "head_names": ["Finance", "Financial Planning & Analysis", "Finance & Accounting"],
        "manager_label": "Finance Manager",
        "lead_label": "Finance Lead",
        "ic_titles": ["Financial Analyst", "Accountant", "FP&A Analyst", "Accounts Payable Specialist", "Payroll Analyst", "Revenue Accountant"],
        "teams": ["FP&A", "Accounting", "Payroll", "Revenue", "Procurement", "Compliance"],
    },
    "People & HR": {
        "sponsor": "CHRO",
        "head_names": ["People", "Human Resources", "People Operations"],
        "manager_label": "People Manager",
        "lead_label": "People Lead",
        "ic_titles": ["Recruiter", "HR Business Partner", "People Operations Specialist", "People Analyst", "Learning Specialist", "Talent Acquisition Partner"],
        "teams": ["Talent Acquisition", "People Operations", "Learning", "Compensation", "Employee Experience", "HR Systems"],
    },
    "Operations": {
        "sponsor": "COO",
        "head_names": ["Operations", "Business Operations", "Business Services"],
        "manager_label": "Operations Manager",
        "lead_label": "Operations Lead",
        "ic_titles": ["Operations Analyst", "Business Operations Specialist", "Process Analyst", "Supply Chain Analyst", "Vendor Specialist", "Workforce Analyst"],
        "teams": ["Business Operations", "Fulfillment", "Process Improvement", "Vendor Operations", "Planning", "Workforce"],
    },
    "Customer Success": {
        "sponsor": "COO",
        "head_names": ["Customer Success", "Client Services", "Customer Experience"],
        "manager_label": "Customer Success Manager",
        "lead_label": "Customer Success Lead",
        "ic_titles": ["Customer Success Associate", "Implementation Consultant", "Support Specialist", "Customer Enablement Specialist", "Technical Support Engineer", "Client Services Analyst"],
        "teams": ["Enterprise", "Onboarding", "Technical Support", "Retention", "Enablement", "SMB"],
    },
}

DEPT_ALIASES = {
    "Engineering": ["Engineering", "Eng", "Technology", "Software Eng.", "Engineering & Technology", ""],
    "Data & Analytics": ["Data & Analytics", "Data", "Analytics", "BI / Data", "Data Eng.", ""],
    "Security": ["Security", "InfoSec", "Cybersecurity", "Information Security", "IT Security", ""],
    "Product Management": ["Product Management", "Product", "Product & Design", "PM", ""],
    "Sales": ["Sales", "Revenue", "Business Development", "Commercial", ""],
    "Marketing": ["Marketing", "Growth", "Marketing & Comms", "Demand Generation", ""],
    "Finance": ["Finance", "Finance & Accounting", "FP&A", "Accounting", ""],
    "People & HR": ["People & HR", "HR", "Human Resources", "People", "Talent", ""],
    "Operations": ["Operations", "Ops", "Business Operations", "BizOps", ""],
    "Customer Success": ["Customer Success", "CS", "Client Services", "Customer Experience", "Support", ""],
}

INDUSTRIES = [
    "Software & SaaS", "Financial Services", "Healthcare", "Manufacturing", "Retail & Commerce",
    "Logistics", "Energy", "Media & Entertainment", "Professional Services", "Telecommunications",
    "Education Technology", "Travel & Hospitality", "Insurance", "Consumer Goods",
]
REGIONS = ["United States", "Canada", "United Kingdom", "India", "Germany", "Australia", "Singapore"]
LOCATIONS = ["New York", "San Francisco", "Austin", "Chicago", "Boston", "Seattle", "Toronto", "London", "Bengaluru", "Berlin", "Sydney", "Remote"]
ADJECTIVES = ["Apex", "Bright", "Cedar", "Cobalt", "Copper", "Crescent", "Crown", "Delta", "Evergreen", "Falcon", "Firstlight", "Granite", "Harbor", "Juniper", "Keystone", "Lighthouse", "Maple", "Meridian", "Northstar", "Oak", "Openfield", "Pioneer", "Redwood", "Ridge", "Silverline", "Summit", "Terra", "TrueNorth", "Vertex", "Westbridge", "Willow", "Bluepeak", "Cloudline", "Clearwater", "Daybreak", "Fieldstone", "Goldleaf", "Ironwood", "Lakeview", "Moonstone", "Newcrest", "Orchard", "Parkside", "Quantum", "Riverbend", "Skyward", "Stonegate", "Sunfield", "Tandem", "Union"]
NOUNS = ["Analytics", "Atlas", "Beacon", "Bridge", "Collective", "Compass", "Dynamics", "Forge", "Frontier", "Galaxy", "Grid", "Harbor", "Horizon", "Labs", "Logic", "Matrix", "Network", "Nexus", "Orbit", "Partners", "Pathway", "Peak", "Pioneer", "Systems", "Works", "Ventures", "Vista", "Wave", "Works", "Sphere", "Signal", "Foundry", "Cloud", "Insights", "Digital", "Solutions", "Studio", "Industries", "Group", "Technologies"]
SUFFIXES = ["", " Labs", " Systems", " Technologies", " Group", " Solutions", " Digital", " Works"]
FIRST_NAMES = ["Alex", "Amara", "Ari", "Avery", "Blake", "Cameron", "Casey", "Charlie", "Dakota", "Dev", "Drew", "Elliot", "Emerson", "Finley", "Harper", "Jordan", "Kai", "Leah", "Logan", "Maya", "Morgan", "Nico", "Noah", "Parker", "Quinn", "Riley", "Robin", "Sage", "Sam", "Skyler", "Taylor", "Terry", "Uma", "Val", "Winter", "Zion", "Priya", "Arjun", "Nina", "Omar", "Sana", "Ishan", "Meera", "Rohan", "Aisha", "Kabir", "Ira", "Neel"]
LAST_NAMES = ["Adams", "Baker", "Bennett", "Brooks", "Carter", "Chen", "Clark", "Coleman", "Davis", "Diaz", "Edwards", "Foster", "Garcia", "Gupta", "Hall", "Harris", "Hayes", "Hughes", "Iyer", "Jackson", "James", "Jenkins", "Kapoor", "Kim", "Lewis", "Lopez", "Martin", "Miller", "Mitchell", "Morgan", "Murphy", "Nelson", "Patel", "Perry", "Reed", "Roberts", "Ross", "Shah", "Singh", "Stewart", "Taylor", "Thomas", "Turner", "Walker", "White", "Wong", "Young", "Zhang"]

EXEC_TITLES = {
    "CEO": ["Chief Executive Officer", "CEO", "Chief Executive Officer (CEO)"],
    "CTO": ["Chief Technology Officer", "CTO", "Chief Technology Officer (CTO)"],
    "CFO": ["Chief Financial Officer", "CFO", "Chief Financial Officer (CFO)"],
    "COO": ["Chief Operating Officer", "COO", "Chief Operating Officer (COO)"],
    "CRO": ["Chief Revenue Officer", "CRO", "Chief Commercial Officer"],
    "CHRO": ["Chief People Officer", "Chief Human Resources Officer", "CHRO"],
    "CPO": ["Chief Product Officer", "CPO", "Chief Product & Strategy Officer"],
}

TEAM_NAMES = sorted({team.lower() for d in DEPARTMENTS.values() for team in d["teams"]}, key=len, reverse=True)


def _messy_title(title: str, rng: random.Random) -> str:
    """Apply small, realistic title variations without changing the role's intended level."""
    replacements = [
        ("Senior ", "Sr. "),
        ("Engineer", "Eng."),
        ("Representative", "Rep."),
        ("Specialist", "Spec."),
        ("Analyst", "Analyst"),
        ("Vice President", "VP"),
        ("Director of ", "Director, "),
    ]
    if rng.random() < 0.19:
        old, new = rng.choice(replacements)
        if old == "Engineer":
            title = re.sub(r"\bEngineer\b", "Eng.", title, count=1)
        elif old in title:
            title = title.replace(old, new, 1)
    if rng.random() < 0.05:
        title = title.replace(" & ", " and ")
    if rng.random() < 0.06:
        title = title.strip() + " "
    return title


def _head_title(dept: str, dept_size: int, rng: random.Random) -> str:
    names = DEPARTMENTS[dept]["head_names"]
    label = rng.choice(names)
    if dept_size >= 15 and rng.random() < 0.65:
        form = rng.choice(["VP of {}", "Vice President of {}", "VP, {}", "Head of {}"])
    elif rng.random() < 0.55:
        form = rng.choice(["Director of {}", "Director, {}", "Head of {}"])
    else:
        form = rng.choice(["VP of {}", "VP, {}", "Head of {}"])
    return form.format(label)


def _add_person(rows, truth, company, next_num, title, department, manager_id, rng, team=None):
    # Employee IDs are pre-shuffled per company so their sequence cannot reveal hierarchy.
    employee_id = company["_employee_ids"][next_num - 1]
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    name = f"{first} {last}"
    # Occasional middle initial and inconsistent casing add harmless data noise.
    if rng.random() < 0.08:
        name = f"{first} {rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}. {last}"
    clean_title = title
    raw_title = _messy_title(title, rng)
    if rng.random() < 0.022:
        raw_title = ""  # missing title is intentionally hard to infer
    raw_dept = rng.choice(DEPT_ALIASES[department])
    if rng.random() < 0.045:
        raw_dept = ""  # missing department
    elif rng.random() < 0.018:
        # A small number of genuinely noisy department assignments.
        raw_dept = rng.choice([a for key, vals in DEPT_ALIASES.items() if key != department for a in vals if a])
    start = date(2015, 1, 1) + timedelta(days=rng.randint(0, 4300))
    domain = company["domain"]
    employee = {
        "employee_id": employee_id,
        "company_id": company["company_id"],
        "company_name": company["company_name"],
        "name": name,
        "title": raw_title,
        "department": raw_dept,
        "location": "" if rng.random() < 0.035 else rng.choice(LOCATIONS),
        "start_date": "" if rng.random() < 0.035 else start.isoformat(),
        "email_domain": "" if rng.random() < 0.025 else domain,
    }
    rows.append(employee)
    truth.append({"employee_id": employee_id, "company_id": company["company_id"], "manager_id": manager_id or ""})
    return employee_id


def _allocate(total: int, n: int, min_each: int, rng: random.Random) -> list[int]:
    """Allocate a total to n buckets with a lower bound for every bucket."""
    sizes = [min_each] * n
    for _ in range(total - min_each * n):
        # Favor slightly larger teams without making any one team dominant.
        idx = rng.randrange(n)
        sizes[idx] += 1
    return sizes


def generate(seed: int = SEED, n_companies: int = 500, min_employees: int = 100, max_employees: int = 180, out_dir: str | Path = "data"):
    if n_companies < 500:
        raise ValueError("The task requires at least 500 companies.")
    if min_employees < 100:
        raise ValueError("The task requires at least 100 employees per company.")
    if max_employees < min_employees:
        raise ValueError("max_employees must be >= min_employees.")

    rng = random.Random(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    company_rows = []
    employee_rows = []
    truth_rows = []
    used_names = set()
    used_domains = set()

    for ci in range(1, n_companies + 1):
        company_id = f"C{ci:04d}"
        while True:
            name = f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)}{rng.choice(SUFFIXES)}".strip()
            if name not in used_names:
                used_names.add(name)
                break
        slug = "".join(ch.lower() for ch in name if ch.isalnum())
        domain = f"{slug}.example"
        suffix = 2
        base_domain = domain
        while domain in used_domains:
            domain = base_domain.replace(".example", f"{suffix}.example")
            suffix += 1
        used_domains.add(domain)

        employee_count = rng.randint(min_employees, max_employees)
        employee_ids = [f"{company_id}-P{i:04d}" for i in range(1, employee_count + 1)]
        rng.shuffle(employee_ids)
        company = {
            "company_id": company_id,
            "company_name": name,
            "industry": rng.choice(INDUSTRIES),
            "company_size": employee_count,
            "hq_region": rng.choice(REGIONS),
            "domain": domain,
            "_employee_ids": employee_ids,
        }
        company_rows.append({k: company[k] for k in ["company_id", "company_name", "industry", "company_size", "hq_region"]})
        next_num = 1

        # Executive layer. Every executive reports directly to the CEO in ground truth.
        ceo_id = _add_person(employee_rows, truth_rows, company, next_num, rng.choice(EXEC_TITLES["CEO"]), "Operations", None, rng)
        next_num += 1
        exec_ids = {}
        for role in ["CTO", "CFO", "COO", "CRO", "CHRO", "CPO"]:
            exec_ids[role] = _add_person(employee_rows, truth_rows, company, next_num, rng.choice(EXEC_TITLES[role]), {
                "CTO": "Engineering", "CFO": "Finance", "COO": "Operations", "CRO": "Sales", "CHRO": "People & HR", "CPO": "Product Management"
            }[role], ceo_id, rng)
            next_num += 1

        dept_names = list(DEPARTMENTS.keys())
        # Ten functions, each with at least six people including the function head.
        dept_sizes = _allocate(employee_count - 7, len(dept_names), 6, rng)
        for dept, dept_size in zip(dept_names, dept_sizes):
            spec = DEPARTMENTS[dept]
            head_title = _head_title(dept, dept_size, rng)
            sponsor_id = exec_ids[spec["sponsor"]]
            head_id = _add_person(employee_rows, truth_rows, company, next_num, head_title, dept, sponsor_id, rng)
            next_num += 1

            staff_count = dept_size - 1  # excludes function head
            # Split department staff into small identifiable teams. Team names are embedded in
            # job titles, never provided as a separate clean feature to the inference engine.
            team_count = max(1, (staff_count + 9) // 10)
            team_sizes = _allocate(staff_count, team_count, 1, rng)
            # Spread the first few teams across distinct tags so duplicate titles remain ambiguous.
            team_choices = rng.sample(spec["teams"], k=min(team_count, len(spec["teams"])))
            for ti, team_size in enumerate(team_sizes):
                team = team_choices[ti % len(team_choices)]
                manager_level = rng.choice(["manager", "senior"]) if team_size >= 7 else "manager"
                manager_labels = {
                    "Engineering": "Engineering", "Data & Analytics": "Data Engineering", "Security": "Security",
                    "Product Management": "Product", "Sales": "Sales", "Marketing": "Marketing", "Finance": "Finance",
                    "People & HR": "People", "Operations": "Operations", "Customer Success": "Customer Success",
                }
                function_label = manager_labels[dept]
                manager_title = f"{function_label} Manager, {team}" if manager_level == "manager" else f"Senior {function_label} Manager, {team}"
                manager_id = _add_person(employee_rows, truth_rows, company, next_num, manager_title, dept, head_id, rng, team)
                next_num += 1
                remaining = team_size - 1
                if remaining <= 0:
                    continue

                # Larger teams have one team lead; all ICs in that team report to the lead.
                # Smaller teams report directly to the manager, which is inferable from title/team.
                lead_id = None
                if team_size >= 8 and remaining >= 3:
                    lead_title = f"{spec['lead_label']}, {team}"
                    lead_id = _add_person(employee_rows, truth_rows, company, next_num, lead_title, dept, manager_id, rng, team)
                    next_num += 1
                    remaining -= 1

                for _ in range(remaining):
                    base_title = rng.choice(spec["ic_titles"])
                    prefix = rng.choices(["", "Senior ", "Sr. ", "Staff ", "Principal ", "Associate "], weights=[45, 22, 10, 7, 5, 11], k=1)[0]
                    ic_title = f"{prefix}{base_title}, {team}"
                    manager_for_ic = lead_id or manager_id
                    _add_person(employee_rows, truth_rows, company, next_num, ic_title, dept, manager_for_ic, rng, team)
                    next_num += 1

        # Defensive check: all company employees generated and no manager leakage into employee table.
        generated_count = sum(1 for r in employee_rows if r["company_id"] == company_id)
        if generated_count != employee_count:
            raise RuntimeError(f"Generated {generated_count} employees for {company_id}; expected {employee_count}")

    # Shuffle input rows too; neither row order nor ID order should leak the hidden hierarchy.
    rng.shuffle(employee_rows)
    rng.shuffle(truth_rows)

    # Only the flat employee table is inference input; manager IDs remain in this separate label file.
    with (out_dir / "companies.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(company_rows[0].keys()))
        writer.writeheader(); writer.writerows(company_rows)
    with (out_dir / "employees.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(employee_rows[0].keys()))
        writer.writeheader(); writer.writerows(employee_rows)
    with (out_dir / "ground_truth.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(truth_rows[0].keys()))
        writer.writeheader(); writer.writerows(truth_rows)

    print(f"Generated {len(company_rows):,} companies and {len(employee_rows):,} employees in {out_dir.resolve()}")
    print(f"Ground-truth reporting rows: {len(truth_rows):,} (keep separate from inference input)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--companies", type=int, default=500)
    parser.add_argument("--min-employees", type=int, default=100)
    parser.add_argument("--max-employees", type=int, default=180)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out-dir", default="data")
    args = parser.parse_args()
    generate(seed=args.seed, n_companies=args.companies, min_employees=args.min_employees, max_employees=args.max_employees, out_dir=args.out_dir)
