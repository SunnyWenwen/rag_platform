import React, {useEffect, useRef, useState} from "react";
import {createRoot} from "react-dom/client";

const operations = {init: "Init", ingestion: "Ingestion", inference: "Inference"};
const businessOperations = [["ingestion", "Ingest"], ["inference", "Inference"]];
const jsonText = value => JSON.stringify(value, null, 2);
const responseSource = "Retrieval-Response-Source";

async function api(path, body, method = "POST") {
  const response = await fetch(path, body === undefined ? undefined : {
    method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    throw Object.assign(new Error(result.error || "HTTP " + response.status), {
      status: response.status, initUnconfirmed: result.init_unconfirmed === true,
    });
  }
  return result;
}

function parseJSON(value, label) {
  try {
    return JSON.parse(value);
  } catch {
    throw new Error(label + " 必須是有效的 JSON。");
  }
}

function Notice({text, error = false}) {
  return text ? <p className={"notice" + (error ? " error" : "")} role={error ? "alert" : "status"}>{text}</p> : null;
}

function Field({label, children, required, hint}) {
  return <label className="field">
    <span>{label}{required && <span className="required-mark"> *</span>}</span>
    {children}{hint && <small>{hint}</small>}
  </label>;
}

function Dialog({id, title, subtitle, wide, busy, onClose, children}) {
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => { if (element.open) element.close(); };
  }, []);
  return <dialog id={id} ref={dialog} className={wide ? "wide-dialog" : undefined} aria-labelledby={id + "-title"}
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <header className="dialog-header">
      <div><h2 id={id + "-title"}>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
      <button type="button" className="icon-button" aria-label="關閉" disabled={busy} onClick={onClose}>×</button>
    </header>
    {children}
  </dialog>;
}

function defaultInputs(schema, parameters) {
  return Object.fromEntries(Object.entries(schema.properties).map(([name, field]) => {
    const value = parameters ? (Object.hasOwn(parameters, name) ? parameters[name] : undefined) : field.default;
    return [name, value === undefined ? "" : field.enum || field.type === "boolean" ? jsonText(value) : String(value)];
  }));
}

function ParametersForm({schema, values, onChange}) {
  const required = new Set(schema.required || []);
  return <>
    {schema.title && <h3 className="schema-title">{schema.title}</h3>}
    {schema.description && <p className="schema-description">{schema.description}</p>}
    {!Object.keys(schema.properties).length && <p className="muted">此 Provider 沒有額外設定。</p>}
    <div className="parameter-list">
      {Object.entries(schema.properties).map(([name, spec]) => {
        const choices = spec.enum || (spec.type === "boolean" ? [true, false] : null);
        const numeric = spec.type === "integer" || spec.type === "number";
        const props = {name, value: values[name] ?? "", onChange: event => onChange(name, event.target.value)};
        return <Field key={name} label={spec.title || name} required={required.has(name)} hint={spec.description}>
          {choices ? <select {...props} aria-required={required.has(name)}>
            <option value="">請選擇</option>
            {choices.map(value => <option key={jsonText(value)} value={jsonText(value)}>
              {typeof value === "boolean" ? (value ? "是" : "否") : String(value)}
            </option>)}
          </select> : <input {...props} type={numeric ? "number" : "text"} step={numeric ? (spec.type === "integer" ? "1" : "any") : undefined}
            aria-required={required.has(name)}/>}
        </Field>;
      })}
    </div>
  </>;
}

function readParameters(schema, values, initial) {
  const required = new Set(schema.required || []);
  const entries = [];
  for (const [name, spec] of Object.entries(schema.properties)) {
    const value = values[name];
    if (value === "") {
      if (spec.type === "string" && !spec.enum && initial?.[name] === "") {
        entries.push([name, ""]);
      } else if (required.has(name)) {
        throw new Error("請填寫必填欄位：" + name);
      }
      continue;
    }
    if (spec.enum || spec.type === "boolean") entries.push([name, JSON.parse(value)]);
    else if (spec.type === "string") entries.push([name, value]);
    else entries.push([name, Number(value)]);
  }
  return Object.fromEntries(entries);
}

