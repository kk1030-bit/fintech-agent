# W02-C 指定文獻／文件卡（R01–R08）

- 任務 ID：W01-C｜製作：C（AI 協助閱讀與整理）｜狀態：**草稿，待組長核准**
- 本檔屬 W02-C 進度（依修改要求），自 W01 轉入。2026-10-31 依 repo 內組長與 B 的文件第二次修訂。
- 日期說明：入口經組長於 2026/09/13 核對；本次 AI 協助閱讀日為 **2026/10/31**。Google 文件頁面的「最後更新日」晚於 9/13（見各卡），內容可能已與 9/13 版本不同。
- 規則：前三張（R01–R03）只根據我實際讀到的摘要頁與論文節選，**不是逐頁讀完全文**，不引用任何效能數字。「全文確認」建議由 C 本人完成後才定稿。
- 本文件不含任何技術成果或測試結果。技術對應需 B/D/組長核准。

## 來源類型分類

| 類型 | 卡號 | 說明 |
|---|---|---|
| 學術論文（arXiv 預印本） | R01、R02、R03 | 未讀完全文，不引用效能數字 |
| 工程文件（公司文章） | R04 | 工程觀點，非同儕審查 |
| 官方產品文件 | R05、R06、R07 | Google Gemini API 文件，內容隨時更新 |
| 專題實作基線 | R08 | 不是外部學術證據 |

## 閱讀範圍總表

| 卡 | 實際讀到的內容 | 未讀到 |
|---|---|---|
| R01 | arXiv 摘要頁、論文貢獻與第 2 節節選 | 實驗章節與完整全文 |
| R02 | arXiv 摘要頁、ar5iv 版的摘要與方法節選 | 實驗與完整全文 |
| R03 | arXiv 摘要頁、論文 HTML 版的摘要與相關工作節選 | 平台細節與完整全文 |
| R04 | 全文（讀取的是 anthropic.com/research/ 路徑） | — |
| R05 | 整頁（日文機器翻譯版） | 英文原頁 |
| R06 | 整頁 | 帳戶實際額度（頁面本身未列逐模型數字） |
| R07 | 頁面前半（約至 Gemini 3 Flash Preview 的 Batch 表） | 後段模型與工具計價 |
| R08 | 固定 commit 53816d4 的檔案清單、PROJECT_STATUS.md、requirements.txt，以及 web_app.py、main.py、report_builder.py 的函式名稱與設定（2026-10-31 以 git 取得該 commit） | 各程式的完整邏輯（C 不判定程式正確性） |

---

## R01｜ReAct: Synergizing Reasoning and Acting in Language Models

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Shunyu Yao、Jeffrey Zhao、Dian Yu、Nan Du、Izhak Shafran、Karthik Narasimhan、Yuan Cao；Princeton University 與 Google Research（Brain team） |
| 年份／查閱日 | 2022-10-06 提交（v1），2023-03-10 修訂（v3）；查閱 2026/10/31 |
| 類型 | arXiv 預印本（cs.CL）。二手頁面提到曾發表於 ICLR 2023，**待 C 以官方頁面確認** |
| 研究問題 | 大型語言模型的推理（如 chain-of-thought）與行動（如行動計畫生成）過去多被當成分開的主題，能否讓兩者結合 |
| 方法摘要 | 提示式方法：把代理的行動空間擴充為「原行動集合加上語言空間」，讓模型交錯產生思考與行動；行動可向知識庫或環境取得外部資訊，觀察再用來更新後續推理。摘要頁提到在問答（HotpotQA）與事實查證（FEVER）上與 Wikipedia API 互動；其他任務名稱來自二手整理，待全文確認 |
| 本專題採用點 | 作為「以行動取得觀察，再調整研究判斷」的概念參考，用於說明 Researcher 取得工具觀察後更新判斷的動機 |
| 不能據此聲稱 | 不引用其一般任務分數作為股價預測能力；不能說 ReAct 證明本系統較準確或可獲利；ReAct 是提示方法，不等於本專題的雙 Agent、預算與 Reviewer 設計；本專題實作是否採用其格式，待 B／組長確認 |
| 原始 URL | https://arxiv.org/abs/2210.03629 |

