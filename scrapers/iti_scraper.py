"""DGT ITI Syllabus parser for auto parts knowledge graph.

Downloads and parses ITI (Industrial Training Institute) syllabus PDFs from
dgt.gov.in for automobile-related trades. Extracts diagnostic/troubleshooting
procedures to build symptom → diagnosis → parts chains.

Trades covered:
- Mechanic Motor Vehicle (MMV) — 2-year, NSQF Level 4
- Mechanic Diesel — 1-year, NSQF Level 3.5
- Mechanic Auto Electrical & Electronics — 1-year, NSQF Level 3
- Mechanic Two & Three Wheeler — 1-year, NSQF Level 3
- Mechanic Tractor — 1-year, NSQF Level 3
- Mechanic Electric Vehicle — 2-year, NSQF Level 4

Sources: https://dgt.gov.in (Directorate General of Training)
Design: ADR-002 (context/decisions/002-data-sources.md)
"""
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pdfplumber
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR, USER_AGENT, REQUEST_DELAY

logger = logging.getLogger(__name__)

ITI_PDF_DIR = KNOWLEDGE_GRAPH_DIR / "iti_pdfs"

# PDF download URLs from dgt.gov.in
ITI_SYLLABI = {
    "mechanic_motor_vehicle": {
        "url": "https://dgt.gov.in/sites/default/files/2023-12/Mechanic%20Motor%20Vehicle_CTS2.0_NSQF-4_0.pdf",
        "trade": "Mechanic Motor Vehicle",
        "duration": "2 years",
        "nsqf_level": 4,
    },
    "mechanic_diesel": {
        "url": "https://dgt.gov.in/sites/default/files/2025-01/Mechanic%20Diesel_CTS2.0_NSQF-3.5.pdf",
        "trade": "Mechanic Diesel",
        "duration": "1 year",
        "nsqf_level": 3.5,
    },
    "mechanic_auto_electrical": {
        "url": "https://dgt.gov.in/sites/default/files/2023-12/Mech.%20Auto%20Electrical%20Electronics_CTS2.0_NSQF-3.pdf",
        "trade": "Mechanic Auto Electrical & Electronics",
        "duration": "1 year",
        "nsqf_level": 3,
    },
    "mechanic_two_three_wheeler": {
        "url": "https://dgt.gov.in/sites/default/files/Mech%20Two%20_%20Three%20Wheeler_CTS2.0_NSQF-3.pdf",
        "trade": "Mechanic Two & Three Wheeler",
        "duration": "1 year",
        "nsqf_level": 3,
    },
    "mechanic_tractor": {
        "url": "https://dgt.gov.in/sites/default/files/Mechanic%20Tractor_CTS2.0_NSQF-3.pdf",
        "trade": "Mechanic Tractor",
        "duration": "1 year",
        "nsqf_level": 3,
    },
    "mechanic_electric_vehicle": {
        "url": "https://dgt.gov.in/sites/default/files/2024-01/Mechanic%20Electric%20Vehicle_CTS2.0_NSQF-4.pdf",
        "trade": "Mechanic Electric Vehicle",
        "duration": "2 years",
        "nsqf_level": 4,
    },
}


@dataclass
class DiagnosticChain:
    """A symptom → diagnosis → parts chain extracted from ITI syllabi."""
    id: str
    symptom: str
    system: str
    diagnosis_steps: list[str]
    related_parts: list[str]
    source_trade: str
    source_page: int = 0
    vehicle_type: str = ""  # "LMV", "HMV", "2W", "3W", "tractor", "EV"
    confidence: float = 0.8


# ---------------------------------------------------------------------------
# PDF downloading
# ---------------------------------------------------------------------------

def download_pdfs(force: bool = False) -> dict[str, Path]:
    """Download ITI syllabus PDFs if not already present."""
    ITI_PDF_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    paths = {}

    for key, info in ITI_SYLLABI.items():
        pdf_path = ITI_PDF_DIR / f"{key}.pdf"
        paths[key] = pdf_path
        if pdf_path.exists() and not force:
            logger.info(f"Already downloaded: {pdf_path.name}")
            continue
        logger.info(f"Downloading {info['trade']}...")
        try:
            resp = session.get(info["url"], timeout=120)
            resp.raise_for_status()
            pdf_path.write_bytes(resp.content)
            logger.info(f"  Saved {pdf_path.name} ({len(resp.content)//1024}KB)")
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            logger.error(f"  Failed to download {key}: {e}")

    return paths


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Clean up PDF extraction artifacts."""
    # Fix common OCR/extraction issues
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)  # camelCase splits
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('E lectrical', 'Electrical')
    text = text.replace('Mecha nic', 'Mechanic')
    return text.strip()


def _extract_full_text(pdf_path: Path) -> list[tuple[int, str]]:
    """Extract text from all pages, returning (page_num, text) tuples."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((i + 1, _normalize_text(text)))
    return pages


# ---------------------------------------------------------------------------
# Diagnostic chain extraction patterns
# ---------------------------------------------------------------------------

# Patterns that indicate diagnostic/troubleshooting content
DIAGNOSTIC_KEYWORDS = [
    r'troubleshoot\w*',
    r'diagnos\w+',
    r'fault\s+find\w*',
    r'causes?\s+and\s+remed\w+',
    r'troubles?\s+and\s+remed\w+',
    r'defects?\s+in',
    r'not\s+starting',
    r'overheating',
    r'abnormal\s+noise',
    r'excessive\s+(?:oil|fuel)\s+consumption',
    r'no\s+(?:cooling|charge|horn|operation)',
    r'poor\s+(?:performance|fuel\s+economy|steering)',
    r'hard\s+(?:start|steering)',
    r'low\s+(?:power|pressure|charge)',
    r'high\s+(?:fuel\s+consumption|pressure|temperature)',
]

DIAGNOSTIC_PATTERN = re.compile(
    '|'.join(DIAGNOSTIC_KEYWORDS), re.IGNORECASE
)

# System classification keywords
SYSTEM_KEYWORDS = {
    "engine": ["engine", "cylinder", "piston", "crankshaft", "camshaft", "valve",
               "combustion", "compression", "spark plug", "glow plug"],
    "fuel_system": ["fuel", "injection", "carburetor", "carburettor", "injector",
                    "fuel pump", "fuel filter", "CRDI", "MPFI", "diesel"],
    "cooling_system": ["cooling", "radiator", "thermostat", "coolant", "water pump",
                       "fan", "overheating", "temperature"],
    "lubrication_system": ["lubrication", "oil pump", "oil filter", "oil pressure",
                           "oil consumption"],
    "ignition_system": ["ignition", "spark plug", "ignition coil", "distributor",
                        "ignition timing", "dwell angle"],
    "electrical_system": ["electrical", "battery", "alternator", "starter", "charging",
                          "wiring", "fuse", "relay", "circuit"],
    "transmission": ["transmission", "gearbox", "gear box", "clutch", "propeller shaft",
                     "differential", "drive shaft"],
    "braking_system": ["brake", "braking", "disc brake", "drum brake", "ABS",
                       "master cylinder", "brake pad", "brake shoe", "bleeding"],
    "suspension_steering": ["suspension", "steering", "shock absorber", "spring",
                            "ball joint", "tie rod", "power steering", "wheel alignment"],
    "ac_system": ["air conditioning", "AC system", "compressor", "condenser",
                  "evaporator", "refrigerant", "cooling", "blower"],
    "exhaust_emission": ["exhaust", "emission", "catalytic", "EGR", "SCR", "silencer",
                         "muffler", "PCV", "pollution"],
    "body_electrical": ["horn", "wiper", "headlight", "tail light", "indicator",
                        "power window", "door lock", "immobilizer", "airbag",
                        "dashboard", "gauge", "speedometer"],
    "ev_system": ["battery management", "BMS", "motor controller", "inverter",
                  "regenerative braking", "charging station", "high voltage",
                  "electric motor", "EV"],
    "hydraulic_system": ["hydraulic", "power take off", "PTO", "lift", "implement"],
}


