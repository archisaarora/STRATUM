"""Foundry transforms for STRATUM, discovered by stratum.pipeline.

Layout mirrors the pipeline stages:
  ingest/   — Stage 1a: external transforms calling source APIs -> raw_*
  clean/    — Stage 1b: standardization -> clean_*
  features/ — Stage 2 + 3: feature engineering and LLM classification
  scores/   — Stage 4: credibility, acceleration, signals, profiles
  ontology_export/ — object-type backing datasets for Ontology Manager

These modules import `transforms.api` and only run inside Foundry; all
business logic lives in stratum.core (locally testable).
"""