## R02｜Toolformer: Language Models Can Teach Themselves to Use Tools

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Timo Schick、Jane Dwivedi-Yu、Roberto Dessì、Roberta Raileanu、Maria Lomeli、Luke Zettlemoyer、Nicola Cancedda、Thomas Scialom；Meta AI Research、Universitat Pompeu Fabra |
| 年份／查閱日 | 2023-02-09（我讀到的是 v1 頁面）；查閱 2026/10/31 |
| 類型 | arXiv 預印本（cs.CL） |
| 研究問題 | 語言模型在少樣本任務上表現強，卻在算術、事實查詢等基本功能上不穩，模型能否自行學會使用外部工具 |
| 方法摘要 | 以自監督方式，只需少量人工示範，讓模型替大量語料標註可能的 API 呼叫，再執行並過濾，最後用含 API 呼叫的資料微調。模型決定呼叫哪個 API、何時呼叫、傳什麼參數。摘要列出的工具包含計算機、問答系統、兩種搜尋引擎、翻譯系統與日曆；基底模型為 GPT-J（約 6.7B 參數） |
| 本專題採用點 | 比較「模型自行決定是否用工具」的設計思想，說明本專題與訓練式方法的差異 |
| 不能據此聲稱 | 本專題沒有做其訓練程序，**不宣稱重現 Toolformer**；不引用其零樣本分數；其工具是輸入輸出皆為文字的簡單 API，不能直接類推到財報資料工具 |
| 原始 URL | https://arxiv.org/abs/2302.04761 |

## R03｜FinRobot: An Open-Source AI Agent Platform for Financial Applications using Large Language Models

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Hongyang (Bruce) Yang 等共 11 位作者；AI4Finance Foundation 相關團隊 |
| 年份／查閱日 | 2024-05-23 提交（v1），2024-05-27 修訂（v2）；查閱 2026/10/31 |
| 類型 | arXiv 預印本（q-fin.ST），組長標註為白皮書性質 |
| 研究問題 | 金融業導入 LLM 時，專有資料與專業知識形成障礙，能否以開源的金融專用工具鏈降低門檻 |
| 方法摘要 | 提出分為四層的平台：金融 AI Agents 層（把金融問題拆成有邏輯的步驟，稱 Financial CoT）、金融 LLM 演算法層、LLMOps／DataOps 層、多來源 LLM 基礎模型層；強調多來源整合與即時資料管線。作者稱其為首個專用於金融分析的 AI Agent 平台（**作者自述**） |
| 本專題採用點 | 金融 Agent 平台的相關工作，作為研究定位參考 |
| 不能據此聲稱 | 不以其架構證明本系統可獲利；「首個」為作者自述，引用時須標明；其涵蓋的市場預測等用途不是本專題範圍；不比較兩者效能 |
| 原始 URL | https://arxiv.org/abs/2405.14767 |

## R04｜Building effective agents

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Anthropic（頁面載明由 Erik S. 與 Barry Zhang 撰寫） |
| 年份／查閱日 | 2024-12-19 發布；頁面中繼資料顯示 2026-10-09 曾修改；查閱 2026/10/31 |
| 類型 | 公司工程文章，非同儕審查 |
| 研究問題 | 如何建構有效的 LLM Agent，何時該用、何時不該用 |
| 方法摘要 | 把 agentic system 分成兩類：workflow 是 LLM 與工具由預先寫好的程式路徑編排；agent 是 LLM 動態主導自己的流程與工具使用。以「增強型 LLM」（含檢索、工具、記憶）為基本單元，介紹五種 workflow 模式（提示串接、路由、平行化、協調者—工作者、評估者—優化者）。agent 需在每一步從環境取得工具結果等真實回饋，可在檢查點暫停請人判斷，並常設停止條件（如最大迭代次數）。建議先用最簡單的方案，確有成效才增加複雜度；附錄談工具介面設計 |
| 本專題採用點 | 區分 workflow 與 agent，說明「功能多」不等於 Agent；工具設計與停止條件的描述依據 |
| 不能據此聲稱 | 這是工程觀點，不當作嚴格統一的學術定義；不能據此說本系統最佳；頁面自註 2024 年底描述的工具生態已有變化；本專題 Reviewer 與其「評估者—優化者」模式的對應，須 B/D 核准後才寫 |
| 原始 URL | 組長提供：https://www.anthropic.com/engineering/building-effective-agents。我實際讀到的是 https://www.anthropic.com/research/building-effective-agents（標題與日期相同）。**兩者是否為同一頁，待 C 確認** |

