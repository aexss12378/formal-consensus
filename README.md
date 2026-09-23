# 三模型 Lean 形式溝通共識系統

本專案實作三個固定模型的同步共享池實驗。模型彼此不直接對話；每輪開始時，系統把先前所有通過 Lean 驗證的完整證明，以固定加入順序放進三個模型的上下文。

本系統只處理候選證明產生，不處理學生作答或學生批改。

## 第一版規則

- 純 Python 實作，不使用 LangGraph。
- 共享池在程式內是 `list`，每輪開始時凍結快照。
- 三個模型在同一輪看到完全相同的共享池內容。
- 每個模型都有 `lean_check` 與 `lean_submit` 兩個工具；`lean_check` 的紀錄不會進入共享池。
- 預設使用同一個常駐 Lean REPL，`Mathlib` 每次流程只載入一次；`config.json` 未設定 `repl_path` 時才使用原本的 `lake build` 後端。
- 模型只能提交固定 theorem header 的 `by ...` 證明本體。
- 含 `sorry`、`admit`、新增 `axiom` 或 `opaque` 的候選直接拒絕。
- `lake build` 後端以 `-E hasSorry` 執行；REPL 後端則同時檢查 `sorries` 與 `declaration uses sorry` 訊息。`apply?` 等搜尋 tactic 留下部分建議時，兩種後端都不能把它誤判為完整證明。
- 只有後端重新執行 Lean 並通過的完整證明才進共享池。
- 失敗候選保留於研究紀錄，但不提供給下一輪模型。
- 作者資訊只保存在後端，不會進入共享提示；方法標籤會隨 proof 一起放進共享池。
- 第一版不打亂共享池順序、不做摘要、不做檔案檢索。
- 若完整共享池超過模型脈絡或 API 限制，該輪明確失敗並留下紀錄；系統不會靜默截斷候選。

題目輸入與固定 theorem header 不建立雜湊；續跑時直接比對批次內凍結的 JSON。內部唯一保留的 `proof_hash` 只用來判斷兩份正規化後的 proof body 是否字串相同，不用來宣稱語意、方法或命題相同。

代理之間交換的是方法標籤加上通過驗證的 Lean 證明。標籤公開是刻意的取捨：最終產出是每個課本方法一份 proof，同一個方法的其他 tactic 寫法在批改上沒有價值，所以下一輪必須看得出哪些方法已經有人做過。標籤取自 59 個固定分類，不是自由文字，而且沿用產生者自己標的值 —— 輪次進行中拿不到 `method_review` 的審查結果，所以下一輪可能讀到標錯的標籤，這點必須與形式驗證結果分開報告。入池與否仍由 `proof_hash` 決定，標籤只供閱讀，模型沒有謊報標籤的好處。

## 每輪實際流程

1. 系統在輪次開始時複製一份共享池快照。
2. 三個模型平行收到完全相同的快照；同輪模型看不到彼此的新提交。
3. 模型可私下呼叫 `lean_check`，送出的可以是用 `exact?`、`apply?`、`simp?`、`rw?`、`aesop?` 或 `library_search` 的不完整探測，也可以是想先確認的完整 proof，送進去的內容一律不入池；`lean_submit` 是提交動作，驗證成功後會立刻把該 proof 存成本輪候選且無法撤回，模型沒有其他候選時呼叫 `stop`。每個模型每輪的工具使用有三個上限：`lean_check` 最多 `max_searches_per_agent_per_round` 次（預設 40），用完即結束該模型本輪；成功的 `lean_submit` 最多 `max_candidates_per_agent_per_round` 份（預設 5）；連續 3 次送出完全相同的 `lean_check` 也會結束該模型本輪。三種情況下，本輪已通過驗證的候選都會保留。
4. 後端依 `config.json` 的固定模型順序，重新驗證每一份候選。
5. 只有唯一且通過驗證的候選會取得匿名流水號並加入下一輪共享池。
6. 只要本輪有新的有效候選入池，就會再開一輪，讓三個模型都看到更新後的共享池；沒有新增有效候選或到達輪次上限時才結束。模型的 `stop` 只代表它對當前快照已無其他貢獻，不能阻止新入池內容被下一輪看見。

模型回覆快慢不會改變候選編號、去重順序或下一輪內容。公開候選編號也不含模型名稱，避免下一輪從編號推知作者。

模型不一定要使用搜尋工具；它可以直接依自身記憶寫 proof，也可以反覆讀取 Lean diagnostics 修正。無論搜尋路徑為何，只有最後經後端重新驗證的完整 proof 才能進共享池。

每個模型回覆只能要求一個工具；此限制由本機 harness 檢查，不依賴不同供應端是否支援 `parallel_tool_calls` 參數。

## 專案結構

```text
formal_consensus/
├── core/               # 設定、schema 與檔案 I/O
├── agents/             # 證明代理與提示詞
├── tools/              # 模型 API 與 Lean 工具介面
└── workflows/          # 候選產生、審查、代表解與報告流程
lean_project/          # 固定 Lean／Mathlib 專案
examples/              # 輸入格式範例
tests/                 # 不呼叫付費 API 的自動測試
config.json            # 模型與實驗設定
taxonomy.json          # 主要方法分類
```