function providerFields(provider, name = provider.system_name) {
  const apis = Object.fromEntries(Object.entries(provider.apis).map(([key, endpoint]) => [key, {
    url: endpoint.url, header: endpoint.auth?.header || "",
    authValue: (key === "init" ? endpoint.auth?.secret_ref : endpoint.auth?.scheme) || "",
    description: endpoint.description || "", sample: key === "init" ? "" : jsonText(endpoint.sample),
  }]));
  return {name, apis, schema: jsonText(provider.config_schema)};
}

function providerRequest(draft) {
  const apis = Object.fromEntries(Object.entries(draft.apis).map(([key, endpoint]) => {
    const header = endpoint.header.trim();
    const value = endpoint.authValue.trim();
    if (!header && value) throw new Error("請為 " + operations[key] + " 填寫 Auth Header。");
    if (header && key === "init" && !value) throw new Error("請填寫 Init Secret 環境變數。");
    const auth = header ? {header, [key === "init" ? "secret_ref" : "scheme"]: value} : null;
    const operation = {url: endpoint.url, auth};
    if (key !== "init") {
      operation.description = endpoint.description;
      operation.sample = parseJSON(endpoint.sample, operations[key] + " Sample");
    }
    return [key, operation];
  }));
  return {system_name: draft.name, apis, config_schema: parseJSON(draft.schema, "Config Schema")};
}

