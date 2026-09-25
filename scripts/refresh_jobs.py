#!/usr/bin/env python3
"""Build a normalized Ops/PM job feed from public source repositories."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
import urllib.parse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

SUMMER_URL = "https://raw.githubusercontent.com/NyXkim5/summer-2027-role-index/main/index.html"
NEW_GRAD_URL = "https://raw.githubusercontent.com/zapplyjobs/New-Grad-Jobs-2027/main/README.md"
APPLYGUY_URL = "https://raw.githubusercontent.com/ApplyGuy/2027-Internships/main/data/internships.json"
JOBRIGHT_PM_URL = "https://raw.githubusercontent.com/jobright-ai/2026-Product-Management-New-Grad/master/README.md"
JOBRIGHT_BA_URL = "https://raw.githubusercontent.com/jobright-ai/2026-Business-Analyst-New-Grad/master/README.md"
SEARCHTERN_URL = "https://raw.githubusercontent.com/KSaifStack/SearchTern-Listings/main/pages/listings.json"
H1B_URL = "https://raw.githubusercontent.com/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships/main/data/h1b.json"
H1B_THRESHOLD = 10

COMPANY_ALIASES = {
    "meta": "meta platforms",
    "amazon": "amazon com services",
    "google": "google",
    "jpmorgan": "jpmorgan chase",
    "amex": "american express",
    "deloitte": "deloitte consulting",
    "pwc": "pricewaterhousecoopers",
    "ey": "ernst young",
    "tiktok": "tiktok",
    "hpe": "hewlett packard enterprise",
    "jnj": "johnson johnson",
}

ROLE_PATTERNS = [
    ("Product", r"\b(associate product manager|product management|product manager|product analyst|product strategy|apm\b)"),
    ("Product Ops", r"\b(product operations|product ops)\b"),
    ("Growth Ops", r"\b(growth operations|growth ops|revenue operations|sales operations)\b"),
    ("Strategy & Ops", r"\b(strategy\s*(?:&|and)\s*operations|strategic operations|business strategy|business planning)\b"),
    ("Business Ops", r"\b(business operations|business management analyst|operations analyst|operations coordinator|program operations|business analyst|project management/business analyst)\b"),
    ("Program Management", r"\b(program management|program manager intern|project management)\b"),
]

EARLY_PATTERN = re.compile(
    r"\b(2027|intern(?:ship)?|new grad|new college grad|university graduate|early career|entry level|"
    r"associate|analyst|coordinator|rotational|rotation|leadership development|graduate program|campus)\b",
    re.I,
)

SENIOR_PATTERN = re.compile(r"\b(senior|sr\.?|principal|director|vice president|vp|head of|lead|staff|mid|mid-level|experienced)\b", re.I)

EXPLICIT_NEW_GRAD_PATTERN = re.compile(
    r"\b(2027|new grad(?:uate)?|new college grad(?:uate)?|university graduate|graduate|entry[ -]level|"
    r"early career|rotational|rotation program|junior)\b",
    re.I,
)

NO_SPONSOR_PATTERN = re.compile(
    r"\b(?:will not|does not|do not|unable to|cannot)\s+(?:provide\s+)?(?:visa\s+)?sponsor|"
    r"\bno\s+(?:visa\s+)?sponsorship|sponsorship\s+(?:is\s+)?not\s+available|"
    r"without\s+(?:current\s+or\s+future\s+)?(?:visa\s+)?sponsorship",
    re.I,
)

CITIZENSHIP_RESTRICTION_PATTERN = re.compile(
    r"\b(?:must\s+be\s+(?:a\s+)?u\.?s\.?\s+citizen|u\.?s\.?\s+citizenship\s+(?:is\s+)?required|"
    r"requires?\s+u\.?s\.?\s+citizenship|active\s+(?:security\s+)?clearance)\b",
    re.I,
)

SEARCHTERN_COMPANY_ALIASES = {
    "andurilindustries": "Anduril",
    "boschgroup": "Bosch",
    "directagents": "Direct Agents",
    "dtcc candidate experience site": "DTCC",
    "egup": "Vertiv",
    "fisglobal": "FIS",
    "flyzipline": "Zipline",
    "fortunebrands": "Fortune Brands",
    "harpercollins": "HarperCollins",
    "hereio": "HERE",
    "hpe": "HPE",
    "id": "ID.me",
    "klaviyocampus": "Klaviyo",
    "rfsmart": "RF-SMART",
    "springswindowfashions": "Springs Window Fashions",
    "us erac": "Enterprise Mobility",
    "usbank": "U.S. Bank",
    "uscampus pepsico": "PepsiCo",
    "zimmerbiomet": "Zimmer Biomet",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip(" |")


def classify_family(role: str) -> str | None:
    lowered = role.lower()
    for family, pattern in ROLE_PATTERNS:
        if re.search(pattern, lowered, re.I):
            return family
    return None


def classify_type(role: str) -> str:
    lowered = role.lower()
    if "intern" in lowered or "co-op" in lowered:
        return "Internship"
    if EXPLICIT_NEW_GRAD_PATTERN.search(lowered):
        return "New Grad"
    return "Entry Level"


def is_relevant(role: str) -> bool:
    if not classify_family(role) or not EARLY_PATTERN.search(role):
        return False
    if SENIOR_PATTERN.search(role):
        return False
    if re.search(r"\bmanager\b", role, re.I) and not re.search(
        r"product manager|program manager intern|operations manager intern|associate product manager", role, re.I
    ):
        return False
    return True


def posted_bucket(posted: str) -> str:
    lowered = posted.lower()
    if re.search(r"\b(today|\d+m|\d+h|1d|2d|3d)\b", lowered):
        return "Fresh now"
    if "unknown" in lowered or not posted:
        return "Date unknown"
    return "Open roles"


def source_date_label(value: str) -> str:
    """Turn an ISO source timestamp into a compact, stable display label."""
    if not value:
        return "Date unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return clean_text(value) or "Date unknown"
    current = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    days = (current.date() - parsed.astimezone(timezone.utc).date()).days
    if days <= 0:
        return "Today"
    if days <= 3:
        return f"{days}d"
    return f"{parsed.strftime('%b')} {parsed.day}"


def stable_id(company: str, role: str, location: str) -> str:
    key = "|".join(re.sub(r"\W+", " ", part.lower()).strip() for part in (company, role, location))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:14]


def canonical_apply_key(url: str) -> str:
    """Normalize tracking parameters so the same ATS posting dedupes across feeds."""
    parsed = urllib.parse.urlsplit(url)
    kept_query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query)
        if key.casefold() in {"gh_jid", "jobid"}
    ]
    host = parsed.netloc.casefold().removeprefix("www.")
    path = parsed.path.rstrip("/").casefold()
    return urllib.parse.urlunsplit(("https", host, path, urllib.parse.urlencode(kept_query), ""))


def normalize_company(name: str) -> str:
    value = re.sub(r"[^\w\s]", " ", (name or "").lower())
    tokens = re.sub(r"\s+", " ", value).strip().split()
    if len(tokens) > 1 and tokens[0] == "the":
        tokens.pop(0)
    suffixes = {"inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "co", "company", "plc"}
    while len(tokens) > 1 and tokens[-1] in suffixes:
        tokens.pop()
    return " ".join(tokens)


def h1b_approvals(company: str, index: dict) -> int | None:
    employers = index.get("employers") or {}
    key = normalize_company(company)
    if key in employers:
        return employers[key]
    alias = COMPANY_ALIASES.get(key)
    if alias in employers:
        return employers[alias]
    return None


@dataclass
class Job:
    id: str
    company: str
    role: str
    location: str
    apply_url: str
    source_name: str
    source_url: str
    source_section: str
    role_family: str
    job_type: str
    posted: str
    posted_bucket: str
    sponsorship: str
    sponsorship_scope: str
    sponsorship_evidence: str
    h1b_approvals: int | None = None
    h1b_window: str = ""
    status: str = "open"


class SummerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.section = ""
        self.in_h2 = False
        self.in_tr = False
        self.in_td = False
        self.h2_parts: list[str] = []
        self.cell_parts: list[str] = []
        self.cells: list[str] = []
        self.href = ""
        self.closed = False
        self.rows: list[tuple[str, list[str], str, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "h2":
            self.in_h2 = True
            self.h2_parts = []
        elif tag == "tr":
            self.in_tr = True
            self.cells = []
            self.href = ""
            self.closed = "closed" in (attr.get("class") or "")
        elif tag == "td" and self.in_tr:
            self.in_td = True
            self.cell_parts = []
        elif tag == "a" and self.in_td and not self.href:
            self.href = attr.get("href") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self.in_h2:
            self.section = clean_text(" ".join(self.h2_parts))
            self.in_h2 = False
        elif tag == "td" and self.in_td:
            self.cells.append(clean_text(" ".join(self.cell_parts)))
            self.in_td = False
        elif tag == "tr" and self.in_tr:
            if len(self.cells) >= 3:
                self.rows.append((self.section, self.cells[:3], self.href, self.closed))
            self.in_tr = False

    def handle_data(self, data: str) -> None:
        if self.in_h2:
            self.h2_parts.append(data)
        if self.in_td:
            self.cell_parts.append(data)


def parse_summer(source: str) -> list[Job]:
    parser = SummerParser()
    parser.feed(source)
    jobs: list[Job] = []
    for section, cells, href, closed in parser.rows:
        company, role_with_date, location = cells
        months = r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
        date_match = re.search(rf"\b(?:(?:{months})\s+\d{{1,2}}|\d{{1,2}}\s+(?:{months}))\b", role_with_date)
        role = re.sub(
            rf"\s+(?:(?:{months})\s+\d{{1,2}}|\d{{1,2}}\s+(?:{months})|via\s+(?:LinkedIn|tracker)\b|closes\b).*$",
            "",
            role_with_date,
            flags=re.I,
        ).strip()
        role = re.sub(r"\s+closed\b.*$", "", role, flags=re.I).strip()
        posted = date_match.group(0) if date_match else "Date unknown"
        family = classify_family(role)
        is_closed = closed or bool(re.search(r"\bclosed\b", role_with_date, re.I))
        if (not href and not is_closed) or not family or not is_relevant(role):
            continue
        jobs.append(Job(
            id=stable_id(company, role, location), company=company, role=role, location=location,
            apply_url=href, source_name="Summer 2027 Role Index",
            source_url="https://github.com/NyXkim5/summer-2027-role-index", source_section=section,
            role_family=family, job_type=classify_type(role), posted=posted,
            posted_bucket=posted_bucket(posted), sponsorship="not-stated", sponsorship_scope="source does not state a refusal",
            sponsorship_evidence="The source does not state that sponsorship is unavailable. Keep under the default eligibility rule, then verify the employer posting before applying.",
            status="closed" if is_closed else "open",
        ))
    return jobs


def markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_new_grad(source: str) -> list[Job]:
    jobs: list[Job] = []
    raw_rows: list[tuple[str, list[str]]] = []
    section = ""
    for line in source.splitlines():
        summary = re.search(r"<summary><h3>.*?<strong>(.*?)</strong>", line)
        if summary:
            section = clean_text(summary.group(1))
            continue
        if not line.startswith("|") or "---" in line:
            continue
        cells = markdown_cells(line)
        if len(cells) < 6 or cells[0].lower() == "company":
            continue
        raw_rows.append((section, cells[:6]))

    sponsor_companies = {
        clean_text(cells[0]).casefold()
        for _, cells in raw_rows
        if "Sponsor" in cells[4]
    }

    for section, cells in raw_rows:
        company, role, location, posted, visa, apply_cell = cells[:6]
        company, role, location, posted = map(clean_text, (company, role, location, posted))
        match = re.findall(r"\]\((https?://[^)]+)\)", apply_cell)
        href = match[-1] if match else ""
        family = classify_family(role)
        if not href or not family or not is_relevant(role):
            continue
        role_signal = "Sponsor" in visa
        company_signal = company.casefold() in sponsor_companies
        sponsor_signal = role_signal or company_signal
        signal_scope = "role/source signal" if role_signal else "company-level source signal"
        jobs.append(Job(
            id=stable_id(company, role, location), company=company, role=role, location=location,
            apply_url=href, source_name="New Grad Jobs 2027",
            source_url="https://github.com/zapplyjobs/New-Grad-Jobs-2027", source_section=section or "Uncategorized",
            role_family=family, job_type=classify_type(role), posted=posted or "Date unknown",
            posted_bucket=posted_bucket(posted), sponsorship="source-signal" if sponsor_signal else "not-stated",
            sponsorship_scope=signal_scope if sponsor_signal else "not provided",
            sponsorship_evidence=(
                "The source marks this listing with a Sponsor signal. Treat it as a lead, not a job-specific guarantee; verify the employer posting."
                if role_signal else
                "The source marks another current listing from this company with a Sponsor signal. This is company-level evidence only, not proof for this role; verify the employer posting."
                if company_signal else
                "No sponsorship signal is provided by this source. Verify the employer posting before applying."
            ),
        ))
    return jobs


def parse_applyguy(source: str) -> list[Job]:
    """Normalize ApplyGuy's frequently reverified open-internship JSON feed."""
    payload = json.loads(source)
    jobs: list[Job] = []
    for item in payload.get("jobs") or []:
        company = clean_text(str(item.get("company") or ""))
        role = clean_text(str(item.get("title") or ""))
        location = clean_text(str(item.get("location") or ""))
        href = str(item.get("listingUrl") or item.get("url") or "").strip()
        family = classify_family(role)
        if not company or not href or not family or not is_relevant(role):
            continue
        posted = clean_text(str(item.get("age") or item.get("posted") or "Date unknown"))
        season = clean_text(str(item.get("season") or "Internships"))
        jobs.append(Job(
            id=stable_id(company, role, location), company=company, role=role, location=location,
            apply_url=href, source_name="ApplyGuy 2027 Internships",
            source_url="https://github.com/ApplyGuy/2027-Internships", source_section=season,
            role_family=family, job_type="Internship", posted=posted,
            posted_bucket=posted_bucket(posted), sponsorship="not-stated",
            sponsorship_scope="source does not state a refusal",
            sponsorship_evidence=(
                "ApplyGuy reports this listing as open and links to the employer posting, but does not provide a "
                "role-specific sponsorship decision. Verify the employer posting before applying."
            ),
        ))
    return jobs