def _classify_system(text: str) -> str:
    """Classify which vehicle system a diagnostic text belongs to."""
    text_lower = text.lower()
    scores = {}
    for system, keywords in SYSTEM_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[system] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"


def _extract_parts(text: str) -> list[str]:
    """Extract part names mentioned in diagnostic text."""
    # Common auto parts patterns
    part_patterns = [
        r'spark\s*plug', r'glow\s*plug', r'fuel\s*pump', r'oil\s*pump',
        r'water\s*pump', r'fuel\s*filter', r'oil\s*filter', r'air\s*filter',
        r'air\s*cleaner', r'radiator', r'thermostat', r'fan\s*belt',
        r'alternator', r'starter\s*motor', r'battery', r'ignition\s*coil',
        r'distributor', r'carbure?tor', r'injector', r'fuel\s*injector',
        r'brake\s*pad', r'brake\s*shoe', r'brake\s*disc', r'brake\s*drum',
        r'master\s*cylinder', r'clutch\s*plate', r'clutch\s*disc',
        r'pressure\s*plate', r'flywheel', r'gearbox', r'gear\s*box',
        r'propeller\s*shaft', r'differential', r'drive\s*shaft',
        r'shock\s*absorber', r'spring', r'ball\s*joint', r'tie\s*rod',
        r'steering\s*rack', r'power\s*steering\s*pump',
        r'compressor', r'condenser', r'evaporator', r'blower\s*motor',
        r'piston', r'piston\s*ring', r'cylinder\s*head', r'head\s*gasket',
        r'crankshaft', r'camshaft', r'connecting\s*rod', r'valve',
        r'valve\s*guide', r'valve\s*seat', r'rocker\s*arm', r'pushrod',
        r'timing\s*chain', r'timing\s*belt', r'tensioner',
        r'exhaust\s*manifold', r'intake\s*manifold', r'silencer', r'muffler',
        r'catalytic\s*converter', r'oxygen\s*sensor', r'EGR\s*valve',
        r'PCV\s*valve', r'turbo\s*charger', r'turbocharger',
        r'ECU', r'ECM', r'sensor', r'actuator',
        r'fuse', r'relay', r'solenoid', r'wiring\s*harness',
        r'horn', r'wiper\s*motor', r'wiper\s*blade',
        r'headlight', r'tail\s*light', r'indicator\s*light',
        r'speedometer', r'fuel\s*gauge', r'temperature\s*gauge',
        r'bearing', r'seal', r'gasket', r'O-ring',
        r'brake\s*line', r'brake\s*fluid', r'coolant',
        r'motor\s*controller', r'inverter', r'BMS',
        r'high\s*voltage\s*battery', r'charger', r'charging\s*port',
        r'hub\s*motor', r'BLDC\s*motor',
    ]
    found = set()
    text_lower = text.lower()
    for pattern in part_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for m in matches:
            # Normalize: title case, strip whitespace
            part = re.sub(r'\s+', ' ', m).strip().title()
            found.add(part)
    return sorted(found)


def _make_id(symptom: str) -> str:
    """Create a deterministic ID from symptom description."""
    slug = re.sub(r'[^a-z0-9]+', '_', symptom.lower()).strip('_')
    # Truncate to reasonable length
    if len(slug) > 60:
        slug = slug[:60].rsplit('_', 1)[0]
    return slug


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------