## 準備環境

需要 Python 3.12 以上、uv、Lean 4 與 elan。

```bash
uv sync
cd lean_project
lake exe cache get
cd ..
```

不要執行 `lake update`。本專案已固定 Lean 與 Mathlib 版本。

常駐 REPL 必須和專案使用完全相同的 Lean 版本。本專案固定使用
`leanprover-community/repl` commit
`f0a88bfca1fa6ac75e2a33d1678a3b67c90fb492`，對應 Lean
`v4.30.0-rc2`。REPL 放在被 Git 忽略的 `.tools/`，不修改 Lean 專案的
`lake-manifest.json`：

```bash
git clone https://github.com/leanprover-community/repl.git .tools/repl
git -C .tools/repl checkout --detach f0a88bfca1fa6ac75e2a33d1678a3b67c90fb492
cd .tools/repl
lake build repl
cd ../..
```

`config.json` 的 `repl_path` 指向建置後的執行檔。啟動後，系統先載入一次
題目的 imports，再讓每次 proof 從同一個基礎 environment 分支驗證，彼此
不會繼承其他候選新增的宣告。若 REPL 遺失、超時或 protocol 錯誤，該次會
明確記為 `tool_failed`，不會靜默退回另一種驗證器。

2026-09-16 在目前機器以 `demo_derivative_square` 實測：第一個正確 proof
連同冷啟動為 170.903 秒；同一 session 的錯誤 proof 為 0.067 秒，含
`apply?` 的搜尋為 11.247 秒。這只是技術 smoke test，不是跨機器效能結論；
正式報告仍應保存每次 `elapsed_seconds`。

目前的三個模型都使用 Ollama Cloud；在本機 `.env` 填入 API key，再載入目前 shell：

```bash
OLLAMA_API_KEY="..."
source .env
```

程式只讀取環境變數，不會自行開啟 `.env`；`.env` 已列入 `.gitignore`。

正式執行前，必須先確認 `config.json` 內三個模型的精確型號仍可使用，並凍結設定。

