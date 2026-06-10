"""STRATUM global configuration.

Single place to adjust Foundry dataset paths, the monitored-country list,
defense-relevant HS codes, scoring thresholds, and the LLM mode.

IMPORTANT — before first build in Foundry:
  1. Set PROJECT_ROOT to the Foundry path of your STRATUM project
     (Compass path, e.g. "/Your Org/STRATUM").
  2. Pick LLM_MODE ("aip" needs AIP model access; "keyword" always works).
  3. Fill in the Source RIDs in stratum/sources.py for API ingestion.
"""

# --------------------------------------------------------------------------
# Foundry project layout (mirrors the build-prompt project structure)
# --------------------------------------------------------------------------
PROJECT_ROOT = "/STRATUM"  # TODO: set to your Foundry project path

RAW = PROJECT_ROOT + "/data/raw"
CLEAN = PROJECT_ROOT + "/data/clean"
FEATURES = PROJECT_ROOT + "/data/features"
SCORES = PROJECT_ROOT + "/data/scores"
REFERENCE = PROJECT_ROOT + "/data/reference"
ONTOLOGY_EXPORT = PROJECT_ROOT + "/data/ontology"


def raw(name: str) -> str:
    return f"{RAW}/{name}"


def clean(name: str) -> str:
    return f"{CLEAN}/{name}"


def features(name: str) -> str:
    return f"{FEATURES}/{name}"


def scores(name: str) -> str:
    return f"{SCORES}/{name}"


def reference(name: str) -> str:
    return f"{REFERENCE}/{name}"


def ontology(name: str) -> str:
    return f"{ONTOLOGY_EXPORT}/{name}"


# --------------------------------------------------------------------------
# Temporal scope — 2020+ gives a 5-year baseline for anomaly detection
# --------------------------------------------------------------------------
HISTORY_START_YEAR = 2020
WORLDBANK_START_YEAR = 2015   # macro context benefits from a longer tail
ROLLING_BASELINE_YEARS = 3

# --------------------------------------------------------------------------
# Country scope
# --------------------------------------------------------------------------
MONITORED_COUNTRIES = [
    "CHN", "RUS", "IRN", "PRK", "BLR", "MMR", "VEN",
    "SYR", "YEM", "ETH", "SDN", "PAK", "IND",
]
NATO_BASELINE = [
    "ALB", "BEL", "BGR", "CAN", "HRV", "CZE", "DNK", "EST", "FIN", "FRA",
    "DEU", "GRC", "HUN", "ISL", "ITA", "LVA", "LTU", "LUX", "MNE", "NLD",
    "MKD", "NOR", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE", "TUR",
    "GBR", "USA",
]
TARGET_COUNTRIES = MONITORED_COUNTRIES + NATO_BASELINE

# UN Comtrade uses M49 numeric reporter codes; ISO-numeric matches M49 for
# standard countries. Taiwan reports as "Other Asia, nes" (490).
COMTRADE_SPECIAL_M49 = {"TWN": 490}

# --------------------------------------------------------------------------
# UN Comtrade — defense-relevant HS codes (4-digit headings)
# --------------------------------------------------------------------------
DEFENSE_HS_CODES = [
    "2710", "2804", "2807", "2814", "2846", "2901", "2902",
    "3601", "3602", "3603", "3604",
    "7108", "7202", "7601", "7612", "8108",
    "8504", "8517", "8526", "8542",
    "8802", "8803", "8905", "8906",
    "9301", "9302", "9303", "9304", "9305", "9306", "9307",
]
COMTRADE_DAILY_CALL_BUDGET = 450      # free tier: 500/day — keep headroom
COMTRADE_PARTNER_DETAIL = False       # True = pull partner-level rows too

# --------------------------------------------------------------------------
# World Bank indicators
# --------------------------------------------------------------------------
WORLDBANK_INDICATORS = [
    "NY.GDP.MKTP.CD",     # GDP current USD
    "NY.GDP.MKTP.KD.ZG",  # GDP growth %
    "NV.IND.MANF.ZS",     # Manufacturing % of GDP
    "EG.USE.PCAP.KG.OE",  # Energy use per capita
    "MS.MIL.XPND.GD.ZS",  # Military expenditure % GDP
    "MS.MIL.XPND.CN",     # Military expenditure current LCU
    "NE.EXP.GNFS.ZS",     # Exports % GDP
    "SP.POP.TOTL",        # Population
]

# --------------------------------------------------------------------------
# USASpending
# --------------------------------------------------------------------------
USASPENDING_AGENCIES = ["Department of Defense"]  # add more toptier names
USASPENDING_AWARD_TYPES = ["A", "B", "C", "D"]    # contract award type codes
USASPENDING_PAGE_LIMIT = 100
USASPENDING_MAX_PAGES_PER_RUN = 400               # ~40k awards per run

# --------------------------------------------------------------------------
# Scoring thresholds (Layer 2 / Layer 3)
# --------------------------------------------------------------------------
BASELINE_ANOMALY_FLAG_PCT = 50.0       # >50% above 3y baseline => anomalous
SIGNAL_MATERIAL_MIN_SCORE = 0.7        # material_anomaly rule
SIGNAL_MATERIAL_MIN_DEVIATION = 100.0  # material_anomaly rule
BUDGET_DISCREPANCY_FLAG_PCT = 15.0     # SIPRI vs World Bank milex
UNDERDECLARATION_SIGNAL_MIN = 60.0     # budget_discrepancy rule
ARMS_SPIKE_MULTIPLIER = 2.0            # current TIV > 2x rolling avg
ACCEL_COUNT_MULTIPLIER = 2.0           # 12m contract count > 2x prior 12m
ACCEL_VALUE_GROWTH_PCT = 50.0          # AND value growth > 50%
COMPOUND_WINDOW_MONTHS = 6
COMPOUND_ESCALATION = 1.5
SIGNAL_ACTIVE_WINDOW_MONTHS = 12       # signals considered "active" for TAI

# Threat tier thresholds on threat_acceleration_index (0–100)
TIER_S = 75.0
TIER_A = 50.0
TIER_B = 25.0

# Lead-time bands (months) by dominant capability maturity stage
LEAD_TIME_BANDS = {
    "research": (36, 72),
    "development": (18, 36),
    "production": (6, 18),
    "sustainment": (6, 18),
    "unknown": (18, 72),
}

# --------------------------------------------------------------------------
# LLM classification (Pipeline Stage 3)
# --------------------------------------------------------------------------
# "aip"      -> palantir_models language model inside the transform (default)
# "keyword"  -> deterministic keyword/NAICS classifier only (no LLM needed)
# "external" -> fine-tuned Mistral behind an OpenAI-compatible endpoint,
#               reached through an External Transform Source
LLM_MODE = "aip"
# AIP model RID — find under AIP > Models; GPT-4o / Claude both work.
AIP_MODEL_RID = "ri.language-model-service..language-model.gpt-4-o"
LLM_BATCH_SIZE = 100
LLM_MAX_RETRIES = 3
LLM_MAX_CONTRACTS_PER_RUN = 2000       # incremental budget per build
