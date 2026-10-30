# Chunk 0.1 草案：欄位切分、來源追溯與向量

> 2026-10-30（Asia/Taipei）· D-47：依討論產出可驗證草案。預設切 fields.text，不要求選欄位；需要時才展開多欄位與複製設定。本稿不是已凍結的 SDK，也不代表 Chunker、UI 或索引更新機制已實作。

## 0. 情境整理與報告摘要

ParsedDocument 保存解析後的文件內容／結構；Chunk 是切分後供 Embedding、Indexing、Rerank、Generation 使用的單位。後續應取得必要內容，不強制回查 ParsedDocument；原文件留作追溯、除錯與重新處理。

| 情境 | 本輪結論 |
|---|---|
| 一般文字文件 | 直接切 fields.text，結果仍寫 fields.text；使用者不用選欄位 |
| 切分同時保留完整原文 | 進階指定 text → original_text；名稱可自訂，不自動增加 original 欄位 |
| 同文件有 text、faq、summary 等多個欄位 | 欄位不等於文件或 Chunk；指定哪些切分、哪些完整複製 |
| 兩個欄位各切 2／3 段 | 結果串接為 5 個 Chunk，不做 2×3 配對；附帶另一完整欄位須明確設定 |
| 全文範圍／Page-Block 來源 | 自動保留可確認的來源位置；位置不是使用者逐項設定的內容 |
| 表格物件、原生結構或其他輔助資料 | 只供追溯可在 metadata；要作為可選處理內容則放 fields；不新增頂層 structure |
| Embedding 後 | vectors 的每個命名向量包含 values、Profile 識別及來源欄位 |
| 重送／重新切分 | 可重現 ID 與全域序號；索引發布成功後再切換，儲存原子性仍另議 |

### 0.1 共用檔案與驗證邊界

| 檔案 | 用途 |
|---|---|
| [chunk.schema.json](../schemas/chunk.schema.json) | 六個頂層 key、向量項目及來源位置形狀 |
| [cases.json](../examples/chunk/cases.json) | 共用來源文件、有效切分設定與 7 個情境／11 個 Chunk |
| [contract.py](../examples/chunk/contract.py) | 本地 Schema Registry、來源／ID／向量語意檢查與參考 Hash |
| [build_examples.py](../examples/chunk/build_examples.py) | 用明確指定的文字片段產生範例，不實作切分演算法 |
| [test_contract.py](../examples/chunk/test_contract.py) | 正反例、來源繼承、多欄位、ID 及 Inference 相容檢查 |

JSON Schema 檢查資料形狀；語意工具另驗證來源範圍、內容對應、欄位映射、ID 與向量 Binding。範例使用人工指定切片與示意向量，沒有呼叫 Tokenizer、模型、搜尋服務或正式 Engine；片段用於驗證單位資料與順序，不是全文切分覆蓋率的驗收。通過契約測試不代表 Recursive／Fixed-size／Header-aware 已實作。

<!-- chunk-report-examples:start -->

### 0.2 使用同一份 Schema 的資料例子

以下由共用 cases.json 產生，包含完整預設 Chunk、進階多欄位結果及來源／向量片段。Hash 是參考規則的實際結果；完整來源與設定見同一案例檔。

**預設：只切 text，不複製其他 fields**

```json
{
  "chunk_id": "chk_25f40b1f36ef7154df4806eb5fe1317db1836f46e0705749efd676b44cbe9182",
  "document_id": "manual-001",
  "source_revision": "v1",
  "fields": {
    "text": "清潔前先斷電。"
  },
  "metadata": {
    "department": "engineering",
    "_rag": {
      "source_refs": [
        {
          "field": "text",
          "output_field": "text",
          "role": "split",
          "start": 5,
          "end": 12
        }
      ],
      "chunking": {
        "chunking_fingerprint": "40da9219f54a8d552281e6fa3573e98352e450df39d8ac6e6c3ed287877a31a3",
        "chunk_ordinal": 0,
        "task_id": "text"
      }
    }
  },
  "vectors": {}
}
```

**進階：T 切 2 段、F 切 3 段，明確設定互相複製完整欄位**

| ordinal | task_id | fields.text | fields.faq |
|---|---|---|---|
| 0 | text | 甲段。 | 問一。問二。問三。 |
| 1 | text | 乙段。 | 問一。問二。問三。 |
| 2 | faq | 甲段。乙段。 | 問一。 |
| 3 | faq | 甲段。乙段。 | 問二。 |
| 4 | faq | 甲段。乙段。 | 問三。 |