def parse_jobright_feed(source: str, source_name: str, source_url: str, source_section: str) -> list[Job]:
    """Keep only explicitly early-career Ops/PM roles from a recent Jobright feed."""
    jobs: list[Job] = []
    previous_company = ""
    for line in source.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = markdown_cells(line)
        if len(cells) < 5 or cells[0].lower() == "company":
            continue
        raw_company, raw_role, raw_location, work_model, posted = cells[:5]
        company = clean_text(raw_company)
        if company == "↳":
            company = previous_company
        elif company:
            previous_company = company
        role = clean_text(raw_role)
        role = re.sub(r"\]\(https?://[^)]+\)", "", role)
        role = role.replace("[", "").replace("]", "").strip()
        location = clean_text(raw_location)
        if clean_text(work_model).casefold() == "remote" and "remote" not in location.casefold():
            location = f"{location} · Remote" if location else "Remote"
        hrefs = re.findall(r"\]\((https?://[^)]+)\)", raw_role)
        href = hrefs[-1] if hrefs else ""
        family = classify_family(role)
        if (
            not company or not href or not family or not EXPLICIT_NEW_GRAD_PATTERN.search(role)
            or SENIOR_PATTERN.search(role)
        ):
            continue
        posted = clean_text(posted) or "Date unknown"
        jobs.append(Job(
            id=stable_id(company, role, location), company=company, role=role, location=location,
            apply_url=href, source_name=source_name, source_url=source_url,
            source_section=source_section, role_family=family, job_type="New Grad",
            posted=posted, posted_bucket=posted_bucket(posted), sponsorship="not-stated",
            sponsorship_scope="source does not state a refusal",
            sponsorship_evidence=(
                "Jobright includes this role in its recent Product Management new-grad feed. Sponsorship is not "
                "stated; verify the employer posting and role requirements before applying."
            ),
        ))
    return jobs


