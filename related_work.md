# 相關研究整理

2026-09-19 查的，2026-09-20 把全部論文讀過全文（不只摘要）補完。主題：**形式驗證與數學證明批改／回饋**。

## 怎麼讀這份文件

每篇標了兩件事：

- **在批改流程的哪一層**：`grading`（給分數）／`feedback`（給回饋不給分）／`tutoring`（教學輔導）／`formalization`（只做工具，不碰學生）
- **驗證狀態**：`✔ 已讀全文` 表示讀過 arXiv／EPTCS／CEUR 全文或可存取的 PDF，不是只看摘要；`△ 代查` 現在專指**全文讀不到**（Springer／ACM／Taylor & Francis 等付費牆擋下、或機構典藏回 403），這類條目仍停在 abstract 層級，引用前要註明「讀不到全文」，不能假裝核實過

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

**全文補充（讀完整篇 20 頁之後）**：

- Stainless 怎麼判等價：不是拿學生跟參考解跑相同測資比對輸出，是把參考解當 spec，用 functional induction 自動生成驗證條件（VC）交給 SMT solver（Z3、cvc5、Princess）證兩者語意等價
- 那 42% 不是單一原因：論文 Table 2 把結果拆成 S(編譯錯)/TS(安全檢查過不了)/I(反例)/C(證對)/TO(equivalence timeout) 五欄，42% 是 TS 加 TO 合計。**論文自己講多數 timeout 的根因是「只給一份參考解」**：「We believe that this difference is due to the scarcity of reference solutions: in our experiment, we only provided one reference solution per exercise.」中途加了第二份參考解後成功率就提升
- **參考解本身的正確性全程沒被驗證或討論**——Threats to Validity（Section 5）沒有一句提到這件事，全程假設老師寫的參考解是對的
- Limitations／Threats to Validity（Section 5，原文有獨立章節）：編譯錯占近三分之一提交，歸咎於學生本地只能編譯 Scala 不能跑 Stainless；完全不做語法／風格檢查；等價檢查器抓不出「用迴圈+變動」跟「純函式」寫法的差異，兩者被歸同一類；只在一門課、一學期、709 份提交跑過，自認是 pilot study 不宣稱能推廣；只適用輸入輸出定義明確的題目，不涵蓋開放式問題
- 論文自己也踩到等價檢查器的反面問題：Figure 5a 顯示同一演算法因為 Stainless 拆解成內部函式再個別比對，兩個內部函式剛好不等價，導致整體判不出來；換另外兩套等價檢查工具（REVE、RVT）結果一樣。這跟本研究共享池「同方法換個寫法就被當成不同」的擔憂是同一類問題，方向相反——他們是漏判相同，我們原本擔心的是漏判不同
- 給分機制沒有明確的全有全無規則，但討論「suboptimal implementation」時提到：純教學題可以給滿分＋客製回饋，效能導向的課程則 partial points 較合適，是設計選項而非硬性規則

**對本研究的意義**：論述上是資產。同樣構想在程式領域已驗證可行且量出天花板，數學領域零篇。但那 42% 要主動處理——它是「形式化學生答案」這條路的極限，本研究不走那條，所以不會踩到，但也享受不到機器判定的確定性。**更重要的是這篇留下兩個沒處理的洞，剛好是本研究的設計在回應**：(1) 42% 判不出來多數死在「只給一份參考解」，本研究用多模型共享池產生多份參考解，直接對症；(2) 參考解本身的正確性從頭到尾是個沒人查核的假設，本研究用 Lean 驗證過，把這個假設坐實。

### A2. On Exams with the Isabelle Proof Assistant　`grading`　✔ 親自核（已讀全文）

Frederik Krogsdal Jacobsen, Jørgen Villadsen（DTU）／2023／arXiv:2303.05866／EPTCS 375, pp. 63–76（ThEdu'22）

> The use of Isabelle enables almost automatic grading of large parts of the exam.

**前提**：學生直接用形式語言作答，所以不需要「把自然語言翻成形式語言」那一步，跟本研究的場景完全不同，不會被本研究的核心問題（自然語言忠實度）踩到。

**全文補充**：

- 考試形式：兩小時筆試，全程可查資料但不能問人，交一份要填的 Isabelle 檔＋一份定義庫檔。5 大題等權重，每題再拆一易一難兩小題
- **「幾乎自動」不是全自動**：Isabelle 判斷證明對錯，但仍需人工複查兩件事——風格好壞扣分、**確認學生沒有偷改題目給的定義讓自己去證別的、更簡單的命題**。原文：「all that is needed to grade the exam are a few manual checks for style and to make sure that the students have not changed any definitions such that they are proving something different than what they were asked to.」**這跟本研究的 `autoImplicit` 問題同源**：形式系統只保證「證明本身邏輯正確」，不保證「證的是不是原本要證的那個命題」，手寫 theorem statement 一定要額外設一道檢查——這正是本研究加 `set_option autoImplicit false` 的動機，兩篇可以並列引用
- 明確拒絕全自動化的理由：「For larger courses it may be desirable or necessary to completely automate the grading, but doing so puts much stricter constraints on the kinds of questions we can ask... it becomes impossible to give partial points to students who have the right proof idea, but hand in files with minor syntax errors.」——partial credit 與全自動化互斥，是這篇的核心權衡，跟 ProofGrader／UIUC 那些「模型給分」的路線形成對照：形式驗證這邊反而是「要嘛全自動零彈性，要嘛留人工才能給部分分數」
- 無參考解比對：學生直接寫 Isabelle 證明，Isabelle 判的是「這是不是一個有效的證明」，沒有等價檢查這一層，跟 A1 完全不同路
- 數字：41 名註冊學生，36 通過（5 缺考、2 到期前退選）；69 名原始選課生中超過三分之一在期末考前就退選；平均成績 9.9/12（丹麥制，12=A，10=B）