**結構來源：從兩頁 Block 組成同一 Chunk，保留兩筆來源與各自輸出位置**

以下是 page_blocks 案例的 metadata._rag.source_refs；頁面不是預設強制切分邊界。

```json
[
  {
    "field": "text",
    "output_field": "text",
    "role": "split",
    "schema_id": "page-blocks/0.1-draft",
    "block_id": "b1",
    "block_start": 0,
    "block_end": 4,
    "chunk_start": 0,
    "chunk_end": 4,
    "locations": [
      {
        "kind": "page",
        "page_number": 1
      }
    ]
  },
  {
    "field": "text",
    "output_field": "text",
    "role": "split",
    "schema_id": "page-blocks/0.1-draft",
    "block_id": "b2",
    "block_start": 0,
    "block_end": 7,
    "chunk_start": 6,
    "chunk_end": 13,
    "locations": [
      {
        "kind": "page",
        "page_number": 2
      }
    ]
  }
]
```

**Embedding 後：vectors.text 的內容**

以下向量為契約用示意數值，沒有呼叫模型；Profile 與來源欄位必須符合可信 Binding。

```json
{
  "values": [
    0.12,
    -0.08,
    0.31
  ],
  "embedding_profile_id": "embedding-demo-v1",
  "source_field": "text"
}
```

<!-- chunk-report-examples:end -->

## 1. 六個固定頂層 key

| Key | 型別／必填 | 規則 |
|---|---|---|
| chunk_id | 非空 string／必填 | Chunking 輸出的識別；參考規則見 §6 |
| document_id | 非空 string／必填 | 繼承 ParsedDocument，作用域為同一 System |
| source_revision | 非空 string／必填 | 繼承文件內容版本；改 Chunk Size 不修改它 |
| fields | 非空 object／必填 | 切分結果與明確複製的欄位，值為 JSON |
| metadata | object／必填 | 完整繼承有效業務 metadata，平台資訊放受控 _rag |
| vectors | object／必填 | Chunking 時 {}；Embedding 後為具名 DenseVector 物件 |

不接受第七個頂層 key。一般文字路徑的 fields.text 為非空字串；通用 Chunk Schema 不強迫所有客製 Component 都有 text。特殊 Component 必須宣告可用欄位／型別與相容下游，不因 fields 可放 JSON 就自動支援任意模態。

Schema 形狀允許 metadata={}，供既有 Inference 範例／受控傳遞投影使用；**完整 Chunker 輸出另要求 metadata._rag.source_refs 與 metadata._rag.chunking**，且 vectors 必須為 {}。資料投影不刪除索引保存的完整內容，不能藉投影移除執行所需的授權資訊。

## 2. 預設路徑與進階欄位設定

### 2.1 不選欄位也能使用

- 預設 split_field=text、output_field=text、copy_fields=[]；直接使用 ParsedDocument.fields.text。
- 不自動複製所有其他 fields，也不自動新增 original_text；有效業務 metadata 仍全部繼承。
- text 缺少、不是字串或內容不可處理時，回報 `[Chunking] fields.text`，不偷偷挑另一個欄位。第一版必要切分欄位全空白亦報錯，不將它當成功匯入；精確 Token 邊界連動 Q-004／Q-005。
- 方法、size、overlap 與 Tokenizer 仍依 Config／Component 的有效設定執行。「不用選」指欄位選擇，不表示不需要有效切分參數。

### 2.2 有需要才開進階設定

每個切分任務指定一個來源欄位、輸出名稱、Component／有效參數與附帶欄位映射。預設只有一個任務；進階才允許多個。每個新任務的切分片段預設都輸出到 fields.text，無須另外選輸出欄位；進階仍允許明確自訂名稱。同一來源可同時切分及完整複製，但兩份輸出名稱不可相同，避免覆蓋。

| 設定 | 例子 | 結果 |
|---|---|---|
| split_field → output_field | text → text | 每個 Chunk.fields.text 是切分片段 |
| copy_fields 映射 | text → original_text | 每個 Chunk 額外帶切分前完整原文 |
| copy_fields 映射 | title → title | 每個 Chunk 帶相同完整標題 |

欄位名稱在參考 spec 中是 fields 容器內的 key，不是任意 JSONPath。第一版要求明確選用的複製欄位存在，缺少即報錯；不因它原本是 Document Schema 的選填欄位而默默省略。可選複製與巢狀路徑有明確需求再擴充。複製保留原型別，不隱式轉文字；完整內容可能超過模型上限，需由 Embedding／Generation 另檢查。