def parse_jobright_pm(source: str) -> list[Job]:
    return parse_jobright_feed(
        source,
        "Jobright Product Management New Grad",
        "https://github.com/jobright-ai/2026-Product-Management-New-Grad",
        "Recent product new-grad roles",
    )


def parse_jobright_ba(source: str) -> list[Job]:
    return parse_jobright_feed(
        source,
        "Jobright Business Analyst New Grad",
        "https://github.com/jobright-ai/2026-Business-Analyst-New-Grad",
        "Recent business analyst new-grad roles",
    )


def parse_searchtern(source: str) -> list[Job]:
    """Keep current U.S. Ops/PM internships and new-grad roles with direct ATS links."""
    payload = json.loads(source)
    jobs: list[Job] = []
    for item in payload:
        role = clean_text(str(item.get("role") or ""))
        description = clean_text(str(item.get("description") or ""))
        source_type = str(item.get("job_type") or "").casefold()
        family = classify_family(role)
        if (
            item.get("country_iso") != "US"
            or source_type not in {"internship", "new_grad"}
            or not family
            or not is_relevant(role)
            or (re.search(r"\b202[56]\b", role) and not re.search(r"\b2027\b", role))
            or re.search(r"\b(group product manager|product manager\s+(?:ii|iii|iv|2|3|4))\b", role, re.I)
            or NO_SPONSOR_PATTERN.search(description)
            or CITIZENSHIP_RESTRICTION_PATTERN.search(description)
        ):
            continue
        company_raw = clean_text(str(item.get("company") or ""))
        company = SEARCHTERN_COMPANY_ALIASES.get(company_raw.casefold(), company_raw)
        location = clean_text(str(item.get("location") or "")) or "United States"
        if str(item.get("is_remote") or "").casefold() == "true" and "remote" not in location.casefold():
            location = f"{location} · Remote"
        href = str(item.get("link") or "").strip()
        if not company or not href.startswith("http"):
            continue
        posted = source_date_label(str(item.get("date") or item.get("observed_at") or ""))
        job_type = "Internship" if source_type == "internship" else "New Grad"
        jobs.append(Job(
            id=stable_id(company, role, location), company=company, role=role, location=location,
            apply_url=href, source_name="SearchTern ATS Feed",
            source_url="https://github.com/KSaifStack/SearchTern-Listings",
            source_section="U.S. internships and new-grad roles", role_family=family,
            job_type=job_type, posted=posted, posted_bucket=posted_bucket(posted),
            sponsorship="not-stated", sponsorship_scope="source does not state a refusal",
            sponsorship_evidence=(
                "SearchTern links directly to the employer ATS. Its captured description does not state a "
                "sponsorship refusal or U.S.-citizenship requirement; verify the live posting before applying."
            ),
        ))
    return jobs


