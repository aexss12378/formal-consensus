# 三模型 Lean 形式溝通共識系統

老師用自然語言出題；系統把題目起草成 Lean 命題，**經人確認後**才產生證明、選出每個方法的代表解，並翻成學生看得懂的教學步驟。本系統不處理學生作答或學生批改。

## 流程

```text
老師寫題目檔（teacher_exam.json）
    │
    ▼
系統起草 Lean 命題（使用步驟 1）
    │  產生 teacher_exam.draft.review.md 與 teacher_exam.draft.json
    ▼
【人工確認 1】題目 → Lean theorem（使用步驟 2）
    │  看 review.md，意思一致就在 draft.json 改成 confirmed
    │  只要有一題還沒確認，系統就拒絕往下做
    ▼
系統產生證明與教學步驟（使用步驟 3）
    │  三個模型寫證明 → Lean 驗證 → 每個解法選一份代表解 → 翻成英文步驟
    │  產生 runs/teacher_exam/solutions.md
    ▼
【人工確認 2】Lean → 自然語言
    │  看 solutions.md，確認數學正確、沒有跳步
    │  系統不會擋這一步，要人自己把關
    ▼
發給學生
```

兩個人工確認點的細節見「兩個要人確認的地方」。

## 輸入與輸出

### 輸入：老師的題目檔

一個 JSON 檔，每題只需要 `problem_id` 與 `problem_text`，範例是 `examples/teacher_exam.json`：

```json
{
  "schema_version": 1,
  "problems": [
    {
      "problem_id": "midterm_q4_piecewise_continuity",
      "problem_text": "Show that f is continuous on (-infinity, infinity), where f(x) = 1 - x^2 if x <= 1, and f(x) = sqrt(x - 1) if x > 1."
    }
  ]
}
```

- `schema_version`：固定填 `1`。
- `problems`：至少一題。
- `problem_id`：題號，只能用英文字母、數字、底線、句點與連字號，第一個字必須是英文字母或數字，同一個檔案內不能重複。
- `problem_text`：題目原文，不能是空字串。

### 輸出

整個流程有兩次輸出，中間要由人確認（見「使用步驟」）。

**第一次：起草 Lean 命題後**，題目檔旁會多出三個檔案，老師只會用到下面兩個，以 `teacher_exam.json` 為例：

| 檔案 | 用途 |
|---|---|
| `teacher_exam.draft.review.md` | **給人看的**。逐題並排「原題」「Lean 命題」「這個命題在說什麼」 |
| `teacher_exam.draft.json` | **給人改的**。確認後把每題的 `statement_fidelity_status` 從 `unresolved` 改成 `confirmed`，再拿這個檔案當下一步的輸入 |

**第二次：產生證明與教學步驟後**，結果放在 `runs/<題目檔名>/`，例如題目檔是 `teacher_exam.json` 時就是 `runs/teacher_exam/`；同名資料夾已經存在時，依序改用 `teacher_exam_01`、`teacher_exam_02`……程式一開始就會印出路徑。最後要拿去用的是：

| 檔案 | 用途 |
|---|---|
| `solutions.md` | **最終成果，也就是交付文件**。每題的題目，加上每個解法一份英文編號步驟，學生可以照著寫在考卷上 |
| `report.md` | 執行紀錄：每題的執行狀態、提交與通過驗證的證明數、每輪共享池大小與 token、方法審查與代表解選擇的結果統計 |

`solutions.md` 長這樣（節錄自實際輸出）：

```markdown
# Solutions

## Problem 1

Show that f is continuous on (-infinity, infinity), where f(x) = 1 - x^2 if x <= 1, ...

### Solution 1: Piecewise Function Case Analysis

1. Strategy: f is built from two formulas glued together at x = 1. ...
2. Case a < 1: On the open interval (-∞, 1), f agrees with the polynomial p(x) = 1 - x². ...
...
5. Conclusion: a ∈ ℝ was arbitrary, ... Hence f is continuous on (-∞, ∞).
```