### 2.3 多欄位是結果串接，不是互相配對

同文件 fields.text=T、fields.faq=F，T 切兩段、F 切三段時，得到 5 個獨立 Chunk。一般多任務預設各自輸出 fields.text=T1／T2／F1／F2／F3；完整附帶內容建議改名為 original_text／original_faq，且須明確 copy，不能覆蓋切分片段。§0.2 的表為明確自訂輸出名稱 text／faq 的進階例子；未指定則每個任務只輸出自己的片段及其他明確附帶欄位。

不同欄位的第 N 段不假設有對應關係，不做笛卡兒積。若業務資料本來有逐段對應，需專屬 Component 宣告配對契約。多個任務使用相同 Component 不代表 spec 相同；來源／輸出／複製規則不同也是有效設定差異。

Embedding／Generation 依 Chunk 實際欄位與設定執行，不能假設所有任務都有相同欄位。預設將不同任務的切分結果都映射到 text，其他完整來源有需要時用不同名稱附帶，以維持簡單下游；若保留 text／faq 異質配置，需明確宣告適用任務／欄位與缺欄位政策，不默默略過。互相複製完整欄位後再全部 Embedding 會重複處理，UI 應說明。

## 3. 來源追溯與 metadata

### 3.1 source_refs 的位置與用途

放在 metadata._rag.source_refs，由可信 Chunker／Engine 產生。用途包含來源引用、原文件頁面／段落定位、除錯與重新處理，不是 Retrieval 分數來源。一般設定 UI 不列逐筆 source_ref 選項，結果詳情可唯讀檢視；ResultItem.source_refs 仍表示 ResultSet 間的候選血緣，兩者不可混用。

| 欄位 | 必要性 | 語意 |
|---|---|---|
| field | 必填 | 原 ParsedDocument.fields 的欄位 key |
| output_field | 必填 | 此次對應的 Chunk.fields key |
| role | 必填 | split：片段來源；copy：完整欄位複製 |
| schema_id／block_id | 視來源提供 | 結構版本與該來源欄位內的 Block ID；block_id 必須帶 schema_id |
| start／end | 成對選填 | 原 ParsedDocument.fields[field] 的 Unicode code point 半開範圍 |
| block_start／block_end | 成對選填 | page-blocks 的 Block.text 內範圍；必須帶 block_id／schema_id |
| chunk_start／chunk_end | 成對選填 | Chunk.fields[output_field] 的本地字串範圍，用於多片段串接 |
| locations | 選填 | 共用 ParsedDocument Location：page／slide／sheet／element 與可取得的 bbox |

範圍採 0-based、end 不包含，與 Python 字串切片一致，不是 UTF-8 bytes／UTF-16 code units。start/end 與 block_start/block_end 不混用；chunk_start/end 是輸出端位置，不會取代來源位置。

- 無 structure 的文字：記來源欄位與 start/end；不捏造頁碼。
- text-spans：使用原全文的 start/end，可附 Block ID 與已知來源位置。
- page-blocks：優先用 Block ID 與 Block.text 內範圍；需要時附輸出本地範圍，不將 Block 內 offset 當全文 offset。
- 一個 Chunk 跨數個 Block／頁：有多筆 refs；參考案例以兩個 LF 串接，分隔字元是組裝規則，不是虛構原始位置。
- copy：整個欄位原值複製，不帶局部文字／Block selector。

locations 是原生元素或頁面註記，並不保證每個字元都有精確 bbox。來源文件的結構驗證引用 [14](14_parsed_document_contract.md)；參考 Chunk 工具檢查可重現文字／複製值，不重新執行解析器或驗證幾何辨識品質。客製結構的 Block 定位／內容轉換需另提供相容 resolver／語意驗證；本輪工具只驗內建兩種結構及直接欄位。

### 3.2 輔助結構放哪裡

追溯用原生結構、表格備份等可以放 metadata；希望在 Embedding／Rerank／Generation 的內容選單供使用者選取，則建議放 fields。這是平台的預設使用慣例，不代表 metadata 不能保存物件或永遠不能參與客製處理。

不自動複製整份 ParsedDocument.structure，也不新增 Chunk.structure。來源 metadata 中已有的輔助資訊會依完整繼承規則保留；Parser 用 data_ref 指向 fields 的表格／圖片仍遵守 ParsedDocument 契約，可由明確 copy 映射附帶，不能只把引用搬過來卻丟失所需 payload。特殊 Component 若要重組／搬移資料需宣告，不由通用切分器猜測。

