# 相關研究整理

2026-09-19 查的。主題：**形式驗證與數學證明批改／回饋**。

## 怎麼讀這份文件

每篇標了兩件事：

- **在批改流程的哪一層**：`grading`（給分數）／`feedback`（給回饋不給分）／`tutoring`（教學輔導）／`formalization`（只做工具，不碰學生）
- **驗證狀態**：`✔ 親自核` 表示直接開過 arXiv abstract 頁、出版商頁面或 PDF 全文確認；`△ 代查` 表示由子代理回報、我沒有親自開頁確認，引用前要自己核一次

數字一律照抄原文，沒有換算。

---

## A 類　形式系統真的拿來給分數

### A1. Formal Autograding in a Classroom　`grading`　✔ 親自核

Dragana Milovančević, Mario Bucev, Marcin Wojnarowski, Samuel Chassot, Viktor Kunčak（EPFL）／2025／ESOP 2025, LNCS／DOI 10.1007/978-3-031-91121-7_7
PDF：https://lara.epfl.ch/~milovanc/papers/esop25.pdf（20 頁）

**跟本研究結構最像的一篇。** 拿參考解當基準，用形式驗證器證明學生提交與參考解等價。

原文照抄：

> Out of the 400 students taking the course, 201 students agreed to...

> in a total of 719 submissions. After removing byte-identical files, we were left with 709 submissions.

> ...terexample (46%). Column C shows the number of submissions that our verifier proved equivalent to the reference solution, and therefore correct (13%). The remaining submissions are neither provably correct nor provably incorrect (42%)

> Our course uses Scala, so we adopt the Stainless verifier

| | |
|---|---|
| 規模 | 400 學生（201 人同意）、709 份提交、4 題 |
| 證明等價 | **13%** |
| 證偽（有反例） | **46%** |
| 兩邊都證不出來 | **42%** |
| 驗證器 | Stainless（Scala），不是 Lean |
| 領域 | 程式設計作業，不是數學證明 |

**對本研究的意義**：論述上是資產。同樣構想在程式領域已驗證可行且量出天花板，數學領域零篇。但那 42% 要主動處理——它是「形式化學生答案」這條路的極限，本研究不走那條，所以不會踩到，但也享受不到機器判定的確定性。

### A2. On Exams with the Isabelle Proof Assistant　`grading`　△ 代查

Frederik Krogsdal Jacobsen, Jørgen Villadsen（DTU）／2023／arXiv:2303.05866／EPTCS 375, pp. 63–76（ThEdu'22）

> The use of Isabelle enables almost automatic grading of large parts of the exam.

abstract 裡**沒有任何數字**。科目是 automated reasoning／邏輯課。

**前提**：學生直接用形式語言作答，所以不需要「把自然語言翻成形式語言」那一步。

### A3. Autograding Weakest Precondition Proofs and Dafny Specifications　`grading`　△ 代查

Graeme Smith, Hunter Whitlock／2026／FMTea 2026, LNCS vol. 16566, pp. 31–49／DOI 10.1007/978-3-032-26743-6_3

> There is relatively little work, however, on autograding in formal methods courses where the emphasis is not on programming, but on writing proofs and specifications.

三項設計目標：(i) 新版作業可重用、最少人力，(ii) **fine-grained marking，給部分分數**，(iii) 不人為限制學生的技巧。

abstract 無數字。用 Dafny。**partial credit 的設計值得當批改設計的骨架參考。**

### A4. Lurch: A Word Processor that Can Grade Students' Proofs　`feedback`（標題宣稱 grading）　△ 代查

Nathan C. Carter, Kenneth G. Monks／2013／CEUR-WS Vol-1010

自家 OpenMath-based 檢查器，不是 Lean/Coq/Isabelle。abstract 只講 check steps，沒有驗證過的分數輸出。2025 年的 survey 引作者原話說它能 grading，但論文本身沒有。

---

## B 類　形式系統給回饋，不給分數

**這一類是「做回饋」路線的先例。**

### B1. Diproche　`feedback`　✔ 親自核

Merlin Carl, Hinrich Lorenzen, Michael Schmitz（Europa-Universität Flensburg）／2022／arXiv:2202.08131／EPTCS 354, pp. 59–70（ThEdu'21）