### A3. Autograding Weakest Precondition Proofs and Dafny Specifications　`grading`　△ 代查（確認讀不到全文，Springer 付費牆）

Graeme Smith, Hunter Whitlock／2026／FMTea 2026, LNCS vol. 16566, pp. 31–49／DOI 10.1007/978-3-032-26743-6_3

> There is relatively little work, however, on autograding in formal methods courses where the emphasis is not on programming, but on writing proofs and specifications.

三項設計目標：(i) 新版作業可重用、最少人力，(ii) **fine-grained marking，給部分分數**，(iii) 不人為限制學生的技巧。

abstract 無數字。用 Dafny。**partial credit 的設計值得當批改設計的骨架參考。**

**確認讀不到全文**：DOI 連結轉到 Springer 登入頁，作者（University of Queensland）個人頁面出版列表也只連到付費頁，沒有另放預印本。查了對應的一場受邀演講公告，摘要沒有比論文摘要更多資訊。這篇目前只有摘要可讀，引用時不可假裝讀過全文。

### A4. Lurch: A Word Processor that Can Grade Students' Proofs　`feedback`（標題宣稱 grading）　✔ 親自核（已讀全文）

Nathan C. Carter, Kenneth G. Monks／2013／CEUR-WS Vol-1010

自家 OpenMath-based 檢查器，不是 Lean/Coq/Isabelle。**讀完全文確認**：完全沒有數字分數或等第輸出，回饋是逐步驟三色圖示（綠=對、紅=錯、黃=有用到但未交代理由的前提）。全文找不到任何「grade／score／points」數字輸出的描述——標題的 "Grade" 是行銷用詞，論文本體從頭到尾只講 step-checking。技術基礎確認是 OpenMath（原文：「Lurch is built on OpenMath...as well as several other technologies, including Qt」）。不是形式驗證器，是使用者自訂規則的檢查器，作者明講不跟 Mizar、Coq 比：「Lurch has no such capabilities, nor should it, because if it did proofs for the student, that would defeat the purpose」。測試規模：兩門課（Bentley University 2008 秋、University of Scranton 2013 春），沒給學生人數，只有問卷質性回饋。一個誠實揭露：「Very rarely, a student would find a case in which Lurch incorrectly graded their work. This happened only twice in the most recent semester of testing」——連使用者自訂規則的簡單檢查器都會判錯，可以佐證「形式化檢查不等於零風險」，但引用時要說明這是不同類型的系統（自訂規則，非標準邏輯庫）。2025 年的 survey 引作者原話說它能 grading，但論文本身沒有輸出過分數。

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

**全文補充**：

- CNL 具體長相（受控德文）：`Es sei x eine ganze Zahl. Zeige: Wenn x gerade ist, dann ist 2-3*x gerade. Beweis: Es sei x gerade. Dann gibt es eine ganze Zahl k mit x=2*k...`——貼近教科書寫法但語法嚴格
- 形式化／批改吻合率（現有摘要沒有的數字）：數論 184 份裡 57% 判定正確、16% 判定有小錯；集合論 86 份裡 51% 正確、16% 有小錯
- 問卷（127/228 人填）：63% 覺得打字輸入不容易；只有 19% 看得懂錯誤訊息在講什麼；只有 33% 會用回饋去改進；27% 覺得對理解證明有正面幫助；88% 收到「正確」訊息會感到鼓勵，41% 收到錯誤訊息會感到挫折
- **不給分數的真正理由（要修正認知）**：原文「In order not to place an excessive burden on the student assistants it was decided not to mark the student solutions to the Diproche problems by hand.」——**是人力考量，不是自動化不可靠所以不敢給分**。引用時不能講成後者，跟本研究要強調的「批改比回饋難」是不同角度

**對本研究的意義**：這是課堂實證規模最大的同類研究，但它走的是本研究明確排除的那條路——**形式化學生的答案**。同樣用形式化，Carl 這一系用在學生答案上（只做到回饋），本研究用在參考答案上（目標是評分）。這個對照在 related work 裡很好用。

同系列其他篇：

