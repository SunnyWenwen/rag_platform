# Component Descriptor 0.1 討論範例

主文件：[25 Descriptor Schema 初版](../../docs/04_component_descriptor.md)；已確認行為：[24](../../docs/04_component_descriptor.md)。**本目錄是待 review 的格式與離線測資，不是正式 SDK／Registry／解析器。**所有 example.* ID、Profile、Feature 與服務引用都是 fixture。

- descriptor.schema.json：B 的共同包裝及有限宣告語法；只靠這份 Schema 不能判定完整語意合法。
- catalog.fixture.json：離線共用 Contract 與可信 Profile 資訊；既有共用資料 Schema 未修改。
- 每個案例都有 descriptor、config、input、output、expected_input.schema、expected_output.schema 六份檔案。
- expected_* 是依宣告人工明列的**預期解析結果**，不是新 Engine 自動產生的成果；測試只驗結構／部分語意與範例資料，不證明細化解析器或 UI 已完成。

| 案例 | 用途 |
|---|---|
| parser | JSON 欄位映射、型別選項、條件頁碼，Input 細節供 Ingestion 預檢 |
| chunker | 參數命名、上游 copy／型別、保留原文與 overlap 約束；筆數政策不混入欄位 Schema |
| embedding | fields A→vectors B，多映射、動態來源、名稱唯一與 Profile 維度 |
| embedding_template | 可選衍生文字欄位，再進行向量映射；模板來源與先後依賴仍需共用語意驗證 |
| remote_segment | 同一服務涵蓋 Parsing～Embedding，只宣告公開邊界，無使用者參數／空表單 |

安裝 jsonschema 4.x 後，從 repo 根目錄執行：

```bash
python examples/component_descriptor/validate_examples.py
```

驗證器不載入 Component、不執行文字模板／Tokenizer／Embedding、不存取模型／DB／Remote／K8s；也沒有自動渲染 UI 或編譯六類細化規則。其餘正式語意與待決項目以 25 的 DS 清單為準。