題目照題目檔的順序編成 Problem 1、2……；`Solution N:` 後面是解題方法，取自 `taxonomy.json` 的固定分類。沒有任何解法通過的題目會寫 `No verified solution was produced for this problem.`。批次資料夾內其他檔案見 [開發說明](docs/開發說明.md) 的「主要輸出」。

## 兩個要人確認的地方（human-in-the-loop）

流程中有兩個地方一定要由人確認，一個在證明之前，一個在發給學生之前：

| | 1. 題目 → Lean theorem | 2. Lean → 自然語言 |
|---|---|---|
| 什麼時候 | 起草 Lean 命題之後、產生證明之前 | 教學步驟翻譯之後、發給學生之前 |
| 看哪個檔案 | `<檔名>.draft.review.md` | `runs/<題目檔名>/solutions.md` |
| 確認什麼 | Lean 命題的意思與原題一致 | 每個步驟的數學正確、沒有跳步，而且用的是 `Solution N:` 後面寫的那個方法 |
| 確認後做什麼 | 在 `<檔名>.draft.json` 把該題的 `statement_fidelity_status` 改成 `confirmed` | 沒有要改的欄位；人看過沒問題才發給學生 |
| 系統會不會擋 | **會**：這次要跑的題目中只要有一題是 `unresolved`，系統就拒絕產生證明 | **不會**：系統只擋步驟裡出現 Lean、Mathlib、tactic 這幾個字，不檢查數學對不對 |

- **第 1 點為什麼要確認**：命題寫錯時 Lean 照樣會通過，後面每一步看起來都正常，但都建立在錯的題目上。Lean 只擋得下「命題無法編譯」，擋不下「命題的意思跟原題不同」。
- **第 2 點為什麼要確認**：Lean 驗證的是 proof 本身。把 proof 改寫成英文步驟是另一次模型呼叫，這一段沒有任何驗證，步驟可能漏掉、寫錯，或換成另一個方法。這一點只需要看數學，不需要看懂 Lean。

兩點都可以把內容整段貼給慣用的 AI 協助檢查，但最後要由人判斷。

## 第一次使用

### 1. 安裝環境

需要 Python 3.12 以上、uv、Lean 4 與 elan。

```bash
uv sync
cd lean_project
lake exe cache get
cd ..
```

不要執行 `lake update`。本專案已固定 Lean 與 Mathlib 版本。

另外要建置 Lean REPL，版本已固定，照下面指令執行即可：

```bash
git clone https://github.com/leanprover-community/repl.git .tools/repl
git -C .tools/repl checkout --detach f0a88bfca1fa6ac75e2a33d1678a3b67c90fb492
cd .tools/repl
lake build repl
cd ../..
```

### 2. 設定 API key：Ollama Cloud 或 OpenRouter 擇一

模型可以走 Ollama Cloud 或 OpenRouter，只需要準備你要用的那一家的 key。key 寫在 repo 根目錄的 `.env`，每一行前面的 `export` 不能省：

```bash
export OLLAMA_API_KEY="你的 key"        # 用 Ollama Cloud 時
export OPENROUTER_API_KEY="你的 key"    # 用 OpenRouter 時
```

每次開新的終端機，先在 repo 根目錄載入：

```bash
source .env
```

程式只讀取環境變數，不會自行開啟 `.env`。少了 `export` 時，變數只存在終端機本身，`uv run` 啟動的程式讀不到，會出現 `缺少環境變數 OLLAMA_API_KEY`（或 `OPENROUTER_API_KEY`）。`.env` 已列入 `.gitignore`。

**用 Ollama Cloud**：目前的 `config.json` 就是這個設定，填好 `OLLAMA_API_KEY` 即可。

**用 OpenRouter**：`config.json` 要改兩處。