- **Using Automated Theorem Provers for Mistake Diagnosis in the Didactics of Mathematics**（arXiv:2002.05083, 2020）——「Anti-ATP」，✔ 已讀全文。機制：正規 ATP 卡住時換一套「刻意寫錯的推理規則」去驗，驗過就回報踩到哪種常見謬誤（例：Inverse Contraposition，從 A→B 和 ¬A 錯誤推出 ¬B→¬A）。**確認完全沒有實測數據**，規則清單是作者自陳「個人改考卷經驗加同事偶爾提供的線索」湊出來的，「an empirical study is currently planned」。`formalization`，純概念提案，判斷不用改
- **Improving the Diproche CNL through Autoformalization via LLMs**（arXiv:2303.17513, EPTCS 400）——✔ 已讀全文。**現有「無數字」的判斷是錯的，要更正**：GPT-4-Turbo 在 50 個典型 Diproche 例句上 49 個處理正確，成功率 **98%**；text-davinci-003 在 33 句使用者文本上全數正確。但論文自己澆冷水：「for reliably checking...more than 10 sentences...anything considerably below a hundred percent is not good enough」——98% 是單句成功率，不是整篇證明的成功率。與原 Prolog 版差異：原本要手寫 definite clause grammar，LLM 版只用 71 行範例就上線，對拼字錯誤容忍度也更高
- **Automatized Evaluation of Formalization Exercises in Mathematics**（arXiv:2006.01800, 2020）——✔ 已讀全文。確認 Math Dictations 和 Game of Def 都是單一陳述式的形式化（自然語言句子→邏輯符號、或看圖寫謂詞），不是證明檢查。全文沒有任何評量數字，作者只說「it is sufficient for all cases attempted so far」一句帶過。可以當「連最簡單的形式化子問題都缺實證」的旁證，份量不大，順帶一提即可
- **Sociomathematical Norms and Automated Proof Checking**（Journal of Humanistic Mathematics 14(2), 2024, DOI 10.5642/jhummath.GVWG5301）——**全文讀不到**（scholarship.claremont.edu 擋爬蟲，403）。abstract 層級：主題是「證明是機械可驗證的形式推導」vs「證明是受社會規範塑造的社會建構」兩種立場的張力，用 Flensburg 2020/21 冬季學期的 Diproche 經驗當討論素材。abstract 未提新數據，但全文讀不到，不能斷言完全沒有

### B2. Waterproof 系列　`feedback` / `tutoring`　✔ 已讀全文

- **Waterproof: Educational Software for Learning How to Write Mathematical Proofs**（arXiv:2211.13513, EPTCS 400, pp. 96–119）。Jelle Wemmenhove 等 11 人。原文：「the software provides feedback on the logical validity of each step」。另有一句值得注意：Waterproof 用於 TU/e 的 Analysis 1 課程已四年，學生開始把工具的證明步驟措辭用在手寫證明裡。**全文補充**：底層真的是 Coq（透過 Coq LSP），自訂證明語言加上 OCaml 寫的客製自動化搜尋，不是規則檢查器。TU/e Analysis 1 是 175 人/年必修，但用不用 Waterproof 是選擇性的，2022-23 學年約 100 人開始用、約 76 人撐到最後一次作業。評分機制是 Momotor 接 Canvas 的**二元制**（過/不過給滿分或零分），論文自己承認這比人類評分「少了轉圜空間」。評估方式是小規模問卷＋個別談話＋助教訪談，**不是對照實驗**，作者原話「this claim needs to be backed up by a proper study」，正式研究排到 2023-24 學年。「學生把工具措辭用進手寫證明」是教師觀察到的印象描述，沒有測量。**值得引用的反面案例**：這篇的 Related Work 提到 Knobelsdorf et al. 的研究——另一所學校的 Coq 課上，學生手寫證明反而比沒上 Coq 課的組差，作者解讀是 Coq 的自動記帳面板沒被好好收掉，學生沒學會自己記狀態。對本研究「反向產生的說明會不會讓學生更依賴工具、學不會自己想」是個現成的反面案例
- **The Educational Proof Assistant Waterproof in an Introductory Proof Course**（arXiv:2606.26809, ThEdu 2026）。Pim Otte, Rogier Bos, Johan Commelin, Jim Portegies。Utrecht University，199 人修課／80 人同意並完成 entry survey／34 人在 Waterproof 組／21 人至少完成一題／16 人至少完成五題。原文自承：「As students **self-selected** into using Waterproof rather than being randomly assigned, these results are **suggestive rather than causal**」。**全文讀完要更正效果強度**：真實分組是 16 個「活躍使用者」（完成≥5題）+18 個「消極使用者」=34 人在 Waterproof 班，另外 5 位其他老師的班共 46 人當對照組；小考成績上，Waterproof 題數對成績的效果是「positive but not statistically significant」（p≈0.1, t=1.669）——**比「suggestive」還要弱**。因果限制不只自我選擇：作者自承兩位授課老師本來就深受 proof assistant 教學影響，這個效果很難跟 Waterproof 本身的效果分開。反直覺發現：活躍使用者反而回報**更差**的回饋品質感受，作者猜是「錯誤訊息不被學生當成回饋」。曾聽聞的「某系學生成績進步」不成立：活躍組 n=4 vs 消極組 n=9，對照組在該系是 0 人，作者自己說這個比較不成立。唯一站得住的結果：活躍使用者的證明明確性統計量比較高（∃-intro 2.31 vs 1.48；signpost-case 4.31 vs 2.78）

### B3. ProofBuddy　`tutoring`　✔ 已讀全文

Nadine Karsten, Frederik Krogsdal Jacobsen, Kim Jana Eiken, Uwe Nestmann, Jørgen Villadsen／2023／arXiv:2308.06970／EPTCS 382, pp. 1–21（TFPIE 2023）

