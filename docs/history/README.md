# 歷史文件與查驗紀錄

本資料夾集中保存過時規格、被取代提案、決策來源／演變、更新流水帳及校對／驗證過程，供日後追查。現行結論請由 [專案入口](../../README.md)、[08 決策摘要與待決事項](../08_implementation_plan.md)及各主責規格閱讀。

## 分類與本次歸檔

| 分類 | 內容 | 檔案 |
|---|---|---|
| decisions | 原始 D-01～D-68 決策表／逐輪討論，包含當時未決或已被取代的說法 | [歷史決策來源](decisions/decision_history.md) |
| changes | 原 README 文件更新流水帳 | [文件更新紀錄](changes/documentation_changelog.md) |
| changes | 從 UI Backlog 移出的逐輪整理說明 | [UI 整理紀錄](changes/ui_backlog_notes.md) |
| reviews | 過程性校對報告，原 docs/24_spec_alignment_review.md | [2026-11-05 規格交叉校對](reviews/2026-11-05_spec_alignment_review.md) |
| validation | 已完成的一次性瀏覽器／契約檢查證據 | [Prototype v0.12 驗證](validation/2026-11-03_prototype_v0.12.md) |
| superseded | 從固定 Git commit 恢復的 ParsedDocument 0.1 舊規格／Parser 對照 | [ParsedDocument 0.1](superseded/parsed_document_0.1.md) |
| superseded | D-54 前的 InferenceState／歷史推論物件提案 | [舊 Inference 規格](superseded/inference_state_pre_d54.md) |
| superseded | D-66 System Config 舊 document_schema 骨架、五案例及離線驗證 | [舊 System Config](superseded/system_config_d66/README.md) |

## 歸檔原則

- **現行規格、結論、Q-ID、SC 待討論選項與未完成 UI 待辦留在現行文件。**23 System Config 討論稿、12 的描述／UI 草案、24 的 B 現行結論與共用契約範例仍在使用，不因尚未定稿就歸檔。D-66 機器稿／五案例因 document_schema 已被 D-67 取代而另行歸檔。
- 已被新版取代的整份文件移入 superseded；更新現行規格時，把純過程／舊版快照放入對應分類，現行文件只保留必要結論與歷史入口。
- 每份歷史檔案記錄來源、日期／commit、適用狀態與現行取代入口；來源內容保留，搬移時修正相對連結。舊規格快照中的來源連結固定指向當時 commit。
- 查驗時可追到原始 Git blob／commit。歷史檔案中的「待定」「已完成」與測試結果屬當時狀態，不自動覆蓋現行決策或代表目前功能驗收。
- 更新歷史檔案以修正連結／補充溯源為主；新討論／新證據另加日期記錄，保留原脈絡。

本次整理日期：2026-11-05。變更來源為 a27e9cdba06c5ada210b00e09de629b53fe7bae1；兩份過時規格另取自 2e1a3863e8c0217246c1869ffa131434c0983338，完整來源與 SHA 見個別檔案。
