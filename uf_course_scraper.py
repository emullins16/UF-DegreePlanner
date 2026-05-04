"""
UF Engineering Course Catalog Scraper
======================================
Scrapes catalog.ufl.edu for all engineering department courses and outputs:
    coursecode, name, department, prereqcode, coreqcode

HTML structure (confirmed via browser inspection):
    div.courseblock.courseblocktoggle
        p.courseblocktitle.noindent      ← course code + name
        p.courseblockextra.noindent      ← credits / misc
        p.courseblockdesc.noindent       ← description text
        p.courseblockextra.noindent      ← "Prerequisite: <a>MAC 2311</a> ..."
        p.courseblockextra.noindent      ← "Corequisite: <a>...</a> ..."

Course codes inside prereq/coreq lines are <a> tags with href="/search/?P=XXX%20NNNN"
We extract them from the <a> tags directly — more reliable than regex on text.

Usage:
    pip install requests beautifulsoup4 pandas
    python uf_course_scraper.py

Output:
    uf_engineering_courses.csv
"""

import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────────────

DEBUG = False   # Set True to print raw HTML of first courseblock per dept

ENGINEERING_DEPARTMENTS = {
    "Agricultural & Biological Eng.":      "agricultural_and_biological_engineering",
    "Biomedical Engineering":              "biomedical_engineering",
    "Chemical Engineering":               "chemical_engineering",
    "Civil & Coastal Engineering":        "civil_and_coastal_engineering",
    "Computer & Info. Science & Eng.":    "computer_and_information_science_and_engineering",
    "Electrical & Computer Engineering":  "electrical_and_computer_engineering",
    "Environmental Eng. Sciences":        "environmental_engineering_sciences",
    "Industrial & Systems Engineering":   "industrial_and_systems_engineering",
    "Materials Science & Engineering":    "materials_science_and_engineering",
    "Mechanical & Aerospace Engineering": "mechanical_and_aerospace_engineering",
    "Engineering (General)":              "engineering_",
}

BASE_URL = "https://catalog.ufl.edu/UGRD/courses/{slug}/"

HEADERS = {
    "User-Agent": (
        "UF-Course-Scheduler-Research/1.0 "
        "(academic scheduling tool; non-commercial)"
    )
}

# Matches course codes in plain text fallback: EEL 3111C, MAC 2311, etc.
COURSE_CODE_RE = re.compile(r'\b([A-Z]{2,4})\s+(\d{4}[A-Z]?)\b')

# Matches the encoded course code in href: /search/?P=MAC%202311 → "MAC 2311"
HREF_CODE_RE = re.compile(r'\?P=([A-Z]{2,4})%20(\d{4}[A-Z]?)', re.IGNORECASE)

# ── Helpers ────────────────────────────────────────────────────────────────

def codes_from_tag(p_tag) -> str:
    """
    Extract course codes from a <p class="courseblockextra"> tag.

    Primary:  pull codes from <a href="/search/?P=XXX%20NNNN"> — these are
              the actual linked course codes UF embeds in prereq/coreq lines.
    Fallback: if no <a> tags found, regex-scan the plain text (catches edge
              cases where UF lists a course without linking it).
    """
    codes = []

    # Primary — harvest from anchor hrefs
    for a in p_tag.find_all("a", href=True):
        m = HREF_CODE_RE.search(a["href"])
        if m:
            code = f"{m.group(1).upper()} {m.group(2).upper()}"
            if code not in codes:
                codes.append(code)

    # Fallback — plain text regex
    if not codes:
        for prefix, num in COURSE_CODE_RE.findall(p_tag.get_text(" ")):
            code = f"{prefix} {num}"
            if code not in codes:
                codes.append(code)

    return "; ".join(codes)