Isabelle 為基礎的網頁工具，收集學生互動的細粒度資料。abstract 只說在 DTU 做過「preliminary usability study」，**但現有「無人數」的判斷是錯的，要更正**：全文有——DTU 2023 春季 Automated Reasoning 課，19 人修課，12 人參加評估；SUS 65/100（「好用但不會常用」）、UEQ pragmatic 0.775／hedonic 0.727；59 個學生問題分類為邏輯 21、Isabelle 語法 19、工具易用性 17、函式 2。細粒度互動資料的用途：檢查頻率過高可能代表學生在瞎試不思考——這個判斷邏輯可以參考，本研究也可以拿 `lean_check` 呼叫頻率當類似訊號。

後續：**ProofBuddy: How it Started, How it's Going**（arXiv:2505.13474, EPTCS 419, pp. 90–111）——✔ 已讀全文。三次部署：2023 夏（14 人全部完成）、2024 夏（22 人開始／21 人撐到最後／15 人交心得）、2024 冬（16 人開始／14 人撐到最後）。計畫中的必修課擴大到 **500-600 人**，是這系列少見有明確擴大規模時程的。新加的 Rule tab 被正面提及能省去背規則。

### B4. 其他　✔ 已讀全文

- **OnlineProver**（arXiv:2505.05987, EPTCS 419, pp. 55–74, 2025）——自然演繹的視覺化教學工具，非 Lean。`feedback`，**abstract 確實無數字，但全文有，要補上**：165 名學生（哥本哈根 IT 大學 Foundations of Computing 課）、55 份問卷、36 份資料提交、SUS 67.27。確認非 Lean/Coq/Isabelle：自製 natural deduction engine（Haskell+ClojureScript），論文明講排斥傳統 proof assistant「不適合入門課」
- **Hazel Prover**（arXiv:2608.23309, 2026）——「deploying Hazel Prover in two different classes」。值得注意的負面結果：「the first design did not effectively achieve transfer to pen-and-paper proofs」。**全文補充**：兩次部署是不同程度的課（Fall 2025 大學部 PL 課 25 人、Winter 2026 研究所 PL 課 16 人），論文沒處理這個混淆因子。「沒做到遷移」具體化：隨機亂點比例 48%→15%（設計改後）、回溯刪除評估步驟 33-50%→0%。設計改動的核心是從「雙擊讓工具自動化簡」改成「學生自己寫出化簡到哪一步再按確認」——**這條最值得本研究借鏡**：工具幫學生做的事情越多，遷移到紙筆越差；要求學生自己動手才有效果。對本研究「用 Lean proof 反向產生說明直接給學生看」是個警訊：純粹展示答案可能跟這裡的「雙擊自動化簡」犯一樣的錯，回饋設計或許要留一步讓學生自己填，不能整段端出去

---

## C 類　Lean 進數學課堂，批改仍由人做

九篇都已試著讀全文，能開的都開了；DOI 論文有四篇被機構典藏或出版商擋下（403／要登入），逐條標明。

| 論文 | 規模 | 性質 | 全文狀態 |
|---|---|---|---|
| **Teaching "Foundations of Mathematics" with Lean**（arXiv:2501.03352, 2025）<br>Bottoni, Cattaneo, Sacikara（UZH） | 11 週；訪談 **5 位 Lean + 4 位 Non-Lean**；全班期末考成績做 t-test 與 Mann-Whitney U | C 類唯一測出統計顯著差異的研究，但學生是自選加入 Lean 組不是隨機分派 | ✔ 已讀全文 |
| **Using the proof assistant Lean in undergraduate mathematics classrooms**（ZDM 56, pp. 1517–1529, 2024, DOI 10.1007/s11858-024-01577-9）<br>Hanna, Larvor, Yan | **3 個學生、1 道題**（double negation） | 純 think-aloud 訪談分析自主性與創造力，**全文確認完全沒有評分或批改機制**，跟批改無關 | ✔ 已讀全文（uhra.herts.ac.uk 開放版） |
| **Interactive theorem provers for university mathematics**（IJMEST, 2023, DOI 10.1080/0020739X.2023.2178981）<br>Iannone, Thoma | **99 份問卷 + 37 個訪談** | 這群裡樣本最大。量的是感受與困難，不是成效 | △ 讀不到全文（tandfonline 與機構典藏皆 403） |
| **'It Feels Like Sort of Cheating…'**（Digital Experiences in Mathematics Education, 2025, DOI 10.1007/s40751-025-00193-w）<br>Iannone, Thoma | **2 個學生**，Natural Number Game 任務訪談 | 質性 | △ 讀不到全文（Springer 要求登入） |
| **Learning about Proof with LEAN: the Abundant Numbers Task**（IJRUME 8, pp. 64–93, 2022, DOI 10.1007/s40753-021-00140-1）<br>Thoma, Iannone | **36 份學生證明**的質性分析 | 書目已證實，abstract 文字未親自核 | △ 讀不到全文（機構典藏連結是防護頁） |
| **Maths with Coq in L1**（arXiv:2505.05990, EPTCS 419, pp. 112–123）<br>Kerjean, Mayero, Rousselin | 18 小時課、3 年 | 給分機制是**「Qed 或零分」二元判定**，加遞減權重（第一個 Qed 權重是第十個的兩倍），這門課只佔學期總分 1/30。最難的定理三年只有 2022 年 5 人證出來，其他兩年零人。作者自承「這門課的實用性需要評估」，沒有考試成績分布或問卷數據。可跟 A3 的 fine-grained marking 設計目標對照 | ✔ 已讀全文 |
| **Learning how to Prove: From Coq to Textbook Style**（arXiv:1803.01466, EPTCS 267）<br>Böhne, Kreitz | abstract 自承「mostly conceptional」 | **本研究反向路線（形式證明→自然語言）的另一個先例，應與 Hattori et al.（E4）並列討論**。設計了三種形式證明到教科書風格證明之間的中間文體（逐行註解→弱化逐行註解→結構忠實證明），小規模實測（漢堡 2016、波茨坦 2017 共 12 人，9 人交回饋、9 人參加期末考）。學生原話批評「structure faithful proofs 跟教科書證明之間的落差還是太大」——跟 Hattori 的失敗模式（4/17 篇無中生有推理）是同一類問題的不同表現。不是全自動轉換，是人工分階段搭鷹架 | ✔ 已讀全文 |
| **Interactive Theorem Provers for Proof Education**（SPLASH-E 2025, DOI 10.1145/3758317.3759679）<br>Mahinpei, Horta Ribeiro, Milano | user study 人數未在 abstract | 發現形式化證明比紙筆證明更冗長，影響學生對難度的感受。**全文讀不到，但確認 abstract 層級這篇其實是三合一研究**：Coq 使用者研究、Coq/Lean/傳統證明的案例比較、對每個 ITP 做 heuristic evaluation，不只是單一 user study | △ 讀不到全文（ACM DL 與 ResearchGate 皆 403） |

