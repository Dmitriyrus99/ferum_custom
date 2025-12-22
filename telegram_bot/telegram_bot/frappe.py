from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class FrappeAPIError(Exception):
	status_code: int
	message: str
	details: str | None = None

	def __str__(self) -> str:  # pragma: no cover
		if self.details:
			return f"{self.status_code}: {self.message} ({self.details})"
		return f"{self.status_code}: {self.message}"


def _extract_frappe_error_message(payload: Any) -> tuple[str, str | None]:
	if not isinstance(payload, dict):
		return "ERP API error", None

	# Typical frappe error payload includes `_server_messages` (JSON-encoded list of strings).
	server_messages = payload.get("_server_messages")
	if isinstance(server_messages, str) and server_messages:
		try:
			msgs = json.loads(server_messages)
			if isinstance(msgs, list) and msgs:
				# Each item can be a JSON-encoded dict/string; keep it simple.
				first = msgs[0]
				if isinstance(first, str) and first:
					return "ERP error", first
		except Exception:
			pass

	exception = payload.get("exception")
	exc_type = payload.get("exc_type")
	if exception and exc_type:
		return str(exc_type), str(exception)
	if exception:
		return "ERP error", str(exception)
	return "ERP API error", None


class FrappeAPI:
	def __init__(
		self,
		base_url: str,
		*,
		api_key: str | None,
		api_secret: str | None,
		client: httpx.AsyncClient,
	) -> None:
		self.base_url = base_url.rstrip("/")
		self.client = client
		self.headers: dict[str, str] = {"Accept": "application/json"}
		if api_key and api_secret:
			self.headers["Authorization"] = f"token {api_key}:{api_secret}"

	async def _request(
		self,
		method: str,
		path: str,
		*,
		params: dict[str, str] | None = None,
		json_body: dict | None = None,
	) -> Any:
		url = f"{self.base_url}{path}"
		resp = await self.client.request(
			method,
			url,
			params=params,
			json=json_body,
			headers=self.headers,
			timeout=20.0,
		)
		if resp.status_code >= 400:
			payload: Any
			try:
				payload = resp.json()
			except Exception:
				payload = resp.text
			msg, details = _extract_frappe_error_message(payload)
			raise FrappeAPIError(resp.status_code, msg, details or resp.text[:500])
		if resp.status_code == 204:
			return None
		return resp.json()

	async def get_list(
		self,
		doctype: str,
		*,
		fields: list[str] | None = None,
		filters: Any | None = None,
		order_by: str | None = None,
		limit_page_length: int | None = None,
	) -> list[dict]:
		params: dict[str, str] = {}
		if fields is not None:
			params["fields"] = json.dumps(fields, ensure_ascii=False)
		if filters is not None:
			params["filters"] = json.dumps(filters, ensure_ascii=False)
		if order_by:
			params["order_by"] = order_by
		if limit_page_length is not None:
			params["limit_page_length"] = str(limit_page_length)
		path = f"/api/resource/{quote(doctype, safe='')}"
		payload = await self._request("GET", path, params=params)
		return payload.get("data") or []

	async def get_doc(self, doctype: str, name: str) -> dict:
		path = f"/api/resource/{quote(doctype, safe='')}/{quote(name, safe='')}"
		payload = await self._request("GET", path)
		return payload.get("data") or {}

	async def insert(self, doctype: str, data: dict) -> dict:
		path = f"/api/resource/{quote(doctype, safe='')}"
		payload = await self._request("POST", path, json_body={"data": data})
		return payload.get("data") or {}

	async def update(self, doctype: str, name: str, data: dict) -> dict:
		path = f"/api/resource/{quote(doctype, safe='')}/{quote(name, safe='')}"
		payload = await self._request("PUT", path, json_body={"data": data})
		return payload.get("data") or {}

	async def call(self, method: str, params: dict | None = None) -> dict:
		path = f"/api/method/{method}"
		payload = await self._request("GET", path, params={k: str(v) for k, v in (params or {}).items()})
		return payload

