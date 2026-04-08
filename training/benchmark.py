"""200-query evaluation benchmark for Indian auto parts search.

Curated from research data: vocabulary, misspellings, symptoms, part numbers.
Tests 6 query types across difficulty levels.
"""
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.schemas import BenchmarkQuery
from auto_parts_search.config import TRAINING_DIR


def _exact_english_queries():
    return [
        BenchmarkQuery(query="brake pad Maruti Swift 2019", query_type="exact_english", expected_parts=["brake pad"], expected_categories=["Brake System"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="oil filter Honda Activa", query_type="exact_english", expected_parts=["oil filter"], expected_categories=["Service Parts"], expected_vehicles=["Honda Activa"], difficulty="easy"),
        BenchmarkQuery(query="chain sprocket kit Hero Splendor", query_type="exact_english", expected_parts=["chain sprocket kit"], expected_categories=["Transmission"], expected_vehicles=["Hero Splendor"], difficulty="easy"),
        BenchmarkQuery(query="shock absorber Hyundai Creta", query_type="exact_english", expected_parts=["shock absorber"], expected_categories=["Suspension & Steering"], expected_vehicles=["Hyundai Creta"], difficulty="easy"),
        BenchmarkQuery(query="clutch plate Maruti Wagon R", query_type="exact_english", expected_parts=["clutch plate"], expected_categories=["Clutch & Transmission"], expected_vehicles=["Maruti Wagon R"], difficulty="easy"),
        BenchmarkQuery(query="air filter Bajaj Pulsar 150", query_type="exact_english", expected_parts=["air filter"], expected_categories=["Service Parts"], expected_vehicles=["Bajaj Pulsar"], difficulty="easy"),
        BenchmarkQuery(query="spark plug Royal Enfield Classic 350", query_type="exact_english", expected_parts=["spark plug"], expected_categories=["Service Parts"], expected_vehicles=["Royal Enfield Classic 350"], difficulty="easy"),
        BenchmarkQuery(query="battery Maruti Baleno", query_type="exact_english", expected_parts=["battery"], expected_categories=["Electrical & Lighting"], expected_vehicles=["Maruti Baleno"], difficulty="easy"),
        BenchmarkQuery(query="headlight bulb Tata Nexon", query_type="exact_english", expected_parts=["headlight bulb"], expected_categories=["Electrical & Lighting"], expected_vehicles=["Tata Nexon"], difficulty="easy"),
        BenchmarkQuery(query="radiator Mahindra Scorpio", query_type="exact_english", expected_parts=["radiator"], expected_categories=["Heating & Cooling"], expected_vehicles=["Mahindra Scorpio"], difficulty="easy"),
        BenchmarkQuery(query="wiper blade Hyundai i20", query_type="exact_english", expected_parts=["wiper blade"], expected_categories=["Electrical & Lighting"], expected_vehicles=["Hyundai i20"], difficulty="easy"),
        BenchmarkQuery(query="silencer Royal Enfield Bullet 350", query_type="exact_english", expected_parts=["silencer", "muffler", "exhaust"], expected_categories=["Body & Exhaust"], expected_vehicles=["Royal Enfield Bullet 350"], difficulty="easy"),
        BenchmarkQuery(query="brake shoe Honda Activa rear", query_type="exact_english", expected_parts=["brake shoe"], expected_categories=["Brake System"], expected_vehicles=["Honda Activa"], difficulty="easy"),
        BenchmarkQuery(query="timing belt Maruti Swift Dzire", query_type="exact_english", expected_parts=["timing belt"], expected_categories=["Engine Parts"], expected_vehicles=["Maruti Dzire"], difficulty="medium"),
        BenchmarkQuery(query="CV joint boot Hyundai Creta", query_type="exact_english", expected_parts=["CV joint", "CV boot"], expected_categories=["Clutch & Transmission"], expected_vehicles=["Hyundai Creta"], difficulty="medium"),
        BenchmarkQuery(query="power steering pump Maruti Ertiga", query_type="exact_english", expected_parts=["power steering pump"], expected_categories=["Suspension & Steering"], expected_vehicles=["Maruti Ertiga"], difficulty="medium"),
        BenchmarkQuery(query="AC compressor Tata Punch", query_type="exact_english", expected_parts=["AC compressor"], expected_categories=["Heating & Cooling"], expected_vehicles=["Tata Punch"], difficulty="medium"),
        BenchmarkQuery(query="fuel injector Maruti Brezza diesel", query_type="exact_english", expected_parts=["fuel injector"], expected_categories=["Engine Parts"], expected_vehicles=["Maruti Brezza"], difficulty="medium"),
        BenchmarkQuery(query="clutch cable Bajaj Pulsar 150", query_type="exact_english", expected_parts=["clutch cable"], expected_categories=["Clutch & Transmission"], expected_vehicles=["Bajaj Pulsar"], difficulty="easy"),
        BenchmarkQuery(query="front bumper Maruti Swift 2022", query_type="exact_english", expected_parts=["bumper"], expected_categories=["Body & Exhaust"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="catalytic converter Hyundai Creta", query_type="exact_english", expected_parts=["catalytic converter"], expected_categories=["Body & Exhaust"], expected_vehicles=["Hyundai Creta"], difficulty="medium"),
        BenchmarkQuery(query="water pump Tata Nexon diesel", query_type="exact_english", expected_parts=["water pump"], expected_categories=["Heating & Cooling"], expected_vehicles=["Tata Nexon"], difficulty="medium"),
        BenchmarkQuery(query="cabin filter Kia Seltos", query_type="exact_english", expected_parts=["cabin filter"], expected_categories=["Service Parts"], expected_vehicles=["Kia Seltos"], difficulty="easy"),
        BenchmarkQuery(query="horn Maruti Alto", query_type="exact_english", expected_parts=["horn"], expected_categories=["Electrical & Lighting"], expected_vehicles=["Maruti Alto"], difficulty="easy"),
        BenchmarkQuery(query="thermostat Toyota Innova", query_type="exact_english", expected_parts=["thermostat"], expected_categories=["Heating & Cooling"], expected_vehicles=["Toyota Innova"], difficulty="medium"),
        BenchmarkQuery(query="master cylinder Mahindra Thar", query_type="exact_english", expected_parts=["master cylinder"], expected_categories=["Brake System"], expected_vehicles=["Mahindra Thar"], difficulty="medium"),
        BenchmarkQuery(query="ignition coil Maruti Baleno", query_type="exact_english", expected_parts=["ignition coil"], expected_categories=["Engine Parts"], expected_vehicles=["Maruti Baleno"], difficulty="medium"),
        BenchmarkQuery(query="wheel bearing Hyundai Grand i10", query_type="exact_english", expected_parts=["wheel bearing"], expected_categories=["Clutch & Transmission"], expected_vehicles=["Hyundai Grand i10"], difficulty="medium"),
        BenchmarkQuery(query="tail lamp Tata Punch", query_type="exact_english", expected_parts=["tail lamp"], expected_categories=["Electrical & Lighting"], expected_vehicles=["Tata Punch"], difficulty="easy"),
        BenchmarkQuery(query="suspension spring Maruti Fronx", query_type="exact_english", expected_parts=["suspension spring", "coil spring"], expected_categories=["Suspension & Steering"], expected_vehicles=["Maruti Fronx"], difficulty="medium"),
        BenchmarkQuery(query="fuel pump Mahindra Scorpio diesel", query_type="exact_english", expected_parts=["fuel pump"], expected_categories=["Engine Parts"], expected_vehicles=["Mahindra Scorpio"], difficulty="medium"),
        BenchmarkQuery(query="side mirror ORVM Maruti Swift", query_type="exact_english", expected_parts=["side mirror", "ORVM"], expected_categories=["Body & Exhaust"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="O2 sensor Hyundai Verna", query_type="exact_english", expected_parts=["O2 sensor", "oxygen sensor"], expected_categories=["Engine Parts"], expected_vehicles=["Hyundai Verna"], difficulty="hard"),
        BenchmarkQuery(query="alternator belt TVS Apache RTR 160", query_type="exact_english", expected_parts=["alternator belt", "belt"], expected_categories=["Engine Parts"], expected_vehicles=["TVS Apache RTR 160"], difficulty="medium"),
        BenchmarkQuery(query="drive belt Hero Splendor Plus", query_type="exact_english", expected_parts=["drive belt", "chain"], expected_categories=["Transmission"], expected_vehicles=["Hero Splendor"], difficulty="medium"),
    ]


def _hindi_hinglish_queries():
    return [
        BenchmarkQuery(query="swift ka shocker", query_type="hindi_hinglish", expected_parts=["shock absorber"], expected_categories=["Suspension & Steering"], expected_vehicles=["Maruti Swift"], difficulty="medium"),
        BenchmarkQuery(query="brake ki patti", query_type="hindi_hinglish", expected_parts=["brake pad"], expected_categories=["Brake System"], difficulty="medium"),
        BenchmarkQuery(query="gaadi ki battery", query_type="hindi_hinglish", expected_parts=["battery"], expected_categories=["Electrical & Lighting"], difficulty="medium"),
        BenchmarkQuery(query="hawa ka filter", query_type="hindi_hinglish", expected_parts=["air filter"], expected_categories=["Service Parts"], difficulty="medium"),
        BenchmarkQuery(query="splendor ka chain set", query_type="hindi_hinglish", expected_parts=["chain sprocket kit"], expected_categories=["Transmission"], expected_vehicles=["Hero Splendor"], difficulty="medium"),
        BenchmarkQuery(query="activa ka brake shoe", query_type="hindi_hinglish", expected_parts=["brake shoe"], expected_categories=["Brake System"], expected_vehicles=["Honda Activa"], difficulty="medium"),
        BenchmarkQuery(query="mobil daalna hai", query_type="hindi_hinglish", expected_parts=["engine oil"], expected_categories=["Service Parts"], difficulty="hard"),
        BenchmarkQuery(query="gaadi ka bonnet", query_type="hindi_hinglish", expected_parts=["bonnet", "hood"], expected_categories=["Body & Exhaust"], difficulty="medium"),
        BenchmarkQuery(query="dikki ka lock", query_type="hindi_hinglish", expected_parts=["trunk lock", "boot lock"], expected_categories=["Body & Exhaust"], difficulty="hard"),
        BenchmarkQuery(query="stepney chahiye", query_type="hindi_hinglish", expected_parts=["spare tyre", "spare wheel"], difficulty="hard"),
        BenchmarkQuery(query="gaadi ka sheesha", query_type="hindi_hinglish", expected_parts=["windshield"], expected_categories=["Body & Exhaust"], difficulty="hard"),
        BenchmarkQuery(query="self nahi lag raha", query_type="hindi_hinglish", expected_parts=["starter motor"], expected_categories=["Electrical & Lighting"], difficulty="hard"),
        BenchmarkQuery(query="dynamo kharaab hai", query_type="hindi_hinglish", expected_parts=["alternator"], expected_categories=["Electrical & Lighting"], difficulty="hard"),
        BenchmarkQuery(query="pichli batti", query_type="hindi_hinglish", expected_parts=["tail lamp", "tail light"], expected_categories=["Electrical & Lighting"], difficulty="hard"),
        BenchmarkQuery(query="creta ka shocker aage wala", query_type="hindi_hinglish", expected_parts=["shock absorber front"], expected_vehicles=["Hyundai Creta"], difficulty="medium"),
        BenchmarkQuery(query="wagon r ka clutch set", query_type="hindi_hinglish", expected_parts=["clutch kit", "clutch plate"], expected_vehicles=["Maruti Wagon R"], difficulty="medium"),
        BenchmarkQuery(query="bullet ka silencer", query_type="hindi_hinglish", expected_parts=["silencer", "exhaust"], expected_vehicles=["Royal Enfield"], difficulty="medium"),
        BenchmarkQuery(query="swift ki headlight", query_type="hindi_hinglish", expected_parts=["headlight"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="activa ka tyre", query_type="hindi_hinglish", expected_parts=["tyre"], expected_vehicles=["Honda Activa"], difficulty="easy"),
        BenchmarkQuery(query="brake oil chahiye", query_type="hindi_hinglish", expected_parts=["brake fluid"], expected_categories=["Brake System"], difficulty="medium"),
        BenchmarkQuery(query="tel ka filter swift", query_type="hindi_hinglish", expected_parts=["oil filter"], expected_vehicles=["Maruti Swift"], difficulty="hard"),
        BenchmarkQuery(query="pankha radiator ka", query_type="hindi_hinglish", expected_parts=["cooling fan", "radiator fan"], expected_categories=["Heating & Cooling"], difficulty="hard"),
        BenchmarkQuery(query="pulsar ka chain sprocket", query_type="hindi_hinglish", expected_parts=["chain sprocket kit"], expected_vehicles=["Bajaj Pulsar"], difficulty="medium"),
        BenchmarkQuery(query="scorpio ka bumper", query_type="hindi_hinglish", expected_parts=["bumper"], expected_vehicles=["Mahindra Scorpio"], difficulty="easy"),
        BenchmarkQuery(query="apache ka brake pad", query_type="hindi_hinglish", expected_parts=["brake pad"], expected_vehicles=["TVS Apache"], difficulty="easy"),
        BenchmarkQuery(query="gear oil daalna hai", query_type="hindi_hinglish", expected_parts=["gear oil", "transmission oil"], difficulty="hard"),
        BenchmarkQuery(query="indicator ki light", query_type="hindi_hinglish", expected_parts=["indicator bulb", "turn signal"], expected_categories=["Electrical & Lighting"], difficulty="medium"),
        BenchmarkQuery(query="palak ki light", query_type="hindi_hinglish", expected_parts=["indicator", "turn signal"], difficulty="hard"),
        BenchmarkQuery(query="servo brake", query_type="hindi_hinglish", expected_parts=["brake booster"], expected_categories=["Brake System"], difficulty="hard"),
        BenchmarkQuery(query="saari guard activa", query_type="hindi_hinglish", expected_parts=["saree guard"], expected_vehicles=["Honda Activa"], difficulty="hard"),
        BenchmarkQuery(query="carby saaf karna hai", query_type="hindi_hinglish", expected_parts=["carburetor"], expected_categories=["Engine Parts"], difficulty="hard"),
        BenchmarkQuery(query="taar badalni hai gaadi ki", query_type="hindi_hinglish", expected_parts=["wiring harness"], expected_categories=["Electrical & Lighting"], difficulty="hard"),
        BenchmarkQuery(query="bearing badalna hai wheel ka", query_type="hindi_hinglish", expected_parts=["wheel bearing"], difficulty="hard"),
        BenchmarkQuery(query="poncha wiper", query_type="hindi_hinglish", expected_parts=["wiper blade"], difficulty="hard"),
        BenchmarkQuery(query="side brake ka wire", query_type="hindi_hinglish", expected_parts=["handbrake cable"], expected_categories=["Brake System"], difficulty="hard"),
    ]


def _misspelled_queries():
    return [
        BenchmarkQuery(query="break pad swift", query_type="misspelled", expected_parts=["brake pad"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="klutch plate wagon r", query_type="misspelled", expected_parts=["clutch plate"], expected_vehicles=["Maruti Wagon R"], difficulty="medium"),
        BenchmarkQuery(query="brakpad maruti", query_type="misspelled", expected_parts=["brake pad"], difficulty="medium"),
        BenchmarkQuery(query="carburator splendor", query_type="misspelled", expected_parts=["carburetor"], expected_vehicles=["Hero Splendor"], difficulty="medium"),
        BenchmarkQuery(query="shok absorber creta", query_type="misspelled", expected_parts=["shock absorber"], expected_vehicles=["Hyundai Creta"], difficulty="easy"),
        BenchmarkQuery(query="break disk swift 2019", query_type="misspelled", expected_parts=["brake disc"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="break fluid", query_type="misspelled", expected_parts=["brake fluid"], difficulty="easy"),
        BenchmarkQuery(query="calliper hyundai creta", query_type="misspelled", expected_parts=["caliper", "brake caliper"], expected_vehicles=["Hyundai Creta"], difficulty="easy"),
        BenchmarkQuery(query="master sillinder swift", query_type="misspelled", expected_parts=["master cylinder"], expected_vehicles=["Maruti Swift"], difficulty="medium"),
        BenchmarkQuery(query="cluch plate nexon", query_type="misspelled", expected_parts=["clutch plate"], expected_vehicles=["Tata Nexon"], difficulty="medium"),
        BenchmarkQuery(query="clutchplate swift", query_type="misspelled", expected_parts=["clutch plate"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="fly wheel wagon r", query_type="misspelled", expected_parts=["flywheel"], expected_vehicles=["Maruti Wagon R"], difficulty="easy"),
        BenchmarkQuery(query="geer box maruti", query_type="misspelled", expected_parts=["gearbox"], difficulty="medium"),
        BenchmarkQuery(query="alternater swift", query_type="misspelled", expected_parts=["alternator"], expected_vehicles=["Maruti Swift"], difficulty="medium"),
        BenchmarkQuery(query="sparkplug pulsar", query_type="misspelled", expected_parts=["spark plug"], expected_vehicles=["Bajaj Pulsar"], difficulty="easy"),
        BenchmarkQuery(query="thermostate creta", query_type="misspelled", expected_parts=["thermostat"], expected_vehicles=["Hyundai Creta"], difficulty="medium"),
        BenchmarkQuery(query="gaskot head maruti", query_type="misspelled", expected_parts=["head gasket"], difficulty="medium"),
        BenchmarkQuery(query="injecter swift diesel", query_type="misspelled", expected_parts=["fuel injector"], expected_vehicles=["Maruti Swift"], difficulty="medium"),
        BenchmarkQuery(query="shok obsorber i20", query_type="misspelled", expected_parts=["shock absorber"], expected_vehicles=["Hyundai i20"], difficulty="medium"),
        BenchmarkQuery(query="boll joint scorpio", query_type="misspelled", expected_parts=["ball joint"], expected_vehicles=["Mahindra Scorpio"], difficulty="medium"),
        BenchmarkQuery(query="tirod end swift", query_type="misspelled", expected_parts=["tie rod end"], expected_vehicles=["Maruti Swift"], difficulty="medium"),
        BenchmarkQuery(query="weel bearing creta", query_type="misspelled", expected_parts=["wheel bearing"], expected_vehicles=["Hyundai Creta"], difficulty="medium"),
        BenchmarkQuery(query="brake ped maruti", query_type="misspelled", expected_parts=["brake pad"], difficulty="medium"),
        BenchmarkQuery(query="mufler royal enfield", query_type="misspelled", expected_parts=["muffler", "silencer"], expected_vehicles=["Royal Enfield"], difficulty="easy"),
        BenchmarkQuery(query="fule filter swift diesel", query_type="misspelled", expected_parts=["fuel filter"], expected_vehicles=["Maruti Swift"], difficulty="medium"),
        BenchmarkQuery(query="brake flude creta", query_type="misspelled", expected_parts=["brake fluid"], expected_vehicles=["Hyundai Creta"], difficulty="medium"),
        BenchmarkQuery(query="clutch plet baleno", query_type="misspelled", expected_parts=["clutch plate"], expected_vehicles=["Maruti Baleno"], difficulty="hard"),
        BenchmarkQuery(query="carburatter splendor", query_type="misspelled", expected_parts=["carburetor"], expected_vehicles=["Hero Splendor"], difficulty="medium"),
        BenchmarkQuery(query="drive saft creta", query_type="misspelled", expected_parts=["drive shaft"], expected_vehicles=["Hyundai Creta"], difficulty="hard"),
        BenchmarkQuery(query="fleewheel wagon r", query_type="misspelled", expected_parts=["flywheel"], expected_vehicles=["Maruti Wagon R"], difficulty="hard"),
    ]


def _symptom_queries():
    return [
        BenchmarkQuery(query="brake lagane par khar-khar awaaz", query_type="symptom", expected_parts=["brake pad", "brake disc", "wheel bearing"], difficulty="hard"),
        BenchmarkQuery(query="engine garam ho raha hai", query_type="symptom", expected_parts=["thermostat", "radiator", "coolant", "water pump"], difficulty="hard"),
        BenchmarkQuery(query="steering bhaari lag rahi hai", query_type="symptom", expected_parts=["power steering pump", "power steering fluid"], difficulty="hard"),
        BenchmarkQuery(query="gaadi start nahi ho rahi", query_type="symptom", expected_parts=["battery", "starter motor", "spark plug"], difficulty="hard"),
        BenchmarkQuery(query="AC thanda nahi kar raha", query_type="symptom", expected_parts=["AC compressor", "refrigerant", "condenser"], difficulty="hard"),
        BenchmarkQuery(query="pickup nahi hai", query_type="symptom", expected_parts=["air filter", "spark plug", "fuel filter"], difficulty="hard"),
        BenchmarkQuery(query="grinding noise front wheel", query_type="symptom", expected_parts=["brake pad", "wheel bearing", "CV joint"], difficulty="medium"),
        BenchmarkQuery(query="car pulling to one side", query_type="symptom", expected_parts=["wheel alignment", "brake caliper", "tyre"], difficulty="medium"),
        BenchmarkQuery(query="kaala dhuaan nikal raha hai", query_type="symptom", expected_parts=["air filter", "fuel injector"], difficulty="hard"),
        BenchmarkQuery(query="engine mein thak-thak awaaz", query_type="symptom", expected_parts=["engine oil", "valve train"], difficulty="hard"),
        BenchmarkQuery(query="dhakke mein thud awaaz", query_type="symptom", expected_parts=["shock absorber", "ball joint"], difficulty="hard"),
        BenchmarkQuery(query="steering ghuma ne par seeti", query_type="symptom", expected_parts=["power steering pump"], difficulty="hard"),
        BenchmarkQuery(query="mod lete waqt ghis-ghis", query_type="symptom", expected_parts=["CV joint", "wheel bearing"], difficulty="hard"),
        BenchmarkQuery(query="takk-takk awaaz mod par", query_type="symptom", expected_parts=["CV joint"], difficulty="hard"),
        BenchmarkQuery(query="zyada speed par kaanpna", query_type="symptom", expected_parts=["wheel balancing", "tyre", "drive shaft"], difficulty="hard"),
        BenchmarkQuery(query="gaadi band ho jaati hai", query_type="symptom", expected_parts=["IAC valve", "fuel pump", "spark plug"], difficulty="hard"),
        BenchmarkQuery(query="idle par hil rahi hai", query_type="symptom", expected_parts=["spark plug", "fuel injector"], difficulty="hard"),
        BenchmarkQuery(query="mileage kharab ho gaya", query_type="symptom", expected_parts=["air filter", "spark plug", "O2 sensor"], difficulty="hard"),
        BenchmarkQuery(query="jhatkhe aa rahe hain", query_type="symptom", expected_parts=["spark plug", "ignition coil", "fuel injector"], difficulty="hard"),
        BenchmarkQuery(query="click ki awaaz start nahi hota", query_type="symptom", expected_parts=["battery", "starter motor"], difficulty="medium"),
        BenchmarkQuery(query="raat ko battery khatam ho jaati hai", query_type="symptom", expected_parts=["alternator", "battery"], difficulty="hard"),
        BenchmarkQuery(query="lights jhilmila rahi hain", query_type="symptom", expected_parts=["alternator", "battery"], difficulty="hard"),
        BenchmarkQuery(query="gear nahi lag raha", query_type="symptom", expected_parts=["clutch fluid", "clutch plate"], difficulty="hard"),
        BenchmarkQuery(query="clutch slip kar raha hai", query_type="symptom", expected_parts=["clutch plate"], difficulty="medium"),
        BenchmarkQuery(query="brake dabane par gaadi kaanpti hai", query_type="symptom", expected_parts=["brake disc", "brake pad"], difficulty="hard"),
        BenchmarkQuery(query="gaadi bahut uchhal rahi hai", query_type="symptom", expected_parts=["shock absorber"], difficulty="medium"),
        BenchmarkQuery(query="brake soft lag raha hai", query_type="symptom", expected_parts=["brake fluid", "master cylinder"], difficulty="hard"),
        BenchmarkQuery(query="brake dabana mushkil ho gaya", query_type="symptom", expected_parts=["brake booster"], difficulty="hard"),
        BenchmarkQuery(query="warning light jal rahi hai", query_type="symptom", expected_parts=["O2 sensor", "MAF sensor"], difficulty="hard"),
        BenchmarkQuery(query="safed dhuaan nikal raha hai", query_type="symptom", expected_parts=["piston rings", "valve seals", "head gasket"], difficulty="hard"),
        BenchmarkQuery(query="squealing noise when braking", query_type="symptom", expected_parts=["brake pad", "brake disc"], difficulty="easy"),
        BenchmarkQuery(query="car overheating in traffic", query_type="symptom", expected_parts=["radiator fan", "thermostat", "coolant"], difficulty="medium"),
        BenchmarkQuery(query="steering wobble at 80 kmph", query_type="symptom", expected_parts=["wheel balance", "tie rod end"], difficulty="medium"),
        BenchmarkQuery(query="rattling noise underneath", query_type="symptom", expected_parts=["exhaust heat shield", "catalytic converter"], difficulty="medium"),
        BenchmarkQuery(query="gear nikal jaata hai", query_type="symptom", expected_parts=["gearbox synchro", "gearbox"], difficulty="hard"),
    ]


def _part_number_queries():
    return [
        BenchmarkQuery(query="16510M68K00", query_type="part_number", expected_parts=["oil filter"], expected_vehicles=["Maruti"], difficulty="medium"),
        BenchmarkQuery(query="37110-C2810", query_type="part_number", expected_parts=["battery"], expected_vehicles=["Hyundai"], difficulty="medium"),
        BenchmarkQuery(query="Bosch 0986AB1234", query_type="part_number", expected_parts=["brake pad"], difficulty="medium"),
        BenchmarkQuery(query="09200-M51K10", query_type="part_number", expected_parts=["brake pad"], expected_vehicles=["Maruti"], difficulty="medium"),
        BenchmarkQuery(query="28313-2GTA0", query_type="part_number", expected_parts=["gasket"], expected_vehicles=["Hyundai"], difficulty="hard"),
        BenchmarkQuery(query="16510M86J00", query_type="part_number", expected_parts=["oil filter"], expected_vehicles=["Maruti"], difficulty="medium"),
        BenchmarkQuery(query="37110-3X000", query_type="part_number", expected_parts=["battery"], expected_vehicles=["Hyundai"], difficulty="medium"),
        BenchmarkQuery(query="NGK BKR6E", query_type="part_number", expected_parts=["spark plug"], difficulty="easy"),
        BenchmarkQuery(query="Valeo 826211", query_type="part_number", expected_parts=["clutch kit"], difficulty="medium"),
        BenchmarkQuery(query="SKF VKBA 3519", query_type="part_number", expected_parts=["wheel bearing"], difficulty="medium"),
        BenchmarkQuery(query="Monroe G7286", query_type="part_number", expected_parts=["shock absorber"], difficulty="medium"),
        BenchmarkQuery(query="Rane RBP-1047", query_type="part_number", expected_parts=["brake pad"], difficulty="medium"),
        BenchmarkQuery(query="Denso 234-4350", query_type="part_number", expected_parts=["O2 sensor"], difficulty="hard"),
        BenchmarkQuery(query="13780M86J00", query_type="part_number", expected_parts=["engine part"], expected_vehicles=["Maruti"], difficulty="hard"),
        BenchmarkQuery(query="Bosch F002H23", query_type="part_number", expected_parts=["oil filter"], difficulty="medium"),
        BenchmarkQuery(query="KYB 333115", query_type="part_number", expected_parts=["shock absorber"], difficulty="medium"),
        BenchmarkQuery(query="Brembo P 30 067", query_type="part_number", expected_parts=["brake pad"], difficulty="medium"),
        BenchmarkQuery(query="287173506317", query_type="part_number", expected_parts=["commercial vehicle part"], expected_vehicles=["Tata"], difficulty="hard"),
        BenchmarkQuery(query="94601-KZZ-900", query_type="part_number", expected_parts=["chain"], expected_vehicles=["Hero"], difficulty="hard"),
        BenchmarkQuery(query="Exide MRED45L", query_type="part_number", expected_parts=["battery"], difficulty="easy"),
        BenchmarkQuery(query="Amaron AAM-FL-0BH45D20L", query_type="part_number", expected_parts=["battery"], difficulty="easy"),
        BenchmarkQuery(query="MRF ZVTV 165/80 R14", query_type="part_number", expected_parts=["tyre"], difficulty="easy"),
        BenchmarkQuery(query="Castrol MAGNATEC 5W-30", query_type="part_number", expected_parts=["engine oil"], difficulty="easy"),
        BenchmarkQuery(query="15400-RTA-003", query_type="part_number", expected_parts=["oil filter"], expected_vehicles=["Honda"], difficulty="medium"),
        BenchmarkQuery(query="Bosch 0242229543", query_type="part_number", expected_parts=["spark plug"], difficulty="medium"),
        BenchmarkQuery(query="LUK 624316700", query_type="part_number", expected_parts=["clutch kit"], difficulty="hard"),
        BenchmarkQuery(query="Minda MG-5423", query_type="part_number", expected_parts=["electrical", "switch"], difficulty="hard"),
        BenchmarkQuery(query="09241M20002", query_type="part_number", expected_parts=["bolt", "fastener"], expected_vehicles=["Maruti"], difficulty="hard"),
        BenchmarkQuery(query="84702M74LG0", query_type="part_number", expected_parts=["interior trim"], expected_vehicles=["Maruti"], difficulty="hard"),
        BenchmarkQuery(query="TVS 3311A-TRK-0100", query_type="part_number", expected_parts=["two-wheeler part"], expected_vehicles=["TVS"], difficulty="hard"),
    ]


def _brand_as_generic_queries():
    return [
        BenchmarkQuery(query="Mobil for Swift", query_type="brand_as_generic", expected_parts=["engine oil"], expected_vehicles=["Maruti Swift"], difficulty="medium"),
        BenchmarkQuery(query="Exide for Activa", query_type="brand_as_generic", expected_parts=["battery"], expected_vehicles=["Honda Activa"], difficulty="medium"),
        BenchmarkQuery(query="Bullet chain sprocket", query_type="brand_as_generic", expected_parts=["chain sprocket kit"], expected_vehicles=["Royal Enfield"], difficulty="medium"),
        BenchmarkQuery(query="Mobil daalna hai Swift mein", query_type="brand_as_generic", expected_parts=["engine oil"], expected_vehicles=["Maruti Swift"], difficulty="hard"),
        BenchmarkQuery(query="Exide dead ho gayi", query_type="brand_as_generic", expected_parts=["battery"], difficulty="hard"),
        BenchmarkQuery(query="Bullet silencer upgrade", query_type="brand_as_generic", expected_parts=["silencer", "exhaust"], expected_vehicles=["Royal Enfield"], difficulty="medium"),
        BenchmarkQuery(query="Delco kharaab hai", query_type="brand_as_generic", expected_parts=["distributor"], difficulty="hard"),
        BenchmarkQuery(query="Bosch plug for Pulsar", query_type="brand_as_generic", expected_parts=["spark plug"], expected_vehicles=["Bajaj Pulsar"], difficulty="easy"),
        BenchmarkQuery(query="NGK for Classic 350", query_type="brand_as_generic", expected_parts=["spark plug"], expected_vehicles=["Royal Enfield Classic 350"], difficulty="medium"),
        BenchmarkQuery(query="Castrol for Creta diesel", query_type="brand_as_generic", expected_parts=["engine oil"], expected_vehicles=["Hyundai Creta"], difficulty="medium"),
        BenchmarkQuery(query="MRF for Swift front", query_type="brand_as_generic", expected_parts=["tyre"], expected_vehicles=["Maruti Swift"], difficulty="medium"),
        BenchmarkQuery(query="Amaron for Innova", query_type="brand_as_generic", expected_parts=["battery"], expected_vehicles=["Toyota Innova"], difficulty="medium"),
        BenchmarkQuery(query="Mobil & Filter Wagon R", query_type="brand_as_generic", expected_parts=["engine oil", "oil filter"], expected_vehicles=["Maruti Wagon R"], difficulty="hard"),
        BenchmarkQuery(query="self motor Splendor", query_type="brand_as_generic", expected_parts=["starter motor"], expected_vehicles=["Hero Splendor"], difficulty="hard"),
        BenchmarkQuery(query="dynamo Swift", query_type="brand_as_generic", expected_parts=["alternator"], expected_vehicles=["Maruti Swift"], difficulty="hard"),
        BenchmarkQuery(query="shocker for Activa front", query_type="brand_as_generic", expected_parts=["shock absorber"], expected_vehicles=["Honda Activa"], difficulty="medium"),
        BenchmarkQuery(query="patti for Creta brake", query_type="brand_as_generic", expected_parts=["brake pad"], expected_vehicles=["Hyundai Creta"], difficulty="hard"),
        BenchmarkQuery(query="company ka part Swift brake pad", query_type="brand_as_generic", expected_parts=["brake pad"], expected_vehicles=["Maruti Swift"], difficulty="hard"),
        BenchmarkQuery(query="numberi nahi chahiye genuine brake pad", query_type="brand_as_generic", expected_parts=["brake pad"], difficulty="hard"),
        BenchmarkQuery(query="duplicate shocker Creta", query_type="brand_as_generic", expected_parts=["shock absorber"], expected_vehicles=["Hyundai Creta"], difficulty="hard"),
        BenchmarkQuery(query="Servo brakes Scorpio", query_type="brand_as_generic", expected_parts=["brake booster"], expected_vehicles=["Mahindra Scorpio"], difficulty="hard"),
        BenchmarkQuery(query="Bosch wiper Swift", query_type="brand_as_generic", expected_parts=["wiper blade"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="Bullet crash guard", query_type="brand_as_generic", expected_parts=["crash guard"], expected_vehicles=["Royal Enfield"], difficulty="easy"),
        BenchmarkQuery(query="Bosch horn Baleno", query_type="brand_as_generic", expected_parts=["horn"], expected_vehicles=["Maruti Baleno"], difficulty="easy"),
        BenchmarkQuery(query="Valeo clutch Swift", query_type="brand_as_generic", expected_parts=["clutch kit", "clutch plate"], expected_vehicles=["Maruti Swift"], difficulty="easy"),
        BenchmarkQuery(query="Denso AC Creta", query_type="brand_as_generic", expected_parts=["AC compressor"], expected_vehicles=["Hyundai Creta"], difficulty="medium"),
        BenchmarkQuery(query="SKF bearing Wagon R front", query_type="brand_as_generic", expected_parts=["wheel bearing"], expected_vehicles=["Maruti Wagon R"], difficulty="medium"),
        BenchmarkQuery(query="Brembo brake Fortuner", query_type="brand_as_generic", expected_parts=["brake pad", "brake disc"], expected_vehicles=["Toyota Fortuner"], difficulty="easy"),
        BenchmarkQuery(query="Dunlop for Splendor", query_type="brand_as_generic", expected_parts=["tyre"], expected_vehicles=["Hero Splendor"], difficulty="medium"),
        BenchmarkQuery(query="Motul for Apache RTR", query_type="brand_as_generic", expected_parts=["engine oil"], expected_vehicles=["TVS Apache"], difficulty="easy"),
    ]


def generate_benchmark():
    queries = []
    queries.extend(_exact_english_queries())
    queries.extend(_hindi_hinglish_queries())
    queries.extend(_misspelled_queries())
    queries.extend(_symptom_queries())
    queries.extend(_part_number_queries())
    queries.extend(_brand_as_generic_queries())
    return queries


def save_benchmark(queries, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [q.to_dict() for q in queries]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(data)} benchmark queries to {output_path}")


def print_benchmark_stats(queries):
    print(f"\nTotal queries: {len(queries)}")
    type_counts = Counter(q.query_type for q in queries)
    print("\nBy query type:")
    for t, c in type_counts.most_common():
        print(f"  {t}: {c}")
    diff_counts = Counter(q.difficulty for q in queries)
    print("\nBy difficulty:")
    for d, c in diff_counts.most_common():
        print(f"  {d}: {c}")


if __name__ == "__main__":
    queries = generate_benchmark()
    output = TRAINING_DIR / "benchmark.json"
    save_benchmark(queries, output)
    print_benchmark_stats(queries)