標題：Natural Language Proof Checking in Introduction to Proof Classes — First Experiences with Diproche

abstract 原文：

> We present and analyze the employment of the Diproche system, a natural language proof checker, within a one-semester mathematics beginners lecture with **228 participants**. The system is used to check the students' solution attempts to proving exercises in Boolean set theory and elementary number theory and to give them **immediate feedback**. The benefits of the employment of the system are assessed via a questionnaire at the end of the semester and via analyzing the solution attempts of a subgroup of the students.

| | |
|---|---|
| 規模 | **228 人**、一學期 |
| 課程 | 數學初階課，Boolean set theory + 初等數論 |
| 做什麼 | 學生寫受控自然語言 → 自動形式化 → ATP 驗 → 立即回饋 |
| 給分數嗎 | **不給**。abstract 裡沒有任何評分機制 |
| 評估方式 | 期末問卷 + 分析一個子群的解題嘗試 |

**對本研究的意義**：這是課堂實證規模最大的同類研究，但它走的是本研究明確排除的那條路——**形式化學生的答案**。同樣用形式化，Carl 這一系用在學生答案上（只做到回饋），本研究用在參考答案上（目標是評分）。這個對照在 related work 裡很好用。

同系列其他篇（全部 △ 代查）：

- **Using Automated Theorem Provers for Mistake Diagnosis in the Didactics of Mathematics**（arXiv:2002.05083, 2020）——「Anti-ATP」，用常見形式謬誤取代健全推理規則來診斷錯誤。`formalization`，無學生數據
- **Improving the Diproche CNL through Autoformalization via LLMs**（arXiv:2303.17513, EPTCS 400）——把 Diproche 的 Prolog 形式化改成 LLM。`formalization`，無數字
- **Automatized Evaluation of Formalization Exercises in Mathematics**（arXiv:2006.01800, 2020）——檢查學生的形式化作業（math dictations、Game of Def），不是證明
- **Sociomathematical Norms and Automated Proof Checking**（Journal of Humanistic Mathematics 14(2), 2024, DOI 10.5642/jhummath.GVWG5301）——Flensburg 2020/21 冬季學期的反思，無新數據

### B2. Waterproof 系列　`feedback` / `tutoring`　△ 代查

- **Waterproof: Educational Software for Learning How to Write Mathematical Proofs**（arXiv:2211.13513, EPTCS 400, pp. 96–119）。Jelle Wemmenhove 等 11 人。原文：「the software provides feedback on the logical validity of each step」。另有一句值得注意：Waterproof 用於 TU/e 的 Analysis 1 課程已四年，學生開始把工具的證明步驟措辭用在手寫證明裡
- **The Educational Proof Assistant Waterproof in an Introductory Proof Course**（arXiv:2606.26809, ThEdu 2026）。Pim Otte, Rogier Bos, Johan Commelin, Jim Portegies。Utrecht University，199 人修課／80 人同意並完成 entry survey／34 人在 Waterproof 組／21 人至少完成一題／16 人至少完成五題。原文自承：「As students **self-selected** into using Waterproof rather than being randomly assigned, these results are **suggestive rather than causal**」

### B3. ProofBuddy　`tutoring`　△ 代查

Nadine Karsten, Frederik Krogsdal Jacobsen, Kim Jana Eiken, Uwe Nestmann, Jørgen Villadsen／2023／arXiv:2308.06970／EPTCS 382, pp. 1–21（TFPIE 2023）

Isabelle 為基礎的網頁工具，收集學生互動的細粒度資料。abstract 只說在 DTU 做過「preliminary usability study」，無人數。

後續：**ProofBuddy: How it Started, How it's Going**（arXiv:2505.13474, EPTCS 419, pp. 90–111）

### B4. 其他　△ 代查

- **OnlineProver**（arXiv:2505.05987, EPTCS 419, pp. 55–74, 2025）——自然演繹的視覺化教學工具，非 Lean。`feedback`，abstract 無數字
- **Hazel Prover**（arXiv:2608.23309, 2026）——「deploying Hazel Prover in two different classes」。值得注意的負面結果：「the first design did not effectively achieve transfer to pen-and-paper proofs」

