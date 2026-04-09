"""ASDC Qualification Pack scraper for auto parts knowledge graph.

Downloads and parses ASDC (Automotive Skills Development Council) qualification
packs to extract task→parts→knowledge mappings per job role. Each QP defines
a job role (e.g. "Automotive Engine Repair Technician") with National
Occupational Standards (NOS) containing:
  - Performance Criteria (PC): specific tasks a technician must perform
  - Knowledge and Understanding (KU): domain knowledge required
  - Generic Skills (GS): soft skills

Sources:
- NSDC S3 bucket: s3.ap-south-1.amazonaws.com/nsdcproddocuments/qpPdf/
- ASDC website: asdc.org.in
"""
import io
import json
import logging
import re
import sys
import time
from pathlib import Path

import pdfplumber
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR, USER_AGENT, REQUEST_DELAY

logger = logging.getLogger(__name__)

# NSDC S3 bucket base URL for qualification pack PDFs
S3_BASE = "https://s3.ap-south-1.amazonaws.com/nsdcproddocuments/qpPdf"

# Top automotive service/repair qualification packs (mechanic-relevant)
TARGET_QPS = [
    {"code": "ASC_Q1401", "version": "v2.0", "name": "Four Wheeler Service Assistant"},
    {"code": "ASC_Q1405", "version": "v2.0", "name": "Automotive Body Repair Technician"},
    {"code": "ASC_Q1407", "version": "v2.0", "name": "Automotive Paint Repair Assistant"},
    {"code": "ASC_Q1409", "version": "v2.0", "name": "Automotive Engine Repair Technician"},
    {"code": "ASC_Q1410", "version": "v4.0", "name": "Automotive Body Repair Assistant"},
    {"code": "ASC_Q1411", "version": "v2.0", "name": "Two Wheeler Service Technician"},
    {"code": "ASC_Q1416", "version": "v2.0", "name": "Automotive AC Technician"},
    {"code": "ASC_Q1424", "version": "v1.0", "name": "Electric Vehicle Service Lead Technician"},
    {"code": "ASC_Q1429", "version": "v5.0", "name": "Electric Vehicle Service Technician"},
    {"code": "ASC_Q1432", "version": "v1.0", "name": "Heavy Commercial Vehicle Service Technician"},
    {"code": "ASC_Q6809", "version": "v1.0", "name": "Electric Vehicle Maintenance Technician"},
    {"code": "ASC_Q8312", "version": "v1.0", "name": "Automotive Assembly Technician"},
]


def download_pdf(qp: dict, session: requests.Session) -> bytes | None:
    """Download a QP PDF from the NSDC S3 bucket."""
    url = f"{S3_BASE}/{qp['code']}_{qp['version']}.pdf"
    logger.info(f"Downloading {qp['name']} from {url}")
    try:
        resp = session.get(url, timeout=60)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/pdf"):
            logger.info(f"  Downloaded {len(resp.content)} bytes")
            return resp.content
        logger.warning(f"  Failed: HTTP {resp.status_code}")
    except requests.RequestException as e:
        logger.warning(f"  Failed: {e}")
    return None


def extract_text(pdf_bytes: bytes) -> list[str]:
    """Extract text from each page of a PDF."""
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return pages


def parse_qp_metadata(pages: list[str]) -> dict:
    """Extract QP-level metadata from first few pages."""
    full_text = "\n".join(pages[:4])

    metadata = {}

    # Job description — usually after "Brief Job Description"
    m = re.search(
        r"Brief Job Description\s*\n(.+?)(?=\nPersonal Attributes|\nApplicable)",
        full_text, re.DOTALL,
    )
    if m:
        metadata["job_description"] = _clean(m.group(1))

    # Sector/sub-sector/occupation from QP parameters table
    for field in ("Sector", "Sub-Sector", "Occupation", "NSQF Level", "Country"):
        m = re.search(rf"{field}\s+(.+?)(?:\n|$)", full_text)
        if m:
            key = field.lower().replace("-", "_").replace(" ", "_")
            metadata[key] = _clean(m.group(1))

    # NOS list
    nos_codes = re.findall(r"(ASC/N\d+):", full_text)
    metadata["nos_codes"] = list(dict.fromkeys(nos_codes))  # deduplicate, preserve order

    return metadata