系統仍支援 OpenRouter 與 Ollama 兩種 API，每個模型用 `api` 欄位指定其中一個；目前的 `config.json` 則全部固定走 Ollama Cloud：[`deepseek-v4-flash:0731`](https://ollama.com/library/deepseek-v4-flash:0731-cloud)、[`qwen3.5:397b`](https://ollama.com/library/qwen3.5:397b-cloud) 與 [`gemma4:31b`](https://ollama.com/library/gemma4:31b-cloud)。這些是直連 `https://ollama.com/v1/chat/completions` 使用的模型識別碼，因此不加 `-cloud`。教學步驟翻譯另用 `translation_model` 指定的模型，目前是 `glm-5.3-flash`，刻意不用產生 proof 的三個模型。指定 API 或模型不可用時，該模型呼叫會明確失敗，不會靜默改走另一個 API。每個 API 回覆紀錄仍會保存實際回傳的模型與供應端欄位，供事後稽核。

## 輸入格式

見 `examples/problems.json`。每題必須提供：

- `problem_id`
- `problem_text`
- `lean_imports`
- `lean_theorem_header`，結尾必須是 `:=`
- `taxonomy_version`
- `statement_fidelity_status`

模型只產生 proof body，不能修改 theorem header。

## 執行

正式啟動三模型前，先以單一模型執行技術 preflight；這份結果只驗證工具迴圈，不列入研究資料：

```bash
uv run python -m formal_consensus.workflows.preflight \
  --config config.json \
  --input examples/problems.json \
  --model qwen \
  --problem demo_derivative_square
```

### 一次跑完（建議）

`run_all` 依序執行候選產生、方法審查、代表解選擇、報告與教學步驟翻譯五步：

```bash
uv run python -m formal_consensus.workflows.run_all \
  --config config.json \
  --input examples/midterm.json \
  --unit midterm_q4_piecewise_continuity
```

把 `--unit 題號` 換成 `--all`，就會依輸入順序跑全部題目。

程式一開始就會印出批次資料夾路徑。任何一步失敗時，錯誤訊息會附上續跑方式，只要在原指令後面加上 `--run-dir`：

```bash
uv run python -m formal_consensus.workflows.run_all \
  --config config.json \
  --input examples/midterm.json \
  --unit midterm_q4_piecewise_continuity \
  --run-dir runs/既有批次資料夾
```

五步都會沿用已保存的結果：已完成的題目不會重跑，已完成的單模型回覆、方法審查票、代表解選擇票與翻譯都不會再次呼叫模型。設定、題目或分類內容若與批次內凍結的 JSON 不同，系統會拒絕續跑。

### 分步執行

需要單獨重跑某一步時，五步也可以分開執行。候選產生：

```bash
uv run python -m formal_consensus.workflows.pipeline \
  --config config.json \
  --input examples/midterm.json \
  --unit midterm_q4_piecewise_continuity
```

它會輸出新批次資料夾，同樣可以加上 `--run-dir` 續跑。候選產生完成後，再執行方法審查、代表解選擇、報告與翻譯：

```bash
uv run python -m formal_consensus.workflows.method_review --run-dir runs/批次資料夾
uv run python -m formal_consensus.workflows.representative_selection --run-dir runs/批次資料夾
uv run python -m formal_consensus.workflows.report --run-dir runs/批次資料夾
uv run python -m formal_consensus.workflows.translate --config config.json --run-dir runs/批次資料夾
```

翻譯的模型讀自 `--config` 指定的設定檔，不讀批次內凍結的設定，所以舊批次也能補翻。

### 各步做什麼

方法審查只判定模型宣稱的主要方法是否符合已驗證 proof；它不重新投票決定數學真偽。三個模型各投一票，`pass` 至少兩票為 `confirmed`、`fail` 至少兩票為 `rejected`，其餘為 `unresolved`。

代表解選擇只看 `confirmed` 的 proof，每個方法選一份。該方法只有一份時直接標為 `selected_singleton`；有多份時匿名顯示 proof，三票中至少兩票相同才自動選出（`selected_by_majority`），三方各選一份時標記為 `needs_human_selection`。

報告會列出每輪開始前的共享池筆數，以及三個模型第一個 API 請求實際回報的 prompt token。這些數字是後續判斷完整 `list` 是否開始逼近脈絡上限的依據，不會在主實驗中自動觸發截斷或改變排序。

教學步驟翻譯把每個方法選出的代表 proof 交給 `translation_model`，寫成學生能在考卷上照著寫的英文編號步驟，不提 Lean、Mathlib 或 tactic；步驟中出現這些字時會退回要求重寫。`needs_human_selection` 的方法沒有代表解，不會翻譯。翻譯沒有經過驗證，只由提示詞要求沿用原 proof 的論證，使用前應人工檢查。

## 主要輸出

```text
runs/批次資料夾/
├── config.json                  # 凍結設定（不是 manifest）
├── input.json                   # 凍結題目
├── taxonomy.json                # 凍結方法分類
├── run_state.json
├── method_review_summary.json   # 全部題目的方法審查結果
├── representatives.json         # 每題每個方法的代表解
├── report.json                  # 報告（機器讀取用）
├── report.md                    # 報告（人閱讀用）
├── translations.json            # 每題每個方法的教學步驟解法
├── translations.md              # 同上，人閱讀用
└── problems/題號/
    ├── state.json               # 內部完整狀態
    ├── candidates.json          # 所有已處理提交與狀態
    ├── failures.json            # 證明輸出失敗，不含 API／Lean 工具故障
    ├── pool_after_round_*.json  # 下一輪真正可見的匿名內容
    ├── rounds/round_*/          # 凍結快照、私有搜尋／驗證紀錄、原始工具回覆與後端重驗結果
    ├── method_reviews/          # 每份 proof 每個模型的方法審查票
    ├── method_review_summary.json
    ├── selection_votes/         # 代表解選擇票
    └── translations/模型/       # 每個代表解的翻譯與原始 API 回覆；換翻譯模型時舊結果保留
```

## 測試

測試不會呼叫 OpenRouter 或 Ollama，也不會產生付費請求：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m unittest discover -s tests -v
```

## 研究解讀限制

Lean 通過只代表固定 Lean 命題具有一份通過檢查的證明。它不會自動確認自然語言題目與 Lean 命題完全相同，也不會自動確認證明所屬的教學方法。方法審查是多模型盲審結果，必須與形式驗證結果分開報告。

本實驗評估的是「固定模型加上相同 Lean 工具」形成的代理系統，而不是模型不使用工具時的純記憶能力。三個模型取得相同的檢查與提交介面；每個代理持續使用工具，成功的 `lean_submit` 會自動暫存候選，直到代理自行呼叫 `stop` 或碰到上方「每輪實際流程」列出的上限。系統不另設每輪 turn 上限。搜尋內容屬於單一代理的私有推理過程，不構成代理間的自然語言溝通。

`statement_fidelity_status=unresolved` 的題目可以用來除錯或探索，但不應混入主結果宣稱「解對原題」；主分析應事先限定為 `confirmed` 或本來就以形式命題定義的 `formal_benchmark`。另外，方法盲審隱藏了候選作者，但仍由同一組三個模型評審，其中可能包含原產生模型，因此它是操作性分組機制，不是獨立人工 ground truth。

第一版把共享池完整 `list` 按加入順序放進上下文。這是刻意保持簡單的實驗條件，不代表已解決長脈絡中的前段偏誤、後段偏誤或「中間資訊較容易被忽略」問題。正式實驗前應先用小規模題目記錄每輪共享池長度與輸入 token；若池子經常逼近模型上限，必須另立排序或擷取條件，不能在主實驗中臨時改規則。