---

## C 類　Lean 進數學課堂，批改仍由人做

全部 △ 代查。

| 論文 | 規模 | 性質 |
|---|---|---|
| **Teaching "Foundations of Mathematics" with Lean**（arXiv:2501.03352, 2025）<br>Bottoni, Cattaneo, Sacikara（UZH） | 11 週；訪談 **5 位 Lean + 4 位 Non-Lean**；全班期末考成績做 t-test 與 Mann-Whitney U | 少數做假設檢定的教學研究，但訪談 n=9 太小 |
| **Using the proof assistant Lean in undergraduate mathematics classrooms**（ZDM 56, pp. 1517–1529, 2024, DOI 10.1007/s11858-024-01577-9）<br>Hanna, Larvor, Yan | **3 個學生、1 道題**（double negation） | 質性 |
| **Interactive theorem provers for university mathematics**（IJMEST, 2023, DOI 10.1080/0020739X.2023.2178981）<br>Iannone, Thoma | **99 份問卷 + 37 個訪談** | 這群裡樣本最大。量的是感受與困難，不是成效 |
| **'It Feels Like Sort of Cheating…'**（Digital Experiences in Mathematics Education, 2025, DOI 10.1007/s40751-025-00193-w）<br>Iannone, Thoma | **2 個學生**，Natural Number Game 任務訪談 | 質性 |
| **Learning about Proof with LEAN: the Abundant Numbers Task**（IJRUME 8, pp. 64–93, 2022, DOI 10.1007/s40753-021-00140-1）<br>Thoma, Iannone | **36 份學生證明**的質性分析 | 書目已證實，abstract 文字未親自核 |
| **Maths with Coq in L1**（arXiv:2505.05990, EPTCS 419, pp. 112–123）<br>Kerjean, Mayero, Rousselin | 18 小時課、3 年 | 經驗報告，abstract 無人數 |
| **Learning how to Prove: From Coq to Textbook Style**（arXiv:1803.01466, EPTCS 267）<br>Böhne, Kreitz | abstract 自承「mostly conceptional」 | 設計了 Coq 到自然語言證明之間的三種中間文體 |
| **Interactive Theorem Provers for Proof Education**（SPLASH-E 2025, DOI 10.1145/3758317.3759679）<br>Mahinpei, Horta Ribeiro, Milano | user study 人數未在 abstract | 發現形式化證明比紙筆證明更冗長，影響學生對難度的感受 |

**綜述**：**Proof Assistants for Teaching: a Survey**（arXiv:2505.13472, EPTCS 419, pp. 1–27, 2025）。Tran Minh, Gonnord, Narboux。27 頁，寫 related work 最省力的入口。子代理掃全文的結果：**整篇 survey 裡唯一被描述成有 grading 功能的系統是 Lurch**，其餘都停在 verification／feedback／tutoring。

---

## D 類　有批改／回饋，但完全不用形式系統

### D1. Autograding Mathematical Induction Proofs with NLP　`grading`　△ 代查（引文已由子代理開內文確認）

Chenyan Zhao（UIUC）, Mariana Silva（UIUC）, Seth Poulsen（Utah State）／arXiv:2406.10268（v2 2025-02-19）／期刊版 International Journal of Artificial Intelligence in Education, DOI 10.1007/s40593-025-00498-2

**這個領域學生資料規模最大的一篇。**

| | |
|---|---|
| 訓練資料 | 4 題歸納法證明，非空證明 P1 1623 / P2 1288 / P3 342 / P4 333 份 |
| 人類評分者 | **9 位研究生、4 所學校**，每人批 4 題各 15 份共 60 份 |
| 使用者研究 | 169 人（Self-eval 68／First 59／Random 42） |
| 課程 | UIUC Discrete Mathematics (CS173) |
| 最佳模型 | Llemma34b／Llemma7b，**90.0%／90.2%** 平均準確率 |
| 人類與標註一致率 | **86.6%** |

**兩句必須正面接招的原文**：

