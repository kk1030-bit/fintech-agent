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
    succeeded: ["研究完成・待人工核准", "b-ok"],
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
  function fmtTime(iso, withSeconds = false) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return esc(iso);
    const opts = { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false };
    if (withSeconds) opts.second = "2-digit";
    return new Intl.DateTimeFormat("zh-TW", opts).format(d);
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
        <div class="actions"><button type="button" class="ghost" data-open-report="${esc(r.report_version_id)}">開啟報告</button></div>
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

  function syncEntry(job) {
    const radio = document.getElementById(`t${job.ticker}`);
    if (radio && !radio.checked) { radio.checked = true; renderFavorites(); }
  }

  function renderJob(job) {
    syncEntry(job);
    const [text, cls] = STATUS_TEXT[job.status] || [job.status, "b-neutral"];
    let note = "";
    if (job.status === "queued") note = `<p class="hint">一次只執行 1 個 job，前面還有 ${esc(job.queue_ahead ?? 0)} 個。</p>`;
    const NOTES = {
      insufficient_evidence: "資料不足時不產生買賣評級；具體缺口見停止原因與軌跡。",
      paused_quota: "已暫停：額度用盡時保存檢查點。恢復後沿用累計請求數，不會歸零；不會自動狂重試。",
      failed: "執行失敗：已完成的步驟保留在軌跡中；失敗不會被標成完成。",
      timed_out: "主動執行時間達 180 秒上限，已停止並保存檢查點，不冒充成功。",
      cancelled: "已由操作者取消；已花費的預算與已完成步驟保留。",
      succeeded: "研究流程完成，但尚未經人工核准，所以不會出現在已發布清單。"
    };
    if (NOTES[job.status]) note = `<p class="hint">${esc(NOTES[job.status])}</p>`;
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
      </div>
      ${job.mock && job.status === "running" ? `<div class="actions" style="margin-top:12px"><button type="button" class="danger" id="cancelJob">取消這個 job</button></div>` : ""}`;
    const cancel = $("#cancelJob");
    if (cancel) cancel.addEventListener("click", cancelJob);
  }

  function renderJobError(err) {
    const msg = err.status === 403 ? "研究入口未啟用（只開放 MOCK 測試環境）。"
      : err.status === 404 ? "找不到這個 job，可能不是 MOCK job 或已被清除。"
      : err.message;
    $("#jobPanel").innerHTML = `<div class="empty error-box">${esc(msg)}</div>`;
  }

  const TOOL_STATUS = { ok: ["ok", "b-ok"], no_data: ["no_data", "b-warn"], invalid_input: ["invalid_input", "b-bad"] };

  function renderTrace(events) {
    if (!events || !events.length) {
      $("#tracePanel").innerHTML = `<div class="empty">job 尚未開始，還沒有動作紀錄。</div>`;
      return;
    }
    $("#tracePanel").innerHTML = `<ol class="trace">${events.map(e => {
      const d = e.detail || {};
      const ts = d.tool_status ? (TOOL_STATUS[d.tool_status] || [d.tool_status, "b-neutral"]) : null;
      const refs = Array.isArray(d.evidence_refs) && d.evidence_refs.length
        ? `<div class="line2">來源 ID：${d.evidence_refs.map(r => `<button type="button" class="ref" data-evidence="${esc(r)}">${esc(r)}</button>`).join(" ")}</div>`
        : (e.tool_name ? `<div class="line2">來源 ID：無</div>` : "");
      const args = d.args_redacted ? `<div class="line2 mono">參數 ${esc(JSON.stringify(d.args_redacted))}</div>` : "";
      const meta = [d.latency_ms != null ? `耗時 ${esc(d.latency_ms)} ms` : "", d.output_hash ? `輸出 hash ${esc(d.output_hash)}` : ""].filter(Boolean).join("・");
      return `<li class="r-${esc(e.role || "system")}">
        <span class="seq">#${esc(e.event_seq)}</span>
        <div>
          <div class="line1">${badge(ROLE_TEXT[e.role] || e.role || "系統", "b-neutral")}<b>${esc(e.event_type)}</b>${e.tool_name ? badge(e.tool_name, "b-run") : ""}${ts ? badge(ts[0], ts[1]) : ""}${d.mock ? badge("MOCK", "b-fixture") : ""}<span class="hint" style="margin:0">${fmtTime(e.created_at, true)}</span></div>
          ${d.summary ? `<div class="line2">${esc(d.summary)}</div>` : ""}
          ${d.decision_summary ? `<div class="line2">決策摘要：${esc(d.decision_summary)}</div>` : ""}
          ${args}${refs}
          ${meta ? `<div class="line2">${meta}</div>` : ""}
        </div>
      </li>`;
    }).join("")}</ol>`;
  }

  async function cancelJob() {
    if (!currentJobId) return;
    const btn = $("#cancelJob");
    if (btn) btn.disabled = true;
    try {
      await getJson(`/api/ui/mock/jobs/${encodeURIComponent(currentJobId)}/cancel`, { method: "POST" });
      setStatus("已取消 job");
    } catch (err) {
      setStatus(`取消失敗：${err.message}`);
    }
    poll();
  }

  /* ---------------- W04: report detail ---------------- */
  const KIND = { fact: ["事實", "k-fact"], inference: ["推論", "k-inference"], unknown: ["未知", "k-unknown"] };
  let currentReportId = null;

  function refButtons(list, reportId) {
    if (!list || !list.length) return "";
    return list.map(r => `<button type="button" class="ref${r.exists ? "" : " missing"}" data-evidence="${esc(r.id)}"${reportId ? ` data-report="${esc(reportId)}"` : ""} title="${r.exists ? "開啟精確來源版本" : "快照中沒有這個來源片段"}">${esc(r.id)}</button>`).join(" ");
  }

  async function openReport(rvId) {
    currentReportId = rvId;
    const url = new URL(location.href);
    url.searchParams.set("report", rvId);
    history.replaceState(null, "", url);
    const panel = $("#reportPanel");
    panel.innerHTML = `<div class="empty">讀取報告中…</div>`;
    try {
      const body = await getJson(`/api/ui/reports/${encodeURIComponent(rvId)}`);
      if (rvId !== currentReportId) return;
      renderReport(body.report);
      $("#reportSection").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      panel.innerHTML = `<div class="empty error-box">${err.status === 404 ? "找不到這份已發布報告（未核准版本不公開）。" : esc(err.message)}</div>`;
    }
  }

  function renderReport(r) {
    const risk = RISK_TEXT[r.data_quality_risk] || ["資料品質風險：未提供", "b-neutral"];
    const outcome = OUTCOME_TEXT[r.research_outcome];
    const counts = { fact: 0, inference: 0, unknown: 0 };
    r.claims.forEach(c => { counts[c.kind] = (counts[c.kind] || 0) + 1; });
    const list = items => items && items.length ? `<ul class="plain">${items.map(i => `<li>${esc(i)}</li>`).join("")}</ul>` : `<p class="hint" style="margin:0">無</p>`;
    $("#reportPanel").innerHTML = `
      <div class="actions">
        <b style="font-size:16px">${esc(r.ticker)} ${esc(r.company)}</b>
        ${r.synthetic_fixture ? badge("FIXTURE", "b-fixture") : ""}${badge("已發布", "b-ok")}${badge(risk[0], risk[1])}
        ${outcome ? badge(outcome[0], outcome[1]) : ""}${r.snapshot_stale ? badge("快照過期", "b-warn") : ""}
      </div>
      <p class="hint">${esc(r.question)}</p>
      <dl class="kv">
        <dt>版本</dt><dd class="mono">${esc(r.report_version_id)}</dd>
        <dt>資料截止</dt><dd>${fmtTime(r.cutoff_at)}</dd>
        <dt>財報期</dt><dd>${esc(r.financial_period || "NA（無可用財報）")}</dd>
        <dt>來源更新</dt><dd>${fmtTime(r.data_updated_at)}${r.snapshot_stale ? "（快照過期，可能非最新）" : ""}</dd>
        <dt>快照</dt><dd class="mono">${esc(r.source_snapshot_id)}</dd>
        <dt>模型／prompt</dt><dd>${esc(r.model_id || "無（FIXTURE，非 Agent 產出）")}・${esc(r.prompt_version)}</dd>
        <dt>PDF</dt><dd>${esc(PDF_TEXT[r.pdf_status] || "未提供")}</dd>
      </dl>
      <div class="sub">主張（事實 ${counts.fact}・推論 ${counts.inference}・未知 ${counts.unknown}）</div>
      <div class="claims">${r.claims.map(c => {
        const k = KIND[c.kind] || [c.kind, "b-neutral"];
        return `<div class="claim">
          <div class="head"><span class="mono">${esc(c.claim_id)}</span>${badge(k[0], k[1])}${c.unsourced ? badge("無來源", "b-bad") : ""}${c.limitations && c.limitations.length ? badge("有限制", "b-warn") : ""}</div>
          <p>${esc(c.text)}</p>
          <div class="refs">來源：${c.evidence.length ? refButtons(c.evidence, r.report_version_id) : "無"}</div>
          ${c.limitations && c.limitations.length ? `<div class="refs">限制：${c.limitations.map(esc).join("；")}</div>` : ""}
        </div>`;
      }).join("")}</div>
      <div class="sub">反向證據</div>${list(r.counter_evidence)}
      <div class="sub">下一個確認訊號</div>${list(r.next_signals)}
      <div class="sub">方法與資料限制</div>${list(r.limitations)}
      <p class="footnote">「無來源」的主張不能當作事實；刪除線的來源 ID 表示快照中找不到該片段。</p>`;
  }

  /* ---------------- W04: peer comparison ---------------- */
  const METRICS = [
    ["pe_ttm", "P/E (TTM)", v => v.toFixed(2) + " 倍"],
    ["pb", "P/B", v => v.toFixed(2) + " 倍"],
    ["revenue_yoy_quarter", "單季營收 YoY", v => (v * 100).toFixed(1) + "%"],
    ["fcf_ttm", "FCF (TTM)", v => v.toLocaleString("zh-TW", { maximumFractionDigits: 1 }) + " 億元"],
    ["dcf_gap", "DCF 差距", v => (v * 100).toFixed(1) + "%"]
  ];
  const ROLE = { subject: ["主體", "b-run"], peer: ["同業", "b-neutral"], industry_reference: ["產業參照・不入平均", "b-warn"] };

  function cell(m, fmt) {
    if (m.value !== null && m.value !== undefined) {
      const mismatch = m.consistent === false ? `<div class="cell-na">與 B 快照 ${esc(m.snapshot_value)} 不一致</div>` : "";
      return `<span class="cell-val">${esc(fmt(m.value))}</span>${mismatch}`;
    }
    const snap = m.snapshot_value !== null && m.snapshot_value !== undefined
      ? `<div class="cell-snap">B 快照值 ${esc(fmt(Number(m.snapshot_value)))}・工具未能重現</div>` : "";
    return `<span class="cell-val">NA</span><div class="cell-na">${esc(m.na_reason)}</div>${snap}`;
  }

  async function loadComparison() {
    const panel = $("#comparisonPanel");
    try {
      const d = await getJson("/api/ui/comparison/2454");
      const ps = d.peer_stats;
      panel.innerHTML = `
        <div class="cmp-head">
          ${d.synthetic_fixture ? badge("FIXTURE／待 B、D 確認", "b-fixture") : ""}
          <span>報價基準日 ${esc(d.price_as_of)}</span>・<span>資料截止 ${fmtTime(d.cutoff_at)}</span>・<span class="mono">${esc(d.method_version)}</span>
          ${d.periods_consistent ? "" : badge("財報期不一致", "b-warn")}
        </div>
        <table class="cmp-table">
          <thead><tr><th>公司（角色）</th><th>財報期／收盤</th>${METRICS.map(m => `<th>${m[1]}</th>`).join("")}<th>來源</th></tr></thead>
          <tbody>${d.rows.map(r => {
            const role = ROLE[r.role] || [r.role, "b-neutral"];
            return `<tr class="${r.role === "industry_reference" ? "ref-row" : ""}">
              <td class="name-cell"><b>${esc(r.ticker)} ${esc(r.name)}</b><br>${badge(role[0], role[1])}</td>
              <td><span class="lbl-m">財報期／收盤</span><span>${esc(r.financial_period || "NA")}（${esc(r.quarters_available)} 季可得）<br>${r.price ? `${esc(r.price.value)} 元・${esc(r.price.trade_date)}` : `<span class="cell-na">無同日收盤價</span>`}</span></td>
              ${METRICS.map(m => `<td><span class="lbl-m">${m[1]}</span><span>${cell(r.metrics[m[0]], m[2])}</span></td>`).join("")}
              <td><span class="lbl-m">來源</span><span>${refButtons(r.evidence) || "無"}</span></td>
            </tr>`;
          }).join("")}</tbody>
        </table>
        <p class="hint"><b>同業平均 P/E：</b>${ps.pe_ttm !== null ? `${esc(ps.pe_ttm)} 倍（n=${esc(ps.n)}）` : `NA・${esc(ps.na_reason)}`}${ps.snapshot_value != null ? `（B 快照值 ${esc(ps.snapshot_value)}，未採用）` : ""}<br>${esc(ps.basis)}；排除：${esc(ps.excluded.join("、"))}</p>
        ${d.checks.length ? `<details><summary class="hint" style="cursor:pointer">待 B、D 處理的 ${d.checks.length} 項資料問題</summary><ul class="checks">${d.checks.map(c => `<li>${esc(c.ticker)}・${esc(c.metric)}：${esc(c.issue)}</li>`).join("")}</ul></details>` : ""}
        <p class="footnote">主值只顯示工具可由快照重現的數字；缺值一律 NA＋原因，不以 0 補。P/E、P/B 不使用營收或獲利比代替。</p>`;
    } catch (err) {
      panel.innerHTML = `<div class="empty error-box">比較資料讀取失敗：${esc(err.message)}</div>`;
    }
  }

  /* ---------------- W04: source drawer ---------------- */
  let lastFocus = null;
  function closeDrawer() {
    $("#drawer").hidden = true; $("#drawerBackdrop").hidden = true;
    if (lastFocus) lastFocus.focus();
  }
  async function openEvidence(id, reportId, trigger) {
    lastFocus = trigger || null;
    $("#drawer").hidden = false; $("#drawerBackdrop").hidden = false;
    $("#drawerTitle").textContent = "來源";
    $("#drawerBody").innerHTML = `<div class="empty">讀取 ${esc(id)}…</div>`;
    $("#drawerClose").focus();
    try {
      const q = reportId ? `?report=${encodeURIComponent(reportId)}` : "";
      const { evidence: e } = await getJson(`/api/ui/evidence/${encodeURIComponent(id)}${q}`);
      $("#drawerBody").innerHTML = `
        <div class="actions">${e.synthetic_fixture ? badge("FIXTURE", "b-fixture") : ""}${e.hash_match ? badge("hash 吻合", "b-ok") : badge("hash 不符・待 B 核對", "b-bad")}${e.cutoff_check ? badge(e.cutoff_check, e.cutoff_check.startsWith("cutoff 前") ? "b-ok" : "b-bad") : ""}</div>
        <dl class="kv">
          <dt>來源版本</dt><dd class="mono">${esc(e.evidence_version_id)}</dd>
          <dt>可得時間</dt><dd>${fmtTime(e.available_at)}</dd>
          <dt>原始來源</dt><dd><a href="${esc(e.source_url)}" target="_blank" rel="noopener noreferrer">${esc(e.source_url)}</a></dd>
        </dl>
        <div class="quote">${esc(e.paragraph)}</div>
        <dl class="kv">
          <dt>記錄 hash</dt><dd class="mono">${esc(e.content_hash)}</dd>
          <dt>重算 hash</dt><dd class="mono">${esc(e.computed_hash)}</dd>
          <dt>算法</dt><dd>${esc(e.hash_algorithm)}</dd>
        </dl>
        <p class="footnote">片段取自不可變快照（read_evidence），不是即時網頁；原始來源連結目前是 MOPS 查詢頁，需 B 補精確連結。</p>`;
    } catch (err) {
      const msg = err.body && err.body.error === "no_data" ? "快照中沒有這個來源片段 → 「無來源」。引用它的主張不能當作事實。"
        : err.body && err.body.error === "not_referenced" ? "這個 ID 不是已發布報告或比較面板引用的來源（例如搜尋結果的 source_id），所以不開放。"
        : err.message;
      $("#drawerBody").innerHTML = `<p class="mono">${esc(id)}</p><div class="empty error-box">${esc(msg)}</div>`;
    }
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

  document.addEventListener("click", e => {
    const ref = e.target.closest("[data-evidence]");
    if (ref) { openEvidence(ref.dataset.evidence, ref.dataset.report || currentReportId, ref); return; }
    const rep = e.target.closest("[data-open-report]");
    if (rep) openReport(rep.dataset.openReport);
  });
  $("#drawerClose").addEventListener("click", closeDrawer);
  $("#drawerBackdrop").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#drawer").hidden) closeDrawer(); });

  renderFavorites();
  loadPublished();
  loadComparison();
  const reportParam = new URL(location.href).searchParams.get("report");
  if (reportParam) openReport(reportParam);
  const jobParam = new URL(location.href).searchParams.get("job");
  if (jobParam) openJob(jobParam);
})();