def parse_nos_units(pages: list[str]) -> list[dict]:
    """Parse individual NOS (National Occupational Standard) units from PDF text.

    Each NOS contains:
    - Description and Scope
    - Performance Criteria (PC1, PC2, ...) — tasks
    - Knowledge and Understanding (KU1, KU2, ...) — knowledge
    - Generic Skills (GS1, GS2, ...) — skills
    """
    full_text = "\n".join(pages)

    # Find NOS headers that are followed by "Description" (actual NOS, not TOC)
    # Pattern: "ASC/N####: Title" followed within ~200 chars by "Description"
    nos_pattern = re.compile(
        r"(ASC/N\d+):\s*(.+?)(?=\n)",
    )

    # Collect all NOS header positions
    all_matches = list(nos_pattern.finditer(full_text))

    # Filter to actual NOS sections (not TOC entries or metadata listings)
    # Actual NOS sections have "Description\n" as a standalone line shortly after
    # the header. TOC entries have "..." and metadata listings are prefixed by
    # numbered markers (e.g. "1. ASC/N...").
    nos_sections = []
    for match in all_matches:
        line = match.group(0)
        # Skip TOC entries (contain dots/ellipsis)
        if re.search(r"\.{3,}|……", line):
            continue
        # Skip numbered list entries in metadata ("1. ASC/N9801:")
        pre = full_text[max(0, match.start() - 5):match.start()]
        if re.search(r"\d+\.\s*$", pre):
            continue
        # Actual NOS sections have "Description" on its own line within ~500 chars
        lookahead = full_text[match.end():match.end() + 500]
        if re.search(r"\nDescription\s*\n", lookahead) or re.search(r"\nElements and Performance", lookahead):
            nos_sections.append(match)

    nos_units = []
    seen_codes = set()

    for i, match in enumerate(nos_sections):
        nos_code = match.group(1)
        nos_title = _clean(match.group(2))

        if nos_code in seen_codes:
            continue
        seen_codes.add(nos_code)

        # Section boundary: from this header to the next NOS section (or Assessment Guidelines)
        start = match.end()
        end = len(full_text)
        for j in range(i + 1, len(nos_sections)):
            end = nos_sections[j].start()
            break

        # Also cut at "Assessment Guidelines" or "Assessment Weightage" sections
        assessment_cut = re.search(r"\nAssessment Guidelines and (?:Weightage|Assessment)", full_text[start:end])
        if assessment_cut:
            end = start + assessment_cut.start()

        section_text = full_text[start:end]

        nos_unit = {
            "nos_code": nos_code,
            "title": nos_title,
            "description": "",
            "scope": [],
            "performance_criteria": [],
            "knowledge": [],
            "skills": [],
        }

        # Description
        m = re.search(r"Description\s*\n(.+?)(?=\nScope|\nElements)", section_text, re.DOTALL)
        if m:
            nos_unit["description"] = _clean(m.group(1))

        # Scope items
        m = re.search(r"Scope\s*\n.*?covers.*?:\s*\n(.+?)(?=\nElements)", section_text, re.DOTALL)
        if m:
            nos_unit["scope"] = [_clean(line) for line in m.group(1).strip().split("\n") if _clean(line)]

        # Extract the "Elements and Performance Criteria" section, stopping before
        # "Knowledge and Understanding" or "Assessment Criteria"
        pc_section = ""
        m = re.search(
            r"Elements and Performance Criteria\s*\n(.+?)(?=\nKnowledge and Understanding|\nAssessment Criteria|\Z)",
            section_text, re.DOTALL,
        )
        if m:
            pc_section = m.group(1)

        # Performance Criteria — only from the elements section (not assessment tables)
        if pc_section:
            pcs = re.findall(r"PC(\d+)\.\s*(.+?)(?=\nPC\d+\.|\Z)", pc_section, re.DOTALL)
            for pc_num, pc_text in pcs:
                cleaned = _clean(pc_text)
                # Filter out assessment table entries (contain mark numbers like "2 1 - -")
                if cleaned and len(cleaned) > 10 and not re.match(r"^[\w\s,/]+\d+\s+\d+\s+-\s+\d+", cleaned):
                    nos_unit["performance_criteria"].append({
                        "id": f"PC{pc_num}",
                        "task": cleaned,
                    })

        # Knowledge and Understanding section
        ku_section = ""
        m = re.search(
            r"Knowledge and Understanding.*?\n(.+?)(?=\nGeneric Skills|\nAssessment Criteria|\Z)",
            section_text, re.DOTALL,
        )
        if m:
            ku_section = m.group(1)

        if ku_section:
            kus = re.findall(r"KU(\d+)\.\s*(.+?)(?=\nKU\d+\.|\nGeneric|\nAssessment|\Z)", ku_section, re.DOTALL)
            for ku_num, ku_text in kus:
                cleaned = _clean(ku_text)
                if cleaned and len(cleaned) > 10:
                    nos_unit["knowledge"].append({
                        "id": f"KU{ku_num}",
                        "description": cleaned,
                    })

        # Generic Skills section
        gs_section = ""
        m = re.search(
            r"Generic Skills.*?\n(.+?)(?=\nAssessment|\Z)",
            section_text, re.DOTALL,
        )
        if m:
            gs_section = m.group(1)

        if gs_section:
            gss = re.findall(r"GS(\d+)\.\s*(.+?)(?=\nGS\d+\.|\nAssessment|\Z)", gs_section, re.DOTALL)
            for gs_num, gs_text in gss:
                cleaned = _clean(gs_text)
                if cleaned and len(cleaned) > 10:
                    nos_unit["skills"].append({
                        "id": f"GS{gs_num}",
                        "description": cleaned,
                    })

        # Only include NOS units that have meaningful content
        if nos_unit["performance_criteria"] or nos_unit["knowledge"]:
            nos_units.append(nos_unit)

    return nos_units


