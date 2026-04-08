"""Generate embedding model training pairs from Indian auto parts vocabulary research.

Sources: /Users/mac/Projects/auto-parts-research/03_vocabulary_taxonomy.md
Covers: synonym pairs, misspelling pairs, symptom-to-part pairs, brand-as-generic pairs, negative pairs.
"""

import json
import random
import sys
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.schemas import TrainingPair

# ---------------------------------------------------------------------------
# 1. Synonym data: English <-> Hindi/Hinglish part name equivalences
#    Extracted from sections 1.1-1.9 of the research
# ---------------------------------------------------------------------------

SYNONYM_PAIRS_RAW: list[tuple[str, str]] = [
    # 1.1 Engine System
    ("engine", "injun"),
    ("piston", "piston"),
    ("spark plug", "baati"),
    ("carburetor", "carby"),
    ("air filter", "hawa ka filter"),
    ("fuel filter", "tel ka filter"),
    ("oil filter", "tel ka filter"),
    ("engine oil", "mobil"),
    ("turbocharger", "turbo"),
    ("ECU", "gaadi ka dimaag"),

    # 1.2 Braking System
    ("brake pad", "brake ki patti"),
    ("brake fluid", "brake oil"),
    ("handbrake", "side brake"),
    ("parking brake", "side brake"),
    ("brake booster", "servo brake"),

    # 1.3 Suspension & Steering
    ("shock absorber", "shocker"),
    ("strut", "shocker"),
    ("leaf spring", "katta"),
    ("power steering fluid", "power steering oil"),
    ("wheel alignment", "pahiyon ki setting"),
    ("wheel alignment", "alignment"),
    ("suspension knuckle", "makdi"),
    ("suspension spider", "makdi"),
    ("suspension knuckle", "gutkha"),
    ("wheel bearing", "bearing"),
    ("control arm", "agli bhuja"),

    # 1.4 Electrical System
    ("battery", "exide"),
    ("alternator", "dynamo"),
    ("starter motor", "self"),
    ("distributor", "delco"),
    ("wiring harness", "taar"),
    ("tail lamp", "pichli batti"),
    ("indicator", "palak"),
    ("turn signal", "palak"),
    ("radiator fan", "pankha"),
    ("cooling fan", "pankha"),
    ("wiper blade", "poncha"),

    # 1.5 Body Parts
    ("bonnet", "hood"),
    ("boot", "dikki"),
    ("trunk", "dikki"),
    ("spare tyre", "stepney"),
    ("spare wheel", "stepney"),
    ("fender", "mudguard"),
    ("windshield", "sheesha"),
    ("rear windshield", "pichla sheesha"),
    ("side mirror", "aaina"),
    ("side mirror", "ORVM"),
    ("roof", "chhat"),

    # 1.6 Transmission
    ("clutch plate", "clutch"),
    ("gearbox", "gear"),
    ("drive shaft", "shaft"),
    ("CV joint", "boot"),
    ("transmission oil", "gear oil"),

    # 1.7 Exhaust System
    ("silencer", "muffler"),
    ("exhaust pipe", "pipe"),
    ("catalytic converter", "cat"),

    # 1.8 Cooling System
    ("radiator", "tabla"),
    ("coolant", "paani"),

    # 1.9 Two-Wheeler Specific
    ("Royal Enfield", "bullet"),
    ("motorcycle", "bike"),

    # From Section 3.2 Workshop Slang
    ("shock absorber", "shock absorber"),
    ("self-starter", "self"),
    ("counterfeit part", "numberi part"),
    ("genuine OEM part", "company ka part"),
    ("aftermarket part", "duplicate"),
    ("wobbling", "bubbling"),
    ("4WD vehicle", "char paiya wali"),

    # British vs American English equivalences
    ("bonnet", "engine cover"),
    ("boot", "trunk"),
    ("silencer", "exhaust muffler"),
    ("dickey", "trunk"),
    ("dickey", "boot"),
    ("stepney", "spare wheel"),

    # Regional variations (Section 3.3)
    ("oil and filter change", "mobil and filter"),  # Kolkata
    ("brake pad", "brake cha pad"),  # Maharashtra Marathi

    # Vehicle-contextualized pairs
    ("swift ka shocker", "shock absorber for Maruti Swift"),
    ("i20 ka shocker", "shock absorber for Hyundai i20"),
    ("swift brake ki patti", "brake pad for Maruti Swift"),
    ("gaadi ki battery", "car battery"),
    ("gaadi ki light", "headlight bulb"),
    ("mobil oil", "engine oil"),
    ("klach set", "clutch set"),

    # Hinglish search queries (Section 2.6)
    ("maruti swift brake pad", "swift brake ki patti"),
    ("shocker", "shock absorber"),
    ("stepni", "spare tyre"),
    ("stefni", "spare tyre"),
    ("saailenser", "silencer"),
    ("hawa ka filter", "air filter"),
    ("poncha", "wiper blade"),

    # Additional cross-category synonym pairs from Quick Reference table
    ("engine oil", "motor oil"),
    ("brake pads", "brake ki patti"),
    ("shock absorber", "shock obsorber"),  # common variant

    # More body/exhaust synonyms
    ("bumper", "bumper"),
    ("door", "darwaza"),
    ("number plate", "registration plate"),
    ("horn", "bajane wala"),

    # More engine synonyms
    ("head gasket", "head gasket"),
    ("timing belt", "timing chain"),
    ("cylinder", "cylinder"),
    ("valves", "valve"),
    ("fuel injector", "fuel injector"),
    ("oil sump", "oil sump"),

    # Additional electrical
    ("headlight", "headlight"),
    ("fog lamp", "fog lamp"),
    ("AC compressor", "AC compressor"),
    ("wiper motor", "wiper motor"),
    ("fuse", "fuse"),
    ("relay", "relay"),

    # Additional brake system
    ("brake disc", "rotor"),
    ("brake drum", "brake drum"),
    ("brake shoe", "brake shoe"),
    ("brake caliper", "caliper"),
    ("master cylinder", "master cylinder"),
    ("wheel cylinder", "wheel cylinder"),
    ("ABS module", "ABS"),
    ("brake line", "brake pipe"),

    # Additional suspension
    ("ball joint", "ball joint"),
    ("tie rod end", "tie rod"),
    ("suspension spring", "spring"),
    ("steering rack", "steering rack"),
    ("steering column", "steering column"),
    ("power steering pump", "power steering pump"),

    # Additional transmission
    ("clutch cover", "pressure plate"),
    ("flywheel", "flywheel"),
    ("differential", "diff"),
    ("gear lever", "gear"),
    ("release bearing", "throw-out bearing"),

    # Additional cooling
    ("water pump", "water pump"),
    ("thermostat", "thermostat"),
    ("radiator cap", "radiator cap"),
    ("heater core", "heater"),

    # Additional two-wheeler
    ("engine guard", "crash guard"),
    ("chain set", "chain sprocket"),
    ("saree guard", "saree guard"),
    ("leg shield", "leg shield"),

    # Additional brand-as-generic cross-pairs
    ("Castrol", "engine oil"),
    ("Bosch plug", "spark plug"),
    ("NGK", "spark plug"),
    ("Dunlop", "tyre"),
    ("MRF", "tyre"),
    ("Servo brakes", "brake booster"),

    # More vehicle-contextualized pairs
    ("nexon ka shocker", "shock absorber for Tata Nexon"),
    ("alto ki battery", "battery for Maruti Alto"),
    ("bullet ka silencer", "silencer for Royal Enfield"),
    ("i20 ka brake pad", "brake pad for Hyundai i20"),
    ("scorpio ki leaf spring", "leaf spring for Mahindra Scorpio"),
    ("swift ki clutch plate", "clutch plate for Maruti Swift"),
    ("creta ka air filter", "air filter for Hyundai Creta"),
    ("baleno ka headlight", "headlight for Maruti Baleno"),
    ("city ka starter", "starter motor for Honda City"),
    ("innova ka radiator", "radiator for Toyota Innova"),
]

