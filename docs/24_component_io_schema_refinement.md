# 24 — B：Component I/O 資料規格、Schema 細化與相依驗證

2026-11-05｜D-67：**責任邊界、第一版宣告能力與處理行為已確認；Descriptor／Manifest Meta-schema、規則鍵名及解析 API 尚未定稿或實作。**本文件整理現行結論；討論來源見 [歷史決策](history/decisions/decision_history.md#d-67)。

## 1. 所屬範疇與閱讀入口

本議題主要屬 [20 的 B：Component 定義](20_contract_inventory_responsibility_matrix.md)。[12](12_component_schema_ui_contract.md) 已有 Config Schema、UI hints、option_sources、rules 與失效選擇卡控；本文件補齊先前未完整記錄的「Component 如何依 Config 提供 I/O 資料規格」，以及資料規格如何沿 Pipeline 成為下游設定的依據。

| 群組 | 本議題的責任 |
|---|---|
| A 共用執行契約 | 固定 IngestionDocument、ParsedDocument、Chunk、QueryContext[] 等形狀與語意；Component 不得任意覆寫 |
| **B Component 定義** | 宣告 Config Schema、I/O Contract 引用、資料細節及依 Config 改變的規則、動態選項來源與相依條件 |
| C Remote Manifest | Remote Developer 提供同等宣告，由平台推導／適配成 B；不要求交 Source Code 或手寫兩份描述 |
| D System Config | 保存 Component ID／版本與 User 的參數值；不再要求獨立頂層 document_schema 重複描述 Parser 輸出 |
| E 環境與資源 | 提供服務／Profile 的相容綁定；URL、Secret、Client 與即時資源不混進資料 Schema |

Admin 制定 Descriptor Schema、Schema 支援範圍與規則語意；Developer 依格式交付宣告及實作；User 選 Component 並填 Config。Descriptor 是純 JSON 描述，不是可執行程式。B 的行為同時適用 Local、Remote Image、Remote External；能否動態改欄位與是否交付 Source Code 無關。

## 2. 要區分的三類 Schema

| 類型 | 回答的問題 | 使用者／消費端 |
|---|---|---|
| Descriptor Schema／描述內 Schema 的採用規範 | Developer 應如何描述設定、I/O 與變動規則？ | Admin 定義；Registry 驗證交付內容 |
| Component Config Schema | User 可以設定哪些參數、型別、預設及限制？ | Builder 產生表單；Engine 驗參數 |
| Component I/O Data Schema | 採用目前 Config 後，接受與產出的資料有哪些欄位、型別與限制？ | API／執行資料驗證；下游選項與組裝相容性 |

Config Schema 本身不會自動推出 I/O Data Schema；Developer 必須提供固定資料規格或受支援的變動規則。正式描述的包裝／欄位名稱待定，本文件的文字名稱不是新發布的 JSON 關鍵字。

System Config Schema 的 $defs 只重用共同設定骨架，例如 ComponentSelection、ParserSlot、ChunkTask；新增 Component 不修改這份平台 Schema。Component 自己的 Config／Data Schema 可有自己的 $defs，依 ID／版本分開解析，不把所有 Component 的 Schema 全塞進主 $defs。

## 3. 共用格式固定，內部欄位可以變

| 層次 | 規則 |
|---|---|
| 共用物件與既有語意 | ParsedDocument 四鍵＋平面 units、Chunk 六鍵、QueryContext[] 等沿用 A，不因細化改名／省略必要根鍵 |
| 開放的內容容器 | Unit、Chunk.fields、vectors、metadata 遵守各自共用型別；容器允許動態名稱不等於 UI 已知有哪些欄位 |
| Component 的細節 | 可依 Config 指定欄位名稱、型別、必填、來源與適用條件，但不得放寬 A 的限制 |

例如同一 Embedding Component 可由 Config 產出 vectors.text 或 vectors.summary；向量物件仍須遵守共用格式，Profile／維度等限制須有宣告依據。固定 Schema 也可以允許任意合法 Key；它只是不會自動提供精確候選清單。

本設計稱「Pipeline 的 Schema 推導／細化與相依驗證」：各 Module 各自細化自己的 I/O，並非共用一份不斷累加欄位的 Schema。也不要求每次請求產生新的 Python class 或執行 Parser 才取得描述。

## 4. 第一版純 Descriptor 可表達的規則

「純 Descriptor」指 Developer 以資料宣告規格，不必為每個 Component 另寫 resolve_io_schema 程式；Engine 仍須實作共用解析器。解析只讀已驗證的有效 Config、已宣告的上游 Schema／能力及核可的 Profile 描述；不讀實際文件、Secret、Live Client 或即時遠端狀態。

| 規則 | 設定／宣告例子 | 可推導結果 |
|---|---|---|
| 固定欄位與型別 | Parser 固定提供文字與頁碼 | Unit 的 text:string、page:integer |
| 依參數決定名稱 | output_field 設 body | 輸出 body:string |
| 依映射清單展開欄位 | Embedding 設兩筆映射，輸出名稱 text／summary | vectors.text／vectors.summary；每項沿用已宣告的向量規格 |
| 選擇／複製上游欄位 | 選 title、category，可依支援設定改名 | 沿用來源型別與已知限制；明確 copy 的欄位須可取得 |
| 依布林／固定選項分支 | include_page=true | 加入 page:integer，依宣告決定必填；已知分支可有不同型別／限制 |
| 固定型別的衍生欄位 | 啟用文字模板，輸出名稱 embedding_text | fields.embedding_text:string；真正組合內容仍由 Component 執行 |

上述規則可以組合；第一版不加入任意算式、腳本、自由迴圈或程式下載。來源不存在／型別不明、輸出名稱衝突、不同宣告互相矛盾時報錯，不猜測、不覆蓋欄位。條件與 Config 尚未確定時標示 unresolved，不把未知當成可用。

映射清單展開是平台核定的有限操作，不等同開放任意程式迴圈。條件語法、支援的型別／限制及與 12 rules 的整合仍待 Meta-schema 核定；不把這張行為表當成已完成解析器。

## 5. 第一版的邊界與未知欄位

| 情境 | 第一版純宣告的限制／處理 |
|---|---|
| 讀 Excel／CSV 才知道實際欄名 | 無法在設定階段列出精確欄位；需提供欄位定義，或由 Sample 推測後確認成設定 |
| JSON 直接傳遞任意業務欄位 | 可以宣告開放物件；若需要下游 Picker／精確驗證，由該 Parser 的 Config 接受欄位定義，不新增全域 document_schema |
| LLM 自行發明 Key 或任意輸出型別 | 不保證靜態候選；若改成固定結構與受支援的限制，可宣告該結構並驗證 |
| 任意 Python／複雜演算法計算 Schema | 超出第一版宣告子集；額外的規格解析介面日後另定，不偷偷執行描述中的程式 |
| Remote 依資料庫即時結構改變回傳 | 沒有交付／確認的 Schema 不能當已知；如何取得額外規格另議，不擅自增加 Remote schema endpoint |

上述「不能」指第一版不保證只靠描述取得精確資料規格，不表示所有開放資料都不能通過共用 Schema。未知 Key 可被寬鬆 Schema 接受，但不得因此當成已知 UI 選項。Sample 是建議／確認來源，不以第一筆樣本推定所有 Units 或所有文件都符合。

文件頁數、Units／Chunks 筆數、文字內容改變通常只是資料不同，不是 Schema 改變。Parser 不需要先知道將產生幾頁才能宣告每個 Unit 的欄位型別。

## 6. 沿 Pipeline 推導設定選項

| 元件／設定 | 參考來源 | 規則 |
|---|---|---|
| Chunker 的切分欄位 | Parser 當前輸出的 Unit Schema | 只允許必定可取得且型別／內容能力相容的文字欄位 |
| Chunker 的複製欄位 | 同一 Unit 的欄位 | 只選 Component 支援的型別；沿用來源規格，不自動跨 Unit 找值 |
| Embedding 的來源欄位 | Chunker 當前輸出的 Chunk.fields | 來源必須已產生且符合模型輸入；模板衍生欄位由支援此能力的 Component 宣告 |
| Indexing 的全文／向量／Filter 欄位 | 當前 fields／vectors／metadata 及後端能力 | 只提供已宣告且相容的候選；保存完整 Chunk 不變 |
| Retrieval 的搜尋欄位 | Indexing 的有效配置與支援能力 | 設定階段先檢查計畫；執行時仍須遵守 IndexBinding／索引格式與就緒狀態 |

例如 Parser 宣告 text:string、title:string、page:integer、tags:array[string]。只支援字串切分的 Chunker 可選 text／title；page／tags 仍顯示但停用並說明原因。若該 Chunker 支援複製這些型別，複製欄位可提供四者。Token 上限則依 Chunker 自己的 Config Schema，不因上游多一欄就新增設定功能。

跨 Module 的連動主要改變參數可選值與適用條件；Component Config Schema 仍由同版本 Developer 宣告。上游不會替下游新增未宣告的參數，也不藉改寫 enum 製造每個 System 一份獨立 Component 定義。

Engine 由前往後驗證 Config、解析當前 I/O 資料規格、檢查接線及產生候選。上游設定變動時重新計算受影響的下游；失效選擇保留並報錯，不換第一個選項。錯誤定位及過期回應沿用 12，不因收合／唯讀而略過檢查。UI、AI、Python、API 共用同一 Engine 規則。

多 Parser 必須保留各 profile／分支的輸出宣告；共用 Chunk 任務所需的切分／copy 欄位須在所有會收到的 Units／分支可取得，不能只取候選聯集就宣稱合法。進階多 Chunk 任務各自推導，輸出相加；多結果形狀須標示差異／可用性，不把某任務的欄位誤當每個 Chunk 都有。

Remote 連續區段只在公開邊界交接規格，平台不要求它回報所有內部 Module 的中間物件。區段在 Chunk 邊界提供資料時，下一個 Module 參考該邊界的 Chunk Schema，不捏造不存在的 ParsedDocument。

## 7. 一個可逐步說明的範例

以下是行為範例，不定義 Descriptor 的正式 JSON 語法。

| 步驟 | User 設定／Developer 宣告 | 當前資料規格與下一步 |
|---|---|---|
| Parser | 將 content.body 映射為 Unit.text；保留 title、page，宣告三者必要且型別為 string／string／integer | API 檢查可取得的 body／title／page；輸出每個 Unit 的 text／title／page |
| Chunker | 切 text、輸出 text、複製 title | Chunk.fields 提供 text:string、title:string；page 未選 copy，不保證留在 fields |
| Embedding | 來源 fields.text，向量名稱 text | Chunk 保留 fields，新增 vectors.text；向量 Profile／來源依既有 Contract |
| Indexing | 全文 fields.text；向量 vectors.text | 只開放已宣告能力；Retrieval 選項依有效索引計畫產生 |

Parser 把保留 title 關掉後，Chunker 原本的 copy title 保留但報錯；Embedding 不能自行改選其他欄位。若 Parser 改輸出名稱，也不將舊欄位當成別名。

## 8. Ingestion API 的驗證與 document_schema 收斂

共用 API 仍接收非空 IngestionDocument[]；每筆與 Parser Input 相同，content／base64／uri 三選一，不新增另一份 ParserInput 或資料轉換層。

| 時點 | 驗證 |
|---|---|
| 設定／套用前 | 驗證 Component Config、推導 I/O Schema／選項、檢查 Module 與欄位相容；不必先跑文件或初始化模型／DB |
| 回 202 前的整批預檢 | 共用外層、可判定的 Parser 路由／輸入欄位及其他既有快速接收條件；任一不通過則整批拒絕 |
| 背景文件工作 | 需下載、解碼、辨識或實際解析才能驗證的內容；Parser 輸出再驗共用 ParsedDocument＋當前輸出細節，後續 Module 同理 |

202 不表示文件已解析成功。組裝時的 Schema 相容也不保證實際資料／遠端服務遵守宣告；執行期仍驗證並記錄既有工作失敗，不靠 Schema 推導跳過驗證。

取消 D 頂層獨立 document_schema 的要求。固定輸出 Parser 直接提供規格；欄位映射由參數決定規格；任意 JSON Parser 有需要時開放資料欄位定義參數。metadata 的業務限制／Component 處理提示也由適用的 I/O 宣告與參數表達，不重複維護全域權威。可信 metadata／授權保留區仍由 A／Q-006 管理，不能由 Parser 放寬。

Engine／Builder 可保留解析出的規格供驗證與顯示，但它是由 B／C＋D 推導的結果，不是另一份要求 User 手填的來源。快照包裝／版本、Export 是否攜帶解析結果仍待核定。

## 9. Developer 交付與驗收

Local 從 SDK 取得共用資料契約，交付 Component 宣告與實作；Remote 經 C 的 Manifest 提供等價規格，由 Adapter／Registry 形成 B 的目錄資訊。固定 I/O 不要求自訂解析函式；第一版受支援規則由通用解析器處理。特殊程式／遠端規格解析機制不因本文件成為首版必備。

Developer 需交付：共用 Contract／版本引用、Config Schema、固定或設定相依的 I/O 細節、下游選項來源／相依條件、合法與非法 Config／資料、變更影響及測試材料。Meta-schema 尚未發布前，交付候選描述／範例，不宣稱已完成 Registry 相容驗收。

| 驗收案例 | 預期行為 |
|---|---|
| 固定欄位、改名、清單映射、copy、條件分支、衍生文字欄位 | 六種宣告分別及組合有正反例，推導不需執行業務處理 |
| 相同 Descriptor／Config／上游宣告／Profile 版本 | UI、AI、Python、API 得到一致候選及驗證結果 |
| 缺來源、錯型別、輸出碰撞、未知必要規則 | 定位至 Module／參數並拒絕；不忽略限制或執行自由程式 |
| 上游刪欄位、條件改變或舊回應晚到 | 原值保留報錯；過期結果不得覆寫最新草稿 |
| 多 Parser／多任務有不同欄位 | 明示分支與可用性，不以第一筆 Sample／欄位聯集當作全體保證 |
| Remote 單 Module／連續區段 | 相同公開邊界規則，內部處理不要求交付中間物件 |
| Config 合法但實際資料或 Remote 回傳違規 | 工作階段失敗可查；不因描述合法跳過執行資料驗證 |

這是待建立的驗收清單，不是已通過的新解析器測試；UI 變更集中在 [10 UIB-021](10_ui_adjustment_backlog.md#uib-021-io-schema-refinement)，使用者要求改 UI 時才實作。

## 10. 仍待核定的格式細節

具體初版已整理為 [25 Descriptor Schema 討論稿](25_component_descriptor_schema_draft.md)，包含五組對照、機器結構稿及 DS-01～DS-13。以下細節已有候選表示，仍需 review，不視為已核定。

- Descriptor／Manifest 的固定 I/O、共用 Contract 引用、變動規則與 option_sources 的正式鍵名／Meta-schema；沿用版本及未知必要語意拒絕政策。
- 六類規則的精確語法、型別／required／default／nullable／額外欄位政策，以及與既有 12 rules 的整合；不能把「支援方向」當作所有 JSON Schema keyword 都可自動呈現。
- Engine 解析結果與來源／版本的回傳格式、錯誤定位、快取／失效及 Runtime API；不先凍結 resolve_io_schema 簽名或新增 Remote 端點。
- 未知資料欄位由 Sample 建議／User 確認的流程；複雜自訂規格解析另案。
- [23](23_system_config_schema_draft.md) 其餘 SC 選項，包含 Fusion／Top N 的參數位置、Profile、正規化與 Export 包裝，維持待議；本決策不代為定案。
