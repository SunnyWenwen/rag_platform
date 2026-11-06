# Component Descriptor 0.1 討論範例

主文件：[25 Descriptor Schema 初版](../../docs/04_component_descriptor.md)；已確認行為：[24](../../docs/04_component_descriptor.md)。**本目錄是待 review 的格式與離線測資，不是正式 SDK／Registry／解析器。**所有 example.* ID、Profile、Feature 與服務引用都是 fixture。

- descriptor.schema.json：B 的共同包裝及有限宣告語法；只靠這份 Schema 不能判定完整語意合法。
- catalog.fixture.json：離線共用 Contract 與可信 Profile／欄位規格來源；既有共用資料 Schema 未修改。
- Ingestion 每個案例都有 descriptor、config、input、output、expected_input.schema、expected_output.schema 六份檔案。expected_* 是人工明列的**預期解析結果**，不是 Engine 自動產生的成果。
- Inference 使用三份 Descriptor 及一份串接 [inference.fixture.json](inference.fixture.json)，包含設定、原始 Query、模擬模型結果、IndexBinding、取回欄位保證與模擬命中。

| 案例 | 用途 |
|---|---|
| parser | JSON 欄位映射、型別選項、條件頁碼，Input 細節供 Ingestion 預檢 |
| chunker | 參數命名、上游 copy／型別、保留原文與 overlap 約束；筆數政策不混入欄位 Schema |
| embedding | fields A→vectors B，多映射、動態來源、名稱唯一與 Profile 維度 |
| embedding_template | 可選衍生文字欄位，再進行向量映射；模板來源與先後依賴仍需共用語意驗證 |
| remote_segment | 同一服務涵蓋 Parsing～Embedding，只宣告公開邊界，無使用者參數／空表單 |
| [query_transformation](query_transformation.descriptor.json) | LLM 選項、改寫數量與原始問題保留；Provider 私有格式和公開 `QueryContext[]` 分開 |
| [retrieval](retrieval.descriptor.json) | 索引能力、ES Hybrid／Local 分路、每路 Top K、已宣告的取回欄位 |
| [rerank](rerank.descriptor.json) | 從巢狀 Chunk 選文字欄位、融合後 Query 卡控、新 score 與 Top N |

安裝 jsonschema 4.x 後，從 repo 根目錄執行：

```bash
python examples/component_descriptor/validate_examples.py
python examples/component_descriptor/validate_inference_examples.py
```

Inference 驗證器以離線程式解析本例使用的邊界綁定、欄位繼承與選項來源，使用既有參考函式驗證 RRF 與 Rerank。詳見[手冊的 Inference 對照](../../docs/04_component_descriptor.md#inference-descriptor-walkthrough)。兩支驗證器都不載入 Component、不存取模型／DB／Remote／K8s，也不是完整 Descriptor 編譯器、Registry 或 UI Renderer。
