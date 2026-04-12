"""Merge LLM-extracted ITI content (6 per-PDF JSONs) into v2 knowledge-graph files.

Reads: data/knowledge_graph/iti_extracted/<trade>.json (6 files)
Writes:
- data/knowledge_graph/iti_systems_v2.json
- data/knowledge_graph/iti_diagnostics_v2.json
- data/knowledge_graph/iti_aliases_v2.json

Every output entry carries provenance: {method: "llm_extracted", trade, pdf, page}.
Dedupes across trades (same system appears in MMV + Diesel + 2W/3W → one canonical
entry with union of parts + all source pages). See ADR 008.

Run:
    python3 scripts/merge_iti_v2.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
EXTRACTED = ROOT / "data" / "knowledge_graph" / "iti_extracted"
OUT = ROOT / "data" / "knowledge_graph"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


# Canonical system IDs — normalize variants across trades.
# Extraction agents used slightly different IDs; this collapses them to our schema.
SYSTEM_ALIAS = {
    "engine": "engine",
    "internal_combustion_engine": "engine",
    "ic_engine": "engine",
    "diesel_engine": "engine",
    "petrol_engine": "engine",
    "engine_system": "engine",
    "fuel_system": "fuel_system",
    "fuel_injection_system": "fuel_system",
    "diesel_fuel_system": "fuel_system",
    "petrol_fuel_system": "fuel_system",
    "fuel_supply_system": "fuel_system",
    "cooling_system": "cooling_system",
    "engine_cooling": "cooling_system",
    "engine_cooling_system": "cooling_system",
    "lubrication_system": "lubrication_system",
    "engine_lubrication": "lubrication_system",
    "intake_system": "intake_system",
    "air_intake_system": "intake_system",
    "air_intake": "intake_system",
    "intake": "intake_system",
    "exhaust_system": "exhaust_emission",
    "exhaust_and_emission_system": "exhaust_emission",
    "exhaust_and_emission": "exhaust_emission",
    "emission_system": "exhaust_emission",
    "exhaust_emission": "exhaust_emission",
    "emission_control_system": "exhaust_emission",
    "braking_system": "braking_system",
    "brake_system": "braking_system",
    "brakes": "braking_system",
    "electronic_brakes": "braking_system",
    "suspension": "suspension",
    "suspension_system": "suspension",
    "suspension_steering": "suspension",
    "steering": "steering",
    "steering_system": "steering",
    "power_steering": "steering",
    "electric_power_steering": "steering",
    "electronic_power_steering": "steering",
    "transmission": "transmission",
    "transmission_system": "transmission",
    "manual_transmission": "transmission",
    "automatic_transmission": "transmission",
    "electronic_transmission": "transmission",
    "driveline": "transmission",
    "drivetrain": "transmission",
    "clutch_system": "transmission",
    "clutch": "transmission",
    "final_drive": "transmission",
    "electrical_system": "electrical_system",
    "charging_system": "electrical_system",
    "starting_system": "electrical_system",
    "ignition_system": "electrical_system",
    "cdi_ignition": "electrical_system",
    "tci_ignition": "electrical_system",
    "auto_electrical": "electrical_system",
    "battery_system": "electrical_system",
    "body_electrical": "body_electrical",
    "body_electrical_and_accessories": "body_electrical",
    "lighting_system": "body_electrical",
    "lighting": "body_electrical",
    "lighting_and_accessories": "body_electrical",
    "lighting_accessories": "body_electrical",
    "dashboard": "body_electrical",
    "dashboard_instrumentation": "body_electrical",
    "instrumentation": "body_electrical",
    "vehicle_networks": "body_electrical",
    "can_lin_networks": "body_electrical",
    "hvac_system": "ac_system",
    "hvac": "ac_system",
    "ac_system": "ac_system",
    "ac_and_climate_control_system": "ac_system",
    "climate_control": "ac_system",
    "ev_system": "ev_system",
    "electric_vehicle_system": "ev_system",
    "electric_drive_system": "ev_system",
    "ev_drive": "ev_system",
    "high_voltage_system": "ev_system",
    "battery_management": "ev_system",
    "motor_controller": "ev_system",
    "charging_infrastructure": "ev_system",
    "chassis": "chassis",
    "chassis_body": "chassis",
    "body": "chassis",
    "frame": "chassis",
    "wheels_tyres": "wheels",
    "wheels_and_tyres": "wheels",
    "wheels": "wheels",
    "tyres": "wheels",
    "hydraulic_system": "hydraulic_system",
    "tractor_hydraulics": "hydraulic_system",
    "pto_system": "pto_system",
    "pto": "pto_system",
    "power_take_off": "pto_system",
    "implements": "implements",
    "agricultural_implements": "implements",
    "hitch_system": "implements",
    "three_point_hitch": "implements",
    "safety_system": "safety",
    "safety": "safety",
    "hvil": "safety",
    "high_voltage_interlock": "safety",
    # Additional consolidations after first v2 pass (2026-04-12)
    "engine_2w3w": "engine",
    "tractor_diesel_engine": "engine",
    "engine_head_valvetrain": "engine",
    "cylinder_head_valve_train": "engine",
    "engine_crank_block": "engine",
    "engine_piston_rod": "engine",
    "piston_conrod": "engine",
    "cylinder_block": "engine",
    "crankshaft_flywheel": "engine",
    "edc_mpfi": "fuel_system",
    "diesel_fuel_injection": "fuel_system",
    "fuel_carburetor": "fuel_system",
    "fuel_petrol_efi": "fuel_system",
    "fuel_diesel": "fuel_system",
    "fuel_feed_diesel": "fuel_system",
    "fuel_injection": "fuel_system",
    "lpg_cng": "fuel_system",
    "governor": "fuel_system",
    "cooling": "cooling_system",
    "thermal_management": "cooling_system",
    "lubrication": "lubrication_system",
    "braking": "braking_system",
    "brakes_electronic": "braking_system",
    "starting": "electrical_system",
    "charging": "electrical_system",
    "ignition": "electrical_system",
    "battery": "electrical_system",
    "wiring": "electrical_system",
    "charging_electrical": "electrical_system",
    "electrical_accessories": "body_electrical",
    "lv_accessories": "body_electrical",
    "electrical_charging_starting": "electrical_system",
    "starting_charging": "electrical_system",
    "comm_networks": "body_electrical",
    "diagnostic_tools": "body_electrical",
    "clutch_transmission": "transmission",
    "transmission_manual": "transmission",
    "transmission_electronic": "transmission",
    "differential": "transmission",
    "intake_exhaust": "intake_system",
    "exhaust": "exhaust_emission",
    "emission": "exhaust_emission",
    "emission_control": "exhaust_emission",
    # EV consolidation — keep ev_system as the umbrella
    "hv_battery_pack": "ev_system",
    "hv_distribution": "ev_system",
    "traction_motor": "ev_system",
    "regenerative_braking": "ev_system",
    "bms": "ev_system",
    "dc_dc_converter": "ev_system",
    "onboard_charging": "ev_system",
    "charging_ecosystem": "ev_system",
    "ev_2w3w": "ev_system",
    "ev_components": "ev_system",
    "chassis_drivetrain": "chassis",
    "body_frame_2w3w": "chassis",
}


def canonical_system_id(system_name: str, system_id: str = "") -> str:
    raw = (system_id or "").replace("system:", "")
    if not raw:
        raw = slug(system_name)
    return SYSTEM_ALIAS.get(raw, raw)


def main() -> int:
    files = sorted(EXTRACTED.glob("*.json"))
    if not files:
        print("no extractions found", file=sys.stderr)
        return 1

    systems: dict[str, dict] = {}
    diagnostics: dict[str, dict] = {}
    aliases: list[dict] = []

    for f in files:
        data = json.load(open(f))
        trade = data.get("trade_key", f.stem)
        pdf = data.get("pdf_path", "")

        for s in data.get("systems", []):
            cid = canonical_system_id(s.get("system_name", ""), s.get("system_id", ""))
            entry = systems.setdefault(cid, {
                "system_id": f"system:{cid}",
                "system_name": s.get("system_name", cid.replace("_", " ").title()),
                "description": s.get("description", ""),
                "source_trades": set(),
                "source_pages_by_trade": defaultdict(list),
                "parts": {},
            })
            entry["source_trades"].add(trade)
            for pg in s.get("source_pages", []):
                entry["source_pages_by_trade"][trade].append(pg)
            if not entry["description"] and s.get("description"):
                entry["description"] = s["description"]

            for p in s.get("parts", []):
                pname = (p.get("name") or "").strip()
                if not pname:
                    continue
                pkey = slug(pname)
                part = entry["parts"].get(pkey)
                if part is None:
                    part = {
                        "name": pname,
                        "aliases": list(p.get("aliases", [])),
                        "role": p.get("role", "") or "",
                        "provenance": [],
                    }
                    entry["parts"][pkey] = part
                else:
                    for a in p.get("aliases", []):
                        if a and a not in part["aliases"]:
                            part["aliases"].append(a)
                    if not part["role"] and p.get("role"):
                        part["role"] = p["role"]
                part["provenance"].append({
                    "method": "llm_extracted",
                    "trade": trade,
                    "pdf": pdf,
                    "page": p.get("source_page", 0),
                })

        for d in data.get("diagnostics", []):
            symptom = (d.get("symptom") or "").strip()
            if not symptom:
                continue
            dkey = slug(symptom)
            diag = diagnostics.get(dkey)
            if diag is None:
                diag = {
                    "id": f"diag:{dkey}",
                    "symptom": symptom,
                    "system": d.get("system", ""),
                    "diagnosis_steps": list(d.get("diagnosis_steps", [])),
                    "related_parts": list(d.get("related_parts", [])),
                    "vehicle_types": [],
                    "provenance": [],
                }
                diagnostics[dkey] = diag
            else:
                for st in d.get("diagnosis_steps", []):
                    if st and st not in diag["diagnosis_steps"]:
                        diag["diagnosis_steps"].append(st)
                for rp in d.get("related_parts", []):
                    if rp and rp not in diag["related_parts"]:
                        diag["related_parts"].append(rp)
            vt = d.get("vehicle_type", "")
            if vt and vt not in diag["vehicle_types"]:
                diag["vehicle_types"].append(vt)
            diag["provenance"].append({
                "method": "llm_extracted",
                "trade": trade,
                "pdf": pdf,
                "page": d.get("source_page", 0),
                "confidence": d.get("confidence", 0.8),
            })

        for a in data.get("aliases", []):
            canonical = (a.get("canonical") or "").strip()
            alias = (a.get("alias") or "").strip()
            if not (canonical and alias):
                continue
            aliases.append({
                "canonical": canonical,
                "alias": alias,
                "provenance": {
                    "method": "llm_extracted",
                    "trade": trade,
                    "pdf": pdf,
                    "page": a.get("source_page", 0),
                },
            })

    # Serialize: sets → lists, sort stably
    systems_out = []
    for cid in sorted(systems):
        s = systems[cid]
        s["source_trades"] = sorted(s["source_trades"])
        s["source_pages_by_trade"] = {
            k: sorted(set(v)) for k, v in sorted(s["source_pages_by_trade"].items())
        }
        s["parts"] = sorted(s["parts"].values(), key=lambda x: x["name"])
        systems_out.append(s)

    diagnostics_out = sorted(diagnostics.values(), key=lambda x: x["id"])

    trades = sorted({p["provenance"][0]["trade"] for s in systems_out for p in s["parts"]})

    systems_payload = {
        "metadata": {
            "description": "Vehicle systems + parts extracted from DGT ITI syllabi via LLM (T102b)",
            "source": "iti_dgt_v2",
            "version": "2.0",
            "extraction_date": "2026-04-12",
            "method": "llm_extracted",
            "trades_processed": trades,
            "total_systems": len(systems_out),
            "total_parts": sum(len(s["parts"]) for s in systems_out),
            "supersedes": "iti_systems.json (hand-curated v1 retained as fallback per ADR 008)",
        },
        "systems": systems_out,
    }
    diagnostics_payload = {
        "metadata": {
            "description": "Diagnostic chains extracted from DGT ITI syllabi via LLM (T103b)",
            "source": "iti_dgt_v2",
            "version": "2.0",
            "extraction_date": "2026-04-12",
            "method": "llm_extracted",
            "total_chains": len(diagnostics_out),
            "supersedes": "iti_diagnostics.json (hand-curated v1 retained as fallback per ADR 008)",
        },
        "chains": diagnostics_out,
    }
    aliases_payload = {
        "metadata": {
            "description": "Indian-English / Hindi aliases extracted from DGT ITI syllabi via LLM",
            "source": "iti_dgt_v2",
            "version": "2.0",
            "extraction_date": "2026-04-12",
            "method": "llm_extracted",
            "total_aliases": len(aliases),
        },
        "aliases": aliases,
    }

    (OUT / "iti_systems_v2.json").write_text(
        json.dumps(systems_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT / "iti_diagnostics_v2.json").write_text(
        json.dumps(diagnostics_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT / "iti_aliases_v2.json").write_text(
        json.dumps(aliases_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"iti_systems_v2.json:      {len(systems_out)} systems, "
          f"{sum(len(s['parts']) for s in systems_out)} parts")
    print(f"iti_diagnostics_v2.json:  {len(diagnostics_out)} chains")
    print(f"iti_aliases_v2.json:      {len(aliases)} alias pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