**綜述**：**Proof Assistants for Teaching: a Survey**（arXiv:2505.13472, EPTCS 419, pp. 1–27, 2025）。Tran Minh, Gonnord, Narboux。27 頁，寫 related work 最省力的入口。✔ 已讀全文，核對先前子代理的結論**正確**：整篇 survey 裡唯一被描述成有 grading 功能的系統是 Lurch（原文「a word processor...equipped with...grading, coaching and providing hints」），其餘都停在 verification／feedback／tutoring。作者對整個領域現況的總結，可以直接引用強化「這塊還很空白」的論述：「the evaluation of the impact of these tools from a didactic point of view...is still at its debut」，且「there has been no systematic comparative study」。

---

## D 類　有批改／回饋，但完全不用形式系統

### D1. Autograding Mathematical Induction Proofs with NLP　`grading`　✔ 已讀全文

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

**全文補充**：評分者流程是 9 位研究生助教，每人評 4 題各 15 份（共 60 份），拿到 15 份範例評分＋詳細評分標準，用 7 點量表 R1–R7，Cronbach's α = 0.82–0.92，每人酬勞 $100。169 人使用者研究三組差異：Self-eval(68) 只給 7 個評分點自己改；First(59) 只給第一個錯的評分點；Random(42) 隨機給一個錯的評分點。三題最佳分數 Self-eval 組顯著低於另外兩組（如 P1: 75.8 vs 92.1 vs 90.1，p=0.004），但 First 和 Random 之間無顯著差異。除 Llemma34b(90.0%)/Llemma7b(89.3%) 外，另測了 MathBERT(84.1%)、GPT-3(87.7%)，人類評分者本身 86.6%。**「不信任」的原因論文有專節討論（§7.1–7.3），可以直接補進「做回饋」路線要處理的接受度問題**：模型是黑箱嵌入、學生反映「改個 LaTeX 符號分數就無故變了」、主觀任務的算法厭惡（引 Castelo et al. 2019、Lee 2018）。

### D2. Imperial AI Teaching Assistant　`feedback`　✔ 已讀全文

Aron Gohr, Marie-Amelie Lawn, Kevin Gao, Inigo Serjeant, Stephen Heslip／2026／arXiv:2601.03458

| | |
|---|---|
| 規模 | **65 份解答、3 位人類評分者**（0–5 分，兩位各批一半、一位獨立批全部） |
| 課程 | Imperial College London 一年級必修 Introduction to University Mathematics |
| 指標 | 與人類評分的 Pearson correlation |
| 部署 | Imperial 的作業平台 Lambdafeedback |

> the quality of the feedback generated is comparable to that produced by human experts when assessing early undergraduate homework

**這是「做回饋」路線門檻最低的可引先例**：65 份、3 位評分者就進得了 arXiv 並實際部署。

**全文補充與更正**：3 位評分者分工細節（§3.1.4）——兩位各批一半、一位獨立批全部，論文沒說是不是盲評。**要更正**：Pearson 相關係數**全文也沒給精確數字**，只寫「quite high」——不是「abstract 未給數字」，是全文通篇都沒給。部署到 Lambdafeedback 之後有沒有使用數據：讀到的整合章節被截斷，只提到「四項技術挑戰」，不確定是論文真的沒寫還是沒讀到那一段，**這點先別下「沒有數據」的結論**，之後找 PDF 版本再確認。

