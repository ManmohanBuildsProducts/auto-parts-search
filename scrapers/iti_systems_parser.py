"""ITI Syllabus parser for vehicle system → parts mappings.

Extracts which parts belong to which vehicle system, based on DGT ITI
syllabi content. Complements iti_scraper.py (T103 diagnostic chains) with
system-level part decomposition for the knowledge graph.

Output: data/knowledge_graph/iti_systems.json

Design: ADR-002 (context/decisions/002-data-sources.md)
"""
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR

logger = logging.getLogger(__name__)

ITI_PDF_DIR = KNOWLEDGE_GRAPH_DIR / "iti_pdfs"

# ---------------------------------------------------------------------------
# Vehicle system definitions extracted from ITI syllabi
# ---------------------------------------------------------------------------
# These mappings are derived from the Learning Outcomes in ITI syllabi:
# - Mechanic Motor Vehicle (MMV): LO 5-24 cover all major vehicle systems
# - Mechanic Diesel: LO 3-18 cover diesel-specific systems
# - Mechanic Auto Electrical: LO 3-20 cover electrical/electronic systems
# - Mechanic Two & Three Wheeler: LO 3-16 cover 2W/3W systems
# - Mechanic Tractor: LO 3-14 cover tractor/agricultural systems
# - Mechanic Electric Vehicle: LO 3-18 cover EV systems

