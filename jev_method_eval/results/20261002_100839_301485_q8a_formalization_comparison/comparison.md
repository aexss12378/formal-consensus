# Q8(a) 命題轉譯比對

本次實際使用既有 `formal_consensus/workflows/formalize.py`，沿用 `config.json` 的 `translation_model`：`glm-5.3-flash`、Ollama、temperature 0.2。模型只收到原題，沒有收到 Codex 先前寫的命題、教師答案或額外的定義域提示。回譯呼叫只收到模型產生的 Lean 命題，沒有收到原題。

## 原題

Find the derivative of the function F(t) = (1/(2t + 1))^4.

來源：`題目/114-1, Calculus(I), Midterm Exam answer.pdf`，第 6 頁，Part II Q8(a)。來源 SHA-256：`91fbd55c64025ff013574476b1b9d013d4a1a35692922a5f686a027afa3cba93`。

## 兩個版本

Codex 在模型呼叫前提出的版本：

```lean
theorem midterm_q8a_derivative (t : ℝ) (h : 2 * t + 1 ≠ 0) :
    HasDerivAt (fun s : ℝ => (1 / (2 * s + 1)) ^ 4)
      (-8 / (2 * t + 1) ^ 5) t :=
```

既有命題轉譯流程實際產生的版本：

```lean
theorem midterm_q8a_derivative (t : ℝ) :
    deriv (fun s => (1 / (2 * s + 1)) ^ 4) t = -8 / (2 * t + 1) ^ 5 :=
```

| 比對項目 | Codex 版本 | 模型版本 |
| --- | --- | --- |
| 函數 | `(1 / (2 * s + 1)) ^ 4` | 相同 |
| 導數公式 | `-8 / (2 * t + 1) ^ 5` | 相同 |
| 適用點 | `2 * t + 1 ≠ 0` | 所有實數 |
| 表述 | `HasDerivAt`，明示導數存在且具有指定值 | `deriv` 的數值等式 |

## 已驗證的差異

在原題的自然定義域 `2 * t + 1 ≠ 0` 上，兩種表述可證等價。這次已用 Lean 完整證明此等價性，沒有使用 `sorry`，也沒有引用兩個占位命題。反向推導成立的原因是本題右側導數公式在分母非零時也非零，因此可由 `differentiableAt_of_deriv_ne_zero` 得到可微，再取得 `HasDerivAt`。

模型版本額外涵蓋 `t = -1/2`。Lean 的實數除以零等於零，因此此處函數值與公式右側都等於零；兩項計算已用 Lean 驗證。Mathlib 的 `deriv` 在不可微的點也定義為零，所以無條件的 `deriv` 等式不能直接解讀成「原題函數在每個實數點都有通常意義的導數」。

模型的回譯說明有指出這個定義域差異，以及 `deriv` 和除以零的慣例。回譯另外聲稱此函數在 `-1/2` 不可微；本次沒有獨立驗證該項聲稱，因此不把它列為本次已證明的結果，也不據此宣稱無條件版本已獲完整證明。

## 編譯與輸出狀態

- 兩個完整命題各附 `by sorry` 後，都通過 Lean 語法與型別檢查；這不代表導數公式本身已證明。
- 定義域內的等價性，以及兩項分母零處的計算，均以沒有 `sorry` 的證明通過 Lean；整份檢查只出現前兩個占位命題的兩則 `sorry` 警告。
- 模型草稿的 `statement_fidelity_status` 仍為 `unresolved`，尚未送入解法生成。
- 沒有修改專案原始碼，也沒有變更模型、提示詞或既有重試流程。
- 實際共呼叫 API 三次：首次沒有回傳必要的 `submit_statement` 工具呼叫；既有流程要求重試後取得命題；第三次做回譯。這是一次流程執行的紀錄，不能用來估計模型可靠度。

保留的檔案：`teacher_problem.json`、`manual_statement.json`、`model_statement.draft.json`、`model_statement.draft.review.md`、`model_statement.draft.records.json`、`api_trace.json`、`lean_comparison_verification.json`。其中 `manual_statement.json` 的驗證備註是 API 呼叫前的快照；後續完整占位編譯及等價性驗證以本報告和 `lean_comparison_verification.json` 為準。API 紀錄包含原始請求內容與回覆，不包含授權標頭或金鑰；臨時 Lean 檔已刪除，驗證原始碼保留在 JSON 紀錄中。

結論：既有轉譯階段算出的函數與導數公式和 Codex 版本一致，差別在是否明確排除分母為零的點。要用於原題的解法生成，應先確認定義域；加上非零條件後，本題可以保留 `deriv` 等式，也可以採用等價的 `HasDerivAt` 表述。本次僅比對並保留草稿，沒有自動修改或確認命題。
