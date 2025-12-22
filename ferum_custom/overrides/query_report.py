from __future__ import annotations

# Compatibility wrapper: the app's primary module is `ferum_custom`, while most custom code lives under
# `ferum_custom.ferum_custom` (historical structure). Keep hook paths stable.

from ferum_custom.ferum_custom.overrides.query_report import run  # noqa: F401

