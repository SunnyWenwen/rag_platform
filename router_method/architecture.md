# Builder、Route Service 與 Runtime

Builder 的 Python 程序建置並提供 React 前端和管理 API。Provider 版 System 由獨立 Route Service 呼叫現有的 Retrieval Provider，可透過匯出的 YAML 在沒有 Builder 的環境啟動。

```mermaid
flowchart TD
    B["React Builder 與 Python 管理 API"]
    R["獨立 Route Service"]
    P["既有 Provider Service"]
    E["Runtime 與索引管理"]
    B -->|"Provider 路徑：註冊設定及同源轉發"| R
    R -->|"Init、Ingestion、Inference"| P
    B -.->|"後續整合 Runtime 路徑"| E
```

Provider 路徑先滿足快速接入既有服務的需求。Runtime 路徑與它平行，日後再接回原有的索引重建與 Runtime 生命週期操作。這次的執行介面是 Router MVP 的 Provider 路徑。

## Provider 上架視角

```mermaid
flowchart TD
    P["Provider 開啟 Provider page"] --> D["填寫 System 名稱與三支 API"]
    D --> X["填寫 Ingestion / Inference 說明與範例"]
    X --> S["貼上 Config Schema 並預覽表單"]
    S --> V{"Builder 驗證 Schema 與上架資料"}
    V -->|修正| S
    V -->|通過| C["上架至 Provider 目錄"]
    C --> U["User 可選用已上架服務"]
```

Provider 預覽與 User 建立表單使用相同欄位渲染。Provider 提供三支固定 API，並透過各業務 API 的說明與範例定義各自的操作。

## User 建立與送出請求

```mermaid
flowchart TD
    U["User 選 Provider 並填寫設定"] --> I["Builder 註冊至 Route Service，Router 呼叫 Provider Init"]
    I --> D{"Provider 回報就緒"}
    D -->|未就緒| E["Builder 顯示發布失敗"]
    D -->|就緒| S["Builder 啟用 System"]
    S --> T["User 選 Ingestion 或 Inference"]
    T --> F["顯示說明並填入 Provider Sample"]
    F --> Q["User 編輯 Payload 並送出"]
    Q --> R["Route Service 補上 System ID 與已發布參數"]
    R --> P["依操作轉發到對應 Provider URL"]
    P --> A["原樣回傳 Provider 結果給 User"]
```

Builder 發起註冊，Route Service 呼叫 Init，Provider 執行資源初始化。瀏覽器透過 Builder 的同源入口送出業務請求，部署後的呼叫端也可直連 Router。Route Service 保留呼叫端 Auth，Provider 判斷 Payload 的操作並管理資料。