# Structured diagnostic patterns found in ITI syllabi
# These capture the specific troubleshooting procedures documented in the curricula
STRUCTURED_DIAGNOSTICS = {
    "mechanic_motor_vehicle": [
        # From Learning Outcome 13 & 18 (pages 20, 23-24)
        {
            "symptom": "Engine not starting — mechanical causes",
            "system": "engine",
            "diagnosis_steps": [
                "Check fuel supply to engine",
                "Check compression pressure in cylinders",
                "Inspect valve timing and clearance",
                "Check for seized engine components",
                "Inspect crankshaft and camshaft condition",
            ],
            "related_parts": ["fuel pump", "spark plug", "piston ring", "cylinder head gasket", "valve", "crankshaft"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Engine not starting — electrical causes",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check battery voltage and connections",
                "Test starter motor operation",
                "Check ignition switch and wiring",
                "Test ignition coil output",
                "Inspect spark plug condition and gap",
            ],
            "related_parts": ["battery", "starter motor", "ignition coil", "spark plug", "ignition switch", "fuse"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Engine abnormal noise",
            "system": "engine",
            "diagnosis_steps": [
                "Identify noise type: knocking, tapping, rattling, or grinding",
                "Check engine oil level and pressure",
                "Inspect valve clearance and rocker arm",
                "Check connecting rod and main bearing clearance",
                "Inspect piston and cylinder bore for wear",
                "Check timing chain/belt tension",
            ],
            "related_parts": ["bearing", "piston", "piston ring", "connecting rod", "valve", "rocker arm", "timing chain"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "High fuel consumption",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Check air filter for clogging",
                "Inspect fuel injectors for leaking or improper spray pattern",
                "Check engine compression",
                "Test oxygen sensor and ECU readings",
                "Inspect for fuel line leaks",
                "Check tire pressure (low pressure increases consumption)",
            ],
            "related_parts": ["air filter", "fuel injector", "oxygen sensor", "ECU", "spark plug", "fuel filter"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Engine overheating",
            "system": "cooling_system",
            "diagnosis_steps": [
                "Check coolant level in radiator and reservoir",
                "Test thermostat operation",
                "Inspect radiator for blockage or leaks",
                "Check water pump operation",
                "Inspect fan belt tension and fan operation",
                "Test cooling system pressure",
                "Check for head gasket failure (bubbles in coolant)",
            ],
            "related_parts": ["radiator", "thermostat", "water pump", "fan belt", "coolant", "head gasket"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Low engine power / poor performance",
            "system": "engine",
            "diagnosis_steps": [
                "Check air filter condition",
                "Test fuel pressure and flow",
                "Check compression in all cylinders",
                "Inspect exhaust system for blockage",
                "Test ignition timing",
                "Check for vacuum leaks",
                "Read ECU error codes with scan tool",
            ],
            "related_parts": ["air filter", "fuel pump", "fuel filter", "spark plug", "catalytic converter", "ECU"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Excessive oil consumption",
            "system": "lubrication_system",
            "diagnosis_steps": [
                "Check for external oil leaks",
                "Inspect valve stem seals",
                "Check piston rings for wear (compression test)",
                "Inspect cylinder bore for scoring",
                "Check PCV valve operation",
                "Inspect turbocharger seals if fitted",
            ],
            "related_parts": ["piston ring", "valve", "valve guide", "seal", "PCV valve", "gasket", "oil pump"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Low engine oil pressure",
            "system": "lubrication_system",
            "diagnosis_steps": [
                "Check oil level and condition",
                "Replace oil filter",
                "Test oil pressure with mechanical gauge",
                "Inspect oil pump for wear",
                "Check main and connecting rod bearing clearance",
                "Inspect oil pressure relief valve",
            ],
            "related_parts": ["oil pump", "oil filter", "bearing", "oil pressure sensor", "seal"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "High engine oil pressure",
            "system": "lubrication_system",
            "diagnosis_steps": [
                "Check oil viscosity (wrong grade used)",
                "Inspect oil pressure relief valve for sticking",
                "Check for blocked oil passages",
                "Test oil pressure sending unit accuracy",
            ],
            "related_parts": ["oil filter", "oil pump", "oil pressure sensor"],
            "vehicle_type": "LMV/HMV",
        },
        # From Learning Outcome 17 — Steering/Suspension (page 23)
        {
            "symptom": "Abnormal tire wear",
            "system": "suspension_steering",
            "diagnosis_steps": [
                "Check tire pressure",
                "Inspect wheel alignment (toe, camber, caster)",
                "Check suspension components for wear",
                "Inspect ball joints and tie rod ends",
                "Check wheel bearings for play",
            ],
            "related_parts": ["ball joint", "tie rod", "shock absorber", "spring", "bearing"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Wheel wobbling",
            "system": "suspension_steering",
            "diagnosis_steps": [
                "Check wheel balance",
                "Inspect wheel bearings",
                "Check tire for bulge or damage",
                "Inspect suspension bushings",
                "Check wheel rim for runout",
            ],
            "related_parts": ["bearing", "ball joint", "tie rod", "shock absorber"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Poor self-centering of steering",
            "system": "suspension_steering",
            "diagnosis_steps": [
                "Check caster angle alignment",
                "Inspect steering column and U-joints",
                "Check power steering fluid level and pump",
                "Inspect tie rod ends and ball joints",
                "Check for binding in steering gear",
            ],
            "related_parts": ["power steering pump", "tie rod", "ball joint", "steering rack"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Hard steering",
            "system": "suspension_steering",
            "diagnosis_steps": [
                "Check power steering fluid level",
                "Inspect power steering pump and belt",
                "Check for air in power steering system",
                "Inspect steering gear/rack for damage",
                "Check tire pressure (low pressure causes hard steering)",
                "Inspect ball joints and tie rod ends",
            ],
            "related_parts": ["power steering pump", "fan belt", "steering rack", "ball joint", "tie rod"],
            "vehicle_type": "LMV/HMV",
        },
        # From Learning Outcome 23 — Electrical accessories (page 25)
        {
            "symptom": "No horn / poor horn / continuous horn",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Check horn fuse",
                "Test horn relay operation",
                "Check horn switch (steering wheel)",
                "Inspect wiring from relay to horn",
                "Test horn unit with direct battery power",
                "Check ground connection",
            ],
            "related_parts": ["horn", "fuse", "relay", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Wiper not operating / continuous operation / intermittent failure",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Check wiper fuse",
                "Test wiper switch operation",
                "Inspect wiper motor with direct power",
                "Check wiper relay (intermittent mode)",
                "Inspect wiper linkage for binding",
                "Check washer pump if washer not working",
            ],
            "related_parts": ["wiper motor", "wiper blade", "fuse", "relay", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Power window not operating",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Check power window fuse",
                "Test window switch with multimeter",
                "Check window motor with direct power",
                "Inspect wiring harness in door",
                "Check window regulator mechanism",
            ],
            "related_parts": ["fuse", "relay", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Power door lock not operating",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Check door lock fuse",
                "Test door lock switch",
                "Check door lock actuator with direct power",
                "Inspect wiring in door harness",
                "Check central locking module",
            ],
            "related_parts": ["fuse", "relay", "solenoid", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Immobilizer / keyless entry not operating",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Check key fob battery",
                "Test key transponder signal",
                "Check immobilizer control module",
                "Inspect antenna coil around ignition",
                "Read error codes with diagnostic tool",
            ],
            "related_parts": ["ECU", "relay", "sensor"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Airbag warning light / error indication",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Read airbag system error codes with scan tool",
                "Check airbag module connectors",
                "Inspect clock spring in steering column",
                "Check seat belt pretensioner connections",
                "Inspect crash sensors",
            ],
            "related_parts": ["sensor", "ECU", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        # From Learning Outcome 24 — AC system (page 25)
        {
            "symptom": "AC system — no cooling",
            "system": "ac_system",
            "diagnosis_steps": [
                "Check refrigerant level/charge",
                "Inspect compressor clutch engagement",
                "Check compressor belt tension",
                "Test AC switch and wiring",
                "Inspect condenser for blockage",
                "Check blower motor operation",
            ],
            "related_parts": ["compressor", "condenser", "evaporator", "blower motor", "fan belt"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "AC system — intermittent cooling",
            "system": "ac_system",
            "diagnosis_steps": [
                "Check refrigerant level (low charge causes cycling)",
                "Inspect compressor clutch for slipping",
                "Test pressure switch operation",
                "Check for moisture in system (freeze at expansion valve)",
                "Inspect electrical connections",
            ],
            "related_parts": ["compressor", "evaporator", "sensor"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "AC system — insufficient cooling",
            "system": "ac_system",
            "diagnosis_steps": [
                "Check refrigerant charge with pressure gauges",
                "Inspect condenser for dirt/blockage",
                "Check cabin air filter",
                "Test compressor output",
                "Inspect evaporator for icing",
                "Check for air in system",
            ],
            "related_parts": ["compressor", "condenser", "evaporator", "air filter"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "AC system — abnormal noise from compressor/clutch",
            "system": "ac_system",
            "diagnosis_steps": [
                "Check compressor belt tension and condition",
                "Inspect compressor mounting bolts",
                "Check compressor clutch bearing",
                "Test compressor for internal damage",
                "Inspect magnetic clutch air gap",
            ],
            "related_parts": ["compressor", "fan belt", "bearing"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "AC high pressure gauge reading too high",
            "system": "ac_system",
            "diagnosis_steps": [
                "Check condenser fan operation",
                "Inspect condenser for blockage",
                "Check for overcharge of refrigerant",
                "Test expansion valve operation",
                "Check for air/non-condensable gas in system",
            ],
            "related_parts": ["condenser", "compressor", "evaporator"],
            "vehicle_type": "LMV/HMV",
        },
        # From MPFI/ECU section (page 24)
        {
            "symptom": "Check engine light / MIL lamp illuminated",
            "system": "engine",
            "diagnosis_steps": [
                "Read error codes with OBD-II scan tool",
                "Test reference voltage on sensor circuits",
                "Check wiring continuity per vehicle wiring diagram",
                "Repair or replace defective sensor/wiring",
                "Erase error memory and verify fix",
            ],
            "related_parts": ["ECU", "sensor", "wiring harness", "oxygen sensor"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Engine cranks but will not start (MPFI/ECU)",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Check fuel pump operation (listen for prime)",
                "Test fuel pressure at rail",
                "Check spark at plug",
                "Read ECU error codes",
                "Test crankshaft position sensor signal",
                "Check immobilizer system",
            ],
            "related_parts": ["fuel pump", "fuel injector", "spark plug", "ECU", "sensor"],
            "vehicle_type": "LMV/HMV",
        },
        # From trade syllabus — braking system (pages 50-51)
        {
            "symptom": "Brake pedal spongy / soft",
            "system": "braking_system",
            "diagnosis_steps": [
                "Check brake fluid level in reservoir",
                "Bleed hydraulic brake system (all four wheels)",
                "Inspect brake lines for leaks",
                "Check master cylinder for internal bypass",
                "Inspect brake hoses for swelling",
            ],
            "related_parts": ["master cylinder", "brake line", "brake fluid"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Vehicle pulling to one side during braking",
            "system": "braking_system",
            "diagnosis_steps": [
                "Check brake pad/shoe thickness on both sides",
                "Inspect for oil contamination on brake surface",
                "Check brake caliper for sticking",
                "Inspect brake hose for restriction",
                "Check tire pressure on both sides",
            ],
            "related_parts": ["brake pad", "brake shoe", "brake disc", "brake drum"],
            "vehicle_type": "LMV/HMV",
        },
        # From trade syllabus — clutch (page 34)
        {
            "symptom": "Clutch slipping (engine revs but vehicle slow)",
            "system": "transmission",
            "diagnosis_steps": [
                "Check clutch pedal free play adjustment",
                "Inspect clutch disc lining for wear",
                "Check pressure plate spring tension",
                "Inspect flywheel surface for glazing",
                "Check for oil leak on clutch disc",
            ],
            "related_parts": ["clutch plate", "clutch disc", "pressure plate", "flywheel"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Clutch dragging (hard to shift gears)",
            "system": "transmission",
            "diagnosis_steps": [
                "Adjust clutch pedal free play",
                "Check clutch hydraulic system for air",
                "Inspect clutch disc for warping",
                "Check release bearing operation",
                "Inspect pilot bearing",
            ],
            "related_parts": ["clutch plate", "clutch disc", "bearing", "master cylinder"],
            "vehicle_type": "LMV/HMV",
        },
        # From trade syllabus — cooling system (page 36)
        {
            "symptom": "Coolant leaking externally",
            "system": "cooling_system",
            "diagnosis_steps": [
                "Pressure test cooling system",
                "Inspect radiator hoses and clamps",
                "Check radiator for cracks or damage",
                "Inspect water pump weep hole",
                "Check heater core connections",
                "Inspect freeze plugs/core plugs",
            ],
            "related_parts": ["radiator", "water pump", "thermostat", "seal"],
            "vehicle_type": "LMV/HMV",
        },
        # From trade syllabus — emission (page 45)
        {
            "symptom": "Vehicle failing emission test (petrol)",
            "system": "exhaust_emission",
            "diagnosis_steps": [
                "Use engine gas analyser to measure CO/HC",
                "Check and replace air filter",
                "Inspect spark plugs for proper combustion",
                "Test catalytic converter efficiency",
                "Check PCV valve and crankcase ventilation",
                "Inspect oxygen sensor response",
            ],
            "related_parts": ["catalytic converter", "spark plug", "oxygen sensor", "PCV valve", "air filter"],
            "vehicle_type": "LMV/HMV",
        },
        # From trade syllabus — lighting (page 42)
        {
            "symptom": "Headlight misaligned / poor visibility at night",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Check headlight alignment with beam setter",
                "Inspect headlight mounting and adjusters",
                "Check for corroded or dim bulbs",
                "Inspect headlight lens for clouding/damage",
                "Check alternator charging voltage (dim at idle = low charge)",
            ],
            "related_parts": ["headlight", "alternator", "fuse"],
            "vehicle_type": "LMV/HMV",
        },
    ],
    "mechanic_diesel": [
        # From Learning Outcome 15 and trade syllabus (pages 17, 32)
        {
            "symptom": "Diesel engine not starting — mechanical causes",
            "system": "engine",
            "diagnosis_steps": [
                "Check fuel level in tank",
                "Bleed fuel system for air locks",
                "Check fuel filter for clogging",
                "Test compression pressure",
                "Inspect glow plugs (cold start aid)",
                "Check injection pump timing",
            ],
            "related_parts": ["fuel filter", "glow plug", "fuel pump", "fuel injector", "piston ring"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Diesel engine not starting — electrical causes",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check battery charge and connections",
                "Test starter motor cranking speed",
                "Check glow plug relay and timer",
                "Test glow plug resistance individually",
                "Inspect fuel cut-off solenoid",
            ],
            "related_parts": ["battery", "starter motor", "glow plug", "relay", "solenoid"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Diesel engine excessive black smoke",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Check air filter for restriction",
                "Inspect injector nozzles for proper spray pattern",
                "Check injection pump timing",
                "Test turbocharger boost pressure",
                "Inspect EGR valve operation",
                "Check for overloading",
            ],
            "related_parts": ["air filter", "fuel injector", "turbocharger", "EGR valve"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Diesel engine white smoke on startup",
            "system": "engine",
            "diagnosis_steps": [
                "Check glow plug operation (incomplete combustion)",
                "Test injection timing (retarded timing)",
                "Check for coolant entering combustion chamber",
                "Inspect head gasket",
                "Check cylinder compression",
            ],
            "related_parts": ["glow plug", "head gasket", "fuel injector", "thermostat"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Diesel engine knocking/detonation",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Check injection timing (too advanced)",
                "Test injector opening pressure",
                "Inspect injector nozzle spray pattern",
                "Check fuel quality",
                "Inspect for worn engine bearings",
            ],
            "related_parts": ["fuel injector", "fuel pump", "bearing"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "CRDI system fault",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Read error codes with diagnostic scan tool",
                "Check common rail pressure with scan tool",
                "Test rail pressure sensor",
                "Inspect high pressure pump",
                "Check injector return flow (back-leak test)",
                "Inspect fuel pressure regulator",
            ],
            "related_parts": ["ECU", "sensor", "fuel injector", "fuel pump"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Diesel engine high fuel consumption",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Check injector spray pattern and opening pressure",
                "Inspect air filter for restriction",
                "Check injection pump calibration",
                "Test turbocharger boost",
                "Check for fuel leaks",
                "Inspect exhaust back pressure",
            ],
            "related_parts": ["fuel injector", "air filter", "fuel pump", "turbocharger", "fuel filter"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Diesel engine overheating",
            "system": "cooling_system",
            "diagnosis_steps": [
                "Check coolant level and condition",
                "Test thermostat opening temperature",
                "Inspect radiator for blockage",
                "Check water pump flow",
                "Inspect fan belt and fan clutch",
                "Check injection timing (late timing causes overheating)",
                "Test for head gasket leak",
            ],
            "related_parts": ["radiator", "thermostat", "water pump", "fan belt", "head gasket", "coolant"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Diesel engine low power",
            "system": "engine",
            "diagnosis_steps": [
                "Check air filter restriction",
                "Test fuel supply pressure",
                "Check turbocharger operation and boost",
                "Test injection pump delivery",
                "Check exhaust system for restriction",
                "Test compression in all cylinders",
            ],
            "related_parts": ["air filter", "fuel pump", "turbocharger", "fuel injector", "exhaust manifold"],
            "vehicle_type": "LMV/HMV",
        },
        # Emission-related (pages 31-32)
        {
            "symptom": "Diesel vehicle failing emission test (high smoke)",
            "system": "exhaust_emission",
            "diagnosis_steps": [
                "Use diesel smoke meter to measure opacity",
                "Check and clean/replace air filter",
                "Test injector nozzles for wear",
                "Check injection timing",
                "Inspect EGR valve function",
                "Check turbocharger condition",
                "Inspect PCV valve and crankcase ventilation",
            ],
            "related_parts": ["air filter", "fuel injector", "EGR valve", "turbocharger", "PCV valve"],
            "vehicle_type": "LMV/HMV",
        },
        # Stationary/marine diesel (page 30)
        {
            "symptom": "Stationary diesel engine vibration",
            "system": "engine",
            "diagnosis_steps": [
                "Check engine mounting bolts and pads",
                "Inspect flywheel for balance",
                "Check fuel injection timing and balance",
                "Inspect crankshaft damper",
                "Check engine alignment with driven equipment",
            ],
            "related_parts": ["flywheel", "crankshaft", "fuel injector", "bearing"],
            "vehicle_type": "stationary",
        },
    ],
    "mechanic_auto_electrical": [
        # From pages 17-19, 27-30
        {
            "symptom": "Dashboard gauge malfunction (speedometer/fuel/temperature)",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Identify which gauge is faulty",
                "Check gauge fuse",
                "Test sending unit/sensor with multimeter",
                "Check wiring from sensor to gauge",
                "Compare gauge reading with standard parameters",
                "Replace defective gauge or sender",
            ],
            "related_parts": ["speedometer", "fuel gauge", "temperature gauge", "sensor", "fuse"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Engine cranks but hard to start (ignition fault)",
            "system": "ignition_system",
            "diagnosis_steps": [
                "Check spark plug condition and gap",
                "Test ignition coil primary and secondary winding",
                "Check ignition timing",
                "Inspect ballast resistor",
                "Test distributor cap and rotor (if fitted)",
                "Check high-tension leads for damage",
            ],
            "related_parts": ["spark plug", "ignition coil", "distributor"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Poor fuel economy (ignition-related)",
            "system": "ignition_system",
            "diagnosis_steps": [
                "Check spark plug condition (fouled/worn)",
                "Test ignition timing with timing light",
                "Check dwell angle",
                "Inspect distributor advance mechanism",
                "Test hall effect sensor signal",
            ],
            "related_parts": ["spark plug", "ignition coil", "distributor", "sensor"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Engine hard to start (fuel system electrical)",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Check fuel pump relay and fuse",
                "Test fuel pump voltage supply",
                "Inspect fuel level sensor signal to ECU",
                "Check injector circuit resistance",
                "Diagnose possible causes for hard or no start related to fuel system",
            ],
            "related_parts": ["fuel pump", "relay", "fuse", "fuel injector", "sensor"],
            "vehicle_type": "LMV/HMV",
        },
        # Starter motor diagnostics (page 29)
        {
            "symptom": "Starter motor not running",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check battery voltage under load",
                "Test starter solenoid click",
                "Check ignition switch and neutral safety switch",
                "Inspect starter motor brushes and commutator",
                "Check ground connection",
                "Test starter relay",
            ],
            "related_parts": ["starter motor", "battery", "solenoid", "relay", "fuse"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Starter motor runs but too slow (low torque)",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check battery state of charge",
                "Test battery cable voltage drop",
                "Inspect starter motor brushes for wear",
                "Check commutator condition",
                "Test ground strap resistance",
            ],
            "related_parts": ["battery", "starter motor", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Starter motor runs but not cranking engine",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Inspect starter drive (Bendix) for wear",
                "Check flywheel ring gear teeth",
                "Inspect starter mounting bolts",
                "Test starter motor free-running speed",
            ],
            "related_parts": ["starter motor", "flywheel"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Starter motor does not stop running",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check ignition switch return spring",
                "Inspect starter solenoid for sticking",
                "Check for welded solenoid contacts",
                "Disconnect battery immediately if motor won't stop",
            ],
            "related_parts": ["solenoid", "starter motor"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Starter motor grinding noise",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Inspect flywheel ring gear for damaged teeth",
                "Check starter drive (Bendix) mechanism",
                "Growler test rotor for shorts",
                "Check starter alignment with flywheel",
            ],
            "related_parts": ["starter motor", "flywheel", "bearing"],
            "vehicle_type": "LMV/HMV",
        },
        # Charging system (page 29-30)
        {
            "symptom": "Battery undercharge condition",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check alternator belt tension",
                "Test alternator output voltage",
                "Inspect alternator brushes and slip rings",
                "Check voltage regulator",
                "Test battery for internal shorts",
                "Check for parasitic current drain",
            ],
            "related_parts": ["alternator", "battery", "fan belt"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Battery no charge from alternator",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check alternator belt (broken or slipping)",
                "Test alternator field winding continuity",
                "Inspect rotor for ground or open circuit",
                "Check alternator diode rectifier",
                "Test voltage regulator",
                "Inspect wiring from alternator to battery",
            ],
            "related_parts": ["alternator", "fan belt", "fuse", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Battery overcharge condition",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Test voltage regulator output (should be 13.8-14.4V)",
                "Check for faulty voltage regulator (stuck closed)",
                "Inspect alternator for internal short",
                "Check battery for sulfation",
            ],
            "related_parts": ["alternator", "battery"],
            "vehicle_type": "LMV/HMV",
        },
        # Charging warning lamp issues (page 30)
        {
            "symptom": "Charge warning lamp does not glow when ignition on",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check warning lamp bulb",
                "Test alternator excitation circuit",
                "Check wiring from ignition to alternator",
                "Test voltage regulator",
            ],
            "related_parts": ["alternator", "fuse", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Charge warning lamp stays on while engine running",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check alternator belt tension",
                "Test alternator output at battery",
                "Inspect alternator diodes",
                "Check alternator field winding",
                "Test voltage regulator",
            ],
            "related_parts": ["alternator", "fan belt"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Charge warning lamp flickers",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check alternator belt for slipping",
                "Inspect alternator brush contact with slip rings",
                "Check wiring connections for looseness",
                "Test alternator diode condition",
            ],
            "related_parts": ["alternator", "fan belt", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        # Excessive battery drain (page 25)
        {
            "symptom": "Excessive key-off battery drain (parasitic draw)",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Measure parasitic draw with ammeter (should be <50mA)",
                "Pull fuses one at a time to isolate circuit",
                "Check for stuck relays",
                "Inspect interior lights, glove box light, trunk light",
                "Check aftermarket accessories",
                "Test door and hood switches",
            ],
            "related_parts": ["battery", "fuse", "relay", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        # MPFI/EDC diagnostics (page 30)
        {
            "symptom": "MPFI system — engine misfire",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Read error codes with scan tool",
                "Test individual injector resistance",
                "Check ignition coil output per cylinder",
                "Test spark plug condition",
                "Check compression per cylinder",
                "Inspect wiring to injectors and coils",
            ],
            "related_parts": ["fuel injector", "spark plug", "ignition coil", "ECU", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
        {
            "symptom": "Headlight not working / dim",
            "system": "body_electrical",
            "diagnosis_steps": [
                "Check headlight fuse",
                "Test headlight bulb",
                "Check headlight relay",
                "Inspect wiring and ground connections",
                "Test headlight switch",
                "Align headlights for proper focus",
            ],
            "related_parts": ["headlight", "fuse", "relay", "wiring harness"],
            "vehicle_type": "LMV/HMV",
        },
    ],
    "mechanic_two_three_wheeler": [
        # From pages 15, 17, 23, 26-33
        {
            "symptom": "Two-wheeler engine not starting",
            "system": "engine",
            "diagnosis_steps": [
                "Check fuel tap and fuel flow",
                "Inspect spark plug for spark",
                "Check engine kill switch position",
                "Test battery (for electric start models)",
                "Check compression",
                "Inspect carburetor for clogging",
            ],
            "related_parts": ["spark plug", "battery", "fuel filter", "carburetor"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler engine overheating",
            "system": "cooling_system",
            "diagnosis_steps": [
                "Check engine oil level",
                "Inspect cooling fins for blockage (air-cooled)",
                "Check coolant level (liquid-cooled)",
                "Inspect thermostat operation",
                "Check for lean fuel mixture",
                "Inspect ignition timing",
            ],
            "related_parts": ["thermostat", "radiator", "oil pump", "spark plug"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler poor pickup / acceleration",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Check air filter for clogging",
                "Inspect carburetor jets and float level",
                "Check spark plug condition",
                "Test compression pressure",
                "Inspect exhaust for blockage",
                "Check clutch for slipping",
            ],
            "related_parts": ["air filter", "carburetor", "spark plug", "clutch plate", "exhaust manifold"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler excessive vibration",
            "system": "engine",
            "diagnosis_steps": [
                "Check engine mounting bolts",
                "Inspect balancer shaft (if fitted)",
                "Check for misfiring cylinder",
                "Inspect chain/sprocket for wear",
                "Check wheel balance",
            ],
            "related_parts": ["bearing", "spark plug", "crankshaft"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler clutch slipping",
            "system": "transmission",
            "diagnosis_steps": [
                "Check clutch cable free play adjustment",
                "Inspect clutch plates for wear",
                "Check clutch spring tension",
                "Inspect clutch basket for notching",
                "Check engine oil level and type (wet clutch)",
            ],
            "related_parts": ["clutch plate", "clutch disc", "spring"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler clutch dragging (hard to shift)",
            "system": "transmission",
            "diagnosis_steps": [
                "Adjust clutch cable free play",
                "Check clutch plates for warping",
                "Inspect clutch hub and basket",
                "Check engine oil viscosity",
            ],
            "related_parts": ["clutch plate", "clutch disc"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler gear shifting difficulty",
            "system": "transmission",
            "diagnosis_steps": [
                "Check clutch adjustment",
                "Inspect gear shift linkage",
                "Check gear shift drum and forks",
                "Inspect gear dogs for rounding",
                "Check engine oil level",
            ],
            "related_parts": ["gearbox", "clutch plate"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler chain noise / snapping",
            "system": "transmission",
            "diagnosis_steps": [
                "Check chain slack/tension adjustment",
                "Inspect chain for wear and stretched links",
                "Check sprocket teeth for wear",
                "Inspect chain lubrication",
                "Check wheel alignment",
            ],
            "related_parts": ["drive shaft"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler brake squeal / poor braking",
            "system": "braking_system",
            "diagnosis_steps": [
                "Check brake shoe/pad thickness",
                "Inspect brake drum/disc for scoring",
                "Check brake cable/hydraulic line adjustment",
                "Inspect brake lever free play",
                "Check for oil contamination on brake surface",
            ],
            "related_parts": ["brake shoe", "brake pad", "brake drum", "brake disc"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler electrical system dim lights",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check battery charge and electrolyte level",
                "Test charging voltage at battery",
                "Inspect alternator/magneto output",
                "Check main fuse and ground connections",
                "Inspect regulator-rectifier",
            ],
            "related_parts": ["battery", "alternator", "fuse"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Three-wheeler engine misfiring",
            "system": "engine",
            "diagnosis_steps": [
                "Check spark plug condition",
                "Inspect ignition coil and HT lead",
                "Test CDI/TCI unit",
                "Check fuel supply and mixture",
                "Test compression",
            ],
            "related_parts": ["spark plug", "ignition coil"],
            "vehicle_type": "3W",
        },
        {
            "symptom": "Two-wheeler kick starter not engaging",
            "system": "engine",
            "diagnosis_steps": [
                "Inspect kick starter gear and return spring",
                "Check kick starter shaft splines",
                "Inspect idle gear and ratchet mechanism",
                "Check for seized components",
            ],
            "related_parts": ["spring"],
            "vehicle_type": "2W",
        },
        {
            "symptom": "Two-wheeler self-starter not working",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check battery voltage",
                "Test starter relay click",
                "Inspect starter motor brush condition",
                "Check starter motor wiring",
                "Test clutch/side-stand safety switch",
            ],
            "related_parts": ["battery", "starter motor", "relay"],
            "vehicle_type": "2W",
        },
    ],
    "mechanic_tractor": [
        # From pages 17, 25, 28, 32, 35-36
        {
            "symptom": "Tractor engine not starting",
            "system": "engine",
            "diagnosis_steps": [
                "Check fuel supply and bleed system",
                "Test battery and starter motor",
                "Check glow plug operation",
                "Test compression pressure",
                "Inspect fuel filters for water/contamination",
                "Check fuel injection pump timing",
            ],
            "related_parts": ["fuel filter", "glow plug", "battery", "starter motor", "fuel pump"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor engine overheating",
            "system": "cooling_system",
            "diagnosis_steps": [
                "Check coolant level",
                "Clean radiator fins and core",
                "Test thermostat",
                "Check water pump operation",
                "Inspect fan belt tension",
                "Check injection timing",
                "Inspect for radiator cap pressure loss",
            ],
            "related_parts": ["radiator", "thermostat", "water pump", "fan belt"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor low hydraulic lift power",
            "system": "hydraulic_system",
            "diagnosis_steps": [
                "Check hydraulic oil level",
                "Inspect hydraulic filter for clogging",
                "Test hydraulic pump pressure",
                "Check control valve for internal leaks",
                "Inspect lift cylinder seals",
                "Check PTO engagement",
            ],
            "related_parts": ["oil pump", "oil filter", "seal"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor PTO not engaging",
            "system": "hydraulic_system",
            "diagnosis_steps": [
                "Check PTO clutch adjustment",
                "Inspect PTO shaft splines",
                "Test PTO engagement mechanism",
                "Check hydraulic pressure to PTO clutch",
                "Inspect PTO seal and bearing",
            ],
            "related_parts": ["clutch plate", "bearing", "seal"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor steering heavy / wandering",
            "system": "suspension_steering",
            "diagnosis_steps": [
                "Check steering fluid level (power steering)",
                "Inspect steering linkage for wear",
                "Check front axle pivot pins and bushings",
                "Inspect tie rod ends",
                "Check tire pressure",
                "Test power steering pump",
            ],
            "related_parts": ["power steering pump", "tie rod", "bearing"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor clutch judder / vibration",
            "system": "transmission",
            "diagnosis_steps": [
                "Inspect clutch disc for oil contamination",
                "Check pressure plate for warping",
                "Inspect flywheel surface",
                "Check engine and transmission mounting",
                "Inspect clutch release bearing",
            ],
            "related_parts": ["clutch plate", "clutch disc", "pressure plate", "flywheel", "bearing"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor excessive exhaust smoke",
            "system": "fuel_system",
            "diagnosis_steps": [
                "Check air filter (black smoke = restricted air)",
                "Inspect injector nozzles",
                "Test injection timing",
                "Check fuel quality",
                "Inspect turbocharger (if fitted)",
                "Check valve clearances",
            ],
            "related_parts": ["air filter", "fuel injector", "turbocharger", "valve"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor transmission noise",
            "system": "transmission",
            "diagnosis_steps": [
                "Check transmission oil level and condition",
                "Inspect gear teeth for wear or damage",
                "Check bearing condition",
                "Inspect shift forks for wear",
                "Check input/output shaft play",
            ],
            "related_parts": ["gearbox", "bearing", "seal"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor brakes not holding",
            "system": "braking_system",
            "diagnosis_steps": [
                "Adjust brake pedal free play",
                "Inspect brake shoes/discs for wear",
                "Check brake linkage adjustment",
                "Inspect brake drum for scoring",
                "Check for oil contamination on brake surfaces",
                "Bleed hydraulic brake system if fitted",
            ],
            "related_parts": ["brake shoe", "brake disc", "brake drum", "master cylinder"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor battery not charging",
            "system": "electrical_system",
            "diagnosis_steps": [
                "Check alternator belt tension and condition",
                "Test alternator output voltage",
                "Inspect wiring from alternator to battery",
                "Test voltage regulator",
                "Check battery terminals for corrosion",
            ],
            "related_parts": ["alternator", "battery", "fan belt", "fuse"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor implement not lifting evenly",
            "system": "hydraulic_system",
            "diagnosis_steps": [
                "Check hydraulic lift arm adjustment",
                "Inspect lift cylinder for leaks",
                "Check control valve spool centering",
                "Inspect draft control linkage",
                "Check for bent lift rod",
            ],
            "related_parts": ["seal", "oil pump"],
            "vehicle_type": "tractor",
        },
        {
            "symptom": "Tractor engine hard to start in cold weather",
            "system": "engine",
            "diagnosis_steps": [
                "Test glow plug operation and timer relay",
                "Check battery cold cranking amps",
                "Use correct viscosity engine oil for temperature",
                "Check fuel for wax/paraffin (diesel gelling)",
                "Inspect intake air preheater",
            ],
            "related_parts": ["glow plug", "battery", "starter motor", "fuel filter"],
            "vehicle_type": "tractor",
        },
    ],
    "mechanic_electric_vehicle": [
        # From pages 14-19, 29-42
        {
            "symptom": "EV not starting / no power",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check high voltage battery state of charge",
                "Inspect main contactor operation",
                "Check 12V auxiliary battery",
                "Test key switch and vehicle controller",
                "Check for error codes on dashboard",
                "Inspect high voltage interlocks",
            ],
            "related_parts": ["high voltage battery", "battery", "ECU"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV reduced range / battery draining fast",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check individual cell voltages in battery pack",
                "Test BMS operation and cell balancing",
                "Inspect for parasitic power drains",
                "Check tire pressure (affects range significantly)",
                "Monitor regenerative braking operation",
                "Check ambient temperature effect on battery",
            ],
            "related_parts": ["high voltage battery", "BMS", "motor controller"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV motor not running / jerky operation",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check motor controller for error codes",
                "Test motor winding resistance (phase to phase)",
                "Inspect motor controller connections",
                "Check hall sensor signals (BLDC motor)",
                "Test throttle position sensor",
                "Inspect motor temperature sensor",
            ],
            "related_parts": ["motor controller", "BLDC motor", "sensor", "inverter"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV not charging / slow charging",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check charging port and cable connection",
                "Inspect onboard charger for faults",
                "Test AC supply voltage to charger",
                "Check BMS communication with charger",
                "Inspect charging pilot signal",
                "Test isolation resistance of HV system",
            ],
            "related_parts": ["charger", "charging port", "BMS", "high voltage battery"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV high voltage warning / isolation fault",
            "system": "ev_system",
            "diagnosis_steps": [
                "Test isolation resistance with megger",
                "Inspect HV cable insulation",
                "Check for moisture in HV connectors",
                "Inspect motor winding insulation",
                "Check battery pack for coolant leak (liquid-cooled)",
                "Follow HV safety procedures (de-energize before inspection)",
            ],
            "related_parts": ["high voltage battery", "wiring harness", "BLDC motor"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV regenerative braking not working",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check motor controller settings",
                "Test brake pedal sensor signal",
                "Inspect motor winding connections",
                "Check BMS for charge limit reached",
                "Test controller CAN bus communication",
            ],
            "related_parts": ["motor controller", "BMS", "sensor"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV battery overheating",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check battery cooling system (fan/liquid)",
                "Test battery temperature sensors",
                "Inspect for cell imbalance in BMS",
                "Check for excessive charging/discharging rate",
                "Inspect coolant level and pump (liquid-cooled)",
                "Reduce load and allow cool-down",
            ],
            "related_parts": ["high voltage battery", "BMS", "sensor", "water pump"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV abnormal noise from motor",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check motor mounting bolts",
                "Inspect motor bearings for wear",
                "Test motor phase current balance",
                "Check for debris in motor housing",
                "Inspect reduction gear (if fitted)",
            ],
            "related_parts": ["BLDC motor", "bearing", "inverter"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV 12V auxiliary battery draining",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check DC-DC converter operation",
                "Test 12V battery health",
                "Inspect for parasitic draws on 12V system",
                "Check if main HV system enters sleep mode properly",
                "Test auxiliary battery charging voltage",
            ],
            "related_parts": ["battery", "inverter", "fuse"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV dashboard warning lights — multiple errors",
            "system": "ev_system",
            "diagnosis_steps": [
                "Read all error codes with EV diagnostic tool",
                "Check CAN bus communication between controllers",
                "Inspect main fuse and contactor",
                "Check 12V supply to instrument cluster",
                "Inspect HV battery management system status",
            ],
            "related_parts": ["ECU", "BMS", "fuse", "wiring harness"],
            "vehicle_type": "EV",
        },
        {
            "symptom": "EV power loss during driving",
            "system": "ev_system",
            "diagnosis_steps": [
                "Check battery SOC and cell voltages",
                "Monitor motor controller temperature",
                "Test throttle position sensor",
                "Check for thermal derating (overheated battery or motor)",
                "Inspect motor phase connections",
            ],
            "related_parts": ["high voltage battery", "motor controller", "sensor", "BLDC motor"],
            "vehicle_type": "EV",
        },
    ],
}


# ---------------------------------------------------------------------------
# PDF-extracted chain augmentation
# ---------------------------------------------------------------------------

def _extract_chains_from_text(pages: list[tuple[int, str]], trade_key: str) -> list[dict]:
    """Extract additional diagnostic chains from PDF text using pattern matching.

    This supplements the structured data above with chains found by parsing
    the actual PDF text for diagnostic patterns.
    """
    chains = []
    trade_name = ITI_SYLLABI[trade_key]["trade"]

    # Combine all pages into sections based on diagnostic keywords
    for page_num, text in pages:
        if not DIAGNOSTIC_PATTERN.search(text):
            continue

        # Extract symptom-like phrases
        # Pattern: "Diagnose for [symptom]" or "Troubleshoot [problem]"
        symptom_patterns = [
            r'[Dd]iagnos[ei]s?\s+(?:for\s+|the\s+|&\s+rectif\w+\s+)?(.+?)(?:\.|$)',
            r'[Tt]roubleshoot(?:ing)?\s+(?:the\s+|for\s+|in\s+)?(.+?)(?:\.|$)',
            r'[Cc]arryout\s+the\s+(?:recommended\s+)?troubl?e?\s*shoot(?:ing)?\s+procedure\s+(?:as\s+per\s+\w+\s+manual\s+)?for\s*[:\-]?\s*(.+?)(?:\.|$)',
            r'[Cc]auses?\s+and\s+remed(?:y|ies)\s+for\s*[:\-]?\s*(.+?)(?:\.|$)',
            r'[Ff]ault\s+find(?:ing)?\s+(?:in|for|of)\s+(.+?)(?:\.|$)',
        ]

        for pattern in symptom_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                symptom_text = match.group(1).strip()
                # Clean up the symptom text
                symptom_text = re.sub(r'\s+', ' ', symptom_text)
                symptom_text = symptom_text.rstrip(',;:- ')
                # Filter low-quality extractions
                if len(symptom_text) < 15 or len(symptom_text) > 100:
                    continue
                # Skip if it's just a reference or instruction, not a symptom
                skip_words = ['workshop manual', 'carryout', 'carry out', 'perform',
                              'ascertain', 'procedure as', 'NOS:', 'ASC/N',
                              'ensure functionality', 'plan and', 'coverings',
                              'throughout', 'removal and replacement',
                              'replace the pump if', 'the defects']
                if any(sw.lower() in symptom_text.lower() for sw in skip_words):
                    continue
                # Must start with a reasonable word (not "the", "a", "-", etc.)
                if re.match(r'^[\-\s]*(?:the|a|an|and|or|of|in|for|to)\s', symptom_text, re.IGNORECASE):
                    continue
                if symptom_text.startswith('-') or symptom_text.startswith('–'):
                    continue
                # Skip entries with page numbers or garbled text
                if re.search(r'\d{2}\s*$', symptom_text):
                    continue
                # Skip entries that look like section headings, not symptoms
                if any(h in symptom_text.lower() for h in [
                    'identify type', 'operate standard', 'requirement for',
                    'electronic valves', 'servo motors', 'automatic seat belt',
                    'diagnose air bag', 'engine for engine', 'corrective action',
                    'troubles and defects', 'low/high engine vehicle',
                ]):
                    continue
                # Clean up list-style symptoms (a) b) c) format)
                if symptom_text.startswith('a)'):
                    items = re.findall(r'[a-z]\)\s*([^a-z\)]+)', symptom_text)
                    if items:
                        symptom_text = '; '.join(i.strip().rstrip(',') for i in items if len(i.strip()) > 3)
                        if not symptom_text:
                            continue
                # Must contain at least one diagnostic-relevant word
                relevance_words = ['not', 'no ', 'low', 'high', 'poor', 'excessive',
                                   'abnormal', 'noise', 'leak', 'fail', 'fault',
                                   'defect', 'overheat', 'vibrat', 'wear', 'slow',
                                   'hard', 'dim', 'weak', 'stuck', 'slip', 'drag',
                                   'misfire', 'smoke', 'stall', 'idle', 'rough',
                                   'drain', 'charge', 'cool', 'start', 'crank',
                                   'warning', 'error', 'trouble']
                if not any(rw in symptom_text.lower() for rw in relevance_words):
                    continue

                # Get surrounding context for parts/steps extraction
                start = max(0, match.start() - 200)
                end = min(len(text), match.end() + 500)
                context = text[start:end]

                system = _classify_system(context)
                parts = _extract_parts(context)

                chain = {
                    "symptom": symptom_text,
                    "system": system,
                    "diagnosis_steps": [],  # PDF text rarely has clean step lists
                    "related_parts": parts,
                    "source_trade": trade_name,
                    "source_page": page_num,
                    "vehicle_type": _infer_vehicle_type(trade_key),
                    "confidence": 0.6,  # Lower confidence for auto-extracted
                }
                chains.append(chain)

    return chains


def _infer_vehicle_type(trade_key: str) -> str:
    """Infer vehicle type from trade key."""
    mapping = {
        "mechanic_motor_vehicle": "LMV/HMV",
        "mechanic_diesel": "LMV/HMV",
        "mechanic_auto_electrical": "LMV/HMV",
        "mechanic_two_three_wheeler": "2W/3W",
        "mechanic_tractor": "tractor",
        "mechanic_electric_vehicle": "EV",
    }
    return mapping.get(trade_key, "")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def parse_iti_diagnostics(pdf_dir: Path = ITI_PDF_DIR) -> list[dict]:
    """Parse all ITI syllabus PDFs and extract diagnostic chains.

    Returns a list of diagnostic chain dicts.
    """
    all_chains = []
    seen_symptoms = set()

    # Step 1: Add all structured diagnostic chains
    for trade_key, chains in STRUCTURED_DIAGNOSTICS.items():
        trade_name = ITI_SYLLABI[trade_key]["trade"]
        for chain_data in chains:
            symptom = chain_data["symptom"]
            chain_id = f"diag:{_make_id(symptom)}"

            if chain_id in seen_symptoms:
                continue
            seen_symptoms.add(chain_id)

            chain = {
                "id": chain_id,
                "symptom": symptom,
                "system": chain_data["system"],
                "diagnosis_steps": chain_data["diagnosis_steps"],
                "related_parts": chain_data["related_parts"],
                "source_trade": trade_name,
                "source_page": chain_data.get("source_page", 0),
                "vehicle_type": chain_data.get("vehicle_type", ""),
                "confidence": 0.8,
            }
            all_chains.append(chain)

    # Step 2: Parse PDFs for additional chains
    for trade_key, info in ITI_SYLLABI.items():
        pdf_path = pdf_dir / f"{trade_key}.pdf"
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            continue

        logger.info(f"Parsing {info['trade']} ({pdf_path.name})...")
        pages = _extract_full_text(pdf_path)
        pdf_chains = _extract_chains_from_text(pages, trade_key)

        for chain in pdf_chains:
            chain_id = f"diag:{_make_id(chain['symptom'])}"
            if chain_id in seen_symptoms:
                continue
            seen_symptoms.add(chain_id)
            chain["id"] = chain_id
            all_chains.append(chain)

        logger.info(f"  {info['trade']}: {len(pdf_chains)} additional chains from PDF text")

    logger.info(f"Total diagnostic chains: {len(all_chains)}")
    return all_chains


def save_diagnostics(chains: list[dict], output_path: Path) -> None:
    """Save diagnostic chains to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build summary stats
    systems = {}
    vehicle_types = {}
    for chain in chains:
        s = chain["system"]
        systems[s] = systems.get(s, 0) + 1
        vt = chain["vehicle_type"]
        vehicle_types[vt] = vehicle_types.get(vt, 0) + 1

    output = {
        "metadata": {
            "description": "Diagnostic chains extracted from DGT ITI syllabi",
            "source": "iti_dgt",
            "trades": [info["trade"] for info in ITI_SYLLABI.values()],
            "total_chains": len(chains),
            "chains_by_system": dict(sorted(systems.items(), key=lambda x: -x[1])),
            "chains_by_vehicle_type": dict(sorted(vehicle_types.items(), key=lambda x: -x[1])),
        },
        "chains": chains,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(chains)} diagnostic chains to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # Download PDFs if needed
    download_pdfs()

    # Parse and extract diagnostic chains
    chains = parse_iti_diagnostics()

    # Save output
    output_file = KNOWLEDGE_GRAPH_DIR / "iti_diagnostics.json"
    save_diagnostics(chains, output_file)

    # Summary
    print(f"\nDone. {len(chains)} diagnostic chains saved to {output_file}")
    print("\nChains by system:")
    systems = {}
    for c in chains:
        s = c["system"]
        systems[s] = systems.get(s, 0) + 1
    for system, count in sorted(systems.items(), key=lambda x: -x[1]):
        print(f"  {system}: {count}")
    print(f"\nChains by vehicle type:")
    vtypes = {}
    for c in chains:
        vt = c["vehicle_type"]
        vtypes[vt] = vtypes.get(vt, 0) + 1
    for vtype, count in sorted(vtypes.items(), key=lambda x: -x[1]):
        print(f"  {vtype}: {count}")