## R05｜Gemini function calling

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Google（Gemini API 官方文件） |
| 年份／查閱日 | 頁面標示最後更新 2026-10-15（我讀到的版本）；查閱 2026/10/31 |
| 類型 | 官方產品文件 |
| 研究問題 | 如何讓模型連接外部工具與 API |
| 方法摘要 | 流程為四步：定義函式宣告；帶宣告呼叫模型，模型回傳函式名稱、參數與 id；**由應用程式自己執行函式**（模型不執行）；把結果連同 id 回傳給模型。支援平行與組合式呼叫。呼叫模式有 AUTO、ANY、NONE（及 VALIDATED）。最佳實務包含：描述具體、參數強型別、同時提供的工具以 10–20 個為上限、後果重大的呼叫先請使用者驗證、檢查 finishReason、做好錯誤處理。手動管理對話歷史時須回傳思考簽章；自動函式呼叫僅限 Python SDK |
| 本專題採用點 | 實作函式 schema、模型選工具、回傳工具結果的依據。實際 SDK 版本由組長鎖定 |
| 不能據此聲稱 | 範例中的模型名稱不代表本專題採用；文件不證明工具選擇的正確性。**我讀到的是日文機器翻譯版，頁面標題含「Generate Content API (Legacy)」，不是英文原頁 `/docs/function-calling`**，兩者可能有差異，待 C 或組長確認 |
| 原始 URL | https://ai.google.dev/gemini-api/docs/function-calling（實際讀取：.../generate-content/function-calling?hl=ja） |

## R06｜Gemini API rate limits

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Google（Gemini API 官方文件） |
| 年份／查閱日 | 頁面標示最後更新 2026-10-28；查閱 2026/10/31 |
| 類型 | 官方產品文件 |
| 研究問題 | 說明 API 請求如何受速率限制管理 |
| 方法摘要 | 限制以每分鐘請求數（RPM）、每分鐘輸入 token（TPM）、每日請求數（RPD）衡量，任一超限即報錯；以專案而非 API key 計算；每日額度於太平洋時間午夜重置。用量分 Free 與 Tier 1–3，依帳單與累計付款升級。另有以 10 分鐘滾動視窗計算的花費型限制。頁面註明限制不保證，實際額度須在 AI Studio 查看，**頁面本身沒有逐模型的 RPM／TPM 數字** |
| 本專題採用點 | 配額治理的背景；說明為何專題預算要有上限。帳戶實際數字由組長於 W01 保存脫敏紀錄 |
| 不能據此聲稱 | 不能把頁面通則當作本專案帳戶額度；「每 job 8 次發送、10 工具、2 補查輪」是專案內部預算，不是 Google 規定；紀錄不得含 API key |
| 原始 URL | https://ai.google.dev/gemini-api/docs/rate-limits |

## R07｜Gemini API pricing

| 欄位 | 內容 |
|---|---|
| 作者／機構 | Google（Gemini API 官方文件） |
| 年份／查閱日 | 查閱 2026/10/31；我讀到的部分未顯示頁面更新日 |
| 類型 | 官方產品文件 |
| 研究問題 | 說明 Gemini Developer API 的方案與計價 |
| 方法摘要 | 分 Free、Paid、Enterprise 三種方案。Free 提供免費 token、僅限部分模型，且內容可能用於改進產品；Paid 提供較高限額、context caching、Batch API，且內容不用於改進產品。各模型依 Standard、Batch、Flex、Priority 分別計價。我讀到的部分中，有些模型標註價格將於特定日期調整，也有模型不提供免費層。**本卡只讀到頁面前半** |
| 本專題採用點 | 區分免費與付費的使用條件，作為方案選擇的背景 |
| 不能據此聲稱 | 不預測未來價格；論文不抄錄價格數字（易過期）；未經組長提供實際模型與用量，不據此估算專案成本 |
| 原始 URL | https://ai.google.dev/gemini-api/docs/pricing |

