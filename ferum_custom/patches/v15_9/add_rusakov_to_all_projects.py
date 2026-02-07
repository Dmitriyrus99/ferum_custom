from __future__ import annotations

from ferum_custom.services.project_users import add_user_to_all_projects


def execute() -> None:
	# Needed for Telegram bot access via standard Project.users.
	add_user_to_all_projects("rusakov@ferumrus.ru")