function ProviderDialog({provider, demo, onSave, onClose}) {
  const loadDemo = () => providerFields(demo, demo.system_name + "（範例）");
  const [draft, setDraft] = useState(() => provider ? providerFields(provider) : loadDemo());
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [values, setValues] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let current = true;
    const timer = setTimeout(async () => {
      try {
        const schema = parseJSON(draft.schema, "Config Schema");
        await api("/api/schema/validate", schema);
        if (current) {
          setPreview(schema);
          setValues(defaultInputs(schema));
          setPreviewError("");
        }
      } catch (err) {
        if (current) {
          setPreview(null);
          setPreviewError(err.message);
        }
      }
    }, 200);
    return () => { current = false; clearTimeout(timer); };
  }, [draft.schema]);

  const change = (operation, field, value) => setDraft(current => ({
    ...current, apis: {...current.apis, [operation]: {...current.apis[operation], [field]: value}},
  }));

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const path = provider ? "/api/providers/" + provider.id : "/api/providers";
      await onSave(await api(path, providerRequest(draft), provider ? "PUT" : "POST"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return <Dialog id="provider-dialog" title={provider ? "Edit Template" : "Provide Retrieval System Template"} wide busy={busy} onClose={onClose}>
    <div className="provider-layout dialog-body">
      <form id="provider-form" className="panel provider-form" noValidate onSubmit={save}>
        <header className="panel-heading"><h2>新增 Retrieval Service</h2><p>System Description</p></header>
        <Field label="System 名稱" required>
          <input id="provider-name" value={draft.name} onChange={event => setDraft({...draft, name: event.target.value})}/>
        </Field>
        <div className="provider-apis">
          {Object.entries(operations).map(([key, label]) => {
            const endpoint = draft.apis[key];
            const props = field => ({value: endpoint[field], onChange: event => change(key, field, event.target.value)});
            return <details key={key} open={key === "init"}>
              <summary>{label}</summary>
              <div className="api-fields">
                <Field label={label + " URL"} required><input id={key + "-url"} type="url" {...props("url")}/></Field>
                <div className="auth-fields">
                  <Field label="Auth Header" hint="留空表示無需 Auth。"><input id={key + "-auth-header"} {...props("header")}/></Field>
                  <Field label={key === "init" ? "Secret 環境變數" : "Auth 格式提示"}><input id={key + "-auth-value"} {...props("authValue")}/></Field>
                </div>
                {key !== "init" && <>
                  <Field label={label + " 使用說明"} required><textarea id={key + "-description"} rows="2" {...props("description")}/></Field>
                  <Field label={label + " JSON Sample"} required><textarea id={key + "-sample"} className="code-input" rows="5" spellCheck={false} {...props("sample")}/></Field>
                </>}
              </div>
            </details>;
          })}
        </div>
        <Field label="Config Schema" required>
          <textarea id="config-schema" className="code-input" rows="12" spellCheck={false} value={draft.schema}
            onChange={event => setDraft({...draft, schema: event.target.value})}/>
        </Field>
        <div className="form-actions">
          <div className="form-resources">
            <a href="/provider-guide" target="_blank" rel="noopener">使用說明 ↗</a>
            <a href="/config-schema.meta.schema.json" target="_blank" rel="noopener">檢視 Meta Schema ↗</a>
          </div>
          <div className="form-buttons">
            {!provider && <button type="button" className="button secondary" onClick={() => { setDraft(loadDemo()); setError(""); }}>重載範例</button>}
            <button className="button primary" id="publish-provider" disabled={busy}>{provider ? "儲存調整" : "上架服務"}</button>
          </div>
        </div>
        <Notice error text={error}/>
      </form>
      <aside className="provider-side">
        <section className="panel preview-panel" aria-labelledby="preview-title">
          <header className="panel-heading"><h2 id="preview-title">User 表單預覽</h2><p>依 Config Schema 即時更新。</p></header>
          <div id="schema-preview" aria-live="polite">
            <Notice error text={previewError}/>
            {preview && <ParametersForm schema={preview} values={values} onChange={(name, value) => setValues(current => ({...current, [name]: value}))}/>}
          </div>
        </section>
      </aside>
    </div>
  </Dialog>;
}

function SystemDialog({system, providers, workspaceId, onSave, onClose}) {
  const [provider, setProvider] = useState(system?.provider || providers[0]);
  const [name, setName] = useState(system?.system_name || "");
  const [values, setValues] = useState(() => defaultInputs(provider.config_schema, system?.parameters));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const retry = useRef(null);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!retry.current) {
        const schema = provider.config_schema;
        const initial = system?.parameters || Object.fromEntries(Object.entries(schema.properties).map(([key, field]) => [key, field.default]));
        const config = {system_name: name.trim(), parameters: readParameters(schema, values, initial)};
        if (!system) Object.assign(config, {
          system_id: crypto.randomUUID(), provider_id: provider.id, workspace_id: workspaceId,
        });
        retry.current = config;
      }
      const path = system ? "/api/systems/" + system.system_id : "/api/systems";
      await onSave(await api(path, retry.current, system ? "PUT" : "POST"));
    } catch (err) {
      const unknown = Boolean(retry.current && (err.initUnconfirmed || !err.status || (unconfirmed && err.status === 409)));
      setUnconfirmed(unknown);
      if (!unknown) retry.current = null;
      setError(unknown
        ? "初始化結果未確認。請重試以沿用同一個 System ID 與設定。"
        : err.message);
    } finally {
      setBusy(false);
    }
  }

  return <Dialog id="create-dialog" title={system ? "Edit Config" : "Create Retrieval System"}
    subtitle={system ? "儲存時會以同一個 System ID 重新呼叫 Provider Init。" : "選擇 Provider Template 並填寫初始化設定。"} busy={busy} onClose={onClose}>
    <form id="system-form" onSubmit={save}>
      <div className="dialog-body">
        <div inert={unconfirmed || busy}>
          <Field label="Provider" required><select id="system-provider" value={provider.id} disabled={Boolean(system)} onChange={event => {
            const selected = providers.find(item => item.id === event.target.value);
            setProvider(selected);
            setValues(defaultInputs(selected.config_schema));
            setError("");
          }}>
            {(system ? [system.provider] : providers).map(item => <option key={item.id} value={item.id}>{item.system_name}</option>)}
          </select></Field>
          <Field label="System 名稱" required><input id="system-name" value={name} onChange={event => setName(event.target.value)} required/></Field>
          <div id="system-config" className="dialog-config">
            <ParametersForm schema={provider.config_schema} values={values} onChange={(key, value) => setValues(current => ({...current, [key]: value}))}/>
          </div>
        </div>
        <Notice error text={error}/>
      </div>
      <footer className="dialog-footer">
        <button type="button" className="button secondary" disabled={busy} onClick={onClose}>取消</button>
        <button className="button primary" id="publish-system" disabled={busy}>{busy ? "初始化中…" : unconfirmed ? "重試初始化" : system ? "儲存並套用" : "建立並初始化"}</button>
      </footer>
    </form>
  </Dialog>;
}

