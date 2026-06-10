"""Transform 1.9a — OpenSanctions consolidated targets -> raw_opensanctions_entities.

Snapshot: fetches the full (small) consolidated CSV each run.
Alternative: skip this transform entirely and manually upload
targets.simple.csv into the same dataset — clean_opensanctions handles
both shapes.
"""
from __future__ import annotations

import logging

from transforms.api import Output, transform
from transforms.external.systems import Source, external_systems

from stratum import config, sources
from stratum.core.clients import opensanctions
from stratum.core.parsing.opensanctions import parse_targets
from stratum.datasets._util import to_spark

log = logging.getLogger(__name__)


@external_systems(osx=Source(sources.OPENSANCTIONS_SOURCE_RID))
@transform(out=Output(config.raw("raw_opensanctions_entities")))
def compute(ctx, osx, out):
    conn = osx.get_https_connection()
    text = opensanctions.fetch_targets_csv(
        conn.get_client(), conn.url, sources.OPENSANCTIONS_DEFAULT_PATH)
    pdf = parse_targets(text)
    log.info("opensanctions: %d entities", len(pdf))
    out.write_dataframe(to_spark(ctx, pdf))