# ---------------------------------------------------------------------------
# 2. Misspelling data: Common misspellings -> correct terms
#    Extracted from sections 2.2-2.6 of the research
# ---------------------------------------------------------------------------

MISSPELLING_PAIRS_RAW: list[tuple[str, str]] = [
    # 2.2 Braking System Misspellings
    ("break pad", "brake pad"),
    ("brak pad", "brake pad"),
    ("brakpad", "brake pad"),
    ("brake ped", "brake pad"),
    ("brake pead", "brake pad"),
    ("break disk", "brake disc"),
    ("brake disk", "brake disc"),
    ("brakedisc", "brake disc"),
    ("break fluid", "brake fluid"),
    ("brake flued", "brake fluid"),
    ("brake flude", "brake fluid"),
    ("calliper", "caliper"),
    ("caliber", "caliper"),
    ("callipper", "caliper"),
    ("master sillinder", "master cylinder"),
    ("masster cylinder", "master cylinder"),

    # 2.3 Clutch & Transmission Misspellings
    ("klutch plate", "clutch plate"),
    ("clutch plet", "clutch plate"),
    ("cluch plate", "clutch plate"),
    ("clutchplate", "clutch plate"),
    ("clutch sett", "clutch set"),
    ("fly wheel", "flywheel"),
    ("fleewheel", "flywheel"),
    ("gear box", "gearbox"),
    ("geer box", "gearbox"),
    ("driveshaft", "drive shaft"),
    ("drive saft", "drive shaft"),

    # 2.4 Engine Parts Misspellings
    ("carburettor", "carburetor"),
    ("carburator", "carburetor"),
    ("carburatter", "carburetor"),
    ("carb", "carburetor"),
    ("alternater", "alternator"),
    ("altrnator", "alternator"),
    ("sparkplug", "spark plug"),
    ("spark plag", "spark plug"),
    ("thermostate", "thermostat"),
    ("themostat", "thermostat"),
    ("gaskot", "gasket"),
    ("gascet", "gasket"),
    ("injecter", "injector"),
    ("injektor", "injector"),

    # 2.5 Suspension Misspellings
    ("shock obsorber", "shock absorber"),
    ("shok absorber", "shock absorber"),
    ("boll joint", "ball joint"),
    ("tirod", "tie rod"),
    ("tie-rod end", "tie rod end"),
    ("wheel bering", "wheel bearing"),
    ("weel bearing", "wheel bearing"),

    # 2.6 Hinglish search misspellings
    ("stepni", "stepney"),
    ("stefni", "stepney"),
    ("klach set", "clutch set"),
    ("saailenser", "silencer"),
    ("klach plet", "clutch plate"),

    # Additional phonetic patterns from Section 2.1
    ("mufler", "muffler"),
    ("shok obsorber", "shock absorber"),
    ("brekpad", "brake pad"),
    ("brek pad", "brake pad"),
    ("breake pad", "brake pad"),
    ("sillencer", "silencer"),
    ("silensar", "silencer"),
    ("steepney", "stepney"),
    ("radiater", "radiator"),
    ("raditor", "radiator"),
    ("altenator", "alternator"),
    ("batree", "battery"),
    ("battry", "battery"),
    ("genrator", "generator"),
    ("stearing", "steering"),
    ("steeling", "steering"),
    ("suspention", "suspension"),
    ("clutsh", "clutch"),
    ("pistion", "piston"),
    ("cylindar", "cylinder"),
    ("exhoust", "exhaust"),
    ("exaust", "exhaust"),
    ("tharmostat", "thermostat"),
    ("coolent", "coolant"),
    ("condensor", "condenser"),
    ("compresser", "compressor"),
    ("igniton", "ignition"),
    ("distributer", "distributor"),
    ("bearring", "bearing"),
    ("bering", "bearing"),
]

