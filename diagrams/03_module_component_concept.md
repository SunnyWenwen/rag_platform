# 同一份 Library，以三份 Config 建立三個 Retrieval System

2026-11-02｜目標設計示例，非已交付能力。

![Library＋Config A／B／C](03_module_component_concept.png)

[Mermaid 關係定義](03_module_component_concept.mmd) · [固定版面 SVG](03_module_component_concept.svg)

## 報告說明重點

1. **Library 是可重用程式庫。**同一份 Library 配不同 Config，並綁定必要服務／資料資源，即可組裝不同 System，不需要為 A／B／C 各寫一份 Library。
2. **每個 System 各有 Ingestion 與 Retrieval Service。**圖中展開對應模組實例，例如 Parsing A、Chunking A、Retrieval A；A／B／C 是實例識別，不是強制不同 class。
3. **Config 決定選用的 Component 與參數。**三張 Config 卡只列部分設定；其餘方法於 System 內標示，屬語意示例，不是正式可執行 Config Schema。
4. **System C 可以把 Parsing 委派給外部服務。**Config C 選 Remote API Component；Parsing C 是 Retrieval Builder 提供、在 System 內執行的 Adapter，真正解析邏輯在額外 Parsing Service。其他 C 模組仍依序執行。
5. 外部 Parsing Service 接收 **IngestionDocument**，回傳 **list[ParsedDocument]**。URL／Secret／Image 是部署綁定；Image Deployment／External Endpoint 兩種交付均適用，見 [04 交付模式](04_component_delivery_modes.md)。

| 示例 | Parsing | Chunking | Indexing／Retrieval | Query Transformation | Rerank |
|---|---|---|---|---|---|
| A | Structured JSON | Fixed-size | Elasticsearch | None | None |
| B | Structured JSON | Recursive | Local Search | Multi-query | Rerank API |
| C | Remote API Component | Header-aware | Elasticsearch | Rewrite | Rerank API |

C 的例子假設遠端 Parser 產出相容、保留 Markdown 標題的 Unit.text，才能使用 Header-aware；共同物件形狀不免除格式與語意驗證。Local／Remote Parser 的實際教學程式見 [16](../docs/16_parser_component_development_examples.md)。

## 邊界與連線

- 實線表示組裝或執行順序；虛線表示共用 Library 或索引／資料綁定，並不表示 Query 會重新跑 Ingestion。
- Parsing C 與額外服務的雙向箭頭是 HTTP request／response；不是每一個 Module 都需要變成獨立微服務。
- Ingestion Service／Retrieval Service 是邏輯功能邊界；Runtime 的程序、Pod 與多 System 配置仍由架構／部署政策決定。
- Evaluation 獨立於單次處理主線；Fusion／Top N 由配置的結果處理計畫執行，這裡不新增 Module 或 Generation。
