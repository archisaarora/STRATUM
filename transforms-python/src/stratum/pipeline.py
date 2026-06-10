from transforms.api import Pipeline

import stratum.datasets.clean
import stratum.datasets.features
import stratum.datasets.ingest
import stratum.datasets.ontology_export
import stratum.datasets.scores

my_pipeline = Pipeline()
my_pipeline.discover_transforms(
    stratum.datasets.ingest,
    stratum.datasets.clean,
    stratum.datasets.features,
    stratum.datasets.scores,
    stratum.datasets.ontology_export,
)
