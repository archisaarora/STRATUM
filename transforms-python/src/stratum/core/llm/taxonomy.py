"""Capability-domain taxonomy (18 domains + none) and keyword banks.

The keyword banks serve three purposes:
  1. deterministic fallback classifier when no LLM is configured,
  2. weak-label bootstrapping for the fine-tuning dataset (Stage 5.1),
  3. validation that LLM outputs stay inside the taxonomy.
"""
from __future__ import annotations

CAPABILITY_DOMAINS = [
    "hypersonics",
    "autonomous_systems_air",
    "autonomous_systems_ground",
    "autonomous_systems_naval",
    "directed_energy",
    "electronic_warfare",
    "cyber_offense",
    "cyber_defense",
    "biodefense",
    "nuclear",
    "space_systems",
    "isr_platforms",
    "missile_defense",
    "conventional_ground_forces",
    "naval_surface",
    "submarine",
    "logistics_supply_chain",
    "dual_use_research",
    "none",
]

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "hypersonics": [
        "hypersonic", "hgv", "glide vehicle", "scramjet", "mach 5", "mach 6",
        "mach 8", "boost-glide", "boost glide", "arrw", "conventional prompt strike",
        "high-speed strike", "thermal protection system",
    ],
    "autonomous_systems_air": [
        "unmanned aircraft", "unmanned aerial", "uas", "uav", "drone",
        "loyal wingman", "collaborative combat aircraft", "loitering munition",
        "autonomous flight", "swarm", "counter-uas", "mq-9", "mq-25", "rq-4",
    ],
    "autonomous_systems_ground": [
        "unmanned ground vehicle", "ugv", "autonomous ground", "robotic combat vehicle",
        "ground robot", "autonomous convoy", "teleoperated vehicle",
    ],
    "autonomous_systems_naval": [
        "unmanned underwater", "uuv", "unmanned surface vessel", "usv",
        "autonomous underwater vehicle", "auv", "unmanned maritime",
        "extra-large unmanned", "xluuv", "mine countermeasures unmanned",
    ],
    "directed_energy": [
        "directed energy", "high energy laser", "high-energy laser", "laser weapon",
        "high power microwave", "high-powered microwave", "particle beam",
        "beam control", "electromagnetic railgun", "counter-electronics weapon",
    ],
    "electronic_warfare": [
        "electronic warfare", "electronic attack", "electronic protection", "jammer",
        "jamming", "signals intelligence", "sigint", "electromagnetic spectrum",
        "radar warning receiver", "electronic countermeasures", "spectrum dominance",
        "phased array", "aesa",
    ],
    "cyber_offense": [
        "offensive cyber", "cyber effects", "computer network attack", "cyber operations",
        "exploit development", "vulnerability research", "cyber mission force",
    ],
    "cyber_defense": [
        "cybersecurity", "cyber security", "cyber defense", "network defense",
        "zero trust", "endpoint detection", "intrusion detection", "cryptographic",
        "information assurance", "security operations center",
    ],
    "biodefense": [
        "biodefense", "biosurveillance", "biological threat", "medical countermeasure",
        "vaccine development", "pathogen", "chemical biological", "cbrn",
        "biosafety", "select agent", "anthrax", "battlefield medicine",
    ],
    "nuclear": [
        "nuclear deterrent", "nuclear weapon", "warhead", "stockpile stewardship",
        "icbm", "ballistic missile submarine", "uranium enrichment", "plutonium",
        "nuclear command", "w88", "w87", "sentinel icbm", "tritium",
    ],
    "space_systems": [
        "satellite", "space vehicle", "launch vehicle", "space domain awareness",
        "space situational awareness", "on-orbit", "geosynchronous", "low earth orbit",
        "space launch", "anti-satellite", "proliferated warfighter space",
    ],
    "isr_platforms": [
        "intelligence surveillance reconnaissance", "isr", "reconnaissance",
        "surveillance aircraft", "electro-optical", "infrared sensor", "synthetic aperture radar",
        "maritime patrol", "airborne early warning", "geospatial intelligence", "imagery intelligence",
    ],
    "missile_defense": [
        "missile defense", "interceptor", "thaad", "patriot", "aegis", "sm-3", "sm-6",
        "ballistic missile defense", "air and missile defense", "kill vehicle",
        "early warning radar", "counter-hypersonic", "glide phase interceptor",
    ],
    "conventional_ground_forces": [
        "armored vehicle", "tank", "artillery", "howitzer", "ammunition", "munitions",
        "small arms", "infantry", "ground combat", "armored personnel carrier",
        "155mm", "120mm", "precision fires", "rocket system", "himars", "gmlrs",
    ],
    "naval_surface": [
        "destroyer", "frigate", "surface combatant", "shipbuilding", "aircraft carrier",
        "amphibious assault", "littoral combat ship", "naval gun", "vertical launching system",
        "ddg", "ffg", "shipyard",
    ],
    "submarine": [
        "submarine", "undersea warfare", "torpedo", "sonar", "anti-submarine",
        "virginia class", "columbia class", "attack submarine", "periscope",
        "towed array",
    ],
    "logistics_supply_chain": [
        "logistics", "sustainment", "supply chain", "depot maintenance", "spare parts",
        "transportation services", "fuel delivery", "warehousing", "distribution center",
        "prepositioned stock",
    ],
    "dual_use_research": [
        "basic research", "applied research", "university research", "quantum",
        "artificial intelligence", "machine learning", "microelectronics",
        "semiconductor", "advanced materials", "additive manufacturing", "biotechnology",
        "research initiative", "stem education",
    ],
}

MATURITY_KEYWORDS: dict[str, list[str]] = {
    "research": [
        "basic research", "applied research", "research and development", "phase i",
        "sbir", "sttr", "study", "feasibility", "science and technology", "6.1", "6.2",
        "university", "laboratory research",
    ],
    "development": [
        "development", "prototype", "prototyping", "demonstration", "demonstrator",
        "engineering and manufacturing development", "emd", "phase ii", "phase iii",
        "test and evaluation", "flight test", "qualification testing", "design",
    ],
    "production": [
        "production", "procurement of", "full rate production", "low rate initial production",
        "lrip", "manufacture", "manufacturing", "delivery of", "deliveries", "lot ",
        "fabrication", "assembly", "supply of",
    ],
    "sustainment": [
        "sustainment", "maintenance", "repair", "overhaul", "spares", "logistics support",
        "in-service support", "depot", "modernization of fielded", "follow-on support",
        "technical support services", "contractor logistics",
    ],
}
