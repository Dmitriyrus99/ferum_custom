from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _upsert_client_script(*, name: str, dt: str, script: str) -> None:
	if not frappe.db.exists("DocType", "Client Script"):
		return

	existing = frappe.db.get_value("Client Script", {"name": name}, "name")
	if existing:
		doc = frappe.get_doc("Client Script", name)
	else:
		doc = frappe.new_doc("Client Script")
		doc.dt = dt
		doc.script_type = "Client"
		doc.enabled = 1
		doc.name = name
		doc.__newname = name

	doc.script = script.strip()
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)


def execute() -> None:
	if not frappe.db.exists("DocType", "Project"):
		return

	project_meta = frappe.get_meta("Project")
	project_insert_after = "welcome_email_sent_date" if project_meta.has_field("welcome_email_sent_date") else None

	create_custom_fields(
		{
			"Project": [
				{
					"fieldname": "ferum_docs_section",
					"label": "Документы",
					"fieldtype": "Section Break",
					"insert_after": project_insert_after,
					"collapsible": 1,
					"collapsed": 0,
				},
				{
					"fieldname": "ferum_docs_html",
					"label": "Документы",
					"fieldtype": "HTML",
					"insert_after": "ferum_docs_section",
				},
			],
		},
		ignore_validate=True,
	)

	if frappe.db.exists("DocType", "Contract"):
		contract_meta = frappe.get_meta("Contract")
		contract_insert_after = "amended_from" if contract_meta.has_field("amended_from") else None
		create_custom_fields(
			{
				"Contract": [
					{
						"fieldname": "ferum_docs_section",
						"label": "Документы",
						"fieldtype": "Section Break",
						"insert_after": contract_insert_after,
						"collapsible": 1,
						"collapsed": 0,
					},
					{
						"fieldname": "ferum_docs_html",
						"label": "Документы",
						"fieldtype": "HTML",
						"insert_after": "ferum_docs_section",
					},
				],
			},
			ignore_validate=True,
		)

	project_script = """
function ferum_can_upload_project_docs() {
  const roles = frappe.user_roles || [];
  if (roles.includes('System Manager')) return true;
  if (roles.includes('Project Manager') || roles.includes('Projects Manager')) return true;
  if (roles.includes('Office Manager') || roles.includes('Ferum Office Manager')) return true;
  return false;
}

function ferum_project_docs_options() {
  return [
    'Договоры с заказчиком',
    'Договоры с подрядчиками/исполнителями',
    'Удостоверения и разрешительные документы исполнителей',
    'Закрывающие документы с подписью заказчика',
    'Входящие письма от заказчика',
    'Исходящие письма в адрес заказчика'
  ];
}

function ferum_render_project_documents(frm) {
  if (!frm.doc || !frm.doc.name) return;
  if (!frm.fields_dict.ferum_docs_html) return;

  const wrapper = frm.fields_dict.ferum_docs_html.$wrapper;
  if (!wrapper) return;
  wrapper.empty();

  const container = $('<div class="ferum-project-docs"></div>').appendTo(wrapper);
  const toolbar = $('<div class="flex" style="gap:8px; align-items:center; flex-wrap:wrap;"></div>').appendTo(container);

  const typeSelect = $('<select class="form-control" style="max-width:420px;"></select>').appendTo(toolbar);
  typeSelect.append('<option value="">Все типы</option>');
  for (const t of ferum_project_docs_options()) {
    typeSelect.append(`<option value="${frappe.utils.escape_html(t)}">${frappe.utils.escape_html(t)}</option>`);
  }

  const dateFrom = $('<input type="date" class="form-control" style="max-width:170px;" />').appendTo(toolbar);
  const dateTo = $('<input type="date" class="form-control" style="max-width:170px;" />').appendTo(toolbar);

  const refreshBtn = $('<button class="btn btn-sm btn-default">Обновить</button>').appendTo(toolbar);
  const uploadBtn = ferum_can_upload_project_docs()
    ? $('<button class="btn btn-sm btn-primary">Загрузить документ</button>').appendTo(toolbar)
    : null;

  const listArea = $('<div style="margin-top:10px;"></div>').appendTo(container);

  function renderList(rows) {
    const safe = frappe.utils.escape_html;
    if (!rows || !rows.length) {
      listArea.html('<div class="text-muted">Документов нет.</div>');
      return;
    }

    const table = $(`
      <div class="table-responsive">
        <table class="table table-bordered table-hover">
          <thead>
            <tr>
              <th style="width:140px;">Дата</th>
              <th style="width:260px;">Тип</th>
              <th>Наименование</th>
              <th style="width:120px;">Файл</th>
              <th style="width:160px;">Загрузил</th>
              <th style="width:160px;">Контракт</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    `);

    const tbody = table.find('tbody');
    for (const r of rows) {
      const created = r.creation ? safe(frappe.datetime.str_to_user(r.creation)) : '';
      const docType = safe(r.ferum_doc_type || '');
      const title = safe(r.ferum_doc_title || r.file_name || '');
      const owner = safe(r.owner || '');
      const contract = safe(r.ferum_contract || '');
      const url = r.file_url || '';
      const link = url ? `<a href="${safe(url)}" target="_blank" rel="noopener">Открыть</a>` : '';
      tbody.append(`
        <tr>
          <td>${created}</td>
          <td>${docType}</td>
          <td>${title}</td>
          <td>${link}</td>
          <td>${owner}</td>
          <td>${contract}</td>
        </tr>
      `);
    }

    listArea.empty().append(table);
  }

  function load() {
    listArea.html('<div class="text-muted">Загрузка...</div>');
    frappe.call({
      method: 'ferum_custom.api.project_documents.list_project_documents',
      args: {
        project: frm.doc.name,
        doc_type: typeSelect.val() || null,
        date_from: dateFrom.val() || null,
        date_to: dateTo.val() || null
      },
      callback(r) {
        renderList((r && r.message) || []);
      }
    });
  }

  refreshBtn.on('click', () => load());
  typeSelect.on('change', () => load());

  if (uploadBtn) {
    uploadBtn.on('click', () => {
      const d = new frappe.ui.Dialog({
        title: 'Загрузить документ',
        fields: [
          {fieldname: 'doc_title', label: 'Наименование документа', fieldtype: 'Data', reqd: 1},
          {fieldname: 'doc_type', label: 'Тип документа', fieldtype: 'Select', options: ferum_project_docs_options().join('\\n'), reqd: 1},
          {fieldname: 'contract', label: 'Контракт', fieldtype: 'Link', options: 'Contract'},
          {fieldname: 'file_picker', label: 'Файл', fieldtype: 'HTML'}
        ],
        primary_action_label: 'Загрузить',
        primary_action(values) {
          const file = fileInput && fileInput[0] && fileInput[0].files ? fileInput[0].files[0] : null;
          if (!file) {
            frappe.msgprint('Выберите файл.');
            return;
          }
          if (!values || !values.doc_title || !values.doc_type) {
            frappe.msgprint('Заполните обязательные поля.');
            return;
          }

          const primaryBtn = d.get_primary_btn();
          primaryBtn.prop('disabled', true);
          primaryBtn.text('Загрузка...');

          const fd = new FormData();
          fd.append('file', file, file.name);
          fd.append('method', 'ferum_custom.api.project_documents.upload_project_document');
          fd.append('project', frm.doc.name);
          fd.append('ferum_doc_title', values.doc_title);
          fd.append('ferum_doc_type', values.doc_type);
          if (values.contract) fd.append('ferum_contract', values.contract);

          $.ajax({
            url: '/api/method/upload_file',
            type: 'POST',
            data: fd,
            processData: false,
            contentType: false,
            headers: {'X-Frappe-CSRF-Token': frappe.csrf_token},
            success() {
              d.hide();
              frappe.show_alert({message: 'Документ загружен', indicator: 'green'});
              load();
            },
            error(xhr) {
              primaryBtn.prop('disabled', false);
              primaryBtn.text('Загрузить');
              const msg = (xhr && xhr.responseJSON && xhr.responseJSON.exception) ? xhr.responseJSON.exception : 'Ошибка загрузки.';
              frappe.msgprint(msg);
            }
          });
        }
      });

      const fileWrapper = d.fields_dict.file_picker.$wrapper;
      const fileInput = $('<input type="file" class="form-control" />').appendTo(fileWrapper);
      d.show();
    });
  }

  load();
}

frappe.ui.form.on('Project', {
  refresh(frm) {
    ferum_render_project_documents(frm);
  }
});
""".strip()

	contract_script = """
function ferum_render_contract_documents(frm) {
  if (!frm.doc || !frm.doc.name) return;
  if (!frm.fields_dict.ferum_docs_html) return;

  const wrapper = frm.fields_dict.ferum_docs_html.$wrapper;
  if (!wrapper) return;
  wrapper.empty();

  const container = $('<div class="ferum-contract-docs"></div>').appendTo(wrapper);
  const toolbar = $('<div class="flex" style="gap:8px; align-items:center; flex-wrap:wrap;"></div>').appendTo(container);
  const refreshBtn = $('<button class="btn btn-sm btn-default">Обновить</button>').appendTo(toolbar);
  const listArea = $('<div style="margin-top:10px;"></div>').appendTo(container);

  function renderList(rows) {
    const safe = frappe.utils.escape_html;
    if (!rows || !rows.length) {
      listArea.html('<div class="text-muted">Документов нет.</div>');
      return;
    }

    const table = $(`
      <div class="table-responsive">
        <table class="table table-bordered table-hover">
          <thead>
            <tr>
              <th style="width:140px;">Дата</th>
              <th style="width:260px;">Тип</th>
              <th>Наименование</th>
              <th style="width:120px;">Файл</th>
              <th style="width:160px;">Загрузил</th>
              <th style="width:160px;">Проект</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    `);

    const tbody = table.find('tbody');
    for (const r of rows) {
      const created = r.creation ? safe(frappe.datetime.str_to_user(r.creation)) : '';
      const docType = safe(r.ferum_doc_type || '');
      const title = safe(r.ferum_doc_title || r.file_name || '');
      const owner = safe(r.owner || '');
      const project = safe(r.project || '');
      const url = r.file_url || '';
      const link = url ? `<a href="${safe(url)}" target="_blank" rel="noopener">Открыть</a>` : '';
      tbody.append(`
        <tr>
          <td>${created}</td>
          <td>${docType}</td>
          <td>${title}</td>
          <td>${link}</td>
          <td>${owner}</td>
          <td>${project}</td>
        </tr>
      `);
    }

    listArea.empty().append(table);
  }

  function load() {
    listArea.html('<div class="text-muted">Загрузка...</div>');
    frappe.call({
      method: 'ferum_custom.api.project_documents.list_contract_documents',
      args: { contract: frm.doc.name },
      callback(r) {
        renderList((r && r.message) || []);
      }
    });
  }

  refreshBtn.on('click', () => load());
  load();
}

frappe.ui.form.on('Contract', {
  refresh(frm) {
    ferum_render_contract_documents(frm);
  }
});
""".strip()

	_upsert_client_script(name="Ferum Project Documents", dt="Project", script=project_script)
	_upsert_client_script(name="Ferum Contract Documents", dt="Contract", script=contract_script)

	frappe.clear_cache()
