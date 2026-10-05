/* V1.2 research workspace (A). Read-only pages never start an analysis:
 * this file never calls the synchronous analyze endpoint and holds no API key or token. */
(() => {
  "use strict";

  const CFG = window.RESEARCH_UI || {};
  const TZ = "Asia/Taipei";
  const FAV_KEY = "fintech-agent.favorites.v1";
  const FAV_MAX = 5;
  const FAV_ALLOWED = ["2330", "2317", "2454", "2379", "3034"];
  const POLL_MS = 2000;
  const TERMINAL = ["succeeded", "insufficient_evidence", "timed_out", "failed", "cancelled"];

  const $ = sel => document.querySelector(sel);
  const pageStatus = $("#pageStatus");

  const STATUS_TEXT = {
    queued: ["排隊中", "b-neutral"],
    running: ["執行中", "b-run"],
    paused_quota: ["暫停：配額", "b-warn"],
    succeeded: ["完成（待人工核准）", "b-ok"],
    insufficient_evidence: ["資料不足", "b-warn"],
    timed_out: ["逾時停止", "b-bad"],
    failed: ["失敗", "b-bad"],
    cancelled: ["已取消", "b-neutral"]
  };
  const STAGE_TEXT = { research: "研究", tools: "工具", review: "覆核", revision: "修正", finished: "結束" };
  const ROLE_TEXT = { researcher: "Researcher", reviewer: "Reviewer", system: "系統" };
  const RISK_TEXT = { high: ["資料品質風險：高", "b-bad"], medium: ["資料品質風險：中", "b-warn"], low: ["資料品質風險：低", "b-ok"] };
  const VALUATION_TEXT = {
    below_model: "低於模型估值", above_model: "高於模型估值", near_model: "接近模型估值",
    undeterminable: "無法判定", fixture_pending: "待 W05 規則（FIXTURE）"
  };
  const PDF_TEXT = { not_available: "線上 PDF 尚未提供（W07）", published: "可下載", pdf_failed: "PDF 產製失敗" };
  const OUTCOME_TEXT = { succeeded: null, insufficient_evidence: ["研究結果：資料不足", "b-warn"] };

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function fmtTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return esc(iso);
    return new Intl.DateTimeFormat("zh-TW", {
      timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false
    }).format(d);
  }
  function badge(text, cls) { return `<span class="badge ${cls}">${esc(text)}</span>`; }
  function setStatus(text) { pageStatus.textContent = text; }

  async function getJson(url, options) {
    const res = await fetch(url, options);
    const type = res.headers.get("content-type") || "";
    const body = type.includes("application/json") ? await res.json() : null;
    if (!body) throw Object.assign(new Error(`伺服器回應非 JSON（HTTP ${res.status}）`), { status: res.status });
    if (!res.ok || body.ok === false) {
      throw Object.assign(new Error(body.message || body.error || `HTTP ${res.status}`), { status: res.status, body });
    }
    return body;
  }

  /* ---------------- favourites (localStorage, ≤5 codes, nothing else) ---------------- */
  const Favorites = {
    read() {
      try {
        const raw = JSON.parse(localStorage.getItem(FAV_KEY) || "[]");
        return Array.isArray(raw) ? raw.filter(c => FAV_ALLOWED.includes(c)).slice(0, FAV_MAX) : [];
      } catch { return []; }
    },
    write(list) {
      try { localStorage.setItem(FAV_KEY, JSON.stringify(list.slice(0, FAV_MAX))); return true; } catch { return false; }
    },
    add(code) {
      const list = this.read();
      if (!FAV_ALLOWED.includes(code) || list.includes(code)) return list;
      if (list.length >= FAV_MAX) { setStatus(`收藏最多 ${FAV_MAX} 檔，請先移除一檔`); return list; }
      list.push(code); this.write(list); return list;
    },
    remove(code) { const list = this.read().filter(c => c !== code); this.write(list); return list; }
  };

  function renderFavorites() {
    const list = Favorites.read();
    $("#favList").innerHTML = list.length
      ? list.map(code => `<span class="fav">★ ${esc(code)}${CFG.comparisonOnly.includes(code) ? "（比較）" : ""}
          <button type="button" data-unfav="${esc(code)}" aria-label="移除收藏 ${esc(code)}">×</button></span>`).join("")
      : `<span class="hint" style="margin:0">尚無收藏。收藏只影響清單篩選，不會啟動研究。</span>`;
    const selected = currentTicker();
    const on = list.includes(selected);
    const btn = $("#favToggle");
    btn.textContent = on ? `★ 已收藏 ${selected}` : `☆ 收藏 ${selected}`;
    btn.setAttribute("aria-pressed", String(on));
    renderReports();
  }

  /* ---------------- published reports (server metadata, read-only) ---------------- */
  let published = null;
  let publishedError = null;

  async function loadPublished() {
    try {
      published = await getJson("/api/ui/published");
      publishedError = null;
    } catch (err) {
      published = null; publishedError = err;
    }
    renderReports();
  }

  function renderReports() {
    const box = $("#reportList");
    if (publishedError) {
      box.innerHTML = `<div class="empty error-box">已發布清單讀取失敗：${esc(publishedError.message)}</div>`;
      return;
    }
    if (!published) return;
    const favs = Favorites.read();
    let rows = published.reports.slice();
    if ($("#onlyFav").checked) rows = rows.filter(r => favs.includes(r.ticker));
    const dir = $("#sortOrder").value === "asc" ? 1 : -1;
    rows.sort((a, b) => dir * (Date.parse(a.published_at || 0) - Date.parse(b.published_at || 0)));
    if (!rows.length) {
      box.innerHTML = `<div class="empty">${$("#onlyFav").checked ? "收藏中的股票還沒有已發布研究。" : "目前沒有已發布研究。"}</div>`;
      return;
    }
    box.innerHTML = rows.map(r => {
      const risk = RISK_TEXT[r.data_quality_risk] || ["資料品質風險：未提供", "b-neutral"];
      const outcome = OUTCOME_TEXT[r.research_outcome];
      return `<article class="report-card" data-report="${esc(r.report_version_id)}">
        <header>
          <b>${esc(r.ticker)} ${esc(r.company)}</b>
          <span class="tags">${r.synthetic_fixture ? badge("FIXTURE", "b-fixture") : ""}${badge("已發布", "b-ok")}${favs.includes(r.ticker) ? badge("★ 收藏", "b-run") : ""}</span>
        </header>
        <div class="meta">
          <span>版本 <b class="mono">${esc(r.report_version_id)}</b></span>
          <span>發布 <b>${fmtTime(r.published_at)}</b></span>
          <span>資料截止 <b>${fmtTime(r.cutoff_at)}</b></span>
          <span>財報期 <b>${esc(r.financial_period || "NA（無可用財報）")}</b></span>
          <span>來源更新 <b>${fmtTime(r.data_updated_at)}</b></span>
          <span>估值狀態 <b>${esc(VALUATION_TEXT[r.valuation_status] || "未提供")}</b></span>
          <span>PDF <b>${esc(PDF_TEXT[r.pdf_status] || "未提供")}</b></span>
        </div>
        <div class="tags">
          ${badge(risk[0], risk[1])}
          ${outcome ? badge(outcome[0], outcome[1]) : ""}
          ${r.snapshot_stale ? badge("快照過期", "b-warn") : ""}
        </div>
        ${r.data_quality_reason ? `<div class="hint" style="margin:0">${esc(r.data_quality_reason)}</div>` : ""}
      </article>`;
    }).join("");
  }

  /* ---------------- research entry (MOCK only) ---------------- */
  function currentTicker() {
    const el = document.querySelector('input[name="ticker"]:checked');
    return el ? el.value : CFG.researchTickers[0];
  }

  function sessionNonce() {
    try {
      let n = sessionStorage.getItem("fintech-agent.ui-nonce");
      if (!n) { n = Math.random().toString(36).slice(2, 10); sessionStorage.setItem("fintech-agent.ui-nonce", n); }
      return n;
    } catch { return "nostorage"; }
  }

  function cutoffIso() {
    const v = $("#cutoff").value; // local wall time, interpreted as Asia/Taipei
    return v ? `${v}:00+08:00` : "";
  }

  let inFlight = false;
  async function submitJob(event) {
    event.preventDefault();
    if (!CFG.mockEnabled || inFlight) return;
    const ticker = currentTicker();
    if (!CFG.researchTickers.includes(ticker)) { setStatus(`${ticker} 不能建立研究 job`); return; }
    const cutoff = cutoffIso();
    if (!cutoff) { setStatus("請填資料截止時間"); return; }
    const mode = $("#mode").value;
    const scenario = $("#scenario") ? $("#scenario").value : "succeeded";
    const key = `ui-${ticker}-${cutoff}-${mode}-${scenario}-${sessionNonce()}`;
    inFlight = true;
    $("#submitJob").disabled = true;
    setStatus("送出研究中…");
    try {
      const body = await getJson("/api/ui/mock/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, cutoff_at: cutoff, mode, scenario, idempotency_key: key })
      });
      setStatus(body.created ? "已建立 MOCK job" : "相同條件已有 job，沿用原 job");
      openJob(body.job.job_id);
    } catch (err) {
      renderJobError(err);
      setStatus("送出失敗");
    } finally {
      inFlight = false;
      $("#submitJob").disabled = !CFG.mockEnabled;
    }
  }

  /* ---------------- job status + trace (from the job DB) ---------------- */
  let pollTimer = null;
  let currentJobId = null;

  function openJob(jobId) {
    currentJobId = jobId;
    const url = new URL(location.href);
    url.searchParams.set("job", jobId);
    history.replaceState(null, "", url);
    $("#jobPanel").innerHTML = `<div class="empty">讀取 job 狀態中…</div>`;
    poll();
  }

  async function poll() {
    clearTimeout(pollTimer);
    if (!currentJobId) return;
    const jobId = currentJobId;
    try {
      const body = await getJson(`/api/ui/jobs/${encodeURIComponent(jobId)}`);
      if (jobId !== currentJobId) return;
      renderJob(body.job);
      renderTrace(body.events);
      if (!TERMINAL.includes(body.job.status)) pollTimer = setTimeout(poll, POLL_MS);
      else setStatus(`job ${STATUS_TEXT[body.job.status][0]}`);
    } catch (err) {
      renderJobError(err);
      if (err.status >= 500 || !err.status) pollTimer = setTimeout(poll, POLL_MS * 3);
    }
  }

  function meter(label, used, max, unit = "") {
    const value = Number(used) || 0;
    const pct = Math.min(100, Math.round((value / max) * 100));
    return `<div class="meter"><span>${esc(label)}</span><span class="bar"><i class="${pct >= 100 ? "full" : ""}" style="width:${pct}%"></i></span><span>${esc(value)}${unit}/${max}${unit}</span></div>`;
  }

  function renderJob(job) {
    const [text, cls] = STATUS_TEXT[job.status] || [job.status, "b-neutral"];
    let note = "";
    if (job.status === "queued") note = `<p class="hint">一次只執行 1 個 job，前面還有 ${esc(job.queue_ahead ?? 0)} 個。</p>`;
    if (job.status === "insufficient_evidence") note = `<p class="hint">資料不足時不產生買賣評級；停止原因見下方與軌跡。</p>`;
    $("#jobPanel").innerHTML = `
      <div class="actions">${badge(text, cls)}${badge(`階段：${STAGE_TEXT[job.stage] || job.stage}`, "b-neutral")}${job.mock ? badge("MOCK", "b-fixture") : ""}</div>
      ${note}
      <dl class="kv">
        <dt>標的</dt><dd>${esc(job.ticker)}・${esc(job.mode)}</dd>
        <dt>資料截止</dt><dd>${fmtTime(job.cutoff_at)}</dd>
        <dt>快照</dt><dd class="mono">${esc(job.source_snapshot_id)}</dd>
        <dt>模型</dt><dd>${esc(job.model_id || "未設定（MOCK 不呼叫模型）")}・prompt ${esc(job.prompt_version)}</dd>
        <dt>停止原因</dt><dd>${esc(job.stop_reason || "—")}</dd>
        <dt>job_id</dt><dd class="mono">${esc(job.job_id)}</dd>
      </dl>
      <div class="meters">
        ${meter("模型請求", job.calls_used, 8)}
        ${meter("工具呼叫", job.tool_calls_used, 10)}
        ${meter("補查輪數", job.supplement_rounds, 2)}
        ${meter("主動時間", Math.round(job.active_seconds || 0), 180, "s")}
      </div>`;
  }

  function renderJobError(err) {
    const msg = err.status === 403 ? "研究入口未啟用（只開放 MOCK 測試環境）。"
      : err.status === 404 ? "找不到這個 job，可能不是 MOCK job 或已被清除。"
      : err.message;
    $("#jobPanel").innerHTML = `<div class="empty error-box">${esc(msg)}</div>`;
  }

  function renderTrace(events) {
    if (!events || !events.length) {
      $("#tracePanel").innerHTML = `<div class="empty">job 尚未開始，還沒有動作紀錄。</div>`;
      return;
    }
    $("#tracePanel").innerHTML = `<ol class="trace">${events.map(e => {
      const d = e.detail || {};
      return `<li class="r-${esc(e.role || "system")}">
        <span class="seq">#${esc(e.event_seq)}</span>
        <div>
          <div class="line1">${badge(ROLE_TEXT[e.role] || e.role || "系統", "b-neutral")}<b>${esc(e.event_type)}</b>${e.tool_name ? badge(e.tool_name, "b-run") : ""}${d.mock ? badge("MOCK", "b-fixture") : ""}<span class="hint" style="margin:0">${fmtTime(e.created_at)}</span></div>
          ${d.summary ? `<div class="line2">${esc(d.summary)}</div>` : ""}
          ${d.decision_summary ? `<div class="line2">決策摘要：${esc(d.decision_summary)}</div>` : ""}
        </div>
      </li>`;
    }).join("")}</ol>`;
  }

  /* ---------------- wiring ---------------- */
  $("#entryForm").addEventListener("submit", submitJob);
  document.querySelectorAll('input[name="ticker"]').forEach(el => el.addEventListener("change", renderFavorites));
  $("#favToggle").addEventListener("click", () => {
    const code = currentTicker();
    Favorites.read().includes(code) ? Favorites.remove(code) : Favorites.add(code);
    renderFavorites();
  });
  $("#favAdd").addEventListener("change", e => { if (e.target.value) Favorites.add(e.target.value); e.target.value = ""; renderFavorites(); });
  $("#favList").addEventListener("click", e => { const c = e.target.dataset.unfav; if (c) { Favorites.remove(c); renderFavorites(); } });
  $("#onlyFav").addEventListener("change", renderReports);
  $("#sortOrder").addEventListener("change", renderReports);

  renderFavorites();
  loadPublished();
  const jobParam = new URL(location.href).searchParams.get("job");
  if (jobParam) openJob(jobParam);
})();
