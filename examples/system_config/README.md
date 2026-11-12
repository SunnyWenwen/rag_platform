# System Config 與 Component Descriptor 草案

現行設計見 [System Config](../../docs/05_system_config.md)及 [Component Descriptor](../../docs/04_component_descriptor.md)。

## 可驗證的 Local Search 設定

- [System Config Schema 草案](../../schemas/system_config.draft.schema.json)驗證發布快照 `{system_id, config_revision, config}`。`config` 包含 `contract_version` 與固定 Module 骨架的 `pipelines`。
- [內建版本](local_memory.builtin.json)及 [Remote Parsing 版本](local_memory.remote_parsing.json)使用同一個 System。第二版只把 Parsing 換成 Remote，兩版推導出相同的候選欄位、向量與索引能力。

內建節點以 `method_id`／`method_version` 找到對應 Descriptor，再驗證 `parameters`。Remote 節點放在替換區段的第一個 Module，以 `through` 指定最後一個 Module，已涵蓋的後續節點從有效設定省略。Remote Parsing 宣告輸出 `structdata`，Request 依上游 Import 設定推導。Remote 服務以 `service_ref` 引用，Endpoint 與認證由環境綁定解析。

離線驗證同時檢查 JSON 形狀及跨節點規則。案例驗證以 Local Search、固定測試 Profile 與內建 Inference 為範圍。正式鍵名、逐方法參數、完整部署綁定及 Runtime 執行仍待定稿與整合。

## Component Descriptor 驗證

- [Meta-schema 草案](../../schemas/component_descriptor.draft.schema.json)驗證 Descriptor 的外層及目前測試的宣告語法。
- [Recursive Descriptor](recursive.descriptor.json)示範一個切分欄位、動態選項、欄位複製及 overlap 約束。
- Python 驗證包含 16 組案例，涵蓋代表性內建鏈、欄位失效、IndexBinding、外部候選及 Remote 區段。其他內建方法驗共用外層。IndexBinding 驗證使用符合現行 Schema 的 fixture，檢查全文／向量能力。
- Remote API fixture 涵蓋批次請求、向量輸出與外部檢索候選。實際 Parser、Tokenizer、模型、索引、權限、服務可用性與跨環境部署仍需整合驗收。

從 repo 根目錄執行，Python 需要 jsonschema 4.x。

```sh
python3 examples/system_config/validate_descriptor_draft.py
python3 examples/user_remote_api/validate.py
```

完整 System Config 序列化依 Q-002 定稿。[歷史草案](../../docs/history/superseded/system_config_d66/README.md)保留 D-66 的原始測資。