function AuthField({auth, value, onChange}) {
  const [visible, setVisible] = useState(false);
  const action = visible ? "隱藏憑證" : "顯示憑證";
  return <div className="field auth-field">
    <label htmlFor="request-auth">{auth.header}</label>
    <div className="password-control">
      <input id="request-auth" type={visible ? "text" : "password"} autoComplete="off" value={value} onChange={onChange}
        placeholder={auth.scheme ? auth.scheme + " …" : "輸入憑證"}/>
      <button type="button" className="password-toggle" aria-controls="request-auth" aria-label={action} title={action}
        onClick={() => setVisible(!visible)}><span className="eye-icon" aria-hidden="true"/></button>
    </div>
  </div>;
}

function shellQuote(value) {
  return "'" + value.replaceAll("'", "'\\''") + "'";
}

function curlCommand(url, headers, body) {
  const lines = ["curl --globoff --request POST " + shellQuote(url)];
  for (const header of headers) lines.push("--header " + shellQuote(header));
  lines.push("--data-binary " + shellQuote(body));
  return lines.join(" \\\n  ");
}

function Console({route, systemId, endpoint, drafts, busy, setBusy}) {
  const sample = jsonText(endpoint.sample);
  const [body, setBody] = useState(() => drafts.get(route) ?? sample);
  const [credential, setCredential] = useState("");
  const [sent, setSent] = useState(null);
  const [response, setResponse] = useState({status: "", source: "", body: ""});
  const input = useRef(null);

  async function send(event) {
    event.preventDefault();
    setBusy(true);
    setResponse({status: "傳送中…", source: "", body: ""});
    try {
      parseJSON(body, "Payload");
      const providerBody = '{\n  "system_id": ' + jsonText(systemId) + ',\n  "payload": ' + body + "\n}";
      const headers = new Headers({"Content-Type": "application/json"});
      const display = ["Content-Type: application/json"];
      if (endpoint.auth && credential) {
        headers.set(endpoint.auth.header, credential);
        display.push(endpoint.auth.header + ": [已遮蔽]");
      }
      setSent({
        provider: ["POST " + endpoint.url, ...display, "", providerBody].join("\n"),
        builder: ["POST " + route, ...display, "", body].join("\n"),
        curl: curlCommand(endpoint.url, display, providerBody),
      });
      const result = await fetch(route, {method: "POST", headers, body});
      setResponse({
        status: "HTTP " + result.status, source: result.headers.get(responseSource), failed: !result.ok,
        body: (await result.text()) || "空白回應",
      });
    } catch (err) {
      setResponse({status: "傳送失敗", source: "", body: err.message, failed: true});
    } finally {
      setBusy(false);
    }
  }

  return <div className="console-grid">
    <div>
      <form onSubmit={send}>
        <div className="console-title"><h3>Request Payload</h3><button type="button" className="link-button" onClick={() => {
          drafts.delete(route); setBody(sample); input.current.focus();
        }}>還原範例</button></div>
        <textarea id="request-body" ref={input} className="code-input" rows="7" spellCheck={false} aria-label="Request Payload"
          value={body} onChange={event => { drafts.set(route, event.target.value); setBody(event.target.value); }}/>
        {endpoint.auth && <AuthField auth={endpoint.auth} value={credential} onChange={event => setCredential(event.target.value)}/>}
        <div className="send-row"><button className="button primary" disabled={busy}>送出請求</button></div>
      </form>
      {sent && <section className="sent-request">
        <h3 id="sent-request-title">Provider Request</h3>
        <pre className="response-editor" tabIndex="0" aria-labelledby="sent-request-title">{sent.provider}</pre>
        <details><summary>瀏覽器送往 Builder 的測試 Request</summary>
          <pre className="response-editor" tabIndex="0">{sent.builder}</pre>
        </details>
        <h3 id="sent-curl-title">直連 Provider 的 cURL（Bash）</h3>
        <pre className="response-editor" tabIndex="0" aria-labelledby="sent-curl-title">{sent.curl}</pre>
      </section>}
    </div>
    <section>
      <div className="console-title"><h3>Response Body</h3><div className="response-meta">
        <span role="status" className={"http-status" + (response.failed ? " failed" : "")}>{response.status}</span>
        {response.source && <span className="response-source">來源 {response.source}</span>}
      </div></div>
      <pre className="response-editor" tabIndex="0" aria-label="Response Body">{response.body}</pre>
    </section>
  </div>;
}