metadata._rag 為受控平台區：已驗證業務 metadata 全部繼承；可信 ACL／來源等不得由輸入覆蓋。建立 Chunk 時重算 source_refs／chunking，保留其他可信平台資訊。此草案將兩個子鍵具體化，不代表全平台的可信來源／ACL／保留名稱協定已在 Q-006 全部定案。第一版不提供 metadata 排除選單。

## 4. 向量與 Embedding Profile

每個 vectors 名稱對應一個物件，必填 values、embedding_profile_id、source_field。values 為非空有限數值陣列；source_field 是此 Chunk.fields 的 key。Profile 的 Provider／模型版本／維度／正規化／Document 與 Query encoding 保存在共用 Config／Profile，不在每筆 Chunk 重複，也不包含 Secret。

Profile ID 必須解析到可追溯的不可變設定版本；修改模型或 encoding 應使用新的識別／版本。Embedding／Indexing 用向量邏輯名稱的 Binding 核對 Profile、來源欄位、維度與模型相容性，不能只驗陣列長度。Query Embedding 也依同一 Profile 的 query encoding 配對；未配置的向量名稱須報錯。

一般預設方向為 fields.text → vectors.text，有需求才改輸入欄位與輸出名稱；本稿不新增另一組模型選擇。純全文 Pipeline 可一直保持 vectors={}。檢索為省傳輸可回 vectors={}，不因此刪除已保存向量；若傳非空向量，必須遵守同一物件格式。Sparse／多模態／late interaction 另議。

**草案遷移**：舊 05／Inference Schema 的 vectors.name=[...] 改為 vectors.name={values, embedding_profile_id, source_field}；本輪不接受兩種形狀混用。既有 Inference 例子 vectors={} 仍通過，Python 型別與 JSON Schema 已同步引用／描述新格式。需要遷移非空舊資料時，必須從可信 Binding 補齊 Profile 與來源欄位，不能靠向量名稱猜測。Prototype 的模擬資料尚未遷移，記入 UIB-013。

## 5. 有效切分設定與 fingerprint

chunking_spec 是 Engine 解析後的**有效切分執行設定**，不是每個 Chunker class 的固定值，也不是多一份由使用者手填的資料。參考格式名稱為 chunking-spec/0.1-draft；完整 Pipeline Config／Router 的 Schema 仍由 Q-002／Q-004／Q-025 核定。

| 內容 | 納入 fingerprint 的原因 |
|---|---|
| 有序 tasks、唯一 task_id | 決定多欄位輸出順序與任務識別 |
| Component ID／實作版本 | 演算法版本可能影響邊界或結果 |
| split／output／copy 映射 | 決定輸出內容與欄位 |
| 解析後有效參數／Tokenizer ID 與 revision | size／overlap／分隔符／正規化等會影響結果 |

未啟用的方法參數、UI 收合狀態、HTTP 連線、Secret、Run ID、Embedding／Retrieval／Generation 設定不納入。預設值須先補齊；路由時記錄實際選用的 Component／版本與有效設定。本文範例 tokenizer 是示意識別，沒有下載或驗證真實 Tokenizer。

同一份解析後設定處理不同文件，fingerprint 相同；同一個 Recursive Component 改欄位、長度或版本，fingerprint 不同。本輪採**整份有效任務計畫的一個 fingerprint**；改其中一個任務會影響這份文件所有 Chunk ID，換取簡單一致的重建語意，暫不承諾逐任務局部保留 ID。

參考計算：json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) → UTF-8 → SHA-256。保留字串原樣，不偷偷做 Unicode normalization。這是 Python 草案規範；跨語言的數字正規化與正式 canonicalization 仍在 Q-007，不能用 Python 內建 hash()。

## 6. Chunk ID、序號與重建

metadata._rag.chunking 記錄 chunking_fingerprint、chunk_ordinal、task_id。實際 spec 存在可追溯 Config／Run，不在每個 Chunk 重複。

- chunk_ordinal 是同一文件本次輸出的**全域** 0-based 序號，依設定任務順序，再依各任務的穩定內容順序編排；不是每個欄位各從 0 開始。
- 任務併行時先按上述順序整併，再產生 ID；不能使用完成先後順序。相同輸入的 Component 若不具決定性，須明確宣告並提供可重現策略，不能承諾穩定 ID。
- 參考 chunk_id 為 chk_ 加上 SHA-256；輸入是 document_id、source_revision、chunking_fingerprint、chunk_ordinal 的固定 JSON。完整可執行函式在 contract.py。
- 文件內容變更更新 source_revision；切分設定變更更新 fingerprint；只換 Embedding 或 Inference 設定不改 Chunk ID。相同 revision 不得偷偷表示不同來源內容；來源版本產生與衝突政策仍由 Q-007／Q-008 定案。
- 文件／Chunk ID 作用域為 System；存取必須另帶可信 System 範圍，相同字串不授權跨 System 存取。