### D3. ProofGrader / Reliable Fine-Grained Evaluation of Natural Language Math Proofs　`grading`（評模型不評學生）　✔ 親自核（已讀全文）

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

**全文補充**：marking scheme 生成流程分三階段選型（18 題→36 題比較零樣本／少樣本→定案 Gemini-2.5-Pro 零樣本）。85% 品質數字的來源：36 份評分表中 35 份被兩位專家評 2 分以上（0–3 量表）。435 份的錯誤類型：論文沒有整體分類統計，只對「偏離 2 分以上」的 50 份做人工檢查，過度給分 10.8%、不足給分 12.2%，代數與幾何最容易出錯（各約 25%）。Limitations（§6）四點：範圍只到奧賽證明不到研究級／教育現場、evaluator 還能靠 prompt 優化、只評對錯不評可讀性／優雅度、強的 evaluator 都是 closed model。

### D4. 其他　✔ 已讀全文

- **Cost-Effective Automated Judging of Natural-Language Mathematical Proofs**（arXiv:2608.00004, 2026）——200 份驗證樣本、1000 份完整 benchmark、4 次重複、成本低 100 倍。設定是「candidate proof + **ground-truth proof** + human-grading rubric」，ground-truth 是人寫的不是驗證過的（用 IMO-GradingBench，論文自承「Lean 這類形式驗證是 active frontier，覆蓋率還沒到，所以現在都還是自然語言批改」）。100 倍降成本做法：改用便宜開源模型＋all-three-pass 一致性投票，三個模型是 GPT-OSS-120B、DeepSeek-V4-Flash、Gemma-4-31B，跑四次獨立重複驗穩定性。**值得特別注意**：三個廉價模型裡 DeepSeek-V4-Flash 和 Gemma-4-31B 跟本研究共享池用的 `deepseek-v4-flash:0731`、`gemma4:31b` 是同一個模型家族選擇，只差第三個（這篇用 GPT-OSS-120B，本研究用 `qwen3.5:397b`）——可以佐證「用便宜開源模型做批改／評估」不是本研究自己在瞎猜。但論文自己承認 all-three-pass 是事後從全部 benchmark 挑出來的規則，不是預先定好的，建議獨立複製驗證——這點也提醒本研究的規則設計要小心同樣的問題
- **Pseudo-Formalization for Automatic Proof Verification**（arXiv:2605.20531, 2026, Stanford）——明確放棄 Lean、改用半形式化格式。原文：「translating them into formal languages remains challenging in many frontier math settings」。**「為什麼大家繞開 Lean」的代表作**。半形式化格式具體長相：每個模塊有「前提／結論／證明」三段自然語言，模塊間用依賴圖（DAG）＋作用域繼承森林組織（Figure 2 有 IMO 2024 P6 的完整拆解範例，含抓到一個引理錯誤的實例）。放棄完整形式化的理由：前沿數學形式庫不完整、專家形式化要花數月到數年。論文自己講兩條路互補不是對立：「能形式化的地方形式化更強，不能的地方半形式化是替代方案」
- **Practical Online Assessment of Mathematical Proof**（arXiv:2006.01581, 2020）——Bickerton & Sangwin。STACK 一系的做法：**繞開批改證明，改考證明理解題**。abstract 無人數，自承 preliminary。全文補充：具體題型針對「有界遞增序列收斂」定理設計 5 題，包含「哪一步用了完備性公理」「假設在第幾步首次出現」等追蹤題，證明按行編號方便線上標記。2019–20 學年 344 位學生實測正確率：完備性公理定位題 70.64% 對，有界性定義題只有 24.71% 完全對（57.27% 把有界性跟收斂性搞混）。Limitations：COVID 打斷長期評估、反饋是事後根據學生實際錯誤調整、教學者太熟悉題目會低估學生困難、沒做到 Mejía-Ramos 那套 12 人三輪測試的黃金標準
- **Efficiency of Learning from Proof Blocks Versus Writing Proofs**（arXiv:2211.09609, SIGCSE 2023）——**332 人 RCT、3 組**。不碰形式化（拖放式證明積木），但這是證明教學領域設計最嚴謹的實驗。全文補充：三組具體人數 Proof Blocks 組 107 人、混合組 112 人、寫證明組 113 人；三組後測成績無顯著差異（χ²=0.54, p=0.76），但 Proof Blocks 組花的時間只有寫證明組的四分之一（11.1 分鐘 vs 43.4 分鐘）；作者自陳這是「首篇針對證明寫作能力（不是只有理解）的介入型 RCT」

---

## E 類　形式化本身的可靠性（不涉及批改，但決定路線可不可行）

這一類不是批改研究，但它決定了「能不能把學生的作答形式化」這個問題的答案。

### E1. Beyond Compilation　✔ 親自核（已讀全文，v2）

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