# ---------------------------------------------------------------------------
# 3. Symptom-to-part pairs
#    Extracted from sections 6.1-6.4 of the research
# ---------------------------------------------------------------------------

SYMPTOM_PAIRS_RAW: list[tuple[str, str]] = [
    # 6.1 Noise Symptoms
    ("brake lagane par khar-khar awaaz", "brake pad"),
    ("ghis-ghis awaaz brakes", "brake pad"),
    ("grinding noise when braking", "brake pad brake disc wheel bearing"),
    ("chee-chee awaaz brakein", "brake pad brake disc"),
    ("squealing when braking", "brake pad brake disc"),
    ("engine mein thak-thak awaaz", "engine oil valve train piston"),
    ("chan-chan awaaz engine", "engine oil valve train piston"),
    ("knocking noise from engine", "engine oil valve train piston"),
    ("neeche khar-khar karta hai", "exhaust heat shield catalytic converter"),
    ("rattling from underneath", "exhaust heat shield catalytic converter"),
    ("dhakke mein thud awaaz", "shock absorber ball joint control arm bushing"),
    ("clunking over bumps", "shock absorber ball joint control arm bushing"),
    ("steering ghumane par seeti", "power steering pump"),
    ("whining from steering", "power steering pump power steering fluid"),
    ("mod lete waqt ghis-ghis", "CV joint wheel bearing"),
    ("grinding when turning", "CV joint wheel bearing"),
    ("takk-takk awaaz mod par", "CV joint"),
    ("clicking when turning", "CV joint outer CV joint"),
    ("zyada speed par kaanpna", "wheel balancing tyre drive shaft"),
    ("vibration at high speed", "wheel balancing tyre drive shaft"),

    # 6.2 Performance Symptoms
    ("engine garam ho raha hai", "thermostat radiator coolant water pump"),
    ("temperature zyada", "thermostat radiator coolant water pump radiator fan"),
    ("car overheating", "coolant thermostat radiator water pump radiator fan"),
    ("pickup nahi hai", "air filter fuel filter spark plug fuel injector"),
    ("gaadi nahi uthti", "air filter fuel filter spark plug fuel injector"),
    ("poor acceleration", "air filter fuel filter spark plug fuel injector"),
    ("gaadi band ho jaati hai", "IAC valve fuel pump spark plug MAF sensor"),
    ("stall ho raha hai", "IAC valve fuel pump spark plug MAF sensor"),
    ("engine stalling", "IAC valve fuel pump spark plug MAF sensor"),
    ("idle par hil rahi hai", "spark plug fuel injector IAC valve"),
    ("rough idling", "spark plug fuel injector IAC valve"),
    ("kaala dhuaan nikal raha hai", "air filter fuel injector fuel mixture"),
    ("black smoke from exhaust", "air filter fuel injector rich fuel mixture"),
    ("safed dhuaan", "piston rings valve seals coolant leak"),
    ("neela dhuaan", "piston rings valve seals engine oil burning"),
    ("blue white smoke exhaust", "piston rings valve seals coolant leak"),
    ("mileage kharab ho gaya", "air filter spark plug O2 sensor tyre pressure"),
    ("high fuel consumption", "air filter spark plug O2 sensor tyre pressure"),
    ("jhatkhe aa rahe hain", "spark plug ignition coil fuel injector fuel pump"),
    ("car jerking misfiring", "spark plug ignition coil fuel injector fuel pump"),
    ("gaadi start nahi ho rahi", "battery starter motor spark plug fuel pump"),
    ("engine won't start", "battery starter motor spark plug fuel pump"),

    # 6.3 Handling & Braking Symptoms
    ("steering bhaari lag rahi hai", "power steering fluid power steering pump power steering belt steering rack"),
    ("steering bhaari", "power steering pump"),
    ("heavy stiff steering", "power steering fluid power steering pump steering rack"),
    ("gaadi ek taraf kheench rahi hai", "wheel alignment brake caliper wheel bearing tyre pressure"),
    ("car pulling to one side", "wheel alignment brake caliper wheel bearing tyre pressure"),
    ("brake dab raha hai", "brake fluid master cylinder brake hose"),
    ("soft spongy brakes", "brake fluid master cylinder brake hose"),
    ("brake nahi lag raha", "brake pad brake fluid master cylinder"),
    ("brakes not working", "brake pad brake fluid master cylinder"),
    ("brake dabana mushkil ho gaya", "brake booster vacuum pump"),
    ("hard brake pedal", "brake booster vacuum pump"),
    ("brake lagane par gaadi kaanpti hai", "brake disc brake pad wheel alignment"),
    ("car shaking when braking", "warped brake disc brake pad wheel alignment"),
    ("gaadi bahut uchhal rahi hai", "shock absorber"),
    ("suspension too bouncy", "shock absorber"),
    ("steering kaanpti hai", "wheel balance tie rod end ball joint"),
    ("steering wobble", "wheel balance tie rod end ball joint"),

    # 6.4 Electrical & Other Symptoms
    ("click ki awaaz aati hai start nahi hota", "battery starter motor"),
    ("car not starting click sound", "battery starter motor"),
    ("raat ko battery khatam ho jaati hai", "alternator battery relay"),
    ("battery draining overnight", "alternator battery parasitic draw"),
    ("AC thanda nahi kar raha", "AC compressor condenser cabin filter refrigerant"),
    ("AC not cooling", "AC compressor condenser cabin filter refrigerant"),
    ("lights jhilmila rahi hain", "alternator battery wiring"),
    ("lights flickering", "alternator battery wiring"),
    ("warning light jal rahi hai", "O2 sensor MAF sensor EGR valve air filter"),
    ("check engine light on", "O2 sensor MAF sensor EGR valve air filter fuel cap"),
    ("gear nahi lag raha", "clutch fluid clutch plate clutch master cylinder"),
    ("gear not shifting", "clutch fluid clutch plate clutch master cylinder"),
    ("clutch slip kar raha hai", "clutch plate"),
    ("clutch slipping", "clutch plate worn"),
    ("gear nikal jaata hai", "gearbox synchro"),
    ("gear slipping out", "gearbox synchro gearbox worn"),
]

