"use strict";

const operations = { init: "Init", ingestion: "Ingestion", inference: "Inference" };
const $ = (id) => document.getElementById(id);
const jsonText = (value) => JSON.stringify(value, null, 2);
const has = (object, key) => Object.hasOwn(object, key);
const state = { providers: [], systems: [], systemId: null, operation: "ingestion", drafts: new Map() };
const providerFields = new Map();
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

async function api(path, body) {
  const response = await fetch(path, body === undefined ? undefined : {
    method: "POST",
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
  $("user-page").hidden = page !== "user";
  $("provider-page").hidden = page !== "provider";
  for (const pill of document.querySelectorAll("[data-page]")) {
    if (pill.dataset.page === page) pill.setAttribute("aria-current", "page");
    else pill.removeAttribute("aria-current");
  }
}

function schemaForm(container, schema) {
  container.replaceChildren();
  if (schema.title) container.append(node("h3", "schema-title", schema.title));
  if (schema.description) container.append(node("p", "schema-description", schema.description));
  const group = node("div", "parameter-list");
  const required = new Set(schema.required || []);
  const controls = new Map();
  for (const [name, spec] of Object.entries(schema.properties)) {
    const values = spec.enum || (spec.type === "boolean" ? [true, false] : null);
    let control;
    if (values) {
      control = node("select");
      control.append(option("", "請選擇"));
      values.forEach((value, index) => {
        const label = typeof value === "boolean" ? (value ? "是" : "否") : String(value);
        control.append(option(String(index), label));
      });
      if (has(spec, "default")) control.value = String(values.indexOf(spec.default));
    } else {
      const numeric = spec.type === "integer" || spec.type === "number";
      control = input(numeric ? "number" : "text");
      if (numeric) control.step = spec.type === "integer" ? "1" : "any";
      if (has(spec, "default")) control.value = spec.default;
    }
    control.name = name;
    if (required.has(name)) control.setAttribute("aria-required", "true");
    group.append(field(spec.title || name, control, { required: required.has(name), hint: spec.description }));
    controls.set(name, { control, spec, values });
  }
  if (controls.size) container.append(group);
  else container.append(node("p", "muted", "此 Provider 沒有額外設定。"));

  return () => {
    const pairs = [];
    for (const [name, { control, spec, values }] of controls) {
      if (control.validity.badInput || control.validity.stepMismatch) {
        control.focus();
        throw new Error("請輸入有效的" + (spec.type === "integer" ? "整數" : "數字") + "：" + name);
      }
      const value = control.value;
      if (value === "" && spec.default !== "") {
        if (required.has(name)) {
          control.focus();
          throw new Error("請填寫必填欄位：" + name);
        }
        continue;
      }
      if (values && value === "") {
        if (required.has(name)) {
          control.focus();
          throw new Error("請選擇必填欄位：" + name);
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
  refreshPreview(0);
}

function fillDemo() {
  const demo = providerById("demo");
  if (!demo) return;
  $("provider-name").value = demo.system_name + "（範例）";
  for (const [key, entry] of providerFields) {
    const endpoint = demo.apis[key];
    entry.url.value = endpoint.url;
    entry.header.value = endpoint.auth?.header || "";
    entry.authValue.value = (key === "init" ? endpoint.auth?.secret_ref : endpoint.auth?.scheme) || "";
    if (key !== "init") {
      entry.description.value = endpoint.description;
      entry.sample.value = jsonText(endpoint.sample);
    }
  }
  $("config-schema").value = jsonText(demo.config_schema);
  notice($("provider-message"), "");
  refreshPreview(0);
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
    const provider = await api("/api/providers", describeProvider());
    state.providers.push(provider);
    renderCatalog();
    notice($("provider-message"), "服務「" + provider.system_name + "」已上架，可在 User 工作區選用。");
  } catch (error) {
    notice($("provider-message"), error.message, true);
  } finally {
    submit.disabled = false;
  }
}

function renderCatalog() {
  $("provider-list").replaceChildren(...state.providers.map(
    (provider) => node("div", "catalog-item", provider.system_name),
  ));
  $("create-system").disabled = !state.providers.length;
}

function updateCreateConfig() {
  const provider = providerById($("system-provider").value);
  if (provider) readConfig = schemaForm($("system-config"), provider.config_schema);
  notice($("system-error"), "");
}

function openCreateDialog() {
  $("system-form").reset();
  const choices = state.providers.map((provider) => option(provider.id, provider.system_name));
  $("system-provider").replaceChildren(...choices);
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
    const system = await api("/api/systems", {
      provider_id: $("system-provider").value,
      system_name: $("system-name").value.trim(),
      parameters: readConfig(),
    });
    state.systems.push(system);
    state.systemId = system.system_id;
    state.operation = "ingestion";
    $("create-dialog").close();
    renderSystems();
  } catch (error) {
    notice($("system-error"), error.message, true);
  } finally {
    submit.disabled = false;
    submit.textContent = label;
  }
}

function renderSystems() {
  const list = $("system-list");
  list.replaceChildren();
  if (!state.systems.length) list.append(node("p", "empty", "目前沒有已建立的 System。"));
  for (const system of state.systems) {
    const item = button("", "rail-item");
    item.setAttribute("aria-current", String(system.system_id === state.systemId));
    item.append(
      node("strong", "", system.system_name),
      node("small", "", providerById(system.provider_id).system_name),
    );
    item.addEventListener("click", () => {
      state.systemId = system.system_id;
      renderSystems();
    });
    list.append(item);
  }
  renderWorkbench();
}

function renderWorkbench() {
  const desk = $("workbench");
  desk.replaceChildren();
  const system = state.systems.find((candidate) => candidate.system_id === state.systemId);
  if (!system) {
    desk.append(node("p", "empty", "建立 System 後即可送出匯入或查詢請求。"));
    return;
  }

  const provider = providerById(system.provider_id);
  const header = node("header", "workbench-header");
  const meta = node("div", "system-meta");
  const status = node("span", "tag");
  status.append(node("span", "status-dot"), "已啟用");
  meta.append(status, node("span", "muted", provider.system_name));
  header.append(node("h2", "", system.system_name), meta);

  const tabs = node("nav", "operation-nav");
  tabs.setAttribute("aria-label", "System 操作");
  for (const key of ["ingestion", "inference"]) {
    const tab = button(operations[key], "");
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
  desk.append(header, tabs, body);
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
  if (auth) {
    auth.autocomplete = "off";
    const label = field(endpoint.auth.header, auth);
    label.classList.add("auth-field");
    request.append(label);
  }
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
  $("create-system").addEventListener("click", openCreateDialog);
  for (const id of ["close-dialog", "cancel-create"]) {
    $(id).addEventListener("click", () => $("create-dialog").close());
  }
  $("create-system").disabled = true;
  setupProvider();
  try {
    const result = await api("/api/catalog");
    state.providers = result.providers;
    state.systems = result.systems;
    state.systemId = state.systems[0]?.system_id;
    renderCatalog();
    renderSystems();
  } catch (error) {
    notice($("load-error"), "讀取 System 與 Provider 失敗：" + error.message, true);
  }
}

start();
