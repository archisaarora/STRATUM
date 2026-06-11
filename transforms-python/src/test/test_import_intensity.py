"""Import-intensity forensics: the covert-acquisition detector."""
import pandas as pd

from stratum.core.features.baselines import annual_with_baselines, map_capability
from stratum.core.features.import_intensity import import_intensity
from stratum.core.scoring.signals import generate_all_signals
from test.test_features import make_flows

HS_REF = pd.DataFrame([
    {"hs_code": "3601", "commodity_name": "Propellant powders",
     "capability_category": "propellants_and_explosives", "signal_weight": 1.0},
    {"hs_code": "9301", "commodity_name": "Military weapons",
     "capability_category": "arms_direct", "signal_weight": 1.0},
])


def _scenario_flows() -> pd.DataFrame:
    """IRN: dual-use (propellants) triples while direct arms imports stay
    flat. FRA/USA/PAK/IND: proportional, calm behavior (peer cohort)."""
    frames = [
        make_flows([100e6, 100e6, 100e6, 100e6, 320e6], hs="3601", country="IRN"),
        make_flows([20e6, 20e6, 21e6, 20e6, 21e6], hs="9301", country="IRN"),
    ]
    for c, scale in [("FRA", 1.0), ("USA", 4.0), ("PAK", 0.5), ("IND", 1.5)]:
        frames.append(make_flows(
            [v * scale for v in (90e6, 92e6, 91e6, 93e6, 95e6)],
            hs="3601", country=c))
        frames.append(make_flows(
            [v * scale for v in (40e6, 41e6, 40e6, 42e6, 43e6)],
            hs="9301", country=c))
    return annual_with_baselines(map_capability(pd.concat(frames), HS_REF))


def _milex() -> pd.DataFrame:
    rows = []
    for c, v in [("IRN", 10e9), ("FRA", 55e9), ("USA", 800e9),
                 ("PAK", 11e9), ("IND", 80e9)]:
        for y in range(2020, 2025):
            rows.append({"country_code": c, "year": y,
                         "measure": "expenditure_current_usd", "value": v})
    return pd.DataFrame(rows)


def test_streams_split_and_ratio():
    df = import_intensity(_scenario_flows(), _milex())
    irn_2024 = df[(df.country_code == "IRN") & (df.year == 2024)].iloc[0]
    assert irn_2024["direct_value"] == 21e6
    assert irn_2024["dual_use_value"] == 320e6
    assert 0.9 < irn_2024["dual_use_share"] < 1.0
    assert abs(irn_2024["intensity_ratio"] - 341e6 / 10e9) < 1e-6
    assert irn_2024["top_dual_use_category"] == "propellants_and_explosives"


def test_covert_flag_fires_for_pattern_only():
    df = import_intensity(_scenario_flows(), _milex())
    flagged = df[df["covert_acquisition_flag"].fillna(False)]
    assert set(flagged["country_code"]) == {"IRN"}, (
        "only the dual-use-surge-with-flat-direct pattern should flag")
    assert flagged.iloc[0]["year"] == 2024
    # peers behaving proportionally must never flag
    assert not df[df.country_code == "FRA"]["covert_acquisition_flag"].any()
    assert not df[df.country_code == "USA"]["covert_acquisition_flag"].any()


def test_covert_signal_and_compound_interplay():
    flows = _scenario_flows()
    milex = _milex()
    intensity = import_intensity(flows, milex)
    signals = generate_all_signals(
        flows=flows, accel=None, budget=None, credibility=None,
        velocity=None, intensity=intensity)

    covert = signals[signals.signal_type == "covert_acquisition"]
    assert len(covert) == 1
    sig = covert.iloc[0]
    assert sig["country_code"] == "IRN"
    assert sig["domain"] == "propellants_and_explosives"
    assert 0 < sig["signal_strength"] <= 1
    assert "outside declared channels" in sig["description_text"]

    # covert + material anomaly share (IRN, propellants) => compound fires
    compound = signals[(signals.signal_type == "compound_signal")
                       & (signals.country_code == "IRN")]
    assert len(compound) == 1
    assert sig["signal_id"] in compound.iloc[0]["supporting_evidence"]


def test_empty_inputs():
    empty = import_intensity(
        pd.DataFrame(columns=["flow_direction", "capability_category",
                              "reporter_country", "year", "trade_value_usd",
                              "baseline_deviation_pct"]),
        _milex())
    assert len(empty) == 0
    assert "covert_acquisition_flag" in empty.columns
