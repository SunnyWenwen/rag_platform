# Prototype v0.12 歷史驗證紀錄

> 這是當時的模擬原型／契約驗證結果，不代表現在已交付 Engine／模型／DB／部署。現行狀態與待辦見 [10](../../07_builder_ui.md)。

來源：[原始檔案](https://github.com/SunnyWenwen/rag_platform/blob/a27e9cdba06c5ada210b00e09de629b53fe7bae1/docs/10_ui_adjustment_backlog.md)；歸檔日期：2026-11-05。

回歸測試涵蓋既有設定／DOM、QueryContext 新 JSON、模板／重名、原文 3／4 筆、passthrough、Component 參數／失效版本、Remote 覆蓋／重疊／Export 差異、Save／Cancel／AI Draft。Chromium 153.0.8010.0 已通過 1440×1000 桌面及 390×844 手機互動／水平溢出檢查，無頁面 JavaScript 錯誤；已實際檢視桌面模板、Remote 鎖定及手機畫面。

### 2026-11-03 驗證紀錄

- Pydantic 12 項、Chunk 10 項通過；ParsedDocument 6 個正例／12 個反例通過；五份 Inference JSON 通過新版共用 Schema。RRF 以陣列名次驗算，舊 wrapper 明確拒絕。
- 既有 56 項 Prototype、23 項結果處理、5 項 Schema UI 檢查通過；DOM 回歸及新增 12 組 v0.12 流程通過。
- Chromium 真實互動涵蓋 Create／Edit／取消、CSV 映射、QueryContext 呈現、API 說明、Export、欄位模板、原文 3／4 筆示例、Remote 鎖定／External 固定設定，以及手機版面。Source SVG／MMD／PNG 已同步 QueryContext[]，保留 03 原版型。
- 瀏覽器套件下載曾緩慢，補齊下載後以本地 Chromium 成功驗證；使用 Noto Sans TC 作中文畫面及圖檔輸出。測試可用既有 Playwright Chromium，或設定 CHROMIUM_EXECUTABLE 與選填 CHROMIUM_ARGS_JSON；外部套件未加入產品頁依賴。

以上為契約、瀏覽器配置與模擬操作驗證，沒有呼叫真實模型／DB／Remote API，也沒有建立 Pod 或發布服務。