**全文補充，有一點要修正表述方式**：8 個系統身分是 Kimina-Prover、Goedel-Prover、Kimina-Autoformalizer、Herald Translator、StepFun-Formalizer、GPT-5.2(one-shot)、Sonnet 4.5(one-shot)、Gemini-2.5-Pro(one-shot)，另有自訂的「full agent」（GPT-5.2 orchestrator）。**29.0 個百分點的落差只出現在這個 full agent 身上，其餘 7 個 one-shot 系統的落差只有 0–8 個百分點**——落差隨系統能力（修復迴圈越長）擴大，不是每個系統都差到 29 個百分點，引用時不能讓人誤以為所有系統都差這麼多。400 題來源：Real Analysis／Complex Analysis／Topology／Algebra 各 100 題，取自公開講義而非檢索題庫。獨立審核協定：三批人工審核用 0–10 語意忠實度量表，≥9 才算 faithful。落差成因是多重機制：compiler feedback 讓編譯率大漲但忠實度只小漲；長修復迴圈語意漂移（1-2 步 81.3% faithful → 19-24 步僅 12.0%）；模型常忽略「只寫 statement」指示、混入 proof 內容。**沒有測 round-trip／回譯當緩解方案**，測的是形式等價檢查器（BEq），不是回譯。

### E2. The Faithfulness Gap　✔ 親自核（已讀全文）

Noor Islam S. Mohammad, Tamim Sheikh／2026／arXiv:2606.16541

標題：The Faithfulness Gap: Certifying Semantic Equivalence Between Natural-Language and Formal Mathematical Statements

abstract 原文：

> Autoformalization, translating natural-language mathematics into formal proof assistants, is bottlenecked not by translation fluency but by faithfulness: a formal statement can typecheck and be provable, yet still encode a different theorem than the source intended.

方法為 Bidirectional Provability Fingerprinting (BPF)：

| | |
|---|---|
| BPF 偵測率 | **89.6%** 的 drifted formalizations，false-positive **3.0%** |
| 單靠 typecheck | ~~只抓到 41.2%~~ **更正：實際只有 11.4%，見下方** |
| LLM-judge baseline | **63.3%** |
| 資料集 | 2,183 對 NL／Lean 4，**with controlled drift labels** |

**重大更正（讀全文才發現）**：89.6%／3.0%／41.2%／63.3% 這四個數字全部來自論文 Table 2「controlled DriftBench split」，也就是**用機械式規則人工製造漂移**的 1,799 對資料（原文：「We use deterministic perturbation rules rather than sampling drift from an LLM autoformalizer so that the drift label is unambiguous」）——不是「人工標註」漂移，是**規則生成**漂移，比人工標註更人工，比真實場景更乾淨。**另外 41.2% 這個數字本身標錯對象**：Table 2 裡 typecheck-only 那行實際上是 **11.4%**，41.2% 是另一個叫「Provability」的 baseline，不是 typecheck 的數字——這代表 typecheck 比先前寫的更弱，不是更強，方向性的更正要特別注意。

真實資料的驗證：另有 384 對「wild split」是真實 LLM autoformalizer 輸出，兩位專家標註（κ=0.81）。在這個真實資料上，BPF 與專家一致率 κ=0.77；把 BPF 包成 wrapper 部署在一個現成 autoformalizer 上，drifted-output rate 從 19.4% 降到 10.3%。**這代表現有「89.6% 只在合成資料上測得」的判斷方向正確，但可以講得更完整**：真實輸出上也做了驗證，只是換了指標（κ=0.77 而非偵測率），不能直接跟 89.6% 相提並論。作者自陳限制：BPF 只證「後承鄰域相符」，不保證自然語言本身無歧義；有 30 秒逾時導致的不完備率 η≈0.07；「若無專家複查就把 BPF 認證結果當 ground truth，殘留漂移可能污染資料庫」。

### E3. Faithful Autoformalization via Roundtrip Verification and Repair　✔ 親自核（已讀全文，v2）

Daneshvar Amrollahi, Jerry Lopez, Clark Barrett（Stanford）／2026／arXiv:2604.25031

abstract 原文：

> We propose a roundtrip verification approach which does not require ground-truth annotations: formalize a statement, translate the result back to natural language, re-formalize, and use a formal tool to check logical equivalence. When the two formalizations agree, this provides evidence of a faithful formalization.

**領域是法律條文**：Texas Transportation Code 與 Texas Parks and Wildlife Code。模型為 Claude Opus 4.6 與 GPT-5.2。

abstract 報的數字：未通過等價檢查的條文，NLI drift 高出 **1.4–2.5 倍**。

**更正：那組數字內文其實有，只是限定在單一領域，不能籠統引用**。「45–61% → 83–85%」在 Table 1 裡，只涵蓋 **Traffic（Texas Transportation Code）**：Claude 44.7%→85.3%、GPT 61.3%→82.7%。**Wildlife 領域是另一組數字**：Claude 62.3%→85.7%、GPT 66.2%→77.9%，範圍對不上原本引用的 45–61%。若要重新引用，正確寫法是「Table 1，Traffic 領域：Claude 44.7%→85.3%、GPT 61.3%→82.7%」，不能寫成單一區間代表全部。兩部法規規模：Transportation Code 150 條、Parks and Wildlife Code 77 條（論文只給抽樣進資料集的規則數，沒給各法規全部條文總數）。Repair 迴圈機制：SMT 判不等價後，用診斷函式依序比對「原始NL vs 第一次形式化」「第一次形式化 vs 回譯NL」「回譯NL vs 第二次形式化」三段，找出第一個出錯階段，套對應修復運算子重新生成，最多重試 3 次。Claude vs GPT 是準確度換效率的取捨：Claude 最終 UNSAT 率略高（85.3%/85.7% vs 82.7%/77.9%），但 GPT 每次修復平均呼叫模型次數少很多（Traffic：7.21 vs 14.56）。「1.4–2.5 倍」是比較「形式判定不等價的規則」跟「形式判定等價的規則」的語意漂移程度（pooled 2.03 倍），用來驗證判斷方向一致，不是修復前後的比較。**領域判斷不變**：全文從頭到尾都是德州法規，沒有數學或程式的補充實驗。