> To deal with verifying longer proofs, researchers have also attempted autoformalization [39], translating natural language into formal logic. However, even with several years of research, none of the existing work is able to translate even half of the proofs to formal logic [39]. **The low success rate makes autoformalization not suited for grading mathematical proofs at the moment.**

> To our knowledge, no tools have successfully dealt with grading mathematical proofs using natural language processing.

引的 [39] 是 Wu et al., Autoformalization with Large Language Models, arXiv:2205.12615（2022）——**證據停在 LLM 起飛之前，這是可攻的點**。

另一個對「做回饋」路線有用的發現：

> students are able to make significant improvements to their proofs using the feedback from the autograder, but **students still do not trust the AI autograders as much as they trust human graders**

### D2. Imperial AI Teaching Assistant　`feedback`　△ 代查

Aron Gohr, Marie-Amelie Lawn, Kevin Gao, Inigo Serjeant, Stephen Heslip／2026／arXiv:2601.03458

| | |
|---|---|
| 規模 | **65 份解答、3 位人類評分者**（0–5 分，兩位各批一半、一位獨立批全部） |
| 課程 | Imperial College London 一年級必修 Introduction to University Mathematics |
| 指標 | 與人類評分的 Pearson correlation |
| 部署 | Imperial 的作業平台 Lambdafeedback |

> the quality of the feedback generated is comparable to that produced by human experts when assessing early undergraduate homework

**這是「做回饋」路線門檻最低的可引先例**：65 份、3 位評分者就進得了 arXiv 並實際部署。

### D3. ProofGrader / Reliable Fine-Grained Evaluation of Natural Language Math Proofs　`grading`（評模型不評學生）　✔ 親自核

Wenjie Ma, Andrei Cojocaru, Neel Kolhe, Bradley Louie, Robin Said Sharif, Haihan Zhang, Vincent Zhuang, Matei Zaharia, Sewon Min／2025-10-14／arXiv:2510.13888／ICLR 2026

| | |
|---|---|
| 資料集 | ProofBench：**145 題**、六個競賽（USAMO、IMO、Putnam 等）、**435 份 LLM 生成解答**，專家標註 |
| 給批改模型的 context | **參考解 + 評分表（marking scheme）** |
| 成績 | 對專家分數 **MAE 0.926**；best-of-16 從 2.48 提到 4.14，人類上限 4.62，**closing 78% of the gap** |
| 評分表怎麼來 | 給問題與參考解，讓模型輸出給分／扣分條件清單 + 不該給分的瑣碎情況清單 |
| 評分表品質 | 約 **85%** 被判定為合理且高品質 |
| 參考解來源 | **競賽官方解，沒有任何驗證機制** |

明確拒絕形式化路線的原文：

> While formal math (e.g., Lean) offers absolute certainty, it remains detached from the natural language used in most human mathematics education and research; furthermore, **automatically translating natural-language proofs into formal languages is brittle and remains extremely challenging.**

### D4. 其他　△ 代查

- **Cost-Effective Automated Judging of Natural-Language Mathematical Proofs**（arXiv:2608.00004, 2026）——200 份驗證樣本、1000 份完整 benchmark、4 次重複、成本低 100 倍。設定是「candidate proof + **ground-truth proof** + human-grading rubric」，ground-truth 是人寫的不是驗證過的
- **Pseudo-Formalization for Automatic Proof Verification**（arXiv:2605.20531, 2026, Stanford）——明確放棄 Lean、改用半形式化格式。原文：「translating them into formal languages remains challenging in many frontier math settings」。**「為什麼大家繞開 Lean」的代表作**
- **Practical Online Assessment of Mathematical Proof**（arXiv:2006.01581, 2020）——Bickerton & Sangwin。STACK 一系的做法：**繞開批改證明，改考證明理解題**。abstract 無人數，自承 preliminary
- **Efficiency of Learning from Proof Blocks Versus Writing Proofs**（arXiv:2211.09609, SIGCSE 2023）——**332 人 RCT、3 組**。不碰形式化（拖放式證明積木），但這是證明教學領域設計最嚴謹的實驗

---

## E 類　形式化本身的可靠性（不涉及批改，但決定路線可不可行）

這一類不是批改研究，但它決定了「能不能把學生的作答形式化」這個問題的答案。

