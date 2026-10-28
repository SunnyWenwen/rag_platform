# RAG Engine — Method 開發指南

> 2026-10-28 · 開發流程與 SDK 介面草案
>
> 讀者：Module Developer。目標是在公開契約下開發、測試及交付 Method，讓 Engine 與 RAG Builder 使用。**目前 repository 只有規格與 UI Prototype，尚無可安裝的正式 SDK、Engine、範本套件或測試 Runner；本文 Python API 與套件名稱均為示意，不能當作已可執行的教學。**

## 1. 文件責任與目前可開始的工作

| 要確認的事情 | 單一主責位置 |
|---|---|
| Module／Method、SDK 與角色名稱 | [03 名詞與責任](../03_architecture_proposal.md#developer-terms) |
| Engine 如何載入、執行與驗證 Method | [04 §1.1／§2.3～2.4／§7](04_module_methods_io_contracts.md) |
| ParsedDocument／Chunk、Inference 物件與 Config | [05 共用資料與 Config](05_data_contracts_search_design.md)；Inference Schema／示例由 05 導引 |
| 交付階段、未決項與驗收 | [08](08_implementation_plan.md#method-development-plan) |
| Builder 對應互動待辦 | [10 UIB-010](10_ui_adjustment_backlog.md#uib-010-method-catalog) |
| 開發者如何使用以上規格完成一個 Method | 本文件 |

先選一個既有 Module 與具體需求，描述預期輸入／輸出、設定、必要能力及測試案例；可開始起草方法與套件結構。正式公開 SDK、可執行範本及相容測試需等相關契約核定。尤其 ParsedDocument 實際 Schema 已明確延後討論，見 [待決子題](08_implementation_plan.md#parsed-document-schema-pending)；本指南不另定 structure 模型。

## 2. 開發模式與 repo 分工

建議使用本機 IDE、SDK 與 Method 範本，透過 Git／CI 交付。平台 repo 可同時管理 SDK、Engine 及內建方法；團隊的 Method package 可放獨立 repo。這是可採用的起步方式，實際目錄、套件名稱及發布工具仍待 Q-001／Q-022 核定。

| 程式所在位置 | 內容 | 誰維護 |
|---|---|---|
| 平台 repo 的 SDK package | I/O 型別、Module 介面、Config／RunContext、契約測試工具 | Platform／Engine Developer |
| 平台 repo 的 Engine package | Registry、組裝、執行、資源管理及內建方法整合 | Platform／Engine Developer |
| 團隊獨立 Method repo | 方法實作、第三方依賴、宣告、範例與測試 | Module Developer |

一個 Method repo 可以提供多個方法，例如特殊 Parser 與配套 Chunker，或一組 Graph Indexing／Retrieval。SDK 是發行套件的依賴，不需將 SDK 原始碼複製到每個 Method repo；完整整合測試另安裝 Engine。新增標準介面下的方法應不需要修改 Engine 核心。

建議範本包含：

| 相對路徑示意 | 用途 |
|---|---|
| `pyproject.toml` | 套件名稱／版本、相依套件與 entry point 宣告 |
| `src/team_a_rag_methods/chunking.py` | Method 與設定實作 |
| `tests/` | 契約、語意、例外及 Engine 整合測試 |
| `examples/` | 小型輸入、預期結果、有效 Config 與服務需求 |
| `README.md` | 用途、限制、支援版本、執行方式與維護者 |

首期不因開放開發而要求另建 Web IDE 或開發者入口網站。發布權限不等於可以讀取所有 Workspace 資料；使用平台測試服務仍依各環境授權。

## 3. 識別、版本與相依能力

| 概念 | 示意 | 用途 |
|---|---|---|
| module_type | `chunking` | 決定套用哪個 Module 介面與 I/O 契約 |
| method_id | `team_a.chunking.custom` | Config／Registry 查找方法，不是 Python import path |
| Python class | `TeamChunker` | 實作符號；不同 package 可有同名 class |
| implementation_version | `1.0.0` | 該 Method 實作版本 |
| distribution package | `team-a-rag-methods` | 安裝及發布單位，可以含多個 Method |
| import package | `team_a_rag_methods` | Python 程式 import 時使用的名稱 |
| Contract／SDK／Engine 相容範圍 | 由已核定版本填入 | 決定型別、接口與執行環境能否配合 |

method_id 的名稱空間由平台管理；同一有效 Registry 不接受相同 method_id＋實作版本的不同實作。調整 max_tokens 等使用參數不需要建立新 method_id；修改實作需可追溯的新發布版本。Package 版本與 Method 版本可以不同，但不能在不更新 package 的情況下替換其發布內容。

除型別外，方法應宣告所需與提供能力：例如 Chunker 需要哪個結構／Tokenizer、Retriever 需要哪種 Index artifact／版本。Schema 形狀相容不等於語意或索引相容，驗證規則見 04 §7。宣告精確欄位及版本遷移由 Q-002／Q-015／Q-022 核定。

## 4. Python Method 介面示意

以下只展示開發責任，**類別、import 路徑、建構方式與 async 簽名尚未實作或凍結**。範例刻意保留待實作主體，不提供假切分演算法，也不重新定義 ParsedDocument／Chunk。

```python
from pydantic import BaseModel, Field

# 以下 rag_engine_sdk 路徑與型別為規劃中的公開介面。
from rag_engine_sdk import (
    ChunkingInput,
    ChunkingMethod,
    ChunkingOutput,
    ModuleResult,
    RunContext,
)


class TeamChunkerConfig(BaseModel):
    max_tokens: int = Field(default=500, ge=1)


class TeamChunker(ChunkingMethod):
    method_id = "team_a.chunking.custom"
    implementation_version = "1.0.0"
    config_type = TeamChunkerConfig

    async def run(
        self,
        data: ChunkingInput,
        context: RunContext,
    ) -> ModuleResult[ChunkingOutput]:
        # Engine 先驗證 Config／Input，再注入本次必要資源。
        # 實作切分、來源對照與合法 metadata 繼承後，
        # 回傳公開 ChunkingOutput，由 Engine 再驗證輸出語意。
        raise NotImplementedError("待 Chunking 契約核定後實作")
```

`ModuleResult` 的邏輯用法沿用 04：業務輸出位於 data，metrics／errors 不混進下游業務物件。Module-specific Input／Output 包裝與實際方法簽名由 Q-002 決定。完整方法宣告另需 Config Schema、相依能力、相容版本與維護資訊，範例 class 不代表宣告已齊全。

Method 不自己重建 Engine 的重試、排程與授權流程。必要 Client／Tokenizer 等經受控資源介面取得，初始化與清理配合 Engine；禁止在輸入文字、Config 或自訂輸出中夾帶可執行指令交給 Engine 動態執行。Schema／RunContext 不等於程序隔離，核可與隔離邊界見 04 §7.4。

## 5. 安裝、import 與 Registry

獨立 repo 要先成為可安裝的 Python package。以下是未來已有合格範本與 SDK 時的本機開發指令示意：

```sh
python -m pip install -e ../team-a-rag-methods
```

安裝與註冊是兩件事。初期可在受控 Engine 啟動程式中明確 import：

```python
# 規劃示意：registry.register 的正式簽名尚未核定。
from team_a_rag_methods.chunking import TeamChunker

registry.register(TeamChunker)
```

後續可用 entry points 宣告安裝套件所提供的方法，以下 group／name 是候選值，不是既有正式規格：

```toml
[project.entry-points."rag_engine.methods"]
team_a_custom_chunker = "team_a_rag_methods.chunking:TeamChunker"
```

這只是 `pyproject.toml` 的一段，不是完整可發布專案。Engine 先核對核可的 distribution／版本，再載入指定 entry point，取得類別與宣告、註冊至 Registry。不能因套件已安裝或符合 group 就全部執行；不讓使用者在 Config 填任意 Python 路徑。

Python Packaging User Guide 說明以套件 metadata／entry points 發現及載入 plugin 的方式：[Creating and discovering plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)（查核 2026-10-28）。這支持候選載入機制，並不替本專案決定核可政策、權限或 group 名稱。

使用者的 Config 選擇 method_id、版本引用及參數；Engine 解析成已安裝實作。Config 的正式巢狀結構與版本鎖定檔格式尚待 Q-002，因此這裡不新增另一份看似正式的完整 Config YAML。

## 6. 測試與審查

開發者先跑單方法測試，再以相容的 Engine 做整合；平台的 DEV 試跑提供補充證據，不能取代可在獨立環境執行的測試。

| 層級 | 驗證內容 | 例子 |
|---|---|---|
| Config／I/O 契約 | 型別、必填、能力宣告與錯誤定位 | 缺必要欄位、未知欄位、Parser 結構不符 |
| 模組語意 | 對應 Module 的來源／ID／分數等限制 | Chunk 可對回文件；Rerank 不捏造候選；向量維度正確 |
| 方法邏輯 | 固定小型資料與人工可檢查的預期 | Token 邊界、空輸入、Unicode、Filter 與排序 |
| 資源與失敗 | 依 Engine 政策處理中斷、逾時與釋放 | API 拒絕／Timeout；初始化失敗後不殘留連線 |
| Engine 整合 | 用公開介面接入相鄰模組並跑通 Config | 外部 Parser→外部 Chunker；成對 Indexing→Retrieval |
| 發布與相容 | 乾淨環境安裝、Registry 衝突、版本與 artifact 檢查 | 缺套件／錯版要失敗，不能改用內建方法蒙混通過 |

固定替身用來驗證邊界與錯誤，真實模型／DB／搜尋另留整合證據；Mock 通過不代表方法品質合格。推薦先用 repo 外的一個 Chunking Method 證明 SDK 邊界，再擴充 Parser 與成對 Indexing／Retrieval。確切工具／CLI 指令需 SDK 實作後補上。

### 6.1 每個 Method 的七項交付清單（2026-10-28 補齊）

以下是開發者的交付檢查表；要求以 04 §7.2 為準，不另定第二套契約。

| 配套 | 開發者應交付的材料 |
|---|---|
| I/O Contract | 引用平台 Input／Output 型別與契約版本，列明遵守的語意及相容測試；不自行重新定義相同 Module 的必要外層結構 |
| Config Schema | 參數型別、預設值、必填／條件必填、限制與說明，以及合法／非法設定範例 |
| 能力與相依宣告 | 所需結構、索引能力、模型／Tokenizer、配套 Method 與相容版本；說明方法產出的能力及相關驗證 |
| 執行介面 | 初始化、執行、關閉／取消行為，Batch／Async／Streaming 支援狀態及對應測試；未支援者明示 |
| 資源需求 | API／DB 與 Secret 邏輯引用、暫存／持久化儲存、CPU／Memory 最低／建議需求及測試條件；DEV 測試服務需求、平台可用性與自行提供服務時的設定說明 |
| 版本與變更影響 | SDK／Engine／Contract 相容範圍；實作升級與各有效參數變更時，重新 Parsing／Chunking／Embedding／Indexing 或只重測 Inference 的判定條件、連帶影響及驗證案例 |
| 驗收材料 | 範例 Config、輸入／預期輸出、固定測資、契約／語意／整合測試、錯誤案例、執行方式、限制及維護者 |

交付內容不等於每項都要出現在 Builder 表單。演算法參數由 Config Schema 描述；資源需求另作部署與服務綁定的依據。沒有量測的 CPU／Memory 數值要明示估計或待測，平台沒有提供的 DEV 服務要列為缺項。需要重處理時，交付說明應指出必要來源／中間資料，不能假設所有 System 都保存了它們。

七項內容都需可供審閱；機器可讀的 Method 宣告格式、CLI 與測試 Runner 仍待 SDK 規格核定及實作。這份清單不把當前文件草案標為已通過正式契約驗收。

## 7. 從開發到 Builder 與部署

建議交付流程：

1. **開發者準備**：實作與宣告、固定測資、用途／限制、相容矩陣、外部服務需求及變更影響。
2. **PR／CI 審查**：測試契約、模組語意、依賴與 Engine 整合，確認可發布內容及維護責任。
3. **發布套件與 Image**：產生可追溯的固定套件，納入支援該組方法的 Runtime Image；私有套件倉庫／CI 產品待選。
4. **提供目錄資訊**：Builder 與 AI 助手取得目標 Engine／Runtime 支援且核可的 method_id、設定與能力，供使用者選用。
5. **DEV 驗證**：以該版本建立測試 System，依正常 Ingestion／Inference／Evaluation 流程驗證；新增目錄項目不代表已有執行能力。
6. **FTEST／ENT 交付**：YAML 引用包含所需方法的 Runtime Image，保持相同邏輯 Config 與方法解析版本，補齊環境服務／Secret。使用單位自行部署。

發布新版不自動升級既有 System。缺少舊版套件／Image 時須明示無法重現，不靜默換最新版。Method 更新是否須重建索引由實際輸入／輸出及 artifact 相容性決定，不能只看版本字串。Rollback 是否可沿用原索引同樣需要相容檢查。

不承諾每個 Method 都能自動生成任意複雜 UI：基本欄位可由 Schema 呈現，能力相依、條件卡控與特殊輸入需平台支援。待辦統一記在 10；此流程不新增瀏覽器程式上傳入口，也不把 Runtime 安裝套件變成一般使用者操作。

## 8. 待決項與開始時機

| 待決事項 | 何時需定案 | 目前可先做 |
|---|---|---|
| 共用 I/O、ParsedDocument 結構、Config／錯誤與 SDK 公開介面 | M0 正式契約凍結前；Q-002，關聯 Q-004／Q-005 | 整理使用案例、方法需求、Schema 候選與測試資料 |
| Python／SDK／Engine 版本、repo 目錄、entry point／Factory 形式 | M0～M1 建立可安裝範本前；Q-001／Q-002／Q-022 | 起草範本；以顯式註冊驗證最小方案 |
| 發布審核權限、套件倉庫與可信程式範圍；若開放不受信任程式則需隔離規格 | 外部套件進共享 DEV Runtime 前；Q-022 | 採核可內部套件＋Image 的設計草案，不交付任意程式上傳 |
| 實作／套件版本記錄、既有 System 升級／索引相容與部署鎖定 | 更新既有資料或正式交付前；Q-015／Q-021／Q-022 | 設計相容檢查與失敗案例，不自動升級 |

這些事項不阻擋本輪文件整理；規格定案與工具實作後，再將介面示意換成經測試、可直接執行的開發教學。完整決策狀態只維護於 08，不因本指南提供建議就自動關閉 Q-ID。