## R08｜fintech-agent 固定版本程式

| 欄位 | 內容 |
|---|---|
| 作者／機構 | GitHub 帳號 kk1030-bit（專案組長） |
| 年份／查閱日 | commit `53816d4fb7d178d309cb556bd55fe9f49533e7e5`，提交於 2026-06-15；其中 PROJECT_STATUS.md 標示最後更新 2026-05-30；查閱 2026/10/31（以 git 取得該 commit，非 main 分支） |
| 類型 | 本專題實作基線，**不是外部學術證據** |
| 研究問題 | 不適用（程式基線）。PROJECT_STATUS.md 的描述是：使用者輸入台股代號後，系統串接 FinMind 與 Supabase，執行財務分析與 DCF 估值，在網頁輸出每股內在價值、財務摘要、優勢、風險與三張圖表 |
| 方法摘要 | 檔案清單包含 PROJECT_STATUS.md、web_app.py、main.py、requirements.txt、report_builder.py、macro_agent／（fred_scraper.py、tw_market_scraper.py、uploader.py 等）、valuation_agent／、fundamental_agent／。requirements.txt 列有 pandas、matplotlib、fpdf2、Flask、gunicorn、supabase、FinMind、fredapi 等套件。web_app.py 是 Flask 入口（首頁、股票清單、分析、輸出檔案路由）；main.py 串接 Supabase、DCF 與報告流程，DCF 的 WACC 預設讀環境變數，未設定時為 0.09；report_builder.py 以 fpdf2 與思源黑體產生 PDF。PROJECT_STATUS.md 記載公開網站部署於 Render Free（512MB），為避免記憶體不足預設略過 PDF，PDF 只在本機產出 |
| 本專題採用點 | 描述「學期初基線」與既有系統限制的依據。V1.2 沿用其中的 Python／Flask、FinMind／FRED、Supabase、DCF、matplotlib、fpdf2（工作包） |
| 不能據此聲稱的結論 | 不是外部學術證據；不代表目前系統現況（現況以 main 分支程式與當週實測為準）；不以檔名推斷功能存在；C 不判定其程式是否正確 |
| 原始 URL | https://github.com/kk1030-bit/fintech-agent/tree/53816d4fb7d178d309cb556bd55fe9f49533e7e5 |

---|---|
| 作者／機構 | GitHub 帳號 kk1030-bit（與專案成員的對應待確認） |
| 年份／查閱日 | 固定 commit `53816d4fb7d178d309cb556bd55fe9f49533e7e5`，commit 日期未讀到；我讀到的 PROJECT_STATUS.md 標示最後更新 2026-05-30；查閱 2026/10/31 |
| 類型 | 本專題實作基線，**不是外部學術證據** |
| 研究問題 | 不適用（程式基線）。專案目標：以網站輸入台股代號，串接 FinMind 與 Supabase，輸出估值、財務摘要與圖表（依 PROJECT_STATUS.md 的描述） |
| 方法摘要 | **我開啟的是 main 分支，不是固定 commit，兩者可能不同。** main 分支的 PROJECT_STATUS.md 記載：用 FinMind 抓股價、財報、比率與現金流；用 Supabase 儲存資料；規則式財務摘要與 FCF 預測；DCF 計算每股內在價值；產生三張圖表；Flask 網站；部署於 Render Free（512MB）。公開版為避免記憶體不足預設略過 PDF 產生，PDF 只有本機版可產出。儲存庫首頁另列有 fundamental_agent、macro_agent、valuation_agent 資料夾與 web_app.py、main.py、report_builder.py、requirements.txt。**我沒有讀各程式檔，不能判斷任何功能的實作內容** |
| 本專題採用點 | 描述「學期初基線」與既有系統限制時的依據，內容須由 B 核准 |
| 不能據此聲稱 | 不是外部學術證據；PROJECT_STATUS.md 日期較舊（2026-05-30），現況以程式與當週實測為準；不以檔名推斷功能存在；未提及某功能不代表沒有該功能 |
| 原始 URL | https://github.com/kk1030-bit/fintech-agent/tree/53816d4fb7d178d309cb556bd55fe9f49533e7e5 |