def dedupe(jobs: Iterable[Job]) -> list[Job]:
    by_id: dict[str, Job] = {}
    by_apply_url: dict[str, str] = {}
    for job in jobs:
        apply_key = canonical_apply_key(job.apply_url)
        existing_id = by_apply_url.get(apply_key) if apply_key else None
        if existing_id:
            existing = by_id[existing_id]
            if job.sponsorship == "source-signal" and existing.sponsorship != "source-signal":
                del by_id[existing_id]
                by_id[job.id] = job
                by_apply_url[apply_key] = job.id
            continue
        existing = by_id.get(job.id)
        if not existing or (job.sponsorship == "source-signal" and existing.sponsorship != "source-signal"):
            by_id[job.id] = job
            if apply_key:
                by_apply_url[apply_key] = job.id
    bucket_order = {"Fresh now": 0, "Open roles": 1, "Date unknown": 2}
    return sorted(by_id.values(), key=lambda item: (bucket_order[item.posted_bucket], item.company.lower(), item.role.lower()))


def enrich_h1b_history(jobs: Iterable[Job], index: dict) -> list[Job]:
    years = index.get("fiscal_years") or []
    window = "" if not years else (f"FY{years[0]}" if len(set(years)) == 1 else f"FY{min(years)}–{max(years)}")
    enriched = []
    for job in jobs:
        approvals = h1b_approvals(job.company, index)
        job.h1b_approvals = approvals
        job.h1b_window = window
        if job.sponsorship == "not-stated" and approvals is not None and approvals >= H1B_THRESHOLD:
            job.sponsorship = "history"
            job.sponsorship_scope = "company-level USCIS history"
            job.sponsorship_evidence = (
                f"USCIS history shows {approvals:,} approved H-1B petitions for a confidently matched employer in {window}. "
                "This is company history, not a promise for this role; no explicit refusal appears in the source listing."
            )
        enriched.append(job)
    return enriched


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "OpsPM-Tracker/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summer-file", type=Path)
    parser.add_argument("--new-grad-file", type=Path)
    parser.add_argument("--applyguy-file", type=Path)
    parser.add_argument("--jobright-pm-file", type=Path)
    parser.add_argument("--jobright-ba-file", type=Path)
    parser.add_argument("--searchtern-file", type=Path)
    parser.add_argument("--h1b-file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/jobs.json"))
    args = parser.parse_args()

    try:
        summer = args.summer_file.read_text(encoding="utf-8") if args.summer_file else fetch(SUMMER_URL)
        new_grad = args.new_grad_file.read_text(encoding="utf-8") if args.new_grad_file else fetch(NEW_GRAD_URL)
        applyguy = args.applyguy_file.read_text(encoding="utf-8") if args.applyguy_file else fetch(APPLYGUY_URL)
        jobright_pm = args.jobright_pm_file.read_text(encoding="utf-8") if args.jobright_pm_file else fetch(JOBRIGHT_PM_URL)
        jobright_ba = args.jobright_ba_file.read_text(encoding="utf-8") if args.jobright_ba_file else fetch(JOBRIGHT_BA_URL)
        searchtern = args.searchtern_file.read_text(encoding="utf-8") if args.searchtern_file else fetch(SEARCHTERN_URL)
        h1b_index = json.loads(args.h1b_file.read_text(encoding="utf-8")) if args.h1b_file else json.loads(fetch(H1B_URL))
    except Exception as exc:
        print(f"source fetch failed: {exc}", file=sys.stderr)
        return 2

    summer_jobs = parse_summer(summer)
    new_grad_jobs = parse_new_grad(new_grad)
    applyguy_jobs = parse_applyguy(applyguy)
    jobright_pm_jobs = parse_jobright_pm(jobright_pm)
    jobright_ba_jobs = parse_jobright_ba(jobright_ba)
    searchtern_jobs = parse_searchtern(searchtern)
    normalized = enrich_h1b_history(dedupe([*summer_jobs, *new_grad_jobs, *applyguy_jobs, *jobright_pm_jobs, *jobright_ba_jobs, *searchtern_jobs]), h1b_index)
    if not normalized:
        print("refusing to write an empty feed", file=sys.stderr)
        return 3

    generated_at = now_iso()
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "count": len(normalized),
        "sources": [
            {"name": "Summer 2027 Role Index", "url": "https://github.com/NyXkim5/summer-2027-role-index", "records": len(summer_jobs)},
            {"name": "New Grad Jobs 2027", "url": "https://github.com/zapplyjobs/New-Grad-Jobs-2027", "records": len(new_grad_jobs)},
            {"name": "ApplyGuy 2027 Internships", "url": "https://github.com/ApplyGuy/2027-Internships", "records": len(applyguy_jobs)},
            {"name": "Jobright Product Management New Grad", "url": "https://github.com/jobright-ai/2026-Product-Management-New-Grad", "records": len(jobright_pm_jobs)},
            {"name": "Jobright Business Analyst New Grad", "url": "https://github.com/jobright-ai/2026-Business-Analyst-New-Grad", "records": len(jobright_ba_jobs)},
            {"name": "SearchTern ATS Feed", "url": "https://github.com/KSaifStack/SearchTern-Listings", "records": len(searchtern_jobs)},
            {"name": "USCIS H-1B history index", "url": "https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub", "records": len(h1b_index.get("employers") or {}), "window": h1b_index.get("fiscal_years") or []},
        ],
        "jobs": [asdict(job) | {"verified_at": generated_at} for job in normalized],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "count": len(normalized), "summer": len(summer_jobs), "new_grad": len(new_grad_jobs), "applyguy": len(applyguy_jobs), "jobright_pm": len(jobright_pm_jobs), "jobright_ba": len(jobright_ba_jobs), "searchtern": len(searchtern_jobs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
