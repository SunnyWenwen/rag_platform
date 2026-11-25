"use strict";

const operations = { init: "Init", ingestion: "Ingestion", inference: "Inference" };
const $ = (id) => document.getElementById(id);
const jsonText = (value) => JSON.stringify(value, null, 2);
const has = (object, key) => Object.hasOwn(object, key);
const state = {
  page: "user", workspaces: [], workspaceId: null, providers: [], systems: [], demoTemplate: null,
  systemId: null, operation: "ingestion", drafts: new Map(),
};
const providerFields = new Map();
let editingProvider = null;
let editingSystem = null;
let validateTimer;
let previewRevision = 0;
let readConfig = () => ({});

function node(tag, className = "", text = "") {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

function button(text, className) {
  const value = node("button", className, text);
  value.type = "button";
  return value;
}

function option(value, label) {
  const item = node("option", "", label);
  item.value = value;
  return item;
}

function field(label, input, { required = false, hint = "" } = {}) {
  const wrapper = node("label", "field");
  const title = node("span", "", label);
  if (required) title.append(node("span", "required-mark", " *"));
  wrapper.append(title, input);
  if (hint) wrapper.append(node("small", "", hint));
  return wrapper;
}

function input(type = "text", placeholder = "") {
  const element = node("input");
  element.type = type;
  element.placeholder = placeholder;
  return element;
}

function authField(header, control) {
  const wrapper = node("div", "field auth-field");
  const label = node("label", "", header);
  control.id = "request-auth";
  control.autocomplete = "off";
  label.htmlFor = control.id;

  const row = node("div", "password-control");
  const toggle = button("", "password-toggle");
  const icon = node("span", "eye-icon");
  icon.setAttribute("aria-hidden", "true");
  toggle.append(icon);
  toggle.setAttribute("aria-controls", control.id);
  const setVisibility = (visible) => {
    control.type = visible ? "text" : "password";
    const action = visible ? "隱藏憑證" : "顯示憑證";
    toggle.setAttribute("aria-label", action);
    toggle.title = action;
  };
  setVisibility(false);
  toggle.addEventListener("click", () => setVisibility(control.type === "password"));
  row.append(control, toggle);
  wrapper.append(label, row);
  return wrapper;
}

function textarea(rows) {
  const element = node("textarea", "code-input");
  element.rows = rows;
  element.spellcheck = false;
  return element;
}

function parseJSON(value, label) {
  try {
    return JSON.parse(value);
  } catch {
    throw new Error(label + " 必須是有效的 JSON。");
  }
}

function notice(element, message, failed = false) {
  element.textContent = message;
  element.classList.toggle("error", failed);
  element.hidden = !message;
}

async function api(path, body, method = "POST") {
  const response = await fetch(path, body === undefined ? undefined : {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "HTTP " + response.status);
  return result;
}

function providerById(id) {
  return state.providers.find((provider) => provider.id === id);
}

function selectPage(page) {
  state.page = page;
  $("user-page").hidden = page !== "user";
  $("provider-page").hidden = page !== "provider";
  $("create-system").hidden = page !== "user";
  $("create-provider").hidden = page !== "provider";
  for (const pill of document.querySelectorAll("[data-page]")) {
    if (pill.dataset.page === page) pill.setAttribute("aria-current", "page");
    else pill.removeAttribute("aria-current");
  }
  notice($("workspace-message"), "");
  renderWorkspace();
}

function schemaForm(container, schema, parameters) {
  container.replaceChildren();
  if (schema.title) container.append(node("h3", "schema-title", schema.title));
  if (schema.description) container.append(node("p", "schema-description", schema.description));
  const group = node("div", "parameter-list");
  const required = new Set(schema.required || []);
  const controls = new Map();
  for (const [name, spec] of Object.entries(schema.properties)) {
    const values = spec.enum || (spec.type === "boolean" ? [true, false] : null);
    const initial = parameters ? (has(parameters, name) ? parameters[name] : undefined) : spec.default;
    let control;
    if (values) {
      control = node("select");
      control.append(option("", "請選擇"));
      values.forEach((value, index) => {
        const label = typeof value === "boolean" ? (value ? "是" : "否") : String(value);
        control.append(option(String(index), label));
      });
      if (initial !== undefined) control.value = String(values.indexOf(initial));
    } else {
      const numeric = spec.type === "integer" || spec.type === "number";
      control = input(numeric ? "number" : "text");
      if (numeric) control.step = spec.type === "integer" ? "1" : "any";
      if (initial !== undefined) control.value = initial;
    }
    control.name = name;
    if (required.has(name)) control.setAttribute("aria-required", "true");
    group.append(field(spec.title || name, control, { required: required.has(name), hint: spec.description }));
    controls.set(name, { control, spec, values, initial });
  }
  if (controls.size) container.append(group);
  else container.append(node("p", "muted", "此 Provider 沒有額外設定。"));

  return () => {
    const pairs = [];
    for (const [name, { control, spec, values, initial }] of controls) {
      if (control.validity.badInput || control.validity.stepMismatch) {
        control.focus();
        throw new Error("請輸入有效的" + (spec.type === "integer" ? "整數" : "數字") + "：" + name);
      }
      const value = control.value;
      if (value === "" && (values || initial !== "")) {
        if (required.has(name)) {
          control.focus();
          throw new Error("請填寫必填欄位：" + name);
        }
        continue;
      }
      const parsed = values ? values[Number(value)] : spec.type === "string" ? value : control.valueAsNumber;
      pairs.push([name, parsed]);
    }
    return Object.fromEntries(pairs);
  };
}

async function renderPreview(revision) {
  const preview = $("schema-preview");
  try {
    const schema = parseJSON($("config-schema").value, "Config Schema");
    await api("/api/schema/validate", schema);
    if (revision === previewRevision) schemaForm(preview, schema);
  } catch (error) {
    if (revision === previewRevision) preview.replaceChildren(node("p", "notice error", error.message));
  }
}

function refreshPreview(delay = 200) {
  clearTimeout(validateTimer);
  const revision = ++previewRevision;
  validateTimer = setTimeout(() => renderPreview(revision), delay);
}

function setupProvider() {
  $("provider-form").noValidate = true;
  $("config-schema").value = jsonText({ type: "object", properties: {} });
  for (const [key, label] of Object.entries(operations)) {
    const details = node("details");
    details.open = key === "init";
    const name = node("summary", "", label);
    const section = node("div", "api-fields");
    const url = input("url", "https://provider.example.com/" + key);
    const header = input("text", "Authorization");
    const authValue = input("text", key === "init" ? "PROVIDER_INIT_AUTH" : "Bearer");
    url.id = key + "-url";
    header.id = key + "-auth-header";
    authValue.id = key + "-auth-value";
    const auth = node("div", "auth-fields");
    auth.append(
      field("Auth Header", header, { hint: "留空表示無需 Auth。" }),
      field(key === "init" ? "Secret 環境變數" : "Auth 格式提示", authValue),
    );
    section.append(field(label + " URL", url, { required: true }), auth);
    const entry = { details, url, header, authValue };
    if (key !== "init") {
      entry.description = textarea(2);
      entry.description.classList.remove("code-input");
      entry.description.id = key + "-description";
      entry.sample = textarea(5);
      entry.sample.id = key + "-sample";
      section.append(
        field(label + " 使用說明", entry.description, { required: true }),
        field(label + " JSON Sample", entry.sample, { required: true }),
      );
    }
    details.append(name, section);
    $("provider-apis").append(details);
    providerFields.set(key, entry);
  }
  $("config-schema").addEventListener("input", () => refreshPreview());
  $("fill-demo").addEventListener("click", fillDemo);
  $("provider-form").addEventListener("submit", publishProvider);
}

function fillDemo() {
  fillProviderForm(state.demoTemplate, state.demoTemplate.system_name + "（範例）");
}

function fillProviderForm(provider, name = provider.system_name) {
  $("provider-name").value = name;
  for (const [key, entry] of providerFields) {
    const endpoint = provider.apis[key];
    entry.details.open = key === "init";
    entry.url.value = endpoint.url;
    entry.header.value = endpoint.auth?.header || "";
    entry.authValue.value = (key === "init" ? endpoint.auth?.secret_ref : endpoint.auth?.scheme) || "";
    if (key !== "init") {
      entry.description.value = endpoint.description;
      entry.sample.value = jsonText(endpoint.sample);
    }
  }
  $("config-schema").value = jsonText(provider.config_schema);
  notice($("provider-message"), "");
  refreshPreview(0);
}

function openProviderDialog(provider = null) {
  editingProvider = provider?.id ?? null;
  $("provider-dialog-title").textContent = provider ? "Edit Template" : "Provide Retrieval System Template";
  $("publish-provider").textContent = provider ? "儲存調整" : "上架服務";
  $("fill-demo").hidden = Boolean(provider);
  if (provider) fillProviderForm(provider);
  else fillDemo();
  $("provider-dialog").showModal();
}

function requireValue(control, label) {
  const value = control.value.trim();
  if (!value) {
    control.focus();
    throw new Error("請填寫 " + label + "。");
  }
  return value;
}

function describeProvider() {
  const systemName = requireValue($("provider-name"), "System 名稱");
  const apis = {};
  for (const [key, entry] of providerFields) {
    const label = operations[key];
    try {
      const url = requireValue(entry.url, label + " URL");
      if (entry.url.validity.typeMismatch) throw new Error(label + " URL 格式有誤。");
      const header = entry.header.value.trim();
      const authValue = entry.authValue.value.trim();
      let auth = null;
      if (header) {
        auth = { header };
        if (key === "init") auth.secret_ref = requireValue(entry.authValue, "Secret 環境變數");
        else if (authValue) auth.scheme = authValue;
      } else if (authValue) {
        throw new Error("請為 " + label + " 填寫 Auth Header。");
      }
      apis[key] = { url, auth };
      if (key !== "init") {
        apis[key].description = requireValue(entry.description, label + " 使用說明");
        apis[key].sample = parseJSON(entry.sample.value, label + " Sample");
      }
    } catch (error) {
      entry.details.open = true;
      throw error;
    }
  }
  return { system_name: systemName, apis, config_schema: parseJSON($("config-schema").value, "Config Schema") };
}

async function publishProvider(event) {
  event.preventDefault();
  const submit = $("publish-provider");
  submit.disabled = true;
  notice($("provider-message"), "");
  try {
    const path = editingProvider ? "/api/providers/" + editingProvider : "/api/providers";
    const provider = await api(path, describeProvider(), editingProvider ? "PUT" : "POST");
    if (editingProvider) state.providers = state.providers.map(item => item.id === provider.id ? provider : item);
    else state.providers.push(provider);
    $("provider-dialog").close();
    renderWorkspace();
    notice($("workspace-message"), "已儲存「" + provider.system_name + "」。");
  } catch (error) {
    notice($("provider-message"), error.message, true);
  } finally {
    submit.disabled = false;
  }
}

function updateCreateConfig() {
  const provider = editingSystem?.provider || providerById($("system-provider").value);
  if (provider) readConfig = schemaForm($("system-config"), provider.config_schema, editingSystem?.parameters);
  notice($("system-error"), "");
}

function openSystemDialog(system = null) {
  editingSystem = system;
  $("system-form").reset();
  const providers = system ? [system.provider] : state.providers;
  const choices = providers.map((provider) => option(provider.id, provider.system_name));
  $("system-provider").replaceChildren(...choices);
  $("system-provider").disabled = Boolean(system);
  $("system-name").value = system?.system_name ?? "";
  $("create-dialog-title").textContent = system ? "Edit Config" : "Create Retrieval System";
  $("system-dialog-description").textContent = system
    ? "儲存時會以同一個 System ID 重新呼叫 Provider Init。"
    : "選擇 Provider Template 並填寫初始化設定。";
  $("publish-system").textContent = system ? "儲存並套用" : "建立並初始化";
  updateCreateConfig();
  $("create-dialog").showModal();
}

async function publishSystem(event) {
  event.preventDefault();
  const submit = $("publish-system");
  submit.disabled = true;
  const label = submit.textContent;
  submit.textContent = "初始化中…";
  notice($("system-error"), "");
  try {
    const config = {
      system_name: $("system-name").value.trim(),
      parameters: readConfig(),
    };
    if (!editingSystem) {
      config.provider_id = $("system-provider").value;
      config.workspace_id = state.workspaceId;
    }
    const path = editingSystem ? "/api/systems/" + editingSystem.system_id : "/api/systems";
    const system = await api(path, config, editingSystem ? "PUT" : "POST");
    if (editingSystem) state.systems = state.systems.map(item => item.system_id === system.system_id ? system : item);
    else state.systems.push(system);
    $("create-dialog").close();
    renderWorkspace();
    notice($("workspace-message"), "已套用「" + system.system_name + "」的設定。");
  } catch (error) {
    notice($("system-error"), error.message, true);
  } finally {
    submit.disabled = false;
    submit.textContent = label;
  }
}

function workspaceEntry(name, count, active) {
  const entry = button("", "workspace-link");
  entry.setAttribute("aria-pressed", String(active));
  const icon = node("span", "workspace-icon", "▦");
  icon.setAttribute("aria-hidden", "true");
  entry.append(icon, node("span", "", name), node("span", "workspace-count", String(count)));
  return entry;
}

function card(name, detail, glyph) {
  const article = node("article", "card");
  const top = node("div", "card-top");
  const icon = node("span", "system-icon", glyph);
  icon.setAttribute("aria-hidden", "true");
  top.append(icon);
  article.append(top, node("h2", "", name), node("p", "card-meta", detail));
  return article;
}

function systemCard(system) {
  const article = card(system.system_name, system.provider.system_name, "▧");
  article.firstElementChild.append(node("span", "tag", "已啟用"));
  const actions = node("div", "card-actions");
  for (const [key, label] of [["ingestion", "Ingest"], ["inference", "Inference"]]) {
    const trigger = button(label, "button secondary");
    trigger.addEventListener("click", () => {
      state.systemId = system.system_id;
      state.operation = key;
      renderWorkbench();
      $("operation-dialog").showModal();
    });
    actions.append(trigger);
  }
  const links = node("div", "card-links");
  const edit = button("Edit Config", "link-button");
  edit.addEventListener("click", () => openSystemDialog(system));
  const download = node("a", "link-button", "Export YAML");
  download.href = "/api/systems/" + system.system_id + "/export";
  download.download = "";
  links.append(edit, download);
  article.append(actions, links);
  return article;
}

function providerCard(provider) {
  const count = Object.keys(provider.config_schema.properties).length;
  const article = card(provider.system_name, "Init · Ingestion · Inference · " + count + " 個設定欄位", "▤");
  const actions = node("div", "card-actions");
  const edit = button("Edit Template", "button secondary");
  edit.addEventListener("click", () => openProviderDialog(provider));
  actions.append(edit);
  article.append(actions);
  return article;
}

function renderWorkspace() {
  const nav = $("workspace-list");
  nav.replaceChildren();
  $("create-system").disabled = !state.providers.length;
  $("create-provider").disabled = !state.demoTemplate;
  if (state.page === "provider") {
    $("workspace-label").textContent = "Provider";
    $("breadcrumb").textContent = "Provider / Templates";
    nav.append(workspaceEntry("Templates", state.providers.length, true));
    $("provider-count").textContent = state.providers.length + " Retrieval System Templates";
    $("provider-list").replaceChildren(...state.providers.map(providerCard));
    return;
  }
  $("workspace-label").textContent = "Workspaces";
  const workspace = state.workspaces.find(item => item.id === state.workspaceId);
  if (!workspace) return;
  const systems = state.systems.filter(item => item.workspace_id === workspace.id);
  for (const item of state.workspaces) {
    const count = state.systems.filter(system => system.workspace_id === item.id).length;
    const entry = workspaceEntry(item.name, count, item.id === workspace.id);
    entry.addEventListener("click", () => {
      state.workspaceId = item.id;
      notice($("workspace-message"), "");
      renderWorkspace();
      nav.querySelector('[aria-pressed="true"]').focus();
    });
    nav.append(entry);
  }
  $("breadcrumb").textContent = "Workspaces / " + workspace.name;
  $("workspace-name").textContent = workspace.name;
  $("system-count").textContent = systems.length + " Retrieval Systems";
  const cards = systems.length ? systems.map(systemCard) : [node("p", "empty", "此 Workspace 尚無 Retrieval System。")];
  $("system-list").replaceChildren(...cards);
}

function renderWorkbench() {
  const desk = $("workbench");
  desk.replaceChildren();
  const system = state.systems.find((candidate) => candidate.system_id === state.systemId);
  if (!system) {
    desk.append(node("p", "empty", "建立 System 後即可送出匯入或查詢請求。"));
    return;
  }

  const provider = system.provider;
  $("operation-title").textContent = system.system_name;
  $("operation-subtitle").textContent = provider.system_name;

  const tabs = node("nav", "operation-nav");
  tabs.setAttribute("aria-label", "System 操作");
  for (const key of ["ingestion", "inference"]) {
    const tab = button(key === "ingestion" ? "Ingest" : "Inference", "");
    tab.setAttribute("aria-pressed", String(key === state.operation));
    tab.addEventListener("click", () => {
      state.operation = key;
      renderWorkbench();
      desk.querySelector('[aria-pressed="true"]').focus();
    });
    tabs.append(tab);
  }
  const body = node("div", "operation-body");
  const route = "/systems/" + system.system_id + "/" + state.operation;
  const endpoint = provider.apis[state.operation];
  const path = node("div", "endpoint");
  path.append(node("span", "method", "POST"), node("code", "", route));
  body.append(node("p", "instructions", endpoint.description), path, buildConsole(route, endpoint));
  desk.append(tabs, body);
}

function buildConsole(route, endpoint) {
  const grid = node("div", "console-grid");
  const request = node("form");
  const requestTitle = node("div", "console-title");
  const reset = button("還原範例", "link-button");
  requestTitle.append(node("h3", "", "Request Body"), reset);

  const requestBody = textarea(7);
  requestBody.id = "request-body";
  requestBody.setAttribute("aria-label", "Request Body");
  const sample = jsonText(endpoint.sample);
  requestBody.value = state.drafts.get(route) ?? sample;
  requestBody.addEventListener("input", () => state.drafts.set(route, requestBody.value));
  reset.addEventListener("click", () => {
    state.drafts.delete(route);
    requestBody.value = sample;
    requestBody.focus();
  });
  request.append(requestTitle, requestBody);
  const auth = endpoint.auth ? input("password", endpoint.auth.scheme ? endpoint.auth.scheme + " …" : "輸入憑證") : null;
  if (auth) request.append(authField(endpoint.auth.header, auth));
  const sendRow = node("div", "send-row");
  const send = button("送出請求", "button primary");
  send.type = "submit";
  sendRow.append(send);
  request.append(sendRow);

  const result = node("section");
  const resultTitle = node("div", "console-title");
  const status = node("span", "http-status");
  status.setAttribute("role", "status");
  resultTitle.append(node("h3", "", "Response Body"), status);
  const response = node("pre", "response-editor");
  response.tabIndex = 0;
  response.setAttribute("aria-label", "Response Body");
  result.append(resultTitle, response);
  grid.append(request, result);

  request.addEventListener("submit", async (event) => {
    event.preventDefault();
    await sendRequest({ route, endpoint, requestBody, auth, send, status, response });
  });
  return grid;
}

async function sendRequest({ route, endpoint, requestBody, auth, send, status, response }) {
  send.disabled = true;
  status.textContent = "傳送中…";
  status.classList.remove("failed");
  response.textContent = "";
  try {
    parseJSON(requestBody.value, "Request Body");
    const headers = new Headers({ "Content-Type": "application/json" });
    if (auth?.value) headers.set(endpoint.auth.header, auth.value);
    const result = await fetch(route, { method: "POST", headers, body: requestBody.value });
    status.textContent = "HTTP " + result.status;
    status.classList.toggle("failed", !result.ok);
    response.textContent = (await result.text()) || "空白回應";
  } catch (error) {
    status.textContent = "傳送失敗";
    status.classList.add("failed");
    response.textContent = error.message;
  } finally {
    send.disabled = false;
  }
}

async function start() {
  for (const button of document.querySelectorAll("[data-page]")) {
    button.addEventListener("click", () => selectPage(button.dataset.page));
  }
  $("system-form").addEventListener("submit", publishSystem);
  $("system-provider").addEventListener("change", updateCreateConfig);
  $("create-system").addEventListener("click", () => openSystemDialog());
  $("create-provider").addEventListener("click", () => openProviderDialog());
  for (const dialog of document.querySelectorAll("dialog")) {
    const isSaving = () => dialog.querySelector('button[type="submit"]:disabled');
    for (const close of dialog.querySelectorAll("[data-close]")) {
      close.addEventListener("click", () => { if (!isSaving()) dialog.close(); });
    }
    dialog.addEventListener("cancel", event => { if (isSaving()) event.preventDefault(); });
  }
  setupProvider();
  try {
    const result = await api("/api/catalog");
    state.providers = result.providers;
    state.systems = result.systems;
    state.workspaces = result.workspaces;
    state.workspaceId = state.workspaces[0]?.id;
    state.demoTemplate = result.demo_template;
    renderWorkspace();
  } catch (error) {
    notice($("load-error"), "讀取 System 與 Provider 失敗：" + error.message, true);
  }
}

start();
