# Счета, актирование и оплаты (Invoice / ServiceAct / Sales Invoice)

Дата: 2026‑02‑10  
Контур: ERPNext/Frappe v15 + `ferum_custom`.

Цель: вести реестр финансовых документов по договору/проекту и обеспечить связность “акт → счет → оплата”.

## 1) Реестр счетов (Invoice — кастомный DocType)

DocType: `Invoice` (`ferum_custom/ferum_custom/doctype/invoice/*`)

Назначение:

- внутренний реестр выставленных/полученных счетов
- связь с `Contract`, опционально с `Project` (через `erpnext_project`) и `Sales Invoice`

Ключевые правила (сервер):

- при переводе в `Sent` требуется `due_date`
- при переводе в `Paid` сумма должна быть > 0
- допустимые переходы статусов ограничены (`validate_status_transitions`)

Опциональная интеграция:

- при submit — синхронизация строки в Google Sheets (если установлен `gspread` и настроена учётка)

Код: `ferum_custom/ferum_custom/doctype/invoice/invoice.py`.

## 2) Актирование по периодам (ActSchedule / ServiceAct)

DocType’ы:

- `ActSchedule` — план периодов/сумм по договору (расчёт плановой даты сдачи по дедлайн‑дню из Contract)
- `ServiceAct` — акт по периоду; при подписании меняет статусы расписания и может создавать `Sales Invoice`

Ключевая логика:

- при `ServiceAct.status → Signed` вызывается `on_service_act_signed`
- создание `Sales Invoice` реализовано как “черновик по умолчанию”, чтобы не упираться в бухгалтерские настройки

Код: `ferum_custom/services/acts.py`, контроллеры:
`ferum_custom/ferum_custom/doctype/actschedule/actschedule.py`,
`ferum_custom/ferum_custom/doctype/serviceact/serviceact.py`.

## 3) Оплаты (AS‑IS)

В текущем контуре факт оплаты фиксируется:

- либо в `Invoice.status = Paid`
- либо в учётном документе `Sales Invoice` (ERPNext), если используется полная бухгалтерия

Единая “сверка оплат” и автоматическое банковское сопоставление — отдельная задача следующей фазы.