VEHICLE_SYSTEMS = [
    {
        "system_name": "Engine",
        "system_id": "system:engine",
        "description": "Internal combustion engine — converts fuel energy to mechanical motion. Covers cylinder block, valve train, and rotating assembly.",
        "parts": [
            {"name": "Piston", "aliases": ["piston assembly"], "role": "Converts combustion pressure to linear motion"},
            {"name": "Piston Ring", "aliases": ["compression ring", "oil ring", "piston ring set"], "role": "Seals combustion chamber, controls oil"},
            {"name": "Connecting Rod", "aliases": ["con rod"], "role": "Transfers piston motion to crankshaft"},
            {"name": "Crankshaft", "aliases": ["crank shaft"], "role": "Converts reciprocating to rotary motion"},
            {"name": "Camshaft", "aliases": ["cam shaft"], "role": "Actuates intake/exhaust valves via lobes"},
            {"name": "Cylinder Head", "aliases": ["cylinder head assembly"], "role": "Seals top of cylinder, houses valves"},
            {"name": "Cylinder Head Gasket", "aliases": ["head gasket"], "role": "Seals joint between block and head"},
            {"name": "Valve", "aliases": ["intake valve", "exhaust valve", "engine valve"], "role": "Controls gas flow in/out of cylinder"},
            {"name": "Valve Guide", "aliases": [], "role": "Guides valve stem for alignment"},
            {"name": "Valve Seat", "aliases": ["valve seat insert"], "role": "Sealing surface for valve face"},
            {"name": "Valve Spring", "aliases": [], "role": "Returns valve to closed position"},
            {"name": "Rocker Arm", "aliases": ["rocker"], "role": "Transfers cam motion to valve"},
            {"name": "Pushrod", "aliases": ["push rod"], "role": "Transfers lifter motion to rocker arm (OHV engines)"},
            {"name": "Timing Chain", "aliases": ["timing belt", "cam chain", "cam belt"], "role": "Synchronizes crankshaft and camshaft rotation"},
            {"name": "Tensioner", "aliases": ["chain tensioner", "belt tensioner"], "role": "Maintains timing chain/belt tension"},
            {"name": "Flywheel", "aliases": ["fly wheel"], "role": "Stores rotational energy, smooths power delivery"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV", "2W", "3W", "tractor"],
    },
    {
        "system_name": "Fuel System",
        "system_id": "system:fuel_system",
        "description": "Stores, delivers, and meters fuel to the engine. Covers carburetion, fuel injection (MPFI/CRDI), and fuel supply.",
        "parts": [
            {"name": "Fuel Pump", "aliases": ["fuel delivery pump", "lift pump"], "role": "Delivers fuel from tank to engine"},
            {"name": "Fuel Filter", "aliases": ["fuel strainer", "diesel filter"], "role": "Removes contaminants from fuel"},
            {"name": "Fuel Injector", "aliases": ["injector", "nozzle", "injection nozzle"], "role": "Sprays metered fuel into combustion chamber"},
            {"name": "Carburetor", "aliases": ["carburettor", "carb"], "role": "Mixes fuel with air (older engines)"},
            {"name": "Fuel Tank", "aliases": ["petrol tank", "diesel tank"], "role": "Stores fuel"},
            {"name": "Fuel Line", "aliases": ["fuel pipe", "fuel hose"], "role": "Routes fuel between components"},
            {"name": "Air Filter", "aliases": ["air cleaner", "air filter element"], "role": "Filters intake air to engine"},
            {"name": "Throttle Body", "aliases": ["throttle valve"], "role": "Controls airflow to engine"},
            {"name": "Fuel Pressure Regulator", "aliases": ["pressure regulator"], "role": "Maintains constant fuel rail pressure"},
            {"name": "Injection Pump", "aliases": ["diesel injection pump", "FIP", "fuel injection pump"], "role": "Pressurizes and times diesel fuel delivery"},
        ],
        "source_trade": "Mechanic Diesel",
        "vehicle_types": ["LMV", "HMV", "2W", "3W", "tractor"],
    },
    {
        "system_name": "Cooling System",
        "system_id": "system:cooling_system",
        "description": "Maintains engine operating temperature by transferring excess heat. Covers liquid cooling and air cooling components.",
        "parts": [
            {"name": "Radiator", "aliases": ["radiator assembly", "radiator core"], "role": "Dissipates heat from coolant to air"},
            {"name": "Thermostat", "aliases": ["thermostat valve"], "role": "Regulates coolant flow based on temperature"},
            {"name": "Water Pump", "aliases": ["coolant pump"], "role": "Circulates coolant through engine and radiator"},
            {"name": "Coolant", "aliases": ["antifreeze", "coolant fluid"], "role": "Heat transfer fluid"},
            {"name": "Fan Belt", "aliases": ["drive belt", "V-belt", "serpentine belt"], "role": "Drives water pump and fan from crankshaft"},
            {"name": "Cooling Fan", "aliases": ["radiator fan", "electric fan"], "role": "Draws air through radiator"},
            {"name": "Radiator Cap", "aliases": ["pressure cap"], "role": "Maintains cooling system pressure"},
            {"name": "Radiator Hose", "aliases": ["coolant hose", "upper hose", "lower hose"], "role": "Routes coolant between engine and radiator"},
            {"name": "Expansion Tank", "aliases": ["overflow tank", "reservoir tank", "coolant reservoir"], "role": "Stores excess coolant during expansion"},
            {"name": "Temperature Sensor", "aliases": ["coolant temperature sensor", "CTS"], "role": "Sends temperature reading to ECU/gauge"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV", "tractor"],
    },
    {
        "system_name": "Lubrication System",
        "system_id": "system:lubrication_system",
        "description": "Reduces friction and wear between moving parts by supplying pressurized oil. Covers oil pump, filtration, and galleries.",
        "parts": [
            {"name": "Oil Pump", "aliases": ["engine oil pump"], "role": "Pressurizes and circulates engine oil"},
            {"name": "Oil Filter", "aliases": ["oil filter element"], "role": "Removes contaminants from engine oil"},
            {"name": "Oil Pressure Sensor", "aliases": ["oil pressure switch", "oil pressure sending unit"], "role": "Monitors oil pressure for warning system"},
            {"name": "Oil Pan", "aliases": ["sump", "oil sump"], "role": "Stores engine oil at bottom of engine"},
            {"name": "Oil Cooler", "aliases": [], "role": "Cools engine oil in heavy-duty applications"},
            {"name": "PCV Valve", "aliases": ["positive crankcase ventilation valve"], "role": "Vents crankcase gases back to intake"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV", "tractor"],
    },
    {
        "system_name": "Braking System",
        "system_id": "system:braking_system",
        "description": "Decelerates and stops the vehicle. Covers disc brakes, drum brakes, hydraulic actuation, and ABS.",
        "parts": [
            {"name": "Brake Pad", "aliases": ["disc brake pad", "brake pad set"], "role": "Friction material pressed against disc rotor"},
            {"name": "Brake Shoe", "aliases": ["drum brake shoe", "brake shoe set"], "role": "Friction material pressed against drum"},
            {"name": "Brake Disc", "aliases": ["brake rotor", "disc rotor"], "role": "Rotating disc gripped by pads to slow wheel"},
            {"name": "Brake Drum", "aliases": ["drum"], "role": "Rotating drum pressed by shoes to slow wheel"},
            {"name": "Master Cylinder", "aliases": ["brake master cylinder", "TMC", "tandem master cylinder"], "role": "Converts pedal force to hydraulic pressure"},
            {"name": "Brake Caliper", "aliases": ["caliper", "caliper assembly"], "role": "Clamps pads against disc via hydraulic piston"},
            {"name": "Wheel Cylinder", "aliases": ["brake wheel cylinder"], "role": "Pushes shoes against drum via hydraulic pressure"},
            {"name": "Brake Line", "aliases": ["brake pipe", "brake hose"], "role": "Routes hydraulic fluid to wheel brakes"},
            {"name": "Brake Fluid", "aliases": ["DOT fluid", "hydraulic fluid"], "role": "Transmits hydraulic force in brake system"},
            {"name": "Brake Booster", "aliases": ["vacuum booster", "servo unit"], "role": "Amplifies brake pedal force using vacuum"},
            {"name": "ABS Module", "aliases": ["ABS unit", "anti-lock braking module"], "role": "Prevents wheel lock-up during hard braking"},
            {"name": "ABS Sensor", "aliases": ["wheel speed sensor"], "role": "Monitors wheel rotation speed for ABS"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV", "2W", "3W"],
    },
    {
        "system_name": "Suspension System",
        "system_id": "system:suspension",
        "description": "Absorbs road shocks and maintains tire contact with road surface. Covers springs, dampers, and linkages.",
        "parts": [
            {"name": "Shock Absorber", "aliases": ["damper", "shocker", "strut"], "role": "Dampens spring oscillation, controls body motion"},
            {"name": "Coil Spring", "aliases": ["suspension spring", "spring"], "role": "Absorbs road impact, supports vehicle weight"},
            {"name": "Leaf Spring", "aliases": ["leaf spring assembly", "multi-leaf spring"], "role": "Spring and locating member (trucks/rear axle)"},
            {"name": "Ball Joint", "aliases": ["ball joint assembly"], "role": "Pivot point connecting control arm to knuckle"},
            {"name": "Control Arm", "aliases": ["wishbone", "A-arm", "lower arm", "upper arm"], "role": "Links wheel assembly to vehicle frame"},
            {"name": "Stabilizer Bar", "aliases": ["sway bar", "anti-roll bar"], "role": "Reduces body roll in corners"},
            {"name": "Bushing", "aliases": ["rubber bush", "suspension bush", "silent block"], "role": "Isolates vibration at mounting points"},
            {"name": "Strut Mount", "aliases": ["top mount", "strut bearing"], "role": "Connects strut to body, allows rotation"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV", "2W", "3W"],
    },
    {
        "system_name": "Steering System",
        "system_id": "system:steering",
        "description": "Controls vehicle direction. Covers manual steering, power steering (hydraulic and electric), and wheel alignment.",
        "parts": [
            {"name": "Steering Rack", "aliases": ["rack and pinion", "steering gear"], "role": "Converts rotary steering input to linear wheel motion"},
            {"name": "Tie Rod", "aliases": ["tie rod end", "track rod", "tie rod assembly"], "role": "Links steering rack to steering knuckle"},
            {"name": "Power Steering Pump", "aliases": ["PS pump"], "role": "Provides hydraulic pressure for power assist"},
            {"name": "Power Steering Fluid", "aliases": ["PS fluid", "ATF"], "role": "Hydraulic medium for power steering"},
            {"name": "Steering Column", "aliases": ["steering shaft"], "role": "Connects steering wheel to steering gear"},
            {"name": "Steering Knuckle", "aliases": ["stub axle", "upright"], "role": "Carries wheel hub, pivots for steering"},
            {"name": "Steering Wheel", "aliases": [], "role": "Driver input device for direction control"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV", "3W"],
    },
    {
        "system_name": "Transmission System",
        "system_id": "system:transmission",
        "description": "Transmits engine power to wheels with variable speed/torque ratios. Covers clutch, gearbox, propeller shaft, differential, and axles.",
        "parts": [
            {"name": "Clutch Plate", "aliases": ["clutch disc", "friction plate", "driven plate"], "role": "Friction disc that engages/disengages engine from gearbox"},
            {"name": "Pressure Plate", "aliases": ["clutch cover", "clutch pressure plate"], "role": "Clamps clutch disc against flywheel"},
            {"name": "Release Bearing", "aliases": ["throwout bearing", "clutch bearing"], "role": "Disengages pressure plate when pedal pressed"},
            {"name": "Gearbox", "aliases": ["transmission", "gear box", "manual transmission"], "role": "Provides multiple gear ratios"},
            {"name": "Propeller Shaft", "aliases": ["drive shaft", "prop shaft", "cardan shaft"], "role": "Transmits power from gearbox to differential"},
            {"name": "Universal Joint", "aliases": ["U-joint", "UJ", "cross joint"], "role": "Allows angle changes in propeller shaft"},
            {"name": "Differential", "aliases": ["diff", "rear axle assembly"], "role": "Splits power to wheels, allows speed difference in turns"},
            {"name": "Axle Shaft", "aliases": ["half shaft", "drive axle"], "role": "Transmits power from differential to wheel"},
            {"name": "CV Joint", "aliases": ["constant velocity joint", "CV boot"], "role": "Allows power transmission at variable angles (FWD)"},
            {"name": "Clutch Cable", "aliases": ["clutch wire"], "role": "Mechanical linkage for clutch actuation"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV", "2W", "3W", "tractor"],
    },
    {
        "system_name": "Electrical System",
        "system_id": "system:electrical_system",
        "description": "Generates, stores, and distributes electrical power. Covers battery, charging, starting, ignition, and electronic control systems.",
        "parts": [
            {"name": "Battery", "aliases": ["car battery", "vehicle battery", "lead acid battery"], "role": "Stores electrical energy for starting and accessories"},
            {"name": "Alternator", "aliases": ["generator", "charging alternator"], "role": "Generates AC current, charges battery while running"},
            {"name": "Starter Motor", "aliases": ["starter", "self motor", "cranking motor"], "role": "Cranks engine for starting"},
            {"name": "Ignition Coil", "aliases": ["spark coil", "coil pack"], "role": "Steps up battery voltage for spark plug firing"},
            {"name": "Spark Plug", "aliases": ["sparking plug"], "role": "Ignites air-fuel mixture in cylinder"},
            {"name": "Glow Plug", "aliases": ["heater plug"], "role": "Pre-heats combustion chamber for diesel cold start"},
            {"name": "ECU", "aliases": ["ECM", "engine control unit", "engine control module"], "role": "Central computer managing engine operation"},
            {"name": "Fuse", "aliases": ["fuse box", "blade fuse"], "role": "Protects circuits from overcurrent"},
            {"name": "Relay", "aliases": ["automotive relay"], "role": "Electrically operated switch for high-current circuits"},
            {"name": "Wiring Harness", "aliases": ["wire harness", "loom"], "role": "Bundled wiring connecting all electrical components"},
            {"name": "Voltage Regulator", "aliases": ["regulator"], "role": "Maintains stable charging voltage from alternator"},
        ],
        "source_trade": "Mechanic Auto Electrical & Electronics",
        "vehicle_types": ["LMV", "HMV", "2W", "3W", "tractor"],
    },
    {
        "system_name": "Exhaust and Emission System",
        "system_id": "system:exhaust_emission",
        "description": "Routes exhaust gases out and reduces harmful emissions. Covers exhaust manifold, catalytic converter, EGR, and sensors.",
        "parts": [
            {"name": "Exhaust Manifold", "aliases": ["exhaust header"], "role": "Collects exhaust gases from cylinders"},
            {"name": "Catalytic Converter", "aliases": ["cat converter", "catalytic"], "role": "Reduces harmful exhaust emissions (CO, HC, NOx)"},
            {"name": "Silencer", "aliases": ["muffler", "exhaust silencer"], "role": "Reduces exhaust noise"},
            {"name": "Exhaust Pipe", "aliases": ["tail pipe", "exhaust tube"], "role": "Routes exhaust gases from manifold to tailpipe"},
            {"name": "Oxygen Sensor", "aliases": ["O2 sensor", "lambda sensor"], "role": "Monitors exhaust oxygen content for ECU fuel control"},
            {"name": "EGR Valve", "aliases": ["exhaust gas recirculation valve"], "role": "Recirculates exhaust gas to reduce NOx emissions"},
            {"name": "DPF", "aliases": ["diesel particulate filter", "soot filter"], "role": "Traps soot particles from diesel exhaust"},
            {"name": "Turbocharger", "aliases": ["turbo", "turbo charger"], "role": "Uses exhaust energy to compress intake air"},
            {"name": "Intake Manifold", "aliases": ["inlet manifold"], "role": "Distributes air/fuel mixture to cylinders"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV"],
    },
    {
        "system_name": "Body Electrical and Accessories",
        "system_id": "system:body_electrical",
        "description": "Vehicle lighting, signaling, comfort, and safety electronics. Covers lamps, wipers, power windows, instruments, and safety systems.",
        "parts": [
            {"name": "Headlight", "aliases": ["headlamp", "head light", "headlight assembly"], "role": "Illuminates road ahead"},
            {"name": "Tail Light", "aliases": ["tail lamp", "rear light", "rear lamp assembly"], "role": "Makes vehicle visible from rear"},
            {"name": "Indicator Light", "aliases": ["turn signal", "blinker", "indicator lamp"], "role": "Signals turning/lane change intention"},
            {"name": "Horn", "aliases": ["vehicle horn", "electric horn"], "role": "Audible warning device"},
            {"name": "Wiper Motor", "aliases": ["windshield wiper motor"], "role": "Drives wiper blade across windshield"},
            {"name": "Wiper Blade", "aliases": ["wiper rubber", "windshield wiper blade"], "role": "Clears rain/debris from windshield"},
            {"name": "Speedometer", "aliases": ["speedo", "speedometer cable"], "role": "Displays vehicle speed"},
            {"name": "Fuel Gauge", "aliases": ["fuel level sensor", "fuel sender unit"], "role": "Displays fuel tank level"},
            {"name": "Temperature Gauge", "aliases": ["temp gauge"], "role": "Displays engine coolant temperature"},
        ],
        "source_trade": "Mechanic Auto Electrical & Electronics",
        "vehicle_types": ["LMV", "HMV", "2W", "3W"],
    },
    {
        "system_name": "AC and Climate Control System",
        "system_id": "system:ac_system",
        "description": "Vehicle air conditioning and heating. Covers refrigeration cycle components and cabin air management.",
        "parts": [
            {"name": "Compressor", "aliases": ["AC compressor", "A/C compressor"], "role": "Compresses refrigerant gas to high pressure"},
            {"name": "Condenser", "aliases": ["AC condenser"], "role": "Cools and liquefies high-pressure refrigerant"},
            {"name": "Evaporator", "aliases": ["AC evaporator", "cooling coil"], "role": "Absorbs cabin heat as refrigerant evaporates"},
            {"name": "Expansion Valve", "aliases": ["TXV", "thermostatic expansion valve"], "role": "Meters refrigerant flow to evaporator"},
            {"name": "Blower Motor", "aliases": ["blower fan", "cabin fan"], "role": "Circulates air through evaporator into cabin"},
            {"name": "Receiver Drier", "aliases": ["drier", "accumulator"], "role": "Stores refrigerant and removes moisture"},
            {"name": "AC Compressor Clutch", "aliases": ["magnetic clutch"], "role": "Engages/disengages compressor from engine"},
            {"name": "Cabin Air Filter", "aliases": ["pollen filter", "AC filter"], "role": "Filters air entering the cabin"},
        ],
        "source_trade": "Mechanic Motor Vehicle",
        "vehicle_types": ["LMV", "HMV"],
    },
    {
        "system_name": "Electric Vehicle System",
        "system_id": "system:ev_system",
        "description": "EV-specific powertrain and energy systems. Covers traction motor, battery pack, power electronics, and charging.",
        "parts": [
            {"name": "Traction Motor", "aliases": ["electric motor", "BLDC motor", "hub motor", "drive motor"], "role": "Converts electrical energy to mechanical motion for propulsion"},
            {"name": "High Voltage Battery", "aliases": ["battery pack", "lithium battery", "traction battery"], "role": "Stores electrical energy for driving"},
            {"name": "Motor Controller", "aliases": ["inverter", "motor driver", "VCU"], "role": "Controls motor speed and torque via power electronics"},
            {"name": "BMS", "aliases": ["battery management system"], "role": "Monitors and balances battery cells, manages charging/discharging"},
            {"name": "DC-DC Converter", "aliases": ["auxiliary converter"], "role": "Steps down high voltage to 12V for vehicle accessories"},
            {"name": "Onboard Charger", "aliases": ["OBC", "AC charger"], "role": "Converts AC mains power to DC for battery charging"},
            {"name": "Charging Port", "aliases": ["charge socket", "charging inlet"], "role": "Physical connector for external charging"},
            {"name": "Regenerative Braking Module", "aliases": ["regen braking"], "role": "Recovers kinetic energy during braking"},
        ],
        "source_trade": "Mechanic Electric Vehicle",
        "vehicle_types": ["EV"],
    },
]

# Keywords to look for in PDF text to validate/enrich system mappings
_SYSTEM_SEARCH_PATTERNS = {
    "system:engine": [r"cylinder\s*block", r"valve\s*train", r"piston", r"crankshaft", r"camshaft", r"combustion"],
    "system:fuel_system": [r"fuel\s*injection", r"carbure?tor", r"CRDI", r"MPFI", r"fuel\s*pump", r"injector"],
    "system:cooling_system": [r"radiator", r"thermostat", r"coolant", r"water\s*pump", r"overheat"],
    "system:lubrication_system": [r"oil\s*pump", r"oil\s*filter", r"lubrication", r"oil\s*pressure"],
    "system:braking_system": [r"brake\s*pad", r"disc\s*brake", r"drum\s*brake", r"master\s*cylinder", r"ABS"],
    "system:suspension": [r"shock\s*absorber", r"leaf\s*spring", r"coil\s*spring", r"ball\s*joint"],
    "system:steering": [r"steering\s*rack", r"power\s*steering", r"tie\s*rod", r"rack\s*and\s*pinion"],
    "system:transmission": [r"clutch", r"gearbox", r"gear\s*box", r"differential", r"propeller\s*shaft"],
    "system:electrical_system": [r"battery", r"alternator", r"starter\s*motor", r"ignition\s*coil", r"ECU"],
    "system:exhaust_emission": [r"exhaust\s*manifold", r"catalytic", r"silencer", r"muffler", r"EGR"],
    "system:body_electrical": [r"headlight", r"wiper", r"horn", r"indicator", r"speedometer"],
    "system:ac_system": [r"compressor", r"condenser", r"evaporator", r"refrigerant", r"blower"],
    "system:ev_system": [r"traction\s*motor", r"battery\s*management", r"BMS", r"inverter", r"regenerative"],
}


# ---------------------------------------------------------------------------
# PDF text extraction (reuses pattern from iti_scraper.py)
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Clean up PDF extraction artifacts."""
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_full_text(pdf_path: Path) -> str:
    """Extract all text from a PDF, concatenated."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed, skipping PDF parsing")
        return ""

    all_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                all_text.append(_normalize_text(text))
    return " ".join(all_text)


def _scan_pdfs_for_parts(pdf_dir: Path) -> dict[str, set[str]]:
    """Scan available PDFs to find additional parts mentioned per system.

    Returns dict of system_id -> set of part names found in PDF text.
    """
    additional_parts: dict[str, set[str]] = {}

    # Part patterns to search for in PDF text
    part_patterns = [
        (r"fuel\s*rail", "Fuel Rail"),
        (r"throttle\s*position\s*sensor", "Throttle Position Sensor"),
        (r"MAP\s*sensor", "MAP Sensor"),
        (r"mass\s*air\s*flow", "Mass Air Flow Sensor"),
        (r"knock\s*sensor", "Knock Sensor"),
        (r"crank\s*(?:shaft\s*)?position\s*sensor", "Crankshaft Position Sensor"),
        (r"cam\s*(?:shaft\s*)?position\s*sensor", "Camshaft Position Sensor"),
        (r"idle\s*(?:air\s*)?control\s*valve", "Idle Control Valve"),
        (r"torsion\s*bar", "Torsion Bar"),
        (r"parking\s*brake", "Parking Brake"),
        (r"hand\s*brake", "Parking Brake"),
        (r"brake\s*proportioning\s*valve", "Brake Proportioning Valve"),
    ]

    # Map extra parts to their system
    part_to_system = {
        "Fuel Rail": "system:fuel_system",
        "Throttle Position Sensor": "system:fuel_system",
        "MAP Sensor": "system:fuel_system",
        "Mass Air Flow Sensor": "system:fuel_system",
        "Knock Sensor": "system:engine",
        "Crankshaft Position Sensor": "system:engine",
        "Camshaft Position Sensor": "system:engine",
        "Idle Control Valve": "system:fuel_system",
        "Torsion Bar": "system:suspension",
        "Parking Brake": "system:braking_system",
        "Brake Proportioning Valve": "system:braking_system",
    }

    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        logger.info("No PDFs available for enrichment scan")
        return additional_parts

    for pdf_path in pdf_files:
        logger.info(f"Scanning {pdf_path.name} for additional parts...")
        text = _extract_full_text(pdf_path)
        if not text:
            continue

        text_lower = text.lower()
        for pattern, part_name in part_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                system_id = part_to_system[part_name]
                additional_parts.setdefault(system_id, set()).add(part_name)

    return additional_parts


def _validate_systems_against_pdfs(pdf_dir: Path) -> dict[str, int]:
    """Check how many system keywords appear in PDFs. Returns system_id -> match count."""
    validation: dict[str, int] = {}
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        return validation

    # Concatenate all PDF text
    all_text = ""
    for pdf_path in pdf_files:
        all_text += " " + _extract_full_text(pdf_path)

    all_text_lower = all_text.lower()
    for system_id, patterns in _SYSTEM_SEARCH_PATTERNS.items():
        count = sum(1 for p in patterns if re.search(p, all_text_lower, re.IGNORECASE))
        validation[system_id] = count

    return validation


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_systems(pdf_dir: Path = ITI_PDF_DIR) -> dict:
    """Extract vehicle system → parts mappings.

    Uses structured knowledge from ITI syllabi, enriched with PDF text parsing
    when PDFs are available.
    """
    systems = []

    # Try to enrich from PDFs
    additional_parts = _scan_pdfs_for_parts(pdf_dir)
    validation = _validate_systems_against_pdfs(pdf_dir)

    for system_def in VEHICLE_SYSTEMS:
        system_id = system_def["system_id"]
        parts = list(system_def["parts"])

        # Add any PDF-discovered parts not already in the list
        if system_id in additional_parts:
            existing_names = {p["name"].lower() for p in parts}
            for part_name in sorted(additional_parts[system_id]):
                if part_name.lower() not in existing_names:
                    parts.append({
                        "name": part_name,
                        "aliases": [],
                        "role": f"Component of {system_def['system_name'].lower()}",
                    })

        systems.append({
            "system_name": system_def["system_name"],
            "system_id": system_id,
            "description": system_def["description"],
            "parts": parts,
            "source_trade": system_def["source_trade"],
            "vehicle_types": system_def["vehicle_types"],
        })

    # Build metadata
    total_parts = sum(len(s["parts"]) for s in systems)
    pdf_count = len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.exists() else 0

    output = {
        "metadata": {
            "description": "Vehicle system to component parts mappings from DGT ITI syllabi",
            "source": "iti_dgt",
            "total_systems": len(systems),
            "total_parts": total_parts,
            "parts_per_system": {s["system_name"]: len(s["parts"]) for s in systems},
            "pdfs_scanned": pdf_count,
            "pdf_validation": validation if validation else "no PDFs available",
        },
        "systems": systems,
    }

    return output


def save_systems(output: dict, output_path: Path) -> None:
    """Save system mappings to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {output['metadata']['total_systems']} systems "
                f"({output['metadata']['total_parts']} parts) to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    result = extract_systems()
    output_file = KNOWLEDGE_GRAPH_DIR / "iti_systems.json"
    save_systems(result, output_file)

    print(f"\nDone. {result['metadata']['total_systems']} vehicle systems "
          f"with {result['metadata']['total_parts']} total parts.")
    print("\nParts per system:")
    for name, count in result["metadata"]["parts_per_system"].items():
        print(f"  {name}: {count}")
