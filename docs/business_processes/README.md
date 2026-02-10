# Бизнес‑процессы (документы)

Каталог содержит описания ключевых процессов Ferum ERP (ERPNext/Frappe + `ferum_custom`).

```mermaid
flowchart LR
    A[Contract/Project (контейнер)] --> B[Project Site (объекты)]
    B --> C[Service Request] --> D[Service Report] --> E[Acts/Invoices]
    E --> F[Payments/Closing]
```

Документы по вложениям/Drive и по мониторингу/безопасности поддерживают все стадии цепочки.

## Гайды

- [Описание бизнес‑процессов (AS‑IS, актуально по коду)](business_processes_ru.md)
- [Описание бизнес‑процессов (AS‑IS, legacy версия)](business_processes_ru_legacy.md)
- [Контракт/проект: полный цикл (Project контейнер, Site истина)](erpnext_project_full_cycle.md)
- [Договоры и проекты](project_contract_management.md)
- [Заявки (Service Request)](service_request_management.md)
- [Отчётность по работам (Service Report)](work_reporting.md)
- [Акты/счета/оплата](invoicing_payments.md)
- [HR/зарплата](hr_payroll_management.md)
- [Документы и вложения (File + Google Drive)](document_attachment_management.md)
- [Мониторинг/аналитика/безопасность](monitoring_analytics_security_bp.md)