# ---------------------------------------------------------------------------
# 4. Brand-as-generic pairs
#    Extracted from sections 3.1 of the research
# ---------------------------------------------------------------------------

BRAND_GENERIC_PAIRS_RAW: list[tuple[str, str]] = [
    ("mobil", "engine oil"),
    ("mobil", "motor oil"),
    ("mobil daalna hai", "oil change"),
    ("exide", "battery"),
    ("exide", "car battery"),
    ("bullet", "Royal Enfield"),
    ("bullet", "Royal Enfield motorcycle"),
    ("maruti", "small hatchback car"),
    ("servo", "brake booster"),
    ("servo brakes", "power-assisted brakes"),
    ("delco", "distributor"),
    ("delco", "ignition distributor"),
    ("castrol", "engine oil"),
    ("bosch", "spark plug"),
    ("bosch plug", "spark plug"),
    ("bosch", "fuel injector"),
    ("NGK", "spark plug"),
    ("dunlop", "tyre"),
    ("MRF", "tyre"),
    ("MRF lagwa lo", "get any tyre"),
    ("mobil and filter", "oil and filter change"),
]


def _make_pair(
    text_a: str, text_b: str, label: float, pair_type: str, source: str = ""
) -> TrainingPair:
    return TrainingPair(
        text_a=text_a.strip(),
        text_b=text_b.strip(),
        label=label,
        pair_type=pair_type,
        source=source or "vocabulary_research",
    )


