# Отчётность по работам (Service Report)

Дата: 2026‑02‑10  
Контур: ERPNext/Frappe v15 + `ferum_custom`.

Цель процесса: фиксировать выполненные работы по заявке, прикладывать документы/сканы и переводить заявку в состояние `Completed` только после формализации отчёта.

## Участники

- **Engineer** — заполняет выполненные работы и прикладывает документы.
- **Project Manager / Office Manager** — проверяет полноту и корректность, обеспечивает подписанные/скан‑версии.
- **Client** — получает результат (в рамках доступов; отдельные типы документов могут быть ограничены политикой).

## AS‑IS: структура Service Report

DocType: `Service Report` (`ferum_custom/ferum_custom/doctype/service_report/*`)

- `work_items` (child table `Service Report Work Item`)
  - часы/ставка/итоговая сумма по строке
  - итоговые поля `total_amount/total_payable` пересчитываются в `validate`
- `documents` (child table `Service Report Document Item`)
  - обязательная ссылка на `Custom Attachment` (проверяется в `validate`)

Код: `ferum_custom/ferum_custom/doctype/service_report/service_report.py`.

## Закрытие заявки

При `Service Report.on_submit`:

- в связанной заявке (`Service Request`) выставляется:
  - `linked_report = <report>`
  - `status = "Completed"`

Это обеспечивает “контрольный замок”: без отчёта заявку нельзя корректно закрыть.

## Workflow/статусы отчёта

AS‑IS присутствуют серверные проверки переходов `status` (Draft/Submitted/Approved/Archived/Cancelled),
чтобы исключить некорректные переходы.

## Уведомления

События:

- `Service Report.after_insert` — уведомление о создании
- `Service Report.on_submit` — уведомление о смене статуса/результате

Реализация: `ferum_custom/notifications.py`.

## Примечание (журнал эксплуатации)

В модели данных уже присутствуют `Service Logbook` и `Service Log Entry` (для электронного/бумажного журнала),
но автоматическая связка “закрытие заявки/отчёта → запись в журнал” выделена в отдельную фазу внедрения.
