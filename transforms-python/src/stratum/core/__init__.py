"""Pure-Python/pandas business logic for STRATUM.

Nothing in this package imports `transforms.api` or any Foundry-only
library, so every module here is unit-testable locally and in Foundry CI.
Foundry transform wrappers live in `stratum.datasets.*` and adapt
Spark/Foundry I/O to these functions.
"""
