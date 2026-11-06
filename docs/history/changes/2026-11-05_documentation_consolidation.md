# 2026-11-05：文件整合與主責對照

整合來源 commit：916734ac0bbe0631a205bfd52626ce332aa7beb2。現行入口為 [README](../../../README.md)。原本 23 份規格合併為 8 份主題手冊；舊入口不保留另一套可編輯規格。

資料／Python 範例、SDK／Module、Descriptor、System Config、Runtime HTTP／環境、UI／Backlog 按主責收斂；交叉參照重新定位。原始全文以來源快照保留，只有相對 URL 固定到來源 Git 版本及加上適用狀態，保留所有被精簡的歷史解釋。

| 整合前文件 | 現行主責入口 | 來源快照 |
|---|---|---|
| 03_architecture_proposal.md | [01_architecture.md](../../01_architecture.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/03_architecture_proposal.md) |
| docs/04_module_components_io_contracts.md | [03_engine_and_components.md](../../03_engine_and_components.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/04_module_components_io_contracts.md) |
| docs/05_data_contracts_search_design.md | [02_data_contracts.md](../../02_data_contracts.md)、[03_engine_and_components.md](../../03_engine_and_components.md)、[05_system_config.md](../../05_system_config.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/05_data_contracts_search_design.md) |
| docs/06_ui_development_spec.md | [07_builder_ui.md](../../07_builder_ui.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/06_ui_development_spec.md) |
| docs/07_backend_runtime_integration.md | [03_engine_and_components.md](../../03_engine_and_components.md)、[06_runtime_api_and_deployment.md](../../06_runtime_api_and_deployment.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/07_backend_runtime_integration.md) |
| docs/08_implementation_plan.md | [08_plan_and_decisions.md](../../08_plan_and_decisions.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/08_implementation_plan.md) |
| docs/09_inference_contract_ui_plan.md | [07_builder_ui.md](../../07_builder_ui.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/09_inference_contract_ui_plan.md) |
| docs/10_ui_adjustment_backlog.md | [07_builder_ui.md](../../07_builder_ui.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/10_ui_adjustment_backlog.md) |
| docs/11_component_developer_guide.md | [03_engine_and_components.md](../../03_engine_and_components.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/11_component_developer_guide.md) |
| docs/12_component_schema_ui_contract.md | [03_engine_and_components.md](../../03_engine_and_components.md)、[04_component_descriptor.md](../../04_component_descriptor.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/12_component_schema_ui_contract.md) |
| docs/13_ingestion_parser_input_contract.md | [02_data_contracts.md](../../02_data_contracts.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/13_ingestion_parser_input_contract.md) |
| docs/14_parsed_document_contract.md | [02_data_contracts.md](../../02_data_contracts.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/14_parsed_document_contract.md) |
| docs/15_chunk_contract.md | [02_data_contracts.md](../../02_data_contracts.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/15_chunk_contract.md) |
| docs/16_parser_component_development_examples.md | [03_engine_and_components.md](../../03_engine_and_components.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/16_parser_component_development_examples.md) |
| docs/17_pydantic_contracts_draft.md | [02_data_contracts.md](../../02_data_contracts.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/17_pydantic_contracts_draft.md) |
| docs/18_remote_service_pipeline_integration.md | [03_engine_and_components.md](../../03_engine_and_components.md)、[06_runtime_api_and_deployment.md](../../06_runtime_api_and_deployment.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/18_remote_service_pipeline_integration.md) |
| docs/19_index_binding_artifact_contract.md | [02_data_contracts.md](../../02_data_contracts.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/19_index_binding_artifact_contract.md) |
| docs/20_contract_inventory_responsibility_matrix.md | [01_architecture.md](../../01_architecture.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/20_contract_inventory_responsibility_matrix.md) |
| docs/21_runtime_ingestion_inference_api_inventory.md | [06_runtime_api_and_deployment.md](../../06_runtime_api_and_deployment.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/21_runtime_ingestion_inference_api_inventory.md) |
| docs/22_runtime_settings_catalog.md | [06_runtime_api_and_deployment.md](../../06_runtime_api_and_deployment.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/22_runtime_settings_catalog.md) |
| docs/23_system_config_schema_draft.md | [05_system_config.md](../../05_system_config.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/23_system_config_schema_draft.md) |
| docs/24_component_io_schema_refinement.md | [04_component_descriptor.md](../../04_component_descriptor.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/24_component_io_schema_refinement.md) |
| docs/25_component_descriptor_schema_draft.md | [04_component_descriptor.md](../../04_component_descriptor.md) | [來源](../source_snapshots/2026-11-05_pre_consolidation/docs/25_component_descriptor_schema_draft.md) |

## 保留與修正

- 已確認資料、Module 能力、Local／Remote、版本與失敗政策不變；共用 schemas/ 與業務範例保留。
- Q-001～Q-028、M0～M7、SC-01～SC-10、DS-01～DS-13、API-D01～07 與 40 個未勾選 UI 工作項保留。
- 修正 UIB-021 重號：索引綁定仍為 021，Descriptor 需求改為 024；保留舊描述錨點並同步現行引用，歷史來源不改號。
- 原型現況統一為 v0.12；舊 v0.9／UI 待做的歷史文字不覆蓋已完成的模擬。
- 舊 Descriptor 語法／重複資料模型不再與現行候選並列；DS／SC 未定案，人工明列的預期 Schema 不冒充完整解析器。
- 文件產生器只調整目標 Markdown 路徑，Artifact spec_ref 指向新資料手冊；產品程式、原型、共用資料格式與 Fixture payload 未變。

此為整理紀錄，不是新的功能／協定決策。原 D-01～D-68 與較早歷史資料保留於既有 history 分類。

## 查核補充

補查並保留 Embedding Profile 的 document/query encoding／Tokenizer 配對、ParsedDocument 不相容遷移、候選 repo 目錄、Remote 推論公開邊界與 SDK Schema 輸出責任。相關原始全文仍可從來源快照逐項追查。