### E1. Beyond Compilation　✔ 親自核

Ke Zhang, Patricio Gallardo Candela, Sudhir Murthy, Yi Xie, Zhi Wang, Maziar Raissi／2026／arXiv:2606.31002

標題：Beyond Compilation: Evaluating Faithful Natural-Language-to-Lean Statement Formalization

abstract 原文：

> On an independently audited random sample, it agrees with human majority on 89.7% of cases (Wilson 95% CI: 82.1--94.3%). Across eight systems evaluated on 400 graduate-level statements, every system has a nonzero compile–faithfulness gap, whose observed magnitude ranges from **3.0 to 29.0 percentage points**.

| | |
|---|---|
| 規模 | 8 個系統、400 道研究所程度的陳述 |
| compile–faithfulness gap | 每個系統都大於 0，範圍 **3.0 至 29.0 個百分點** |
| 最佳系統（GPT-5.2 agent） | 編譯成功率 **89.5%**、語意忠實度 **60.5%**（差 29.0 個百分點） |

**意義**：編譯過不代表意思對。編譯成功的裡面將近三分之一表達的不是原本的命題，而編譯器不會告訴你。這是本研究「不形式化學生作答」最有力的依據，也跟我們自己踩到的 `autoImplicit` 是同一回事。

### E2. The Faithfulness Gap　✔ 親自核

Noor Islam S. Mohammad, Tamim Sheikh／2026／arXiv:2606.16541

標題：The Faithfulness Gap: Certifying Semantic Equivalence Between Natural-Language and Formal Mathematical Statements

abstract 原文：

> Autoformalization, translating natural-language mathematics into formal proof assistants, is bottlenecked not by translation fluency but by faithfulness: a formal statement can typecheck and be provable, yet still encode a different theorem than the source intended.

方法為 Bidirectional Provability Fingerprinting (BPF)：

| | |
|---|---|
| BPF 偵測率 | **89.6%** 的 drifted formalizations，false-positive **3.0%** |
| 單靠 typecheck | 只抓到 **41.2%** |
| LLM-judge baseline | **63.3%** |
| 資料集 | 2,183 對 NL／Lean 4，**with controlled drift labels** |

**重要限制**：那是**人工標註漂移**的資料集，不是真實 autoformalization 的輸出。89.6% 是在「已知哪些是錯的」的人造資料上測得的偵測率，與真實場景有距離。引用時必須帶上這個前提。

### E3. Faithful Autoformalization via Roundtrip Verification and Repair　✔ 親自核

Daneshvar Amrollahi, Jerry Lopez, Clark Barrett（Stanford）／2026／arXiv:2604.25031

abstract 原文：

> We propose a roundtrip verification approach which does not require ground-truth annotations: formalize a statement, translate the result back to natural language, re-formalize, and use a formal tool to check logical equivalence. When the two formalizations agree, this provides evidence of a faithful formalization.

**領域是法律條文**：Texas Transportation Code 與 Texas Parks and Wildlife Code。模型為 Claude Opus 4.6 與 GPT-5.2。

abstract 報的數字：未通過等價檢查的條文，NLI drift 高出 **1.4–2.5 倍**。

**注意**：早期草稿曾引用「形式等價從 45–61% 提高到 83–85%」，該數字**在 abstract 查無出處**，已從簡報移除。若要引用內文數字，須自行讀全文確認。

### E4. Hattori et al.（informalization）　△ 代查

Seiji Hattori, Takuya Matsuzaki, Makoto Fujiwara／2025／arXiv:2509.09726

標題：Natural Language Translation of Formal Proofs through Informalization of Proof Steps and Recursive Summarization along Proof Structure

把 Lean proof 逐步 informalize，再沿證明結構遞迴摘要，產出可讀的自然語言證明。在兩個資料集測試：大學課本證明的形式化版本、既有的 Lean 證明庫。**abstract 無量化數字**，需讀全文。

### 對本研究的意義

**正向（自然語言 → Lean）的錯誤無法用編譯檢查出來。** round-trip 是目前主流的補救方式，但兩篇的證據都不在數學：一篇用人工標註漂移的資料集，一篇做法律條文。**數學領域目前沒有 round-trip 的數據。**