def extract_parts_from_nos(nos_unit: dict) -> list[str]:
    """Extract auto parts/systems mentioned in a NOS unit's tasks and knowledge."""
    # Auto parts and systems vocabulary for extraction
    parts_patterns = [
        # Engine & drivetrain
        r"engine", r"cylinder\s*(?:head|block|liner)", r"turbo\s*charger", r"fuel\s*pump",
        r"oil\s*(?:pump|filter|seal)", r"piston", r"crankshaft", r"camshaft", r"valve",
        r"gasket", r"timing\s*(?:chain|belt)", r"clutch", r"gearbox", r"transmission",
        r"propeller\s*shaft", r"drive\s*shaft", r"differential", r"flywheel", r"bearing",
        r"connecting\s*rod", r"spark\s*plug", r"injector", r"carburetor",
        # Brakes
        r"brake\s*(?:pad|disc|drum|shoe|caliper|line|fluid|master\s*cylinder|booster)?",
        r"ABS", r"anti.?lock",
        # Suspension & steering
        r"suspension", r"shock\s*absorber", r"strut", r"spring", r"steering",
        r"power\s*steering", r"tie\s*rod", r"ball\s*joint", r"bush(?:ing)?",
        r"wheel\s*(?:alignment|bearing|hub)",
        # Electrical
        r"battery", r"alternator", r"starter\s*motor", r"ignition", r"spark\s*plug",
        r"wiring\s*harness", r"fuse", r"relay", r"sensor", r"ECU", r"ECM",
        r"head\s*(?:light|lamp)", r"tail\s*(?:light|lamp)", r"horn",
        # Body & chassis
        r"body\s*panel", r"bumper", r"fender", r"bonnet", r"hood", r"door",
        r"windscreen", r"windshield", r"window\s*glass", r"mirror",
        r"chassis", r"frame", r"axle",
        # Cooling & AC
        r"radiator", r"coolant", r"thermostat", r"water\s*pump", r"fan\s*belt",
        r"air\s*condition(?:ing|er)", r"compressor", r"condenser", r"evaporator",
        r"blower", r"refrigerant",
        # Exhaust
        r"exhaust", r"muffler", r"silencer", r"catalytic\s*converter",
        # Filters & fluids
        r"air\s*filter", r"fuel\s*filter", r"oil\s*filter", r"cabin\s*filter",
        r"lubricant", r"coolant", r"brake\s*fluid", r"transmission\s*fluid",
        # EV-specific
        r"(?:EV|electric\s*vehicle)\s*battery", r"motor\s*controller", r"inverter",
        r"charger", r"BMS", r"battery\s*management",
        r"regenerative\s*brak(?:e|ing)", r"powertrain",
        # Tyres & wheels
        r"tyre", r"tire", r"wheel", r"rim", r"tube",
        # Paint & body repair
        r"primer", r"paint", r"clear\s*coat", r"putty", r"filler",
        r"sanding", r"masking", r"spray\s*gun",
    ]

    all_text = " ".join(
        [pc["task"] for pc in nos_unit.get("performance_criteria", [])]
        + [ku["description"] for ku in nos_unit.get("knowledge", [])]
    ).lower()

    found = set()
    for pattern in parts_patterns:
        matches = re.findall(pattern, all_text, re.IGNORECASE)
        for match in matches:
            found.add(match.strip().lower())

    return sorted(found)


