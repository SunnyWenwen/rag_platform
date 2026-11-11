# 2026-11-11 前的 Developer 模式與資料契約

現行方向見 [決策登錄](../../08_plan_and_decisions.md#user-remote-api-decision)。可用 [改版前文件提交](https://github.com/SunnyWenwen/rag_platform/tree/781fd3e31251739290f93b975aff5696090391d0) 重現 D-40／51 的 Developer、Manifest、Remote Image 與 D-66／67 的候選規格。舊根層 Ingestion List 由新批次物件取代。

保留原路徑以便歷史測試重現的資產：

- schemas 下的 ingestion_document、parsed_document、chunk 與 inference_context。
- examples 下的 parsed_document、chunk、inference、pydantic_contracts、component_development、component_descriptor 與 contracts。
- 使用上述格式的舊 tests 與已存產物。

這些案例對應原提交的 Prototype 與契約，現行驗收改用 [User Remote API](../../../examples/user_remote_api/README.md)。