function OperationDialog({system, initialOperation, drafts, onClose}) {
  const [operation, setOperation] = useState(initialOperation);
  const [busy, setBusy] = useState(false);
  const route = "/api/systems/" + system.system_id + "/test/" + operation;
  const endpoint = system.provider.apis[operation];
  return <Dialog id="operation-dialog" title={system.system_name} subtitle={system.provider.system_name} wide busy={busy} onClose={onClose}>
    <section id="workbench" aria-label="System 操作區">
      <nav className="operation-nav" aria-label="System 操作">
        {businessOperations.map(([key, label]) => <button key={key} type="button" disabled={busy} aria-pressed={key === operation}
          onClick={() => setOperation(key)}>{label}</button>)}
      </nav>
      <div className="operation-body">
        <p className="instructions">{endpoint.description}</p>
        <div className="endpoint"><span className="method">POST</span><code>{endpoint.url}</code></div>
        <Console key={route} route={route} systemId={system.system_id} endpoint={endpoint} drafts={drafts} busy={busy} setBusy={setBusy}/>
      </div>
    </section>
  </Dialog>;
}

function WorkspaceEntry({name, count, active, onClick}) {
  return <button type="button" className="workspace-link" aria-pressed={active} onClick={onClick}>
    <span className="workspace-icon" aria-hidden="true">▦</span><span>{name}</span><span className="workspace-count">{count}</span>
  </button>;
}

function Card({name, detail, glyph, status, children}) {
  return <article className="card">
    <div className="card-top"><span className="system-icon" aria-hidden="true">{glyph}</span>{status && <span className="tag">{status}</span>}</div>
    <h2>{name}</h2><p className="card-meta">{detail}</p>{children}
  </article>;
}

