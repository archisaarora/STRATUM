"""Country-name standardization through the ref_country_iso_lookup dataset.

Quality requirement: country standardization must ALWAYS go through the
reference table — never ad-hoc string matching. Build a `CountryIndex`
from the reference DataFrame once per transform and reuse it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")


def _norm(name: str) -> str:
    """Casefold + strip punctuation so 'Côte d’Ivoire' == 'cote divoire'."""
    s = str(name).strip().lower()
    s = (s.replace("’", "'").replace("`", "'")
          .replace("&", " and ").replace("-", " "))
    s = _PUNCT.sub("", s)
    return _WS.sub(" ", s).strip()


@dataclass
class CountryIndex:
    by_name: dict[str, str] = field(default_factory=dict)   # normalized name -> iso3
    by_iso2: dict[str, str] = field(default_factory=dict)
    by_m49: dict[int, str] = field(default_factory=dict)
    meta: pd.DataFrame = field(default_factory=pd.DataFrame)  # iso3-indexed

    @classmethod
    def from_reference(cls, ref: pd.DataFrame) -> "CountryIndex":
        idx = cls()
        for row in ref.itertuples(index=False):
            iso3 = str(row.iso3).upper()
            idx.by_name[_norm(row.country_name)] = iso3
            idx.by_name[_norm(iso3)] = iso3
            aliases = str(getattr(row, "aliases", "") or "")
            for alias in aliases.split("|"):
                if alias.strip():
                    idx.by_name.setdefault(_norm(alias), iso3)
            iso2 = str(getattr(row, "iso2", "") or "").upper()
            if iso2:
                idx.by_iso2[iso2] = iso3
            m49 = getattr(row, "m49_code", None)
            if pd.notna(m49):
                idx.by_m49[int(m49)] = iso3
        idx.meta = ref.set_index(ref["iso3"].str.upper())
        return idx

    def to_iso3(self, value: object) -> str | None:
        """Resolve a country name, ISO2/ISO3 code, or M49 number to ISO3."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, (int, float)):
            return self.by_m49.get(int(value))
        s = str(value).strip()
        if not s:
            return None
        if s.isdigit():
            return self.by_m49.get(int(s))
        up = s.upper()
        if len(up) == 3 and _norm(up) in self.by_name and up == self.by_name.get(_norm(up)):
            return up
        if len(up) == 2 and up in self.by_iso2:
            return self.by_iso2[up]
        return self.by_name.get(_norm(s))

    def standardize_column(
        self, df: pd.DataFrame, col: str, out_col: str | None = None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Map a column to ISO3. Returns (df_with_out_col, unmatched_rows).

        Unmatched rows are returned (not silently dropped) so transforms can
        log them — quality requirement on logging error rates.
        """
        out_col = out_col or col
        df = df.copy()
        mapped = df[col].map(self.to_iso3)
        unmatched = df.loc[mapped.isna() & df[col].notna(), [col]].drop_duplicates()
        df[out_col] = mapped
        return df, unmatched

    def name_of(self, iso3: str) -> str:
        try:
            return str(self.meta.loc[iso3, "country_name"])
        except KeyError:
            return iso3

    def region_of(self, iso3: str) -> str:
        try:
            return str(self.meta.loc[iso3, "region"] or "")
        except KeyError:
            return ""

    def monitored(self) -> list[str]:
        m = self.meta
        return sorted(m.index[m["is_monitored"].astype(bool)].tolist())
