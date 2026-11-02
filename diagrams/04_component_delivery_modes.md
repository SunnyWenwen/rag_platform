# Retrieval Component 的三種交付模式

2026-11-02 討論方案示意。Remote API 的正式 HTTP Contract、Deployment Descriptor、DEV 部署／Export 整合尚待規格與實作；本圖不是已交付功能清單。

![Retrieval Component 的三種交付模式](04_component_delivery_modes.png)

[可編輯 SVG](04_component_delivery_modes.svg)

| 模式 | Developer 交付物 | 執行位置 | Remote API 部署責任 | Export YAML |
|---|---|---|---|---|
| Local Component | Component 原始碼、設定／契約描述 | Retrieval Runtime 內，與 Library 同程序 | 無額外 Remote API；使用單位部署 Runtime | Runtime＋Config，Component 已包入 Runtime Image |
| Remote API — Image Deployment | API Image、部署描述與契約資訊 | 獨立 API 服務，圖中示意為同一使用單位環境 | 使用單位以匯出 YAML 部署；Developer 交付 Image 版本 | Runtime＋Config，以及 Remote API 的 Deployment／Service／資源／Secret 引用等必要設定 |
| Remote API — External Endpoint | Endpoint、認證方式與契約資訊 | Developer 管理的 API 服務，不要求交付原始碼或 Image | Developer 自行部署與維運 | Runtime＋Config＋API 連線／Secret 引用，不產生遠端服務部署 YAML |

共同規則：

- 三種模式遵守相同 Module I/O Contract。Remote API Adapter 傳送可序列化的業務 Input，驗證回應後還原 Module Output；不傳送整個可信 RunContext。
- Library 依 Config 組裝 System；Remote API 模式仍在 Runtime 內有 Adapter，遠端演算法在另一個服務／程序執行。
- 演算法參數放 Config；部署模式、Image、URL、Secret 與 CPU／Memory 等放 Deployment Settings。Image 模式需要明確部署描述，不能僅靠 Image 名稱推導所有設定。
- API 指的是 Module 的遠端執行端點。Local Component 仍可依自身用途連線 DB／模型服務；圖中「無額外 Remote API」不代表完全沒有外部依賴。
- Image 模式可在 DEV 部署測試 Image；External 模式綁定測試端點。DEV 與 FTEST／ENT 沿用相同 I/O 契約。
- Indexing／Retrieval 等有狀態操作，仍須額外定義索引識別、版本、讀寫關係及冪等／重試政策，不能僅憑 HTTP 形狀宣稱相容。


## 搭配開發範例介紹

先用本圖說明三種交付模式，再讀 [16 Parser 開發範例](../docs/16_parser_component_development_examples.md)：同一組 IngestionDocument／ParsedDocument，對照 Local ABC 實作與 Remote API／Adapter。開發方式分兩種；Image Deployment／External Endpoint 共用 Remote API 開發契約。
