# 16 — Parser 開發模式：Local Component 與 Remote API

> 2026-11-05 D-58：公開 Runtime Ingestion body 統一為 IngestionDocument[]；本篇 Remote Parser operation 的 HTTP body 仍是一份 IngestionDocument，由 Runtime／Adapter 逐筆呼叫，範例程式不改成批次 API。API item 與 Parser 共用 Schema，文件管理另見 [21](21_runtime_ingestion_inference_api_inventory.md)。

> 2026-11-02 D-51：本篇維持無參數、單 Parser 的可執行教學；產品端由 Developer 提供 Manifest 註冊服務，Builder User 不手填 API。Adapter 的 endpoint 由部署綁定注入。連續多 Module、Image／External 及固定資料責任見 [18](18_remote_service_pipeline_integration.md)，不因新方向改寫本例 HTTP body。

2026-11-02｜可執行的教學草案，非已發布 SDK。搭配 [04 三種交付模式](../diagrams/04_component_delivery_modes.md)／[比較圖](../diagrams/04_component_delivery_modes.png) 介紹。

## 1. 先分清楚「開發」與「交付」

| 開發方式 | Developer 做什麼 | 對應 04 圖 |
|---|---|---|
| Local Component | 依 SDK 的 Parser ABC 實作，提交原始碼並納入 Library／Runtime Image | 01 Local Component |
| Remote API | 自行實作符合契約的 Parser API，不要求提交原始碼或依賴 ABC；Runtime 內由 Retrieval Builder 提供的 Remote API Adapter 呼叫 | 02 Image Deployment、03 External Endpoint |

Remote 的兩種交付方式使用相同 API：Image 模式附部署描述，由使用單位部署；Endpoint 模式由 Developer 自行部署，使用單位只需綁定連線。**開發模式有兩種，交付模式有三種。**

本例共同邏輯：輸入一筆 JSON，content.text 是包含兩頁內容的單一字串；Parser 辨識頁面後輸出一份 ParsedDocument、其中兩個 Unit。不做 Token 長度切分、不產生向量；Chunker 後續再逐 Unit 切分。

## 2. 共用 Pydantic Contract：先給一版具體型別

形狀來源仍是 [IngestionDocument JSON Schema](../schemas/ingestion_document.schema.json)／[13 說明](13_ingestion_parser_input_contract.md)，以及 [ParsedDocument 0.2 JSON Schema](../schemas/parsed_document.schema.json)／[14 說明](14_parsed_document_contract.md)。這裡不修改共同 Schema，提供對應的 [contracts.py](../examples/component_development/contracts.py) 供示範使用。

以下為**欄位視圖，省略完整驗證器與設定**；可執行版本以 contracts.py 為準：

```python
from pydantic import BaseModel, Field, JsonValue

class IngestionDocument(BaseModel):
    document_id: str
    source_revision: str | None = None
    content: str | dict[str, JsonValue] | None = None
    base64: str | None = None
    uri: str | None = None
    media_type: str | None = None
    schema_id: str | None = None
    parsing_profile: str | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

class ParsedDocument(BaseModel):
    document_id: str
    source_revision: str
    units: list[dict[str, JsonValue]]
    metadata: dict[str, JsonValue]
```

完整版本的規則：

- IngestionDocument 禁止未知根欄位；content／base64／uri **恰好一個**，不能同時提供。
- 可選根欄位可以省略，**明確傳 null 不接受**。Python 的 None 只表示未設定；to_payload() 保留省略狀態，不送出未使用的 None。metadata 省略時補 {}，其內的業務 JSON 值可以為 null。
- document_id／source_revision 等識別字串不可為空；content 字串／object 不可為空。支援何種 URI 協定、實際 Base64 解碼／媒體格式另由相容 Parser／resolver 驗證。
- ParsedDocument 必須有四鍵：document_id、source_revision、units、metadata；禁止未知根欄位。units 為非空有序列表，每筆為非空 dict，直接放欄位，不包 fields、不強制 unit_id、不另設 structure。提供 text 時必須為字串。
- 共用 ParsedDocument 不強制一定有 text，以保留進階欄位選擇；本示範 Parser 的能力另外要求非空白 text。
- 形狀驗證與語意驗證分開。本例另外檢查只輸出一份文件、文件 ID／revision 與 metadata 繼承；一般 Parser 仍可輸出多文件，但需另有明確 ID 派生政策。

### 同一組 Input／Output：一個多頁字串 → 多個 Unit

Parser Input 仍是 IngestionDocument；text 是 **一個 str**，不是預先切好的 page array。本例用獨立一行的 `=== PAGE N ===` 明確表示頁面邊界，方便示範 Parser 如何辨識頁面。這是本示範 Parser 的文字格式約定，不是平台共用 Schema 的新規定，也不代表所有 PDF 匯出的文字都有這種標記。

完整 [輸入 JSON](../examples/component_development/multi_page_input.json)：

