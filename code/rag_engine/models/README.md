# 模型檔案

Runtime 只需要 bge-m3 的 `tokenizer.json` 做 Token 計數與切分；向量由獨立的 Embedding 服務產生，Image 不含模型權重。

建置 Image 前，把檔案放在 `models/bge-m3/tokenizer.json`：

```bash
huggingface-cli download BAAI/bge-m3 tokenizer.json --local-dir models/bge-m3
```

公司內若無法連 Hugging Face，從內部模型倉庫取得同一個 commit 的檔案。記下 commit hash，填入 `resources/dev.yaml` 的 `model_revision` 與 Tokenizer `revision`。這兩個值會進入索引指紋，換版即觸發重建。