def parse_prereq_coreq(block):
    """
    Find all p.courseblockextra tags in a courseblock and classify each as
    a Prerequisite or Corequisite line based on its leading <strong> label.
    Returns (prereq_codes_str, coreq_codes_str).
    """
    prereq_codes = ""
    coreq_codes  = ""

    for p in block.find_all("p", class_="courseblockextra"):
        # The label ("Prerequisite:" / "Corequisite:") is in a <strong> tag
        strong = p.find("strong")
        if not strong:
            continue

        label = strong.get_text(strip=True).rstrip(":").lower()

        if "prerequisite" in label:
            prereq_codes = codes_from_tag(p)
        elif "corequisite" in label:
            coreq_codes = codes_from_tag(p)

    return prereq_codes, coreq_codes


def scrape_department(dept_name: str, slug: str) -> list[dict]:
    """Fetch and parse one department's course listing page."""
    url = BASE_URL.format(slug=slug)
    print(f"  Fetching: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ⚠  Could not fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    blocks = soup.select("div.courseblock")

    if not blocks:
        print(f"  ⚠  No courseblock elements found — check URL or page structure.")
        if DEBUG:
            print(soup.prettify()[:3000])
        return []

    if DEBUG:
        print("\n--- DEBUG: First courseblock HTML ---")
        print(blocks[0].prettify())
        print("---\n")

    courses = []
    for block in blocks:

        # ── Title tag: "EEL 3923C Electrical Engineering Design 1 3 Credits" ──
        title_tag = block.select_one("p.courseblocktitle")
        if not title_tag:
            continue

        title_text = title_tag.get_text(" ", strip=True)

        # Pull course code from the start of the title
        code_match = COURSE_CODE_RE.match(title_text)
        if not code_match:
            continue

        course_code = f"{code_match.group(1)} {code_match.group(2)}"

        # Course name = after code, before the credit count
        remainder  = title_text[code_match.end():].strip()
        name_match = re.match(r'(.+?)\s+\d[\d\-\.]*\s+Credit', remainder)
        course_name = name_match.group(1).strip() if name_match else remainder.strip()

        # ── Prereqs / coreqs ──────────────────────────────────────────────
        prereq_codes, coreq_codes = parse_prereq_coreq(block)

        courses.append({
            "coursecode": course_code,
            "name":       course_name,
            "department": dept_name,
            "prereqcode": prereq_codes,
            "coreqcode":  coreq_codes,
        })

    print(f"     → {len(courses)} courses found")
    return courses


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    all_courses = []

    print("Scraping UF Engineering course catalog...\n")
    for dept_name, slug in ENGINEERING_DEPARTMENTS.items():
        print(f"[{dept_name}]")
        courses = scrape_department(dept_name, slug)
        all_courses.extend(courses)
        time.sleep(1.5)   # polite rate limit — ~1 req per 1.5 sec

    if not all_courses:
        print("\nNo courses scraped. Check your internet connection or catalog URLs.")
        return

    df = pd.DataFrame(all_courses, columns=[
        "coursecode", "name", "department", "prereqcode", "coreqcode"
    ])

    # Deduplicate — some courses appear on multiple dept pages
    df.drop_duplicates(subset=["coursecode"], keep="first", inplace=True)
    df.sort_values("coursecode", inplace=True)
    df.reset_index(drop=True, inplace=True)

    output_file = "uf_engineering_courses.csv"
    df.to_csv(output_file, index=False)

    # ── Summary ───────────────────────────────────────────────────────────
    total      = len(df)
    has_prereq = df["prereqcode"].str.len().gt(0).sum()
    has_coreq  = df["coreqcode"].str.len().gt(0).sum()
    no_prereq  = total - has_prereq

    print(f"\n✅  Done! {total} unique courses written to '{output_file}'")
    print(f"   {has_prereq} with prerequisites  |  {has_coreq} with corequisites  |  {no_prereq} with none")
    print(f"\nSample (courses with prerequisites):")
    sample = df[df["prereqcode"].str.len() > 0][
        ["coursecode", "name", "prereqcode", "coreqcode"]
    ].head(10)
    print(sample.to_string(index=False))


if __name__ == "__main__":
    main()