**反向（Lean → 自然語言）風險低**，因為背後那份 proof 已經驗證過，翻得不精準只會讓說明變模糊，不會把對的講成錯的。本研究用反向把驗證過的參考答案轉成學生看得懂的說明。

---

## 沒找到的方向（子代理明確回報「搜過沒有」）

1. **用 Lean 批改數學系學生的紙筆作業／考試並給分數** —— 零篇。用了 6 種以上措辭搜過
2. **把形式驗證過的參考證明當作 LLM 批改的依據** —— 零篇。RefGrader、ProofGrader、D4 用的參考解都是人寫的自然語言，沒驗證過
3. **Agda 用於批改** —— 零篇，只在教材出現
4. **Rocq（Coq 改名後）名下的批改論文** —— 零篇
5. **STACK 生態裡接形式驗證** —— 零篇。STACK 刻意繞開證明批改

### 有工具、沒論文的空白

leanprover-community 官方 teaching/resources 頁面列出兩套**實際在打分數**的 Lean autograder：

- `robertylewis/lean4-autograder-main`（接 Gradescope）。README：「The attribute `@[autogradedProof pts]` is used to denote exercises where the student should complete a proof of a theorem statement provided by the instructor. The autograder awards `pts` number of points if the student's proof is complete.」
- `adamtopaz/hw_template`（GitHub Classroom）

**兩套都沒有掛任何學術論文。** 這是可以直接主張的 gap：實務上 Lean 打分數已經在跑，但沒人寫成研究。

---

## 結論與定位

### 三層

1. **概念上做過，但在程式設計課** —— EPFL（A1）。拿參考解當基準、用驗證器判等價，400 學生、709 份提交，13%／46%／42%
2. **形式系統當批改器做過，但學生直接寫形式語言** —— Isabelle 考試（A2）、Dafny（A3）。不需要翻譯那一步
3. **Lean 驗證過的參考答案池拿去批改自然語言，零篇**

### 那兩句反對意見打不到本研究

UIUC（D1）和 ProofGrader（D3）都明確否決形式化路線，但**它們打的是「把學生的證明形式化」**：

- UIUC 的理由是「連一半都翻不過去」——翻的是學生的爛證明
- ProofGrader 的理由是「brittle」——同樣指學生答案

本研究**學生答案全程不進 Lean**，只有參考答案那一側形式化。瓶頸在「翻譯學生的爛證明」，不在「翻譯乾淨的標準解」。這個區分要在論文裡明講。

### 一個必須先回答的質疑

**驗證過的參考答案不等於能判定學生答案。** 參考答案的正確性是個常數，不會自動轉成對學生每一步的判斷力。

EPFL 的 13% 是機器證出來的；本研究的批改還是 LLM 在讀 proof code。所以要能回答：**驗證過的參考解，在批改流程的哪一步發生作用？**

- 當 rubric 生成的依據？（ProofGrader 的做法，但它的參考解沒驗證）
- 當里程碑清單的來源？（RefGrader 的做法）
- 當判斷歧異時的裁決依據？

文獻裡沒有現成答案，得自己實測。審稿人看到 EPFL 那篇一定會問。

### 樣本規模參照

```
數學教育質性研究      2 人 / 3 人 / 36 份 / 99 份問卷 / 199 修課取 34 人
自動批改計算研究      65 份 + 3 位評分者（Imperial，已部署）  ← 下限
                     332 人 RCT（Proof Blocks, SIGCSE 2023）
                     3586 份證明 + 169 人 + 9 位評分者（UIUC）
```

**門檻不在人數，在有沒有人類評分基準線與一致性數字。** 本研究 40 人 × 2 題 = 80 份在 Imperial 的下限之上，但**第二位助教重改一部分算一致率是必要的**。

### 評估指標：沒有一篇報告評分者間信度

各篇用的指標與數字（照抄）：

