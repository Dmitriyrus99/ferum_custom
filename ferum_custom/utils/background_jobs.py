from __future__ import annotations

import frappe


def ensure_job_context(method=None, kwargs=None, result=None):
	"""Guard against missing `frappe.local.job` in core background job cleanup.

	Observed in logs: `AttributeError: job` raised from `frappe.utils.background_jobs.execute_job`
	finally-block, which can hide the original exception. We recreate a minimal job context so
	core cleanup (`frappe.local.job.after_job.run()`) won't crash.
	"""

	if hasattr(frappe.local, "job"):
		return

	try:
		from frappe.utils.background_jobs import CallbackManager

		frappe.local.job = frappe._dict(
			site=getattr(frappe.local, "site", None),
			method=method,
			kwargs=kwargs,
			result=result,
			after_job=CallbackManager(),
		)
	except Exception:
		# Best-effort only; never fail the job because of this guard.
		pass
