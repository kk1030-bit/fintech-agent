# W03-A｜job 狀態、動作軌跡與比較面板契約

- 任務 ID：W03-A（原排程 09-28～10-02，2026-10-05 補做）｜驗收人：組長
- 分支：`codex/W03-A-job-trace`（基於 W02-A）｜前置 W02-A ✓、W02-L ✓

## 做了什麼

1. **動作軌跡**：每一步顯示角色（Researcher／Reviewer／系統）、工具名、事件時間（Asia/Taipei，到秒）、工具狀態（ok／no_data／invalid_input）、遮蔽後參數（cutoff 以 `<job.cutoff_at>` 表示）、來源 ID、耗時、輸出 hash。只顯示 `decision_summary` 這種可驗證的簡短理由，**不顯示隱藏思考鏈**；事件欄位走伺服器白名單。
2. **工具結果是真的**：MOCK 只預錄「模型決策」；工具步驟實際執行 B 的 `agents/tools_impl.py` 讀固定快照，所以 2317 的 `no_data`、2454 的 `ev-2454-2026q2-01` 都是真實工具輸出。
3. **重整仍讀同一 job**：job_id 在網址 `?job=`；狀態每次從 job DB 讀，另一個 app 實例（等同重啟）讀得到同一結果。
4. **補齊狀態畫面**：排隊（顯示前面幾個）、暫停配額（累計預算保留、不自動重試）、失敗、逾時 180 秒、取消、資料不足、完成待人工核准。執行中可「取消」；排隊中取消需組長在 JobStore 加方法（CR-A03）。
5. **比較面板契約**：`ui/v12-comparison-contract.md`，並實查 B 資料，列出 6 項需 B/D 處理的問題。
6. 手機版面板順序改為：入口 → 狀態 → 軌跡 → 收藏清單。

## 測試（實際執行 2026-10-05）

`.venv/bin/python -m pytest -q tests` → **105 passed**。W03 新增：五種結束狀態各自到達且 stop_reason 存在、paused_quota 不自動重跑且 calls_used 保留、軌跡含真實工具狀態與來源 ID、缺資料為 no_data 而非 0、第二個 job 排隊、只能取消執行中 job、另一實例從 DB 讀到同一狀態。

## 截圖（本機 MOCK，headless Chromium，橫向溢出皆 0 px）

| 檔案 | 狀態 | 尺寸 |
|---|---|---|
| W03-trace-succeeded-1440-full.png | 完成・待人工核准，完整軌跡 | 1440 寬全頁 |
| W03-trace-succeeded-390-full.png | 同上（手機） | 390 寬全頁 |
| W03-insufficient-1440x900.png | 資料不足（2317） | 1440×900 |
| W03-paused-quota-390-full.png | 暫停配額 | 390 寬全頁 |
| W03-failed-390-full.png | 失敗 | 390 寬全頁 |
| W03-cancelled-1440x900.png | 取消 | 1440×900 |
| W03-timed-out-1440x900.png | 逾時 | 1440×900 |

## 驗收自查

| 驗收項 | 結果 |
|---|---|
| 不顯示秘密與隱藏思考鏈 | ✓ 事件欄位白名單測試 |
| 狀態從 DB 取得 | ✓ JobStore SQLite；跨實例測試 |
| pending 不冒充完成 | ✓ 測試＋「研究完成・待人工核准」用語 |
| 最多 4 公司；不同期或缺值不用 0 補；標 fixture | 契約已定（§1、§3），畫面於 W04 實作 |

## 未完成／需要誰

- 真實 Researcher 軌跡 → 組長 W04-L（runner 完成後把 `/api/ui/jobs` 改讀正式 job DB，事件格式相同）。
- B 資料 6 項問題 → B、D（見比較契約 §4）。
