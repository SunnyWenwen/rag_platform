# Provider 與 User 流程

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
    U["User 選 Provider 並填寫設定"] --> I["Builder 送完整設定到 Provider Init URL"]
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

Builder 發起 Init，Provider 執行資源初始化。業務呼叫使用固定的 System Ingestion／Inference 路徑，Route Service 保留呼叫端 Auth，Provider 判斷 Payload 的操作並管理資料。