function App() {
  const [catalog, setCatalog] = useState(null);
  const [page, setPage] = useState("user");
  const [workspaceId, setWorkspaceId] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const drafts = useRef(new Map());

  useEffect(() => {
    api("/api/catalog").then(result => {
      setCatalog(result);
      setWorkspaceId(result.workspaces[0]?.id);
    }).catch(err => setError("讀取 System 與 Provider 失敗：" + err.message));
  }, []);

  const providers = catalog?.providers || [];
  const systems = catalog?.systems || [];
  const workspaces = catalog?.workspaces || [];
  const workspace = workspaces.find(item => item.id === workspaceId);
  const visibleSystems = systems.filter(item => item.workspace_id === workspaceId);
  const providerPage = page === "provider";
  const close = () => setDialog(null);
  const open = (kind, item, operation) => setDialog({kind, item, operation});

  function save(item, collection, key, label) {
    setCatalog(current => {
      const items = current[collection];
      const next = items.some(entry => entry[key] === item[key])
        ? items.map(entry => entry[key] === item[key] ? item : entry)
        : [...items, item];
      return {...current, [collection]: next};
    });
    setMessage(label + "「" + item.system_name + "」。");
    close();
  }

  return <>
    <aside className="sidebar" aria-label="Workspace 導覽">
      <div className="brand"><span className="brand-mark" aria-hidden="true">r</span> Retrieval Builder</div>
      <h2 className="sidebar-label" id="workspace-label">{providerPage ? "Provider" : "Workspaces"}</h2>
      <nav id="workspace-list" aria-labelledby="workspace-label">
        {providerPage ? <WorkspaceEntry name="Templates" count={providers.length} active/>
          : workspaces.map(item => <WorkspaceEntry key={item.id} name={item.name} active={item.id === workspaceId}
            count={systems.filter(system => system.workspace_id === item.id).length}
            onClick={() => { setWorkspaceId(item.id); setMessage(""); }}/>)}
      </nav>
      <span className="environment">本機 MVP</span>
    </aside>
    <main className="main">
      <header className="workspace-header">
        <p className="crumb" id="breadcrumb">{providerPage ? "Provider / Templates" : "Workspaces / " + (workspace?.name || "")}</p>
        <nav className="page-nav" aria-label="模式切換">
          {["user", "provider"].map(mode => <button key={mode} type="button" data-page={mode}
            aria-current={page === mode ? "page" : undefined} onClick={() => { setPage(mode); setMessage(""); }}>
            {mode === "user" ? "User" : "Provider"}
          </button>)}
        </nav>
        {providerPage ? <button className="button primary" id="create-provider" disabled={!catalog?.demo_template} onClick={() => open("provider")}>＋ Provide Retrieval System Template</button>
          : <button className="button primary" id="create-system" disabled={!providers.length} onClick={() => open("system")}>＋ Create Retrieval System</button>}
      </header>
      <Notice error text={error}/>
      <Notice text={message}/>
      {providerPage ? <section id="provider-page">
        <div className="workspace-heading provider-heading">
          <div><h1>Retrieval System Templates</h1><p className="muted">{providers.length} Retrieval System Templates</p></div>
          <a className="button secondary guide-link" href="/provider-guide" target="_blank" rel="noopener">使用說明 ↗</a>
        </div>
        <div id="provider-list" className="cards">
          {providers.map(provider => <Card key={provider.id} name={provider.system_name} glyph="▤"
            detail={"Init · Ingestion · Inference · " + Object.keys(provider.config_schema.properties).length + " 個設定欄位"}>
            <div className="card-actions"><button className="button secondary" onClick={() => open("provider", provider)}>Edit Template</button></div>
          </Card>)}
        </div>
      </section> : <section id="user-page">
        <div className="workspace-heading"><h1>{workspace?.name || "Retrieval Systems"}</h1><p className="muted">{visibleSystems.length} Retrieval Systems</p></div>
        <div id="system-list" className="cards">
          {catalog && !visibleSystems.length && <p className="empty">此 Workspace 尚無 Retrieval System。</p>}
          {visibleSystems.map(system => <Card key={system.system_id} name={system.system_name} glyph="▧" status="已啟用" detail={system.provider.system_name}>
            <div className="card-actions">
              {businessOperations.map(([operation, label]) => <button key={operation} className="button secondary"
                onClick={() => open("operation", system, operation)}>{label}</button>)}
            </div>
            <div className="card-links">
              <button className="link-button" onClick={() => open("system", system)}>Edit Config</button>
              <a className="link-button" href={"/api/systems/" + system.system_id + "/export"} download>Export YAML</a>
            </div>
          </Card>)}
        </div>
      </section>}
    </main>
    {dialog?.kind === "provider" && <ProviderDialog provider={dialog.item} demo={catalog.demo_template} onClose={close}
      onSave={item => save(item, "providers", "id", "已儲存")}/>}
    {dialog?.kind === "system" && <SystemDialog system={dialog.item} providers={providers} workspaceId={workspaceId} onClose={close}
      onSave={item => save(item, "systems", "system_id", "已套用")}/>}
    {dialog?.kind === "operation" && <OperationDialog system={dialog.item} initialOperation={dialog.operation} drafts={drafts.current} onClose={close}/>}
  </>;
}

createRoot(document.getElementById("root")).render(<App />);