---|---|
| 作者／機構 | GitHub 帳號 kk1030-bit（與專案成員的對應待確認） |
| 年份／查閱日 | 固定 commit `53816d4fb7d178d309cb556bd55fe9f49533e7e5`；commit 日期**未讀到**；查閱日待填 |
| 類型 | 本專題實作基線，**不是外部學術證據** |
| 研究問題 | 待 B／組長提供 |
| 方法摘要 | **未讀到固定版本內容**。依組長說明，內容含 PROJECT_STATUS.md、web_app.py、main.py、requirements.txt、report_builder.py 與 macro_agent。本次只讀過儲存庫首頁的檔案清單（非固定 commit），不足以判斷任何功能是否存在 |
| 本專題採用點 | 描述「既有系統」時的基線，內容須由 B 核准 |
| 不能據此聲稱 | 不是外部學術證據；狀態文件日期較舊，現況以程式與當週實測為準；不以檔名推斷功能存在 |
| 原始 URL | https://github.com/kk1030-bit/fintech-agent/tree/53816d4fb7d178d309cb556bd55fe9f49533e7e5 |

---

## 附加運維連結（不計入 8 筆卡）

- Google Developer Program：https://developers.google.com/program/plans-and-pricing（**未讀**）
- Render Compute：https://render.com/pricing#compute（**未讀**）
- 用途與核對由組長負責。依工作包，Render 2GB 為計畫，不得寫成已部署。

---

## workflow／single agent／dual agent 比較文稿

本節比較三種設計，供方法章與實驗設計章引用。本專題的三種模式在程式中稱為 workflow、single 與 dual（組長 2026-10-24 核定的三模式校準計畫，handoff/calibration-plan-v1.md）。以下用 R01、R02、R04 的概念說明差異，不引用任何效能數字。

**workflow。** R04 把 workflow 定義為由預先寫好的程式路徑編排 LLM 與工具的系統。每一步做什麼由程式決定，模型不決定下一個動作。這類設計的步驟固定，行為較容易預測，也較容易逐步檢查。R04 指出，對任務明確的情境，workflow 能提供可預測性與一致性。本專題的 workflow 模式，是由程式先執行固定的工具，模型只撰稿一次，不自行選工具（組長，agents/research_graph.py）。

**single agent。** R04 把 agent 定義為由 LLM 動態主導自己的流程與工具使用的系統。R01 說明模型交錯產生思考與行動，並用行動取得的觀察更新後續判斷；R02 說明模型可以自行決定呼叫哪個工具、何時呼叫、傳入什麼參數。本專題的 single 模式，是由單一 Researcher 依目前證據選擇工具、取得觀察並決定何時停止，草稿不經 Reviewer 覆核（組長，handoff/state-machine-v1.md）。R04 提醒，agent 常以延遲與成本換取彈性，並可能累積錯誤，需要停止條件與防護。

**dual agent。** 在 single agent 之外，另設一個覆核角色。本專題的 dual 模式，是 Researcher 負責選工具與取得證據，Reviewer 只能使用讀取、財報、總經與計算四類工具，需要查價或搜尋時退回 Researcher（B 核對；agents/prompts/reviewer-v1.2.txt）。只有 dual 模式的草稿會經過覆核。R04 的「評估者—優化者」模式由一個 LLM 產生、另一個提供評估與回饋，與此結構相似，但兩者是否等同，**須 B／D 核准後才能在正文寫成對應**。

**不能據此宣稱的結論。** 三種設計各有取捨，本節不主張任何一種較準確、較省或可帶來獲利。哪一種在本專題表現較好，只能由 D 的正式實驗（20 保留案 × 3 模式 = 60 次執行）回答。

## 待處理事項

| 問題 | 提供人 |
|---|---|
| R01–R03 全文確認 | C |
| R01 是否發表於 ICLR 2023 的官方確認 | C |
| R04 兩個 URL 是否同頁 | C／組長 |
| R05 英文原頁與日文機器翻譯版的差異 | C／組長 |
| R07 後半頁面 | C |
| 本專題與 R01、R04 概念的對應是否成立 | B／D |