def _generate_positive_pairs() -> list[TrainingPair]:
    """Generate all positive (label=1.0) training pairs."""
    pairs: list[TrainingPair] = []

    # Synonym pairs (bidirectional)
    for a, b in SYNONYM_PAIRS_RAW:
        if a.lower() != b.lower():
            pairs.append(_make_pair(a, b, 1.0, "synonym"))
            pairs.append(_make_pair(b, a, 1.0, "synonym"))

    # Misspelling pairs (bidirectional)
    for misspelled, correct in MISSPELLING_PAIRS_RAW:
        pairs.append(_make_pair(misspelled, correct, 1.0, "misspelling"))
        pairs.append(_make_pair(correct, misspelled, 1.0, "misspelling"))

    # Symptom-to-part pairs (single direction: symptom -> parts)
    for symptom, parts in SYMPTOM_PAIRS_RAW:
        pairs.append(_make_pair(symptom, parts, 1.0, "symptom"))

    # Brand-as-generic pairs (bidirectional)
    for brand, generic in BRAND_GENERIC_PAIRS_RAW:
        pairs.append(_make_pair(brand, generic, 1.0, "brand_generic"))
        pairs.append(_make_pair(generic, brand, 1.0, "brand_generic"))

    return pairs


def _collect_all_terms(positive_pairs: list[TrainingPair]) -> list[str]:
    """Collect all unique terms from positive pairs for negative sampling."""
    terms: set[str] = set()
    for p in positive_pairs:
        terms.add(p.text_a)
        terms.add(p.text_b)
    return sorted(terms)