重建應先準備新一批完整資料，成功後切換；失敗保留原本可用資料，不搜尋新舊混合版本。這是本輪同意的行為方向；ES／Local Search 的發布、併行更新、部分失敗、舊資料清除與可查詢時點仍在 Q-008～Q-010／Q-015，未實作原子交易。Memory 重啟仍依既有規則重新 Ingestion，不因 fingerprint 就可恢復資料。

## 7. UI 與 Component 開發配套

基本畫面不顯示 split/copy 欄位選擇，直接使用 text。進階才顯示新增任務、來源／輸出映射、附帶欄位與完整原文保留。metadata 繼承、source_refs、fingerprint、ordinal 不提供一般設定選項；預覽／結果詳情可唯讀顯示。

錯誤標示 `[Chunking]` 與具體任務／欄位；映射重名、來源不存在、型別／結構能力不合、欄位變更造成失效，皆保留選擇並阻止套用。僅展開進階不改有效設定；手動／AI／Edit／匯出使用相同有效計畫。對應事項集中於 [UIB-013](10_ui_adjustment_backlog.md#uib-013-chunk-contract)，本輪不修改 UI。

Component Developer 仍由 [11](11_component_developer_guide.md) 的流程開發，遵守 ParsedDocument → Chunk 清單的公開邊界；宣告結構支援與欄位能力，不能因一般 UI 隱藏欄位就只接受硬編碼 text。Config Schema／UI hints 見 [12](12_component_schema_ui_contract.md)。Runtime 的權限、Context、Batch／Async 與正式類別簽名不由本資料草案代替。

第一版必要切分任務不得默默產生零個 Chunk 後回成功；錯誤顯示來源欄位與 task_id。這是 2026-10-30 後續確認的目標規則，現有參考工具不等於正式 Ingestion／Tokenizer 驗收；批次失敗／提交仍由 Q-009 核定。

## 8. 重現與待核定事項

```bash
python -m pip install -r examples/chunk/requirements.txt
python examples/chunk/build_examples.py
python examples/chunk/render_report.py
python examples/chunk/test_contract.py
```

7 個正例情境共 11 個 Chunk；另外 33 個刻意破壞的 Chunk、4 個序列／設定反例，與 5 份既有 Inference 資料共用 Schema 檢查。測試涵蓋非空向量的新格式，不呼叫外部服務；輸出結果不是實際切分演算法品質或併行更新的驗收證據。

已確認的是六鍵外層、text 預設、進階多任務／複製、來源追溯位置、向量資訊分層及穩定 ID 方向。精確鍵名／nullable／自訂型別與遷移仍以本稿供 M0 審閱；Q-002／Q-003／Q-004／Q-006／Q-007 及索引提交政策不因草案產出而全部結案。

## 9. 後續確認與欄位組裝待討論（2026-10-30）

- D-48 已確認：多任務預設將切分片段寫 fields.text；完整原文複製採不衝突名稱，進階仍可自訂。第一版必要切分欄位缺失／型別錯誤／全空白、明確 copy 欄位缺失或必要任務零產出均明確失敗；可選複製不先擴充。
- Parser 改變需重新處理受影響文件：Parsing → Chunking → Embedding（有配置時）→ Indexing；原始資料可取得時不代表一定要重新上傳。多 Parser 路由的重跑範圍、原始資料保留、重新發布仍須依有效相依與儲存政策決定。這是執行影響說明，沒有新增已實作的重跑／快取能力。
- 重新 Ingestion 與 ID 是否納入解析後輸入內容摘要是不同問題；目前 Hash 規則尚未修改。原始文件版本不變但 Parser 輸出改變時的 ID／index_generation 識別仍在 Q-007／Q-015。
- **待討論，未核定**：切分後 concat 多個欄位、加入固定文字，可候選作為 Chunking 後的共用欄位組裝、在 Embedding 前執行；先不新增 Pipeline Module、不修改 Schema／程式或凍結模板拼字。
- 待確認範圍：是否寫入獨立衍生欄位、來源／衍生血緣與 Token 檢查；與 Embedding Profile 的 encoding prefix、Generation 既有 chunk_template 的分工；模板改動需重跑哪些步驟。不能先把欄位組裝當成已交付能力。
