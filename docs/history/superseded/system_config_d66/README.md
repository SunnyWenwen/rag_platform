# D-66 System Config 歷史草案與離線驗證

歸檔日期：2026-11-05。來源 commit：[e89d5dd]已發布的檔案（下方連結固定於原版）。來源目錄：examples/system_config。

D-67 已取消獨立頂層 document_schema，改由 Component 宣告＋Config 推導 I/O 細節。本目錄保留舊 Schema、五案例、Fixture、環境範例與驗證器作查驗；**不是現行 System Config／Descriptor 格式**。除本 README 的說明／連結／執行路徑外，其餘來源檔內容原樣保留。

現行結論：[23 System Config 討論稿](../../../23_system_config_schema_draft.md)、[24 B：I/O 資料規格](../../../24_component_io_schema_refinement.md)。本目錄測試通過僅代表 D-66 舊候選，不表示 D-67 的推導／UI／Runtime 功能已實作。

[e89d5dd]: https://github.com/SunnyWenwen/rag_platform/tree/e89d5ddcdd72b79e3cde651ab0411c883919467c/examples/system_config

---

# System Config 討論案例

主文件：[23 System Config Schema 初版](https://github.com/SunnyWenwen/rag_platform/blob/e89d5ddcdd72b79e3cde651ab0411c883919467c/docs/23_system_config_schema_draft.md)。本資料夾是離線草案／驗證材料，不是可啟動 Engine 的設定檔或正式 Descriptor／Manifest Meta-schema；所有 example.* 元件／Profile 及服務地址均為 fixture。

| 檔案 | 用途 |
|---|---|
| system_config.schema.json | D 的共同骨架，參數留給所選元件驗證；沒有覆蓋完整能力推導 |
| catalog.fixture.json | 離線 Component config_schema／涵蓋範圍／Profile／格式測資；不是已安裝清單 |
| local_memory.json | 內建路徑的概念配置，全文＋向量與平台 RRF |
| remote_parser.json | 只換成 Remote Parser |
| remote_segment.json | Remote Parsing～Embedding，排除重疊的本地 slot |
| advanced_fields.json | 多任務／欄位、模板、原文 Chunk、多 Query／Rerank／Top 3 |
| es_hybrid.json | Elasticsearch 內部 Sum Score 與平台融合分開 |
| environment.example.json | E 的連線／Secret 引用及 Runtime 限制對照，不是已定稿 E Schema／部署檔 |
| validate_examples.py | 結構、fixture 參數與有限跨模組檢查，五個正例／19 個反例 |

案例保留兩層融合的預設意圖；單 Query／ES 單一路的無效融合需由未來 Engine 編譯器略過。它們尚非已正規化 Effective Config，正規化／Profile 鎖／最終鍵名仍待 23 的 SC 決策。共用資料 Schema 在 schemas/ 不受這份骨架取代。

安裝開發驗證依賴 jsonschema>=4.18,<5 後，從 repo 根目錄執行：

```bash
python docs/history/superseded/system_config_d66/validate_examples.py
```

驗證不呼叫模型、ES／MongoDB、Remote Service、Kubernetes，也不證明全部新 Component 或 Sum Score／Filter 轉換都可用。正式採用需有真實 Descriptor／Manifest、Profile 定義、Engine 與環境綁定驗收。