def _generate_negative_pairs(
    positive_pairs: list[TrainingPair], ratio: float = 2.0, seed: int = 42
) -> list[TrainingPair]:
    """Generate negative pairs by randomly combining unrelated terms.

    For every positive pair, generate `ratio` negative pairs.
    """
    rng = random.Random(seed)
    terms = _collect_all_terms(positive_pairs)

    # Build a set of known positive pairs for fast lookup
    positive_set: set[tuple[str, str]] = set()
    for p in positive_pairs:
        positive_set.add((p.text_a.lower(), p.text_b.lower()))
        positive_set.add((p.text_b.lower(), p.text_a.lower()))

    target_count = int(len(positive_pairs) * ratio)
    negatives: list[TrainingPair] = []
    attempts = 0
    max_attempts = target_count * 10

    while len(negatives) < target_count and attempts < max_attempts:
        a = rng.choice(terms)
        b = rng.choice(terms)
        attempts += 1

        if a.lower() == b.lower():
            continue
        if (a.lower(), b.lower()) in positive_set:
            continue

        negatives.append(_make_pair(a, b, 0.0, "negative"))
        positive_set.add((a.lower(), b.lower()))  # avoid duplicates

    return negatives


def generate_vocabulary_pairs(negative_ratio: float = 2.0, seed: int = 42) -> list[TrainingPair]:
    """Generate all training pairs from vocabulary research data.

    Args:
        negative_ratio: Number of negative pairs per positive pair.
        seed: Random seed for reproducible negative sampling.

    Returns:
        List of TrainingPair objects (positive + negative).
    """
    positive = _generate_positive_pairs()
    negative = _generate_negative_pairs(positive, ratio=negative_ratio, seed=seed)
    return positive + negative


def save_pairs(pairs: list[TrainingPair], output_path: str | Path) -> None:
    """Write training pairs to a JSONL file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair.to_dict(), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    pairs = generate_vocabulary_pairs()

    # Stats
    from collections import Counter

    type_counts = Counter(p.pair_type for p in pairs)
    label_counts = Counter(p.label for p in pairs)
    positive_count = sum(1 for p in pairs if p.label == 1.0)
    negative_count = sum(1 for p in pairs if p.label == 0.0)

    print(f"Total pairs: {len(pairs)}")
    print(f"  Positive: {positive_count}")
    print(f"  Negative: {negative_count}")
    print(f"\nBy type:")
    for ptype, count in sorted(type_counts.items()):
        print(f"  {ptype}: {count}")
    print(f"\nBy label:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count}")

    output_path = Path("/Users/mac/Projects/auto-parts-search/data/training/vocabulary_pairs.jsonl")
    save_pairs(pairs, output_path)
    print(f"\nSaved to {output_path}")
