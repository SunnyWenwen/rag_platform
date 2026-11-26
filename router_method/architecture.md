# Provider 模式架構

Python 啟動並提供 React Builder 與管理 API。Builder 管理上架與 System 設定，Provider 以 `system_id` 管理生效設定及資料。Builder 操作頁的業務測試經 Builder 後端呼叫 Provider，應用程式可直接呼叫 Provider。設定式 Runtime 是 Builder 的另一條路徑，可獨立整合既有的索引與生命週期操作。

```mermaid
flowchart TD
    U["User / Provider 操作頁"] --> B["Builder 後端"]
    B -->|"Init 與 UI 測試"| P["Provider Service"]
    C["業務呼叫端"] -->|"Ingestion / Inference"| P
    P --> D["System 設定、索引與資料"]
    B -.->|"設定式 System"| R["Runtime"]
```

## Provider 上架

```mermaid
flowchart TD
    P["準備 Init、Ingestion、Inference"] --> D["填寫名稱、URL、Auth、說明及 Sample"]
    D --> S["貼上 Config Schema 並預覽表單"]
    S --> V{"Builder 驗證範本"}
    V -->|修正| D
    V -->|通過| C["User 可在目錄選用"]
```

範本上架會驗證欄位及 Schema。建立 System 時才會呼叫 Init 驗證實際連線與初始化。

## User 建立與編輯設定

```mermaid
sequenceDiagram
    participant U as User
    participant B as Builder
    participant P as Provider
    U->>B: 建立或編輯 System
    B->>P: Init {system_id, parameters}
    alt 設定已生效
        P-->>B: HTTP 200 或 204
        B-->>U: 顯示已套用設定
    else Provider 回報失敗
        P-->>B: 失敗狀態
        B-->>U: 顯示失敗，保留最近一次確認的設定
    else Builder 未取得結果
        B-->>U: 結果未確認，以相同 ID 和設定重試
    end
```

Edit Config 沿用既有 System ID。Provider 應先驗證並準備資源，完成後才切換生效設定。同一個 ID 和設定重送時應能安全重試。若逾時，Provider 可能已收到並處理該次 Init，Builder 會等成功回應才更新本機紀錄。

## User 測試與應用程式呼叫

```mermaid
sequenceDiagram
    participant U as Builder 操作頁
    participant B as Builder 後端
    participant P as Provider
    participant C as 業務呼叫端
    U->>B: 送出業務 Payload 與 Auth
    B->>P: POST {system_id, payload} 與 Auth
    P-->>U: 經 Builder 回傳 HTTP 狀態碼及 Body
    C->>P: 直連業務 URL，帶相同 JSON 與 Auth
    P-->>C: HTTP 狀態碼及 Body
```

Provider 依 Auth 判斷呼叫者可否操作該 System，再依 ID 讀取 Init 保存的設定。Ingestion Payload 內各種操作的意義與資料生命週期由 Provider 定義。
