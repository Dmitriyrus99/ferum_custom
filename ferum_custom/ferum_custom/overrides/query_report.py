from __future__ import annotations

"""Compatibility wrapper.

Historically, some installations imported the report override from the Frappe module path
`ferum_custom.ferum_custom.overrides.query_report`. The canonical hook path is
`ferum_custom.overrides.query_report.run`.
"""

from ferum_custom.overrides.query_report import run
