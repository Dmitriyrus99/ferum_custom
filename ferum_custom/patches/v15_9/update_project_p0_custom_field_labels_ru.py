from __future__ import annotations

import frappe


def _update_custom_field_label(dt: str, fieldname: str, label: str) -> None:
	name = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname}, "name")
	if not name:
		return
	frappe.db.set_value("Custom Field", name, "label", label, update_modified=False)


def execute() -> None:
	if not frappe.db.exists("DocType", "Project") or not frappe.db.exists("DocType", "Custom Field"):
		return

	labels: dict[str, str] = {
		"ferum_stage": "Этап (Ferum)",
		"ferum_p0_tab": "Процесс Ferum (P0)",
		"tender_section": "Тендер",
		"tender_source": "Источник победы / тендер",
		"eis_etp_url": "Ссылка ЕИС/ЭТП",
		"tender_customer_name": "Заказчик (тендер)",
		"tender_price": "Цена тендера",
		"tender_term_start": "Срок (начало)",
		"tender_term_end": "Срок (конец)",
		"tender_protocol_date": "Дата итогового протокола",
		"contacts_section": "Контакты заказчика",
		"customer_contacts": "Контакты заказчика",
		"project_sites_section": "Объекты",
		"project_sites": "Объекты",
		"contract_review_section": "Контракт / проверка (до подписания)",
		"contract_draft_reviewed": "PM ознакомился с проектом договора/ТЗ",
		"subcontracting_allowed": "Подряд разрешён",
		"legal_review_required": "Требуется проверка юриста",
		"legal_review_status": "Статус проверки юриста",
		"legal_review_director_override": "Исключение директора (юрист не обязателен)",
		"contract_signed_date": "Дата подписания контракта",
		"contractor_section": "Подрядчик и форма отношений",
		"execution_mode": "Форма исполнения",
		"director_approved_execution_mode": "Директор подтвердил сценарий исполнения",
		"subcontractor_selected": "Подрядчик выбран",
		"subcontractor_party": "Подрядчик (контрагент)",
		"subcontractor_contact_phone": "Телефон подрядчика",
		"subcontractor_contract_signed": "Договор с подрядчиком подписан",
		"subcontractor_contract_file": "Файл договора подрядчика",
		"director_approved_subcontractor": "Директор утвердил подрядчика",
		"mail_section": "Почта России (исходящие)",
		"outbound_mail_items": "Отправления",
		"welcome_email_sent_date": "Дата приветственного письма",
		"survey_section": "Первичка / фото",
		"start_work_date": "Дата старта работ",
		"photo_survey_deadline": "Дедлайн фото/обследования",
		"photo_survey_format": "Формат обследования",
		"photo_only_confirmed": "Фото-only подтверждено (PM)",
		"drive_folder_url": "Папка Google Drive",
		"survey_checklist": "Чек-лист обследования",
		"survey_docs_section": "Акт обследования / ведомость",
		"initial_survey_act_due": "Срок акта обследования",
		"initial_survey_act_file": "Файл акта обследования",
		"defects_list_file": "Файл ведомости",
		"director_approval_required": "Требуется утверждение директора",
		"director_approved": "Утверждено директором",
		"sent_to_customer_date": "Дата отправки заказчику",
		"if_customer_ignored_trigger_mail_task": "Заказчик игнорирует → задача на заказное письмо",
		"billing_section": "Биллинг-периоды",
		"billing_periods": "Периоды",
		"customer_received_docs_confirmed": "Получение документов заказчиком подтверждено",
		"payment_received_date": "Дата оплаты",
		"payment_status": "Статус оплаты",
		"payment_control_notes": "Примечания по оплате",
		"contractor_payments_section": "Подрядчики (минимально)",
		"contractor_payment_due_rule": "Правило оплаты подрядчика",
		"contractor_docs_received": "Документы подрядчика получены",
		"contractor_originals_received": "Оригиналы подрядчика получены",
		"contractor_payment_request_link": "Ссылка на заявку оплаты подрядчика",
		"deadlines_section": "Дедлайны",
		"contractor_selected_deadline": "Дедлайн выбора подрядчика",
		"telegram_section": "Telegram",
		"telegram_users": "Подписчики Telegram",
	}

	for fieldname, label in labels.items():
		_update_custom_field_label("Project", fieldname, label)

	frappe.clear_cache()
