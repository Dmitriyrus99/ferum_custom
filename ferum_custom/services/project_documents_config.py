from __future__ import annotations

ATTACHED_TO_FIELD = "ferum_project_documents"

DOC_TYPES: tuple[str, ...] = (
	"Договоры с заказчиком",
	"Договоры с подрядчиками/исполнителями",
	"Удостоверения и разрешительные документы исполнителей",
	"Закрывающие документы с подписью заказчика",
	"Входящие письма от заказчика",
	"Исходящие письма в адрес заказчика",
	"Служебные / внутренние документы проекта",
)

CLIENT_ALLOWED_TYPES: set[str] = {
	"Договоры с заказчиком",
	"Закрывающие документы с подписью заказчика",
	"Входящие письма от заказчика",
	"Исходящие письма в адрес заказчика",
}

UPLOAD_ROLES: set[str] = {
	"System Manager",
	"Project Manager",
	"Projects Manager",
	"Office Manager",
	"Ferum Office Manager",
}
