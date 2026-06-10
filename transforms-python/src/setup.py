import os

from setuptools import find_packages, setup

setup(
    name=os.environ.get("PKG_NAME", "stratum"),
    version=os.environ.get("PKG_VERSION", "1.0.0"),
    description="STRATUM — Geopolitical Threat Capability Intelligence Platform",
    packages=find_packages(exclude=["test", "test.*"]),
    entry_points={
        "transforms.pipelines": ["root = stratum.pipeline:my_pipeline"],
    },
)
