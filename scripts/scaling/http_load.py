#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from dataclasses import dataclass
from statistics import quantiles
from typing import Any

import httpx


@dataclass(frozen=True)
class Result:
	ok: bool
	status_code: int | None
	latency_ms: float


def _percentile(values: list[float], p: float) -> float | None:
	if not values:
		return None
	if len(values) == 1:
		return float(values[0])
	q = quantiles(values, n=100, method="inclusive")
	idx = int(max(0, min(99, round(p))))
	return float(q[idx - 1]) if idx > 0 else float(min(values))


def _auth_headers(args: argparse.Namespace) -> dict[str, str]:
	if args.api_key and args.api_secret:
		return {"Authorization": f"token {args.api_key}:{args.api_secret}"}
	if args.bearer:
		return {"Authorization": f"Bearer {args.bearer}"}
	return {}


async def _worker(
	*,
	client: httpx.AsyncClient,
	endpoints: list[str],
	headers: dict[str, str],
	stop_at: float,
	timeout_seconds: float,
) -> list[Result]:
	out: list[Result] = []
	i = 0
	while time.monotonic() < stop_at:
		path = endpoints[i % len(endpoints)]
		i += 1
		start = time.perf_counter()
		try:
			resp = await client.get(path, headers=headers, timeout=timeout_seconds)
			lat = (time.perf_counter() - start) * 1000.0
			ok = 200 <= resp.status_code < 400
			out.append(Result(ok=ok, status_code=int(resp.status_code), latency_ms=lat))
		except Exception:
			lat = (time.perf_counter() - start) * 1000.0
			out.append(Result(ok=False, status_code=None, latency_ms=lat))
	return out


async def _run(args: argparse.Namespace) -> dict[str, Any]:
	headers = {"Accept": "application/json", **_auth_headers(args)}
	if args.host_header:
		headers["Host"] = str(args.host_header).strip()
	endpoints = [e.strip() for e in (args.endpoint or []) if str(e).strip()]
	if not endpoints:
		endpoints = ["/api/method/frappe.ping"]

	stop_at = time.monotonic() + float(args.duration_seconds)

	limits = httpx.Limits(max_connections=args.concurrency * 2, max_keepalive_connections=args.concurrency)
	async with httpx.AsyncClient(
		base_url=args.base_url.rstrip("/"),
		limits=limits,
		verify=not bool(args.insecure),
	) as client:
		tasks = [
			_worker(
				client=client,
				endpoints=endpoints,
				headers=headers,
				stop_at=stop_at,
				timeout_seconds=float(args.timeout_seconds),
			)
			for _ in range(int(args.concurrency))
		]
		results_nested = await asyncio.gather(*tasks)

	results: list[Result] = [r for sub in results_nested for r in sub]
	latencies = sorted([r.latency_ms for r in results])
	status_counts = Counter([r.status_code for r in results if r.status_code is not None])

	ok_count = sum(1 for r in results if r.ok)
	err_count = len(results) - ok_count

	return {
		"base_url": args.base_url,
		"host_header": args.host_header,
		"endpoints": endpoints,
		"duration_seconds": float(args.duration_seconds),
		"concurrency": int(args.concurrency),
		"timeout_seconds": float(args.timeout_seconds),
		"total_requests": len(results),
		"ok_requests": ok_count,
		"error_requests": err_count,
		"status_codes": {str(k): int(v) for k, v in status_counts.items()},
		"latency_ms": {
			"min": float(min(latencies)) if latencies else None,
			"p50": _percentile(latencies, 50),
			"p95": _percentile(latencies, 95),
			"p99": _percentile(latencies, 99),
			"max": float(max(latencies)) if latencies else None,
		},
	}


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Lightweight HTTP load scenario runner (no secrets printed)."
	)
	parser.add_argument("--base-url", required=True, help="Base URL, e.g. http://127.0.0.1:8000")
	parser.add_argument(
		"--endpoint",
		action="append",
		default=[],
		help="Path to GET (repeatable), e.g. /api/method/frappe.ping",
	)
	parser.add_argument("--duration-seconds", type=float, default=10.0)
	parser.add_argument("--concurrency", type=int, default=10)
	parser.add_argument("--timeout-seconds", type=float, default=10.0)
	parser.add_argument("--insecure", action="store_true", help="Disable TLS verification (not recommended).")
	parser.add_argument(
		"--host-header",
		default=None,
		help="Explicit Host header for multi-tenant Frappe sites (e.g. test_site or erpclone.ferumrus.ru).",
	)

	parser.add_argument("--api-key", default=None, help="Frappe API key (optional).")
	parser.add_argument("--api-secret", default=None, help="Frappe API secret (optional).")
	parser.add_argument("--bearer", default=None, help="Bearer token (optional).")

	args = parser.parse_args()

	payload = asyncio.run(_run(args))
	print(json.dumps(payload, ensure_ascii=False, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
