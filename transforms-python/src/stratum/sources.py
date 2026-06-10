"""External Transform Source registry.

Every API ingest transform reaches the internet through a Foundry
*Data Connection Source* (REST API source) with an egress policy. Create one
source per system (Data Connection > New Source > REST API), enable
"Allow this source to be imported into code repositories", attach the egress
policy for the domain, add the API credential as an *additional secret*,
then paste the Source RID here.

See docs/00_FOUNDRY_RUNBOOK.md section 4 for click-by-click steps.

Secret names below must match the additional-secret names you configure on
the source. Sources without credentials (USASpending, World Bank,
OpenSanctions, defense.gov) just need the egress policy.
"""

# --- Source RIDs (paste from Data Connection after creating each source) ---
USASPENDING_SOURCE_RID = "ri.magritte..source.REPLACE_ME"   # api.usaspending.gov
DEFENSE_GOV_SOURCE_RID = "ri.magritte..source.REPLACE_ME"   # www.defense.gov
COMTRADE_SOURCE_RID = "ri.magritte..source.REPLACE_ME"      # comtradeapi.un.org
WORLDBANK_SOURCE_RID = "ri.magritte..source.REPLACE_ME"     # api.worldbank.org
ACLED_SOURCE_RID = "ri.magritte..source.REPLACE_ME"         # acleddata.com
OPENSANCTIONS_SOURCE_RID = "ri.magritte..source.REPLACE_ME" # data.opensanctions.org

# --- Additional-secret names configured on each source -----------------
COMTRADE_KEY_SECRET = "additionalSecretComtradeApiKey"
ACLED_KEY_SECRET = "additionalSecretAcledApiKey"      # legacy key auth
ACLED_EMAIL_SECRET = "additionalSecretAcledEmail"     # legacy key auth
ACLED_TOKEN_SECRET = "additionalSecretAcledToken"     # new OAuth bearer token

# --- Public base URLs (used directly by the local fetch scripts; in
#     Foundry the same URL is configured on the source) -----------------
USASPENDING_BASE = "https://api.usaspending.gov"
DEFENSE_GOV_BASE = "https://www.defense.gov"
COMTRADE_BASE = "https://comtradeapi.un.org"   # keyed AND public preview paths
WORLDBANK_BASE = "https://api.worldbank.org"   # classic v2 (default)
DATA360_BASE = "https://data360api.worldbank.org"  # newer World Bank platform
ACLED_LEGACY_BASE = "https://api.acleddata.com"
ACLED_BASE = "https://acleddata.com"
OPENSANCTIONS_BASE = "https://data.opensanctions.org"
OPENSANCTIONS_DEFAULT_PATH = "/datasets/latest/default/targets.simple.csv"