### E4. Hattori et al.（informalization）　✔ 親自核（已讀全文）

Seiji Hattori, Takuya Matsuzaki, Makoto Fujiwara／2025／arXiv:2509.09726

標題：Natural Language Translation of Formal Proofs through Informalization of Proof Steps and Recursive Summarization along Proof Structure

**本研究「反向產生學生回饋」這條路最接近的先例，而且領域重疊。**

#### 方法：兩階段

1. **逐步 informalize**　每個 tactic 轉成一句自然語言，用「模板 + LLM 填空」的混合法：模板依 tactic 類型準備（`rw` 改 goal 或改 hypothesis 用不同模板），LLM 填 `[theorems]`、`[assumptions]`、`[goalsBefore]`、`[goalsAfter]`；另有 premise library 存放定義與定理的預先說明
2. **沿證明結構遞迴摘要**　以 `have` 產生的中間目標為子樹根建出依賴樹，由下而上逐層摘要

#### 資料集

| | |
|---|---|
| 資料集一 | 宮島靜雄《Calculus I - Calculus of one variable》第 1.1、1.2 節的 **17 個證明**，人工形式化並保持原證明結構。評估用 **38 個形式證明**（含 21 個 lemma） |
| 資料集二 | Mathlib 中沒有對應自然語言證明的定理，論文給三個詳細例子 |

**大學微積分課本的證明、人工形式化——與本研究的場景幾乎相同。**

#### 評估與數字

逐步 informalize，**1,242 個步驟**，人工專家評四個維度（accuracy、information sufficiency、necessity、appropriate translation），以 McNemar's test（α=0.05）檢定：

| 正確 | 誤述 | 資訊不足 | 多餘 | 未翻譯 |
|---|---|---|---|---|
| **89.05%** | **5.15%** | 11.50% | 13.87% | 0.40% |

摘要階段，17 個證明，平均每個設 **6.4 條評估標準**，分全對／部分／漏：

| | 全對 | 部分 | 漏 | 分數 |
|---|---|---|---|---|
| 用遞迴摘要 | 87 | 11 | 10 | **0.857** |
| 不用遞迴摘要 | 85 | 10 | 13 | 0.833 |

#### 失敗模式（原文照抄）

> Among the 17 outputs generated without recursive summarization, four included **reasoning not in the original proof** and/or contained **substantial logical inconsistencies**

> Identifying all possible operations a tactic can perform and creating appropriate few-shot examples for them is **extremely time-consuming**

另外：形式語言的表達式偶爾會直接輸出而未翻譯；證明太簡單時，會輸出人類認為瑣碎的細節。

#### 對本研究的三個意涵

1. **評估方法可以照用**：人工專家評四維度，加上每個證明設數條評估標準判全對／部分／漏。這比「找人打分算相關係數」具體，而且直接適用於「轉出來的中文對不對」
2. **89% 不是零風險**：5.15% 誤述表示約每 20 個步驟有一個說錯。參考答案本身雖經驗證，轉成中文這一步仍會引入新的錯誤，論文必須寫明
3. **不能只丟給 LLM 說「翻成中文」**：不用遞迴摘要時，17 個裡有 4 個憑空生出原證明沒有的推理。但模板要逐一 tactic 建立，成本很高——若想省掉模板只用 LLM，須先測品質掉多少

### 對本研究的意義

**正向（自然語言 → Lean）的錯誤無法用編譯檢查出來。** round-trip 是目前主流的補救方式，但兩篇的證據都不在數學：一篇用規則生成漂移的合成資料集（真實輸出上換了指標另外驗證過，κ=0.77），一篇做法律條文（Table 1 的數字也只涵蓋單一領域）。**數學領域目前沒有 round-trip 的數據。**

**反向（Lean → 自然語言）風險低**，因為背後那份 proof 已經驗證過，翻得不精準只會讓說明變模糊，不會把對的講成錯的。本研究用反向把驗證過的參考答案轉成學生看得懂的說明。C 類的**Learning how to Prove: From Coq to Textbook Style**（arXiv:1803.01466）是另一個同方向的教學先例，跟 E4（Hattori et al.）合看：兩篇的失敗模式重疊——把形式證明攤開成自然語言時都會出現「無中生有的推理」或「跟教科書證明的落差太大」。B4 的 Hazel Prover 也提供一個相關警訊：工具幫學生做的事情越多，遷移到紙筆越差；純粹展示答案（而非留步驟讓學生自己填）可能重蹈同樣的錯，這點要寫進本研究「做回饋」路線的設計考量。

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
                     332 人 RCT，3 組 107/112/113 人（Proof Blocks, SIGCSE 2023）
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