```json
{
  "document_id": "manual-001",
  "source_revision": "v1",
  "content": {
    "text": "=== PAGE 1 ===\n# 設備保養\n## 安全注意事項\n清潔前先斷電，並確認設備已冷卻。\n作業時請配戴防護手套。\n\n=== PAGE 2 ===\n# 設備保養\n## 清潔週期\n每月清潔散熱孔。\n若環境粉塵較多，請提高檢查頻率。",
    "title": "設備保養手冊"
  },
  "metadata": {
    "department": "manufacturing",
    "filename": "maintenance-manual.pdf"
  }
}
```

為方便閱讀，content.text 展開如下：

```text
=== PAGE 1 ===
# 設備保養
## 安全注意事項
清潔前先斷電，並確認設備已冷卻。
作業時請配戴防護手套。

=== PAGE 2 ===
# 設備保養
## 清潔週期
每月清潔散熱孔。
若環境粉塵較多，請提高檢查頻率。
```

輸出仍為 **list[ParsedDocument]**；一份文件內有兩個 Unit，並不是拆成兩份文件。完整 [輸出 JSON](../examples/component_development/multi_page_output.json)：

```json
[
  {
    "document_id": "manual-001",
    "source_revision": "v1",
    "units": [
      {
        "text": "# 設備保養\n## 安全注意事項\n清潔前先斷電，並確認設備已冷卻。\n作業時請配戴防護手套。",
        "title": "設備保養手冊",
        "page": 1
      },
      {
        "text": "# 設備保養\n## 清潔週期\n每月清潔散熱孔。\n若環境粉塵較多，請提高檢查頻率。",
        "title": "設備保養手冊",
        "page": 2
      }
    ],
    "metadata": {
      "department": "manufacturing",
      "filename": "maintenance-manual.pdf"
    }
  }
]
```

本例處理規則：

1. Parser 辨識頁面標記，取出頁碼與頁面文字，移除標記及頁面文字頭尾空白，頁內 Markdown 標題保留。
2. 每頁產生一個 Unit；title 等其他 content 欄位複製到各 Unit，page 由標記推導。document_id、source_revision 及文件 metadata 保留。
3. 頁碼必須為正整數、唯一且遞增，允許有間隔；有效標記前有未歸屬文字、空白頁，或同時提供 content.page，都明確報錯，不自行猜測或覆寫。本示範不處理任意／損壞的分頁標記。
4. 沒有分頁標記時沿用原行為：文字／單筆 JSON 產生一個 Unit。實際 PDF、PPT 或 OCR 的頁面辨識由相應 Parser 實作。
5. Chunker 不再辨識頁面標記；它只在每個 Unit 內以所選文字策略切分，不跨 Unit 合併。page、title 要供下游使用時，仍依 Chunking 的 copy 設定帶入 Chunk.fields。

本例要求明確提供 source_revision，省略時回明確錯誤，不自行假設 v1。共同 Input 仍允許省略；正式自動產生政策依 Q-007。本例只支援直接 content 的文字／單筆 JSON，不支援 URI、Base64、PDF 或已解析 content.units；那些必須選用有宣告能力的 Parser。這不是移除共同輸入的來源選項。

## 3. Local Developer：實作 Parser ABC

