from __future__ import annotations


def clean_str(raw: object | None) -> str | None:
	if raw is None:
		return None
	value = str(raw).strip()
	return value or None


def is_truthy(raw: object | None) -> bool:
	value = (str(raw or "")).strip().lower()
	return value in {"1", "true", "yes", "on", "y", "t"}


def parse_int(raw: object | None) -> int | None:
	value = clean_str(raw)
	if value is None:
		return None
	try:
		return int(value)
	except Exception:
		return None


def parse_float(raw: object | None) -> float | None:
	value = clean_str(raw)
	if value is None:
		return None
	try:
		return float(value)
	except Exception:
		return None


def parse_int_set(raw: object | None) -> set[int] | None:
	value = clean_str(raw)
	if value is None:
		return None

	out: set[int] = set()
	for part in value.replace("\n", ",").split(","):
		part = part.strip()
		if not part:
			continue
		try:
			out.add(int(part))
		except Exception:
			continue

	return out or None
