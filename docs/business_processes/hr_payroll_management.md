# HR и зарплата (Payroll Entry Custom)

Дата: 2026‑02‑10  
Контур: ERPNext/Frappe v15 + `ferum_custom`.

Цель процесса: фиксировать начисления/выплаты по сотрудникам за период в простом контролируемом реестре.

## Объектная модель (AS‑IS)

- `Payroll Entry Custom` — документ “зарплатная ведомость” за период:
  - `period_start`, `period_end`
  - `employees` (таблица `Payroll Entry Item`)
  - `total_payroll_amount` пересчитывается на `validate`
  - `status`: Draft / Completed
- `Payroll Entry Item` — строка сотрудника:
  - `employee`, `base_salary`, `advance`, `net_salary`

Код: `ferum_custom/ferum_custom/doctype/payroll_entry_custom/payroll_entry_custom.py`.

## Роли и права

По текущим правам DocType:

- System Manager
- Chief Accountant

## Ограничения

- Это “операционный” контур без автоматической интеграции с банковской выпиской и без сложных расчётов (налоги/удержания).
- При необходимости расширения рекомендуется либо:
  - углубить интеграцию с ERPNext HR/Payroll, либо
  - вынести правила расчёта в отдельный сервис/модуль и оставить DocType как реестр результатов.
