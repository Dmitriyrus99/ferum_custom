from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from ferum_custom.integrations.telegram_bot.frappe import (
	FrappeAPI,
	FrappeAPIError,
	_extract_frappe_error_message,
)


def test_backward_compat_import_path() -> None:
	# Historical path kept for external tools / older run commands.
	from telegram_bot.telegram_bot.frappe import FrappeAPI as OldFrappeAPI

	assert OldFrappeAPI is FrappeAPI


def test_extract_frappe_error_message_server_messages() -> None:
	payload = {
		"_server_messages": json.dumps(
			[
				json.dumps({"message": "first message"}),
			]
		)
	}
	msg, details = _extract_frappe_error_message(payload)
	assert msg == "ERP error"
	assert details


def test_extract_frappe_error_message_exc_fields() -> None:
	payload = {"exc_type": "ValidationError", "exception": "Boom"}
	msg, details = _extract_frappe_error_message(payload)
	assert msg == "ValidationError"
	assert details == "Boom"


def test_frappe_api_get_list_builds_request() -> None:
	requests: list[httpx.Request] = []

	def handler(request: httpx.Request) -> httpx.Response:
		requests.append(request)
		return httpx.Response(200, json={"data": []})

	async def run() -> None:
		transport = httpx.MockTransport(handler)
		async with httpx.AsyncClient(transport=transport) as client:
			api = FrappeAPI(
				"http://example.local",
				api_key="k",
				api_secret="s",
				client=client,
			)
			await api.get_list(
				"Project Site",
				fields=["name"],
				filters=[["Project Site", "parent", "=", "PROJ-0001"]],
				order_by="modified desc",
				limit_page_length=10,
			)

	asyncio.run(run())

	assert requests, "no requests captured"
	req = requests[0]
	assert req.method == "GET"
	assert str(req.url).startswith("http://example.local/api/resource/Project%20Site?")
	assert req.headers.get("Authorization") == "token k:s"
	assert req.headers.get("Accept") == "application/json"
	assert "fields=" in str(req.url)
	assert "filters=" in str(req.url)


def test_frappe_api_raises_on_http_error() -> None:
	def handler(request: httpx.Request) -> httpx.Response:
		_ = request
		return httpx.Response(500, json={"exc_type": "Error", "exception": "Nope"})

	async def run() -> Any:
		transport = httpx.MockTransport(handler)
		async with httpx.AsyncClient(transport=transport) as client:
			api = FrappeAPI(
				"http://example.local",
				api_key=None,
				api_secret=None,
				client=client,
			)
			await api.get_doc("Project", "PROJ-0001")

	with pytest.raises(FrappeAPIError) as excinfo:
		asyncio.run(run())
	assert excinfo.value.status_code == 500