| 研究 | 指標 | 數字 |
|---|---|---|
| LLMs as TA（arXiv:2607.01247） | MAE、RMSE、NRMSE、Pearson、exact agreement | 最佳題目層級 MAE **1.87**、RMSE 2.53；總分 Pearson **0.58** |
| ProofGrader（arXiv:2510.13888） | MAE | **0.926**（對專家分數） |
| Imperial AI TA（arXiv:2601.03458） | Pearson correlation | abstract 未給數字；3 位人類評分者、0–5 分 |
| UIUC Autograding（arXiv:2406.10268） | accuracy、人類與標註一致率 | 模型 **90.0%／90.2%**；人類與研究團隊標註 **86.6%** |
| RefGrader（arXiv:2510.09021） | 與人類評分的一致度 | **abstract 未報具體數字**。資料為 90 份 Gemini 2.5 Pro 解答（1–4 分）與 MathArena IMO/USAMO 2025（0–7 分）。曾聽聞的 QWK 0.359→0.42→0.72 查無出處，引用前須讀內文確認 |
| EPFL（ESOP 2025） | 分類比例 | 等價 13%、證偽 46%、判不出 42% |

**關鍵觀察：沒有一篇報告評分者之間的信度（inter-rater reliability）作為基準線。**

UIUC 那篇有 9 位人類評分者，但報的是「人類與研究團隊標註的一致率 86.6%」——那是人類與黃金標準的一致，不是人類彼此之間的一致。Imperial 有 3 位評分者，但只報與模型的 Pearson。

這代表既有研究的數字都缺一個參照點：**當模型與人類的 MAE 是 1.87 時，無從判斷那算好還是壞，因為不知道兩位人類之間的 MAE 是多少。**

### 本研究應採用的指標

| 層級 | 指標 | 用途 |
|---|---|---|
| 主要 | **誤扣率**（AI 評分低於助教的比例） | 教育現場最不能接受的錯誤類型 |
| 次要 | **漏扣率**（評分高於助教）、MAE、RMSE | 與既有文獻對照 |
| 一致性 | **QWK**（Quadratic Weighted Kappa） | 分數是有序整數；QWK 加重懲罰差距大的不一致，MAE 不會 |
| 基準線 | **助教間 IRR** | 第二位助教重批部分考卷。缺少這項，上述數字都沒有參照點 |
| 穩定性 | 重複施測的評分變異 | 2026-09-18 實測：同一份證明送同一模型判定五次結果不一致，temperature 降至 0 後六組中仍僅兩組一致 |

誤扣率與漏扣率必須分開報，不可只報 MAE：一組全部誤扣、一組全部漏扣，MAE 可能相同，但對學生的意義相反。

**IRR 與「請助教圈註扣分位置」可以同一趟請託完成**：第二位助教重批時順便圈註，一次取得評分者間信度與扣分位置標註兩項資料。

### 關於「做回饋」這條路

不需要助教的分數當 ground truth，**只要學生答案就能做**。這大幅降低資料門檻。

三種評估方式，門檻由低到高：

1. **人類評分者評回饋品質** —— Imperial（D2）的做法，65 份、3 位評分者、Pearson。門檻最低
2. **學生用了回饋後有沒有改進** —— UIUC（D1）做了，最有力，但需要學生重做一次
3. **回饋有沒有指對地方** —— 要有助教標註的扣分位置，回到原本的門檻

回饋跟驗證過的參考答案池很搭：可以告訴學生「這條路確實走得通」，或「你走的這條路在池子裡沒有，請檢查」——後者正好用到多份參考解的價值。

**2026-09-20 的設計決定**：用反向（Lean → 自然語言）把驗證過的 proof 轉成學生看得懂的說明，作為回饋的內容。這條路繞過了一個原本無解的質疑——

> 驗證過的參考答案不會自動變成對學生每一步的判斷力。

該質疑針對的是**批改**：要給分數就得判斷學生寫的每一步，而參考答案的正確性幫不上那件事。但**回饋不需要判斷每一步**，它只要把正確的做法呈現給學生看，這時參考答案的正確性就是全部。E4（Hattori et al.）是這條路的技術先例，E 類結論說明了為什麼反向風險低。

新增的評估問題：轉出來的中文學生看不看得懂、轉得對不對。這不能用誤扣率量，要用人類評分者評（Imperial AI TA 的做法）。

要注意 UIUC 測出的接受度問題：「students still do not trust the AI autograders as much as they trust human graders」。