def parse_qualification_pack(qp: dict, pdf_bytes: bytes) -> dict:
    """Parse a complete qualification pack PDF into structured data."""
    pages = extract_text(pdf_bytes)
    if not pages:
        logger.warning(f"No text extracted from {qp['code']}")
        return None

    metadata = parse_qp_metadata(pages)
    nos_units = parse_nos_units(pages)

    # Extract parts mentioned in each NOS
    for nos in nos_units:
        nos["parts_mentioned"] = extract_parts_from_nos(nos)

    # Aggregate all parts across all NOS units
    all_parts = set()
    for nos in nos_units:
        all_parts.update(nos["parts_mentioned"])

    result = {
        "qp_code": qp["code"].replace("_", "/"),
        "version": qp["version"],
        "name": qp["name"],
        "nsqf_level": metadata.get("nsqf_level", ""),
        "sector": metadata.get("sector", "Automotive"),
        "sub_sector": metadata.get("sub_sector", ""),
        "occupation": metadata.get("occupation", ""),
        "job_description": metadata.get("job_description", ""),
        "nos_codes": metadata.get("nos_codes", []),
        "nos_units": nos_units,
        "all_parts_mentioned": sorted(all_parts),
        "statistics": {
            "nos_count": len(nos_units),
            "total_tasks": sum(len(n["performance_criteria"]) for n in nos_units),
            "total_knowledge": sum(len(n["knowledge"]) for n in nos_units),
            "total_skills": sum(len(n["skills"]) for n in nos_units),
            "parts_count": len(all_parts),
        },
    }

    return result


def _clean(text: str) -> str:
    """Clean extracted text: normalize whitespace, remove page footers."""
    # Remove common footer patterns
    text = re.sub(r"(?:Deactivated-)?NSQC Approved.*?(?:\d+\s*$|\n)", "", text)
    text = re.sub(r"Automotive Skill Council of India.*?(?:\d+\s*$|\n)", "", text)
    text = re.sub(r"Qualification Pack\s*\n?", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def scrape_asdc_tasks() -> list[dict]:
    """Download and parse ASDC qualification packs."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    results = []
    for qp in TARGET_QPS:
        pdf_bytes = download_pdf(qp, session)
        if not pdf_bytes:
            continue

        parsed = parse_qualification_pack(qp, pdf_bytes)
        if parsed:
            results.append(parsed)
            logger.info(
                f"  Parsed {qp['name']}: {parsed['statistics']['nos_count']} NOS, "
                f"{parsed['statistics']['total_tasks']} tasks, "
                f"{parsed['statistics']['total_knowledge']} knowledge items, "
                f"{parsed['statistics']['parts_count']} parts"
            )

        time.sleep(REQUEST_DELAY)

    return results


def save_tasks(results: list[dict], output_path: Path) -> None:
    """Save parsed ASDC tasks to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "metadata": {
            "description": "ASDC Qualification Pack task-parts-knowledge mappings",
            "source": "Automotive Skills Development Council (asdc.org.in)",
            "source_url": "https://nsdcindia.org/nos-listing/4",
            "total_qualification_packs": len(results),
            "total_nos_units": sum(r["statistics"]["nos_count"] for r in results),
            "total_tasks": sum(r["statistics"]["total_tasks"] for r in results),
            "total_knowledge": sum(r["statistics"]["total_knowledge"] for r in results),
        },
        "qualification_packs": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(results)} qualification packs to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    output_file = KNOWLEDGE_GRAPH_DIR / "asdc_tasks.json"
    results = scrape_asdc_tasks()
    save_tasks(results, output_file)

    # Summary
    print(f"\nDone. {len(results)} qualification packs saved to {output_file}")
    for r in results:
        s = r["statistics"]
        print(f"  {r['qp_code']} {r['name']}: {s['nos_count']} NOS, {s['total_tasks']} tasks, {s['total_knowledge']} KU, {s['parts_count']} parts")