1. 在 `apis` 加一項：

   ```json
   "openrouter": {
     "type": "openrouter",
     "base_url": "https://openrouter.ai/api/v1/chat/completions",
     "api_key_env": "OPENROUTER_API_KEY"
   }
   ```

2. 把 `models` 三個模型與 `translation_model` 的 `api` 改成 `"openrouter"`，`model_id` 改成 OpenRouter 上的名稱。兩家的命名格式不同，例如 Ollama 的 `deepseek-v4-flash:0731` 在 OpenRouter 是 `deepseek/deepseek-v4-flash-0731`；其他模型的名稱請到 [OpenRouter 模型列表](https://openrouter.ai/models) 查。

兩家也可以混用：每個模型各自用 `api` 指定走哪一家，兩把 key 都要填。OpenRouter 這條路在目前版本的程式還沒有完整跑過一次，第一次使用請先跑下一步的 preflight。

### 3. 確認系統能跑（preflight）

用範例題目、只用一個模型跑一次，確認連得上模型 API、Lean 也能正常驗證。這一步會實際呼叫模型 API。換了 API 或模型之後也要再跑一次。

```bash
uv run python -m formal_consensus.workflows.preflight \
  --config config.json \
  --input examples/problems.json \
  --model qwen \
  --problem demo_derivative_square
```

## 使用步驟

以範例題目檔 `examples/teacher_exam.json` 為例，換成自己的題目檔時把路徑改掉即可。每次開新的終端機，都要先 `source .env`。

**1. 起草 Lean 命題**

```bash
uv run python -m formal_consensus formalize --input examples/teacher_exam.json
```

系統逐題請 `translation_model` 寫出 Lean 命題，先用 Lean 檢查能否編譯；不能編譯時把錯誤交回模型重寫，最多嘗試三次。接著另外呼叫一次模型，**只給 Lean 命題、不給原題**，說明這個命題實際在說什麼。給了原題的話，模型只會複述原意，看不出命題寫錯的地方。

產生的檔案見「輸出」。草稿已存在時系統會拒絕執行，避免蓋掉人工修改。

**2. 人工確認**

老師或助教照 `teacher_exam.draft.review.md` 逐題比對，一致的題目在 `teacher_exam.draft.json` 裡把該題的

```json
"statement_fidelity_status": "unresolved"
```

改成

```json
"statement_fidelity_status": "confirmed"
```

不一致就修改 `lean_theorem_header` 或刪掉該題。手動修改過的 `lean_theorem_header` 不會重新檢查能否編譯，寫錯的話要到證明階段才會發現。

**3. 產生證明與教學步驟**

```bash
uv run python -m formal_consensus --input examples/teacher_exam.draft.json
```

只要有任何一題仍是 `unresolved`，系統就拒絕執行並列出這些題號，也不會建立批次資料夾。想先跑某一題已確認的題目時，加上 `--unit 題號`（一次只能指定一題）：

```bash
uv run python -m formal_consensus --input examples/teacher_exam.draft.json --unit midterm_q4_piecewise_continuity
```

程式一開始就會印出批次資料夾路徑。中途失敗時，錯誤訊息會附上續跑方式：在原指令後面加上 `--run-dir` 與印出的批次資料夾，已完成的部分不會重跑，也不會再次呼叫模型。

```bash
uv run python -m formal_consensus --input examples/teacher_exam.draft.json --run-dir runs/teacher_exam
```

## 限制

- Lean 通過只代表固定的 Lean 命題有一份通過檢查的證明，不代表命題與原題意思相同。`confirmed` 代表有人比對過，也不代表命題一定正確。
- 每份解法屬於哪個方法（`solutions.md` 裡 `Solution N:` 後面的名稱），是由同一組三個模型投票確認的，其中可能包含寫出這份證明的模型，不是人工判斷。

## 技術細節

證明怎麼產生、每一步的判定規則、批次資料夾的完整內容與測試方式，見 [開發說明](docs/開發說明.md)。
