from __future__ import annotations

import json
from typing import Any

from frappe.email.doctype.email_account.email_account import EmailAccount


def _coerce_description(description: Any) -> str:
	if description is None:
		return ""
	if isinstance(description, str):
		return description
	if isinstance(description, (dict, list, tuple)):
		try:
			return json.dumps(description, ensure_ascii=False, default=str)
		except Exception:
			return str(description)
	return str(description)


class FerumEmailAccount(EmailAccount):
	def _disable_broken_incoming_account(self, description):  # type: ignore[override]
		return super()._disable_broken_incoming_account(_coerce_description(description))