D-62 已確認正式執行方向為共用 Flow，Component 每次接收 input／本次 config／Context，見 [04 §2.2.1](04_module_components_io_contracts.md#shared-flow-execution)。本文件及可執行教學檔暫保留無演算法參數的 run(data, context) 介面，用來驗證 Parser 邏輯與 HTTP I/O，不是新 SDK 的最終簽名；後續 SDK 整合時再同步更新。Remote 服務不因本地傳入 config 就自動新增 HTTP 欄位。

[local_component.py](../examples/component_development/local_component.py) 定義下面的教學介面：

```python
class ParserComponent(ABC):
    component_id: str
    config_type: type[BaseModel] = ParserConfig

    @classmethod
    def config_schema(cls) -> dict:
        return cls.config_type.model_json_schema()

    @abstractmethod
    async def run(
        self, data: IngestionDocument, context: RunContext
    ) -> ModuleResult[list[ParsedDocument]]:
        ...

    async def aclose(self) -> None:
        pass
```

Developer 的實作只處理解析邏輯；相同 ABC 可讓 Engine 呼叫內建或自訂 Component：

```python
class StructuredJsonParser(ParserComponent):
    component_id = "example.parsing.structured_json"

    async def run(self, data, context):
        documents = parse_structured_json(data)
        validate_structured_json_output(data, documents)
        return ModuleResult(data=documents)
```

parse_structured_json() 辨識 text 中的示範分頁標記，產生多個 Unit；未分頁則保留單一 Unit。此處按頁辨識內容單位，不是依 Token 長度切 Chunk，且不跨頁合併。演算法示意在 [parser_logic.py](../examples/component_development/parser_logic.py)，與共用型別分開。

Engine 取 ModuleResult.data 傳下游；ModuleResult 是本地 SDK 包裝，不是 ParsedDocument 的根欄位。示範 RunContext 只有 request_id；正式受控資源、metrics／errors、初始化及清理介面仍依 [04](04_module_components_io_contracts.md)／[11](11_component_developer_guide.md) 凍結，不把本教學 dataclass 當完整 SDK。

## 4. Remote Developer：實作 API，不需要 Component ABC

Remote Developer 可只取 contracts.py，或使用等價的 JSON Schema 自行實作。FastAPI 是**選用範本**，不強制框架或語言。

[remote_service.py](../examples/component_development/remote_service.py)：

```python
from fastapi import FastAPI, HTTPException
from contracts import IngestionDocument, ParsedDocument
from parser_logic import parse_structured_json

app = FastAPI()

@app.post("/parse", response_model=list[ParsedDocument])
async def parse(data: IngestionDocument) -> list[ParsedDocument]:
    try:
        return parse_structured_json(data)  # 換成 Developer 的私有解析邏輯
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

此示範 HTTP 約定：POST /parse，JSON body 直接是 IngestionDocument，200 body 直接是 list[ParsedDocument]；不包 ModuleResult／data，也不要求傳 RunContext。FastAPI 的輸入驗證錯誤為 422，本例不支援的來源／未提供版本為 400；**狀態碼與錯誤 Envelope 尚非全平台正式協定**。

### Retrieval Builder 提供的 Remote API Adapter

[remote_adapter.py](../examples/component_development/remote_adapter.py) 仍實作本地 Parser ABC，讓 Engine 使用相同呼叫方式：

```python
OUTPUT = TypeAdapter(list[ParsedDocument])

class RemoteApiParser(ParserComponent):
    component_id = "example.parsing.remote_api"

    def __init__(self, client, endpoint):
        self.client = client
        self.endpoint = endpoint

    async def run(self, data, context):
        response = await self.client.post(
            self.endpoint,
            json=data.to_payload(),
            headers={"X-Request-ID": context.request_id},
        )
        response.raise_for_status()
        documents = OUTPUT.validate_json(response.content)
        validate_structured_json_output(data, documents)
        return ModuleResult(data=documents)
```

API Input／Output 不轉成另一套文件物件；HTTP 序列化／還原由 Adapter 處理。本例只轉送 request_id，不轉送整個可信 Context。Client、endpoint、認證與 timeout 由部署綁定注入；Client 由建立者關閉。正式版還需錯誤映射、資源限制及核定的重試／冪等政策。

## 5. Developer 最少要拿到什麼？

| 套件／材料 | Local Developer | Remote Developer |
|---|---|---|
| Contracts：Pydantic／JSON Schema、語意檢查與正負測資 | 需要 | 必須遵守；可選 Python 套件或等價語言實作 |
| Component SDK：ABC、Config Schema、受控 Context、生命週期 | 需要 | 不需要；不要求其服務依賴完整 Engine |
| FastAPI 服務與部署範本 | 不需要 | 選用；Image／Endpoint 的 API 相同 |
| 完整 Engine | 整合測試使用 | 非遠端服務依賴；需與 Adapter 做相容測試 |

本例沒有演算法參數，所以不新增 Remote request envelope，body 保持原 Input。未來有 per-System 演算法參數時，要另定參數／初始化協定，不能把任意 Config／連線設定塞入文件 metadata、偷偷借用 parsing_profile，或直接把整個 Config／Secret 傳出去。設定描述與 UI hints 仍需由 Developer 提供並登錄；Pydantic I/O 相同，不代表 UI 參數或語意必然相容。

### 5.1 metadata 處理提示與選填追溯（D-52）

上述禁止任意 Config 傳輸，不禁止 Component 明確支援的文件層 metadata 提示。Parser 可保存合法提示，後續 Component 依自身宣告讀取；例如支援 chunking_mode 的 Chunker 可保留整個 Unit，缺省正常切分，不需通用規則引擎。_rag 追溯由輸出 Component 選擇是否提供；本 Parser 教學與 HTTP body 不因此改寫，見 [15 §4.1](15_chunk_contract.md)。

## 6. 如何重現

以下是獨立教學資料夾，不是正式 SDK 套件。先從 repo 根目錄執行：

```bash
python -m venv .venv-demo
.venv-demo/bin/pip install -r examples/component_development/requirements.txt
.venv-demo/bin/python examples/component_development/test_demo.py
```

要啟動示範 API，可用同一環境執行：

```bash
.venv-demo/bin/uvicorn remote_service:app --app-dir examples/component_development --port 8001
```

測試會以本地 ASGI Transport 跑 FastAPI 與 Remote Adapter，對照 Local 輸出；不呼叫外部模型／服務，也不代表已完成 Image 部署、Secret 管理或正式 Exporter。Shared Schema、Pydantic、HTTP 回應形狀與語意的相容性，都應列為正式 Component 驗收材料。

## 延伸：03 圖全部 Contract 的 Pydantic 草案

本篇的 Parser 教學維持原樣；需要一起檢視 Chunk／IndexBinding／QueryContext／ResultSet 時，見 [17 Pydantic Contract 草案](17_pydantic_contracts_draft.md)。該集合是獨立可執行草案，尚未合併成正式 SDK；IndexBinding 已依 D-55／19 確認輕量交接，正式 SDK／實體索引布局仍需完成。



