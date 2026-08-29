const DATA_URL = "./data/latest.json";
const MANIFEST_URL = "./data/manifest.json";
const SETTINGS_KEY = "stocklab.free.settings.v2";
const LOCAL_FAVORITES_KEY = "stocklab.free.favorites.v2";
const LOCAL_TOMBSTONES_KEY = "stocklab.free.favorite-tombstones.v1";
const SCANNER_PRESETS_KEY = "stocklab.free.scanner.presets.v1";

const state = {
  data: null,
  manifest: null,
  activeView: location.hash.replace("#", "") || "overview",
  selectedStock: null,
  newsFilter: "all",
  snapshot: null,
  favorites: new Map(),
  tombstones: new Map(),
  remoteAvailable: false,
  settings: loadSettings(),
  scanner: {
    minComposite: 55,
    aboveMa20: false,
    positiveNews: false,
    foreignBuy: false,
    lowRsi: false,
    volumeSurge: false,
    riskBelow: false,
  },
};

const app = document.querySelector("#app");
const toastNode = document.querySelector("#toast");
const dialog = document.querySelector("#stock-dialog");
const dialogContent = document.querySelector("#stock-dialog-content");

function loadSettings() {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
  } catch {
    saved = {};
  }
  return {
    endpoint: saved.endpoint || "",
    syncId: saved.syncId || `device-${(crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`).slice(0, 12)}`,
    password: saved.password || "",
    autoSync: saved.autoSync !== false,
  };
}

function saveSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(state.settings));
}

function loadLocalFavorites() {
  try {
    const rows = JSON.parse(localStorage.getItem(LOCAL_FAVORITES_KEY) || "[]");
    return new Map(rows.map((item) => [String(item.symbol), item]));
  } catch {
    return new Map();
  }
}

function loadLocalTombstones() {
  try {
    const rows = JSON.parse(localStorage.getItem(LOCAL_TOMBSTONES_KEY) || "[]");
    return new Map(rows.map((item) => [String(item.symbol), item]));
  } catch {
    return new Map();
  }
}

function saveLocalTombstones() {
  const cutoff = Date.now() - 180 * 24 * 60 * 60 * 1000;
  const rows = [...state.tombstones.values()]
    .filter((item) => {
      const value = Date.parse(item.updated_at || "");
      return !Number.isFinite(value) || value >= cutoff;
    })
    .sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")))
    .slice(0, 200);
  state.tombstones = new Map(rows.map((item) => [String(item.symbol), item]));
  localStorage.setItem(LOCAL_TOMBSTONES_KEY, JSON.stringify(rows));
}

function timestampValue(value) {
  const parsed = Date.parse(value || "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function saveLocalFavorites() {
  localStorage.setItem(LOCAL_FAVORITES_KEY, JSON.stringify([...state.favorites.values()]));
  updateFavoriteCount();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
}

function formatNumber(value, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("zh-TW", { maximumFractionDigits: digits }).format(n);
}

function formatCompact(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("zh-TW", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function formatPct(value, digits = 1, signed = false) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const sign = signed && n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return escapeHtml(value);
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: value.includes?.("T") ? "2-digit" : undefined,
    minute: value.includes?.("T") ? "2-digit" : undefined,
    timeZone: "Asia/Taipei",
  }).format(d);
}

function scoreTone(score) {
  const n = Number(score) || 0;
  if (n >= 68) return "good";
  if (n >= 48) return "warn";
  return "bad";
}

function directionClass(value) {
  const v = String(value || "").toLowerCase();
  if (["positive", "bullish", "up", "正向", "利多"].includes(v)) return "positive";
  if (["negative", "bearish", "down", "負向", "利空"].includes(v)) return "negative";
  return "neutral";
}

function changeClass(value) {
  const n = Number(value) || 0;
  return n > 0 ? "up" : n < 0 ? "down" : "flat";
}

function showToast(message) {
  toastNode.textContent = message;
  toastNode.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toastNode.classList.remove("show"), 2600);
}

function updateFavoriteCount() {
  document.querySelector("#favorite-count").textContent = String(state.favorites.size);
}

async function fetchJson(url) {
  const separator = url.includes("?") ? "&" : "?";
  const response = await fetch(`${url}${separator}t=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function jsonp(endpoint, params = {}, timeoutMs = 12000) {
  return new Promise((resolve, reject) => {
    const callbackName = `__stocklab_cb_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const script = document.createElement("script");
    const timer = setTimeout(() => cleanup(new Error("同步逾時")), timeoutMs);
    const cleanup = (error, result) => {
      clearTimeout(timer);
      script.remove();
      delete window[callbackName];
      error ? reject(error) : resolve(result);
    };
    window[callbackName] = (result) => cleanup(null, result);
    script.onerror = () => cleanup(new Error("無法連線 Google Apps Script"));
    const query = new URLSearchParams({
      ...params,
      callback: callbackName,
      _: String(Date.now()),
    });
    script.src = `${endpoint}${endpoint.includes("?") ? "&" : "?"}${query}`;
    document.head.appendChild(script);
  });
}

async function favoriteRemote(action, extra = {}) {
  const { endpoint, syncId, password } = state.settings;
  if (!endpoint) throw new Error("尚未設定 Apps Script 網址");
  const result = await jsonp(endpoint, {
    action,
    user_key: syncId,
    password,
    ...extra,
  });
  if (!result?.ok) throw new Error(result?.error || "同步失敗");
  return result;
}

async function syncFavorites({ silent = false } = {}) {
  if (!state.settings.endpoint || !state.settings.autoSync) return;
  try {
    const result = await favoriteRemote("list", { include_deleted: "1" });
    const remote = Array.isArray(result.items) ? result.items : [];
    const remoteBySymbol = new Map(remote.map((item) => [String(item.symbol), item]));
    const pending = [];

    // Merge by updated_at. Remote tombstones propagate deletions across devices, while
    // newer local edits or offline deletions are pushed back to Google Sheets.
    for (const item of remote) {
      const key = String(item.symbol);
      const local = state.favorites.get(key);
      const tombstone = state.tombstones.get(key);
      const remoteTime = timestampValue(item.updated_at);
      const localTime = timestampValue(local?.updated_at);
      const tombstoneTime = timestampValue(tombstone?.updated_at);

      if (item.deleted) {
        if (local && localTime > remoteTime) {
          pending.push({ action: "add", item: local });
        } else {
          state.favorites.delete(key);
          state.tombstones.set(key, { symbol: key, updated_at: item.updated_at || new Date().toISOString() });
        }
      } else if (tombstone && tombstoneTime > remoteTime) {
        state.favorites.delete(key);
        pending.push({ action: "remove", item: tombstone });
      } else if (local && localTime > remoteTime) {
        pending.push({ action: "add", item: local });
      } else {
        state.favorites.set(key, item);
        state.tombstones.delete(key);
      }
    }

    for (const item of state.favorites.values()) {
      if (!remoteBySymbol.has(String(item.symbol))) pending.push({ action: "add", item });
    }
    for (const item of state.tombstones.values()) {
      if (!remoteBySymbol.has(String(item.symbol))) pending.push({ action: "remove", item });
    }

    const deduped = new Map();
    pending.forEach((entry) => deduped.set(`${entry.action}:${entry.item.symbol}`, entry));
    for (const { action, item } of deduped.values()) {
      const key = String(item.symbol);
      if (action === "add") {
        const response = await favoriteRemote("add", {
          symbol: key,
          name: item.name || findStock(key)?.name || "",
          note: item.note || "",
        });
        state.favorites.set(key, response.item || item);
        state.tombstones.delete(key);
      } else {
        await favoriteRemote("remove", { symbol: key });
        state.favorites.delete(key);
        state.tombstones.set(key, { symbol: key, updated_at: new Date().toISOString() });
      }
    }

    state.remoteAvailable = true;
    saveLocalFavorites();
    saveLocalTombstones();
    const activeCount = remote.filter((item) => !item.deleted).length;
    if (!silent) showToast(`Google Sheets 同步完成，目前 ${state.favorites.size} 個最愛（雲端原有 ${activeCount} 個）`);
  } catch (error) {
    state.remoteAvailable = false;
    if (!silent) showToast(`雲端同步失敗，已改用本機保存：${error.message}`);
  }
}

async function toggleFavorite(symbol) {
  const stock = findStock(symbol);
  if (!stock) return;
  const key = String(symbol);
  const exists = state.favorites.has(key);
  const now = new Date().toISOString();
  if (exists) {
    state.favorites.delete(key);
    state.tombstones.set(key, { symbol: key, updated_at: now });
  } else {
    state.favorites.set(key, {
      symbol: key,
      name: stock.name,
      note: "",
      created_at: now,
      updated_at: now,
    });
    state.tombstones.delete(key);
  }
  saveLocalFavorites();
  saveLocalTombstones();
  renderActiveView();
  try {
    if (state.settings.endpoint && state.settings.autoSync) {
      if (exists) {
        await favoriteRemote("remove", { symbol: key });
      } else {
        const response = await favoriteRemote("add", { symbol: key, name: stock.name, note: "" });
        state.favorites.set(key, response.item || state.favorites.get(key));
        state.tombstones.delete(key);
        saveLocalFavorites();
        saveLocalTombstones();
      }
      state.remoteAvailable = true;
      showToast(exists ? "已從我的最愛移除，Google Sheets 已同步" : "已加入我的最愛，Google Sheets 已同步");
    } else {
      showToast(exists ? "已從我的最愛移除（本機）" : "已加入我的最愛（本機）");
    }
  } catch (error) {
    state.remoteAvailable = false;
    showToast(`已保存在本機；Google Sheets 同步失敗：${error.message}`);
  }
}

async function saveFavoriteNote(symbol, note) {
  const key = String(symbol);
  const item = state.favorites.get(key);
  if (!item) return;
  item.note = note;
  item.updated_at = new Date().toISOString();
  state.favorites.set(key, item);
  state.tombstones.delete(key);
  saveLocalFavorites();
  saveLocalTombstones();
  try {
    if (state.settings.endpoint && state.settings.autoSync) {
      await favoriteRemote("add", {
        symbol: key,
        name: item.name || findStock(key)?.name || "",
        note,
      });
      showToast("備註已同步至 Google Sheets");
    } else {
      showToast("備註已保存在本機");
    }
  } catch (error) {
    showToast(`備註已保存在本機；雲端同步失敗：${error.message}`);
  }
}

function findStock(symbol, data = state.data) {
  return data?.stocks?.find((stock) => String(stock.symbol) === String(symbol));
}

function allNews(data = state.data) {
  return (data?.stocks || [])
    .flatMap((stock) => (stock.news || []).map((news) => ({ ...news, stock_symbol: stock.symbol, stock_name: stock.name })))
    .sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
}

function getTopStocks() {
  const configured = state.data?.top_picks;
  if (Array.isArray(configured)) {
    const symbols = configured.map((item) => (typeof item === "string" ? item : item.symbol));
    return symbols.map((symbol) => findStock(symbol)).filter(Boolean);
  }
  // Compatibility fallback for older datasets that did not yet contain top_picks.
  return [...(state.data?.stocks || [])].sort((a, b) => (b.scores?.composite || 0) - (a.scores?.composite || 0)).slice(0, 5);
}

function sparkline(history = [], width = 300, height = 78, className = "sparkline") {
  const points = history.map((row) => Number(row.close)).filter(Number.isFinite);
  if (points.length < 2) return `<div class="empty compact">無足夠走勢資料</div>`;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const coords = points.map((value, index) => {
    const x = (index / (points.length - 1)) * width;
    const y = height - 8 - ((value - min) / range) * (height - 16);
    return [x, y];
  });
  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;
  return `<svg class="${className}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="價格走勢圖"><polyline class="area" points="${area}"></polyline><polyline class="line" points="${line}"></polyline></svg>`;
}

function scoreBar(label, value) {
  const n = Math.max(-100, Math.min(100, Number(value) || 0));
  const normalized = (n + 100) / 2;
  return `<div class="score-row"><span>${escapeHtml(label)}</span><div class="score-track"><div class="score-fill ${n < 0 ? "negative" : ""}" style="width:${normalized}%"></div></div><b>${formatNumber(n)}</b></div>`;
}

function favoriteButton(stock) {
  const active = state.favorites.has(String(stock.symbol));
  return `<button type="button" class="favorite-button ${active ? "active" : ""}" data-action="toggle-favorite" data-symbol="${escapeHtml(stock.symbol)}" aria-label="${active ? "移除" : "加入"}我的最愛">${active ? "♥" : "♡"}</button>`;
}

function stockCard(stock, rank = null) {
  const score = Number(stock.scores?.composite) || 0;
  const change = Number(stock.price?.change_pct) || 0;
  const trend = stock.price?.history || [];
  return `<article class="card stock-card" data-action="open-stock" data-symbol="${escapeHtml(stock.symbol)}">
    <div class="card-header">
      <div style="display:flex;gap:10px;align-items:flex-start;min-width:0">
        ${rank ? `<span class="rank-badge">${rank}</span>` : ""}
        <div class="card-title"><h3>${escapeHtml(stock.name)}</h3><p>${escapeHtml(stock.symbol)} · ${escapeHtml(stock.industry || stock.market || "")}</p></div>
      </div>
      ${favoriteButton(stock)}
    </div>
    <div class="stock-main">
      <div><span class="stock-symbol">${escapeHtml(stock.price?.date || state.data?.as_of || "")}</span><div class="stock-price">${formatNumber(stock.price?.close, 2)}</div><span class="change ${changeClass(change)}">${formatPct(change, 2, true)}</span></div>
      <div class="composite-score ${scoreTone(score)}">${formatNumber(score)}</div>
    </div>
    ${sparkline(trend)}
    <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:12px">
      <span class="recommendation ${directionClass(stock.recommendation?.direction)}">${escapeHtml(stock.recommendation?.label || "資料觀察")}</span>
      <small style="color:var(--muted)">完整度 ${formatPct(stock.scores?.completeness || 0, 0)}</small>
    </div>
    <p class="reason">${escapeHtml(stock.recommendation?.reason || "尚無摘要")}</p>
  </article>`;
}

function newsCard(news) {
  const impact = Number(news.impact_score) || 0;
  const direction = directionClass(news.sentiment || news.direction);
  return `<article class="card news-card">
    <div class="news-impact ${direction}"><strong>${impact > 0 ? "+" : ""}${formatNumber(impact)}</strong><small>影響分</small></div>
    <div class="news-content">
      <h3><a href="${safeUrl(news.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(news.title)}</a></h3>
      <div class="news-meta"><span>${escapeHtml(news.stock_symbol || "")}${news.stock_name ? ` ${escapeHtml(news.stock_name)}` : ""}</span><span>${escapeHtml(news.source || "未知來源")}</span><span>${formatDate(news.published_at)}</span><span>信心 ${formatPct((news.confidence || 0) * 100, 0)}</span></div>
      <p class="news-explain">${escapeHtml(news.mechanism || news.summary || "模型尚未提供影響機制說明。")}</p>
      <div class="news-tags">
        <span class="tag">${escapeHtml(news.category || "其他")}</span>
        <span class="tag">${escapeHtml(news.horizon || "短中期")}</span>
        ${news.is_material_info ? '<span class="tag material">官方重大訊息</span>' : ""}
        ${(news.risk_factors || []).slice(0, 2).map((item) => `<span class="tag">風險：${escapeHtml(item)}</span>`).join("")}
      </div>
    </div>
    <div class="source-quality"><span>來源品質</span><b>${formatNumber((news.source_quality || 0) * 100)}</b></div>
  </article>`;
}

function header(title, description, actions = "") {
  return `<header class="page-header"><div><h1>${escapeHtml(title)}</h1><p>${escapeHtml(description)}</p></div>${actions ? `<div class="header-actions">${actions}</div>` : ""}</header>`;
}

function demoBanner(data = state.data) {
  if (data?.mode !== "demo") return "";
  return `<div class="banner"><span>⚠</span><div><strong>目前顯示示範快照，不是即時投資資訊。</strong> 部署後執行 GitHub Actions，系統會改成當日真實資料。示範資料不應用於交易決策。</div></div>`;
}

function renderOverview() {
  const data = state.data;
  const top = getTopStocks();
  const news = allNews().slice(0, 5);
  const modelLabel = data.model?.llm_enabled ? "Qwen LLM + 財經情緒模型" : "財經情緒模型 + 規則備援";
  app.innerHTML = `
    ${header("新聞驅動的台股分析", "每天自動抓取新聞、重大訊息與市場資料，解釋事件如何影響個股，並把最值得優先研究的標的置頂。", `<button class="button" data-view="settings" type="button">⚙ 設定雲端同步</button>`)}
    ${demoBanner()}
    <section class="hero">
      <div class="hero-copy">
        <span class="eyebrow">每日自動更新 · 免費開源</span>
        <h2>先看懂新聞的<em>影響路徑</em>，再看分數。</h2>
        <p>系統不只判斷正負面，還會估計影響強度、信心、作用期間與可能失效條件；每日前 ${top.length} 名會固定置頂。</p>
        <div class="hero-actions"><button class="button primary" data-view="daily" type="button">查看今日精選</button><button class="button ghost" data-view="validation" type="button">進入無洩漏驗證</button></div>
      </div>
      <div class="hero-meta">
        <div class="meta-card"><span>資料切點</span><strong>${escapeHtml(data.as_of || "—")}</strong></div>
        <div class="meta-card"><span>分析模式</span><strong>${escapeHtml(modelLabel)}</strong></div>
        <div class="meta-card"><span>追蹤股票</span><strong>${formatNumber(data.stocks?.length || 0)} 檔</strong></div>
      </div>
    </section>

    <section class="section">
      <div class="section-heading"><div><h2>★ 每日最佳置頂</h2><p>綜合新聞、技術、基本面、籌碼、風險與資料完整度排序。</p></div><button class="text-link" data-view="daily" type="button">查看完整排名 →</button></div>
      ${top.length ? `<div class="grid cols-${Math.min(3, Math.max(2, top.length))}">${top.slice(0, 3).map((stock, index) => stockCard(stock, index + 1)).join("")}</div>` : '<div class="empty"><strong>今天沒有標的通過全部置頂門檻</strong>系統不會為了湊滿名額而推上高風險或資料不足的股票。</div>'}
    </section>

    <section class="section">
      <div class="section-heading"><div><h2>市場摘要</h2><p>只呈現目前資料能支持的訊號，不以缺失資料硬湊分數。</p></div></div>
      <div class="grid cols-4">
        <div class="metric"><span>市場新聞溫度</span><strong class="${directionClass(data.market?.sentiment_label)}">${formatNumber(data.market?.news_temperature)}</strong><small>${escapeHtml(data.market?.sentiment_label || "中性")}</small></div>
        <div class="metric"><span>正向事件</span><strong class="positive">${formatNumber(data.market?.positive_news || 0)}</strong><small>影響分大於 +15</small></div>
        <div class="metric"><span>負向事件</span><strong class="negative">${formatNumber(data.market?.negative_news || 0)}</strong><small>影響分小於 -15</small></div>
        <div class="metric"><span>資料完整度中位數</span><strong>${formatPct(data.market?.median_completeness || 0, 0)}</strong><small>缺資料會降低總分信心</small></div>
      </div>
    </section>

    <section class="section">
      <div class="section-heading"><div><h2>最新重大新聞</h2><p>相同事件會先去重，避免轉載文章重複加分。</p></div><button class="text-link" data-view="news" type="button">全部新聞 →</button></div>
      <div class="grid">${news.length ? news.map(newsCard).join("") : '<div class="empty"><strong>目前沒有新聞</strong>下一次排程更新後再查看。</div>'}</div>
    </section>`;
}

function renderDaily() {
  const stocks = [...(state.data?.stocks || [])].sort((a, b) => (b.scores?.composite || 0) - (a.scores?.composite || 0));
  const topSymbols = new Set(getTopStocks().map((stock) => String(stock.symbol)));
  app.innerHTML = `
    ${header("每日精選與完整排名", "前幾名會自動置頂，但排名代表『值得優先研究』，不等同於保證上漲或直接買進建議。")}
    ${demoBanner()}
    <div class="banner info"><span>ⓘ</span><div>置頂條件會同時檢查資料完整度、風險折扣及最低綜合分，避免新聞很多但資料品質很差的股票被推上榜。</div></div>
    ${topSymbols.size ? `<div class="grid cols-3">${stocks.filter((stock) => topSymbols.has(String(stock.symbol))).map((stock, i) => stockCard(stock, i + 1)).join("")}</div>` : '<div class="empty"><strong>今日沒有通過全部門檻的置頂標的</strong>完整排名仍保留在下方，方便自行研究。</div>'}
    <section class="section">
      <div class="section-heading"><div><h2>全部追蹤標的</h2><p>點擊股票可查看新聞、技術、基本與籌碼明細。</p></div></div>
      <div class="table-wrap"><table><thead><tr><th>排名</th><th>股票</th><th>價格</th><th>新聞</th><th>技術</th><th>基本</th><th>籌碼</th><th>風險</th><th>完整度</th><th>總分</th><th></th></tr></thead><tbody>
      ${stocks.map((stock, index) => `<tr><td>${index + 1}${topSymbols.has(String(stock.symbol)) ? " ★" : ""}</td><td><button class="stock-link" data-action="open-stock" data-symbol="${escapeHtml(stock.symbol)}">${escapeHtml(stock.name)} <small>${escapeHtml(stock.symbol)}</small></button></td><td>${formatNumber(stock.price?.close, 2)} <span class="change ${changeClass(stock.price?.change_pct)}">${formatPct(stock.price?.change_pct, 1, true)}</span></td><td>${formatNumber(stock.scores?.news)}</td><td>${formatNumber(stock.scores?.technical)}</td><td>${formatNumber(stock.scores?.fundamental)}</td><td>${formatNumber(stock.scores?.institutional)}</td><td>${formatNumber(stock.scores?.risk)}</td><td>${formatPct(stock.scores?.completeness || 0, 0)}</td><td><strong class="${scoreTone(stock.scores?.composite)}">${formatNumber(stock.scores?.composite)}</strong></td><td>${favoriteButton(stock)}</td></tr>`).join("")}
      </tbody></table></div>
    </section>`;
}

function renderNews() {
  const filters = [
    ["all", "全部"], ["positive", "正向"], ["negative", "負向"], ["neutral", "中性"], ["material", "官方重訊"],
  ];
  let news = allNews();
  if (state.newsFilter === "material") news = news.filter((item) => item.is_material_info);
  else if (state.newsFilter !== "all") news = news.filter((item) => directionClass(item.sentiment || item.direction) === state.newsFilter);
  app.innerHTML = `
    ${header("新聞影響分析", "每則新聞都有方向、影響分、信心、時間範圍、作用機制與風險條件；來源品質也會影響加權。")}
    ${demoBanner()}
    <div class="filters">${filters.map(([key, label]) => `<button class="filter-chip ${state.newsFilter === key ? "active" : ""}" data-action="news-filter" data-filter="${key}" type="button">${label}</button>`).join("")}</div>
    <div class="grid">${news.length ? news.map(newsCard).join("") : '<div class="empty"><strong>此分類目前沒有新聞</strong>請切換其他篩選條件。</div>'}</div>`;
}

function scannerMatches(stock) {
  const s = state.scanner;
  if ((stock.scores?.composite || 0) < s.minComposite) return false;
  if (s.aboveMa20 && !(Number(stock.price?.close) > Number(stock.technical?.ma20))) return false;
  if (s.positiveNews && !(Number(stock.scores?.news) >= 20)) return false;
  if (s.foreignBuy && !(Number(stock.institutional?.foreign_net) > 0)) return false;
  if (s.lowRsi && !(Number(stock.technical?.rsi14) < 35)) return false;
  if (s.volumeSurge && !(Number(stock.technical?.volume_ratio) >= 1.5)) return false;
  if (s.riskBelow && !(Number(stock.scores?.risk) <= 45)) return false;
  return true;
}

function scannerCheck(key, title, description) {
  return `<label class="check-card"><input type="checkbox" data-scanner="${key}" ${state.scanner[key] ? "checked" : ""}><span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(description)}</small></span></label>`;
}

function loadPresets() {
  try { return JSON.parse(localStorage.getItem(SCANNER_PRESETS_KEY) || "[]"); } catch { return []; }
}

function renderScanner() {
  const matches = (state.data?.stocks || []).filter(scannerMatches).sort((a, b) => (b.scores?.composite || 0) - (a.scores?.composite || 0));
  const presets = loadPresets();
  app.innerHTML = `
    ${header("條件篩選", "保留傳統技術與籌碼篩選的優點，再加入新聞影響分與風險上限；所有勾選條件採 AND。", `<button class="button" data-action="save-preset" type="button">儲存目前條件</button>`)}
    ${demoBanner()}
    <div class="card">
      <div class="form-grid"><div class="field"><label for="min-composite">最低綜合分：<b id="min-composite-label">${state.scanner.minComposite}</b></label><input id="min-composite" type="range" min="0" max="100" value="${state.scanner.minComposite}" data-scanner-range="minComposite"></div><div class="field"><label for="preset-select">已儲存條件</label><div style="display:flex;gap:8px"><select id="preset-select"><option value="">選擇條件…</option>${presets.map((preset, index) => `<option value="${index}">${escapeHtml(preset.name)}</option>`).join("")}</select><button class="button" data-action="load-preset" type="button">載入</button><button class="button danger" data-action="delete-preset" type="button">刪除</button></div></div></div>
      <div class="checkbox-grid" style="margin-top:16px">
        ${scannerCheck("aboveMa20", "站上 MA20", "中期趨勢位於月線上方")}
        ${scannerCheck("positiveNews", "新聞分 ≥ 20", "近期事件偏正向且具一定強度")}
        ${scannerCheck("foreignBuy", "外資買超", "最近可得交易日外資淨買超")}
        ${scannerCheck("lowRsi", "RSI < 35", "接近超賣區，需搭配風險判斷")}
        ${scannerCheck("volumeSurge", "量比 ≥ 1.5", "成交量高於 5 日均量 1.5 倍")}
        ${scannerCheck("riskBelow", "風險分 ≤ 45", "排除波動或事件風險過高標的")}
      </div>
    </div>
    <section class="section"><div class="section-heading"><div><h2>符合條件：${matches.length} 檔</h2><p>缺失欄位不會自動視為符合。</p></div></div>
      ${matches.length ? `<div class="grid cols-3">${matches.map((stock) => stockCard(stock)).join("")}</div>` : '<div class="empty"><strong>沒有股票同時符合全部條件</strong>可降低最低分或取消部分勾選條件。</div>'}
    </section>`;
}

function renderTraditional() {
  const stocks = state.data?.stocks || [];
  const stock = state.selectedStock || stocks[0];
  state.selectedStock = stock;
  if (!stock) {
    app.innerHTML = `${header("傳統分析", "目前沒有股票資料。")}<div class="empty">請先執行每日更新。</div>`;
    return;
  }
  const t = stock.technical || {};
  const f = stock.fundamental || {};
  const i = stock.institutional || {};
  app.innerHTML = `
    ${header("傳統分析", "技術面、基本面、籌碼面、估值與風險全部補齊；缺失資料會直接標示，不會用今天資料回填歷史。", `<select id="traditional-stock-select" class="button">${stocks.map((item) => `<option value="${escapeHtml(item.symbol)}" ${item.symbol === stock.symbol ? "selected" : ""}>${escapeHtml(item.symbol)} ${escapeHtml(item.name)}</option>`).join("")}</select>`)}
    ${demoBanner()}
    <div class="detail-grid">
      <div class="card">
        <div class="card-header"><div class="card-title"><h3>${escapeHtml(stock.name)} ${escapeHtml(stock.symbol)}</h3><p>${escapeHtml(stock.industry || "")} · ${escapeHtml(stock.price?.date || "")}</p></div>${favoriteButton(stock)}</div>
        <div class="stock-main"><div><div class="stock-price">${formatNumber(stock.price?.close, 2)}</div><span class="change ${changeClass(stock.price?.change_pct)}">${formatPct(stock.price?.change_pct, 2, true)}</span></div><div class="composite-score ${scoreTone(stock.scores?.composite)}">${formatNumber(stock.scores?.composite)}</div></div>
        <div class="chart-panel">${sparkline(stock.price?.history || [], 800, 260, "big-chart sparkline")}<div class="chart-labels"><span>${escapeHtml(stock.price?.history?.[0]?.date || "")}</span><span>${escapeHtml(stock.price?.history?.at?.(-1)?.date || "")}</span></div></div>
      </div>
      <div class="card"><div class="card-title"><h3>綜合分解</h3><p>風險分越高代表風險越大，會從總分扣除。</p></div>
        ${scoreBar("新聞", stock.scores?.news)}${scoreBar("技術", stock.scores?.technical)}${scoreBar("基本", stock.scores?.fundamental)}${scoreBar("籌碼", stock.scores?.institutional)}${scoreBar("風險", -(stock.scores?.risk || 0))}
        <p class="reason">${escapeHtml(stock.recommendation?.reason || "")}</p>
      </div>
    </div>
    <section class="section"><div class="section-heading"><div><h2>技術面</h2><p>趨勢、動能、波動與量價。</p></div></div><div class="grid cols-4">
      ${metric("MA5", t.ma5, "短期均線")}${metric("MA20", t.ma20, "月線")}${metric("MA60", t.ma60, "季線")}${metric("RSI 14", t.rsi14, t.rsi14 < 30 ? "超賣區" : t.rsi14 > 70 ? "超買區" : "中性區")}
      ${metric("MACD", t.macd, "柱狀 " + formatNumber(t.macd_hist, 2))}${metric("KD", `K ${formatNumber(t.k, 1)} / D ${formatNumber(t.d, 1)}`, "動能交叉")}${metric("ATR%", formatPct(t.atr_pct, 2), "波動風險")}${metric("量比", `${formatNumber(t.volume_ratio, 2)}x`, "相對 5 日均量")}
    </div></section>
    <section class="section"><div class="section-heading"><div><h2>基本面與估值</h2><p>來源以 TWSE 官方 OpenAPI 為主，歷史切點沒有存檔就顯示未取得。</p></div></div><div class="grid cols-4">
      ${metric("月營收年增", formatPct(f.revenue_yoy, 1, true), f.period || "最新可得")}${metric("月營收月增", formatPct(f.revenue_mom, 1, true), "與上月比較")}${metric("本益比", f.pe, "PE")}${metric("股價淨值比", f.pb, "PB")}${metric("殖利率", formatPct(f.dividend_yield, 2), "近年現金股利")}${metric("營收完整度", formatPct(f.completeness || 0, 0), "官方欄位可用比例")}${metric("資料可用日", f.available_at || "未取得", "Point-in-time")}${metric("來源", f.source || "未取得", "資料血緣")}
    </div></section>
    <section class="section"><div class="section-heading"><div><h2>籌碼面</h2><p>最新可得交易日的三大法人資料。</p></div></div><div class="grid cols-4">
      ${metric("外資淨買超", formatCompact(i.foreign_net), "股")}${metric("投信淨買超", formatCompact(i.investment_trust_net), "股")}${metric("自營商淨買超", formatCompact(i.dealer_net), "股")}${metric("三大法人合計", formatCompact(i.total_net), i.date || "未取得")}
    </div></section>
    <section class="section"><div class="section-heading"><div><h2>關聯新聞</h2><p>按影響強度排序。</p></div></div><div class="grid">${(stock.news || []).slice().sort((a,b)=>Math.abs(b.impact_score||0)-Math.abs(a.impact_score||0)).map((item)=>newsCard({...item,stock_symbol:stock.symbol,stock_name:stock.name})).join("") || '<div class="empty">此股票目前沒有關聯新聞。</div>'}</div></section>`;
}

function metric(label, value, note = "") {
  const display = value === null || value === undefined || value === "" || Number.isNaN(value) ? "未取得" : value;
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(display)}</strong><small>${escapeHtml(note)}</small></div>`;
}

function renderFavorites() {
  const items = [...state.favorites.values()];
  const stocks = items.map((item) => ({ item, stock: findStock(item.symbol) }));
  app.innerHTML = `
    ${header("我的最愛", "預設保存在瀏覽器；設定 Google Apps Script 後，可跨裝置同步到你自己的 Google Sheet。", `<button class="button" data-action="sync-favorites" type="button">↻ 立即同步</button><button class="button" data-view="settings" type="button">⚙ 同步設定</button>`)}
    <div class="banner info"><span>☁</span><div><strong>${state.settings.endpoint ? (state.remoteAvailable ? "Google Sheets 已連線" : "已設定雲端，但目前使用本機備援") : "尚未設定 Google Sheets"}</strong><br>不需要 Firebase、伺服器或信用卡；Apps Script 以同步碼與密碼保護個人資料。</div></div>
    ${stocks.length ? `<div class="grid cols-2">${stocks.map(({item,stock}) => `<article class="card"><div class="card-header"><div class="card-title"><h3>${escapeHtml(stock?.name || item.name || item.symbol)}</h3><p>${escapeHtml(item.symbol)}${stock ? ` · 綜合分 ${formatNumber(stock.scores?.composite)}` : " · 尚未在追蹤清單"}</p></div><button class="favorite-button active" data-action="toggle-favorite" data-symbol="${escapeHtml(item.symbol)}" type="button">♥</button></div>${stock ? sparkline(stock.price?.history || []) : ""}<div class="field"><label>個人備註</label><textarea data-favorite-note="${escapeHtml(item.symbol)}" placeholder="例如：等待法說、價格到某區間再研究">${escapeHtml(item.note || "")}</textarea><button class="button small" data-action="save-note" data-symbol="${escapeHtml(item.symbol)}" type="button">儲存備註</button></div>${stock ? `<button class="button ghost" data-action="open-stock" data-symbol="${escapeHtml(stock.symbol)}" type="button" style="margin-top:12px">查看完整分析</button>` : ""}</article>`).join("")}</div>` : '<div class="empty"><strong>還沒有我的最愛</strong>在股票卡片按下 ♡，即可加入並同步到 Google Sheets。</div>'}`;
}

async function loadSnapshot(date) {
  try {
    const entry = state.manifest?.snapshots?.find((item) => item.date === date);
    if (!entry) throw new Error("找不到快照");
    state.snapshot = await fetchJson(entry.path || `./data/snapshots/${date}.json`);
    renderValidation();
  } catch (error) {
    showToast(`載入歷史快照失敗：${error.message}`);
  }
}

function renderValidation() {
  const snapshots = state.manifest?.snapshots || [];
  const snap = state.snapshot;
  app.innerHTML = `
    ${header("歷史驗證：先預測，後揭曉", "選擇過去日期時，快照只允許使用該日以前已公開的新聞與資料；未確認前不載入未來答案。")}
    <div class="validation-lock"><strong>🔒 無未來資料模式</strong><p style="color:var(--muted);margin:7px 0 0;line-height:1.6">價格、新聞與基本面都以 available_at 截斷。公開快照不含 future_return、hit、actual_outcome 等答案欄位；揭曉結果另存於 data/results，預設不存在。</p></div>
    <section class="section"><div class="card"><div class="form-grid"><div class="field"><label for="snapshot-select">選擇歷史日期</label><select id="snapshot-select"><option value="">請選擇…</option>${snapshots.map((item)=>`<option value="${escapeHtml(item.date)}" ${snap?.as_of===item.date?"selected":""}>${escapeHtml(item.date)} · ${escapeHtml(item.label || "預測快照")}</option>`).join("")}</select></div><div class="field"><label>驗證狀態</label><input value="${snap ? "預測已鎖定；答案尚未載入" : "等待選擇日期"}" readonly></div></div></div></section>
    ${snap ? validationSnapshotHtml(snap) : '<div class="empty" style="margin-top:18px"><strong>選擇日期開始回放</strong>內附 2025-08-15 的示範快照，網站不會顯示該日之後的結果。</div>'}`;
}

function validationSnapshotHtml(snap) {
  const stocks = [...(snap.stocks || [])].sort((a,b)=>(b.scores?.composite||0)-(a.scores?.composite||0));
  return `<section class="section"><div class="section-heading"><div><h2>${escapeHtml(snap.as_of)} 當時可見的預測</h2><p>建立方式：${escapeHtml(snap.snapshot_type || "retrospective_point_in_time")}</p></div></div>
    ${snap.retrospective ? '<div class="banner"><span>⚠</span><div>這是事後依照時間截斷規則重建的回放，不等同於當天已公開登記的預測；真正嚴格驗證需從現在開始每日保存不可變快照。</div></div>' : ""}
    <div class="grid cols-3">${stocks.slice(0,3).map((stock,i)=>stockCard(stock,i+1)).join("")}</div>
    <section class="section"><div class="section-heading"><div><h3>資料時間線</h3><p>所有日期均不得晚於切點。</p></div></div><div class="timeline">${(snap.audit?.timeline || []).map((item)=>`<div class="timeline-item"><time>${escapeHtml(item.time)}</time><div><strong>${escapeHtml(item.label)}</strong><p style="color:var(--muted);margin:4px 0 0">${escapeHtml(item.detail)}</p></div></div>`).join("")}</div></section>
    <section class="section"><div class="card"><h3 style="margin-top:0">揭曉控制</h3><p style="color:var(--muted);line-height:1.6">網站只會嘗試讀取已由你明確產生的結果檔。請先在本機或 GitHub Actions 手動輸入 REVEAL；如果結果檔不存在，畫面不會自行向市場 API 查詢未來價格。</p><div class="field" style="max-width:420px"><label for="reveal-confirm">輸入 REVEAL 才能嘗試載入</label><div style="display:flex;gap:8px"><input id="reveal-confirm" placeholder="REVEAL"><button class="button danger" data-action="reveal-result" data-date="${escapeHtml(snap.as_of)}" type="button">嘗試揭曉</button></div></div><div id="reveal-output"></div></div></section>
  </section>`;
}

async function revealResult(date) {
  const input = document.querySelector("#reveal-confirm");
  const output = document.querySelector("#reveal-output");
  if (input?.value !== "REVEAL") {
    showToast("請完整輸入 REVEAL");
    return;
  }
  try {
    const result = await fetchJson(`./data/results/${date}.json`);
    output.innerHTML = `<div class="banner info" style="margin-top:14px"><span>✓</span><div><strong>已載入你先前明確產生的結果檔。</strong><pre class="code">${escapeHtml(JSON.stringify(result.summary || result, null, 2))}</pre></div></div>`;
  } catch {
    output.innerHTML = `<div class="banner danger" style="margin-top:14px"><span>!</span><div><strong>沒有結果檔，因此沒有揭露答案。</strong><br>執行 <code>python scripts/backtest.py --as-of ${escapeHtml(date)} --reveal</code>，或手動觸發 Historical no-leak validation 工作流程並勾選 reveal 後才會產生。</div></div>`;
  }
}

function renderMethod() {
  app.innerHTML = `
    ${header("方法、限制與資料治理", "分數是研究排序工具，不是價格預言。這一頁說明免費架構如何運作，以及哪些地方仍需人工判斷。")}
    <div class="grid cols-3">
      <div class="card"><h3>1. 新聞蒐集</h3><p class="reason">Google News RSS、GDELT、TWSE 每日重大訊息；以網址、標題相似度與事件時間去重。</p></div>
      <div class="card"><h3>2. 模型分析</h3><p class="reason">中文財經情緒分類器分析全部新聞；Qwen 0.6B 只分析高相關事件並輸出結構化 JSON。模型失敗時採透明規則備援。</p></div>
      <div class="card"><h3>3. 綜合評分</h3><p class="reason">新聞 33%、技術 24%、基本面 15%、籌碼 10%、資料品質 8%，再扣除 18% 風險折扣。</p></div>
    </div>
    <section class="section"><div class="section-heading"><div><h2>影響分怎麼來</h2><p>不是把所有文章做簡單平均。</p></div></div><div class="card"><pre class="code">事件貢獻 = 方向 × 強度 × 公司關聯性 × 來源品質 × 模型信心 × 時效衰減
股票新聞分 = 去重事件貢獻的加權總和（限制在 -100～+100）
綜合分 = 新聞 + 技術 + 基本 + 籌碼 + 資料品質 − 風險折扣</pre></div></section>
    <section class="section"><div class="section-heading"><div><h2>免費模型策略</h2><p>避免把付費 API 當必要條件。</p></div></div><div class="table-wrap"><table><thead><tr><th>層級</th><th>模型/方法</th><th>用途</th><th>成本</th><th>失敗時</th></tr></thead><tbody>
      <tr><td>全量</td><td>bardsai/finance-sentiment-zh-fast</td><td>正負中性與信心</td><td>GitHub runner 本機推論</td><td>關鍵字規則</td></tr>
      <tr><td>高相關事件</td><td>Qwen/Qwen3-0.6B</td><td>機制、期間、風險與結構化摘要</td><td>GitHub runner 本機推論</td><td>分類器 + 規則摘要</td></tr>
      <tr><td>歷史大量回填</td><td>Kaggle Notebook</td><td>可選 GPU 批次分析</td><td>免費額度內</td><td>GitHub CPU 小批次</td></tr>
    </tbody></table></div></section>
    <section class="section"><div class="section-heading"><div><h2>重要限制</h2></div></div><div class="grid cols-2"><div class="banner danger"><span>1</span><div>新聞情緒不等於股價報酬；市場可能已提前反映、事件可能被其他消息抵消。</div></div><div class="banner danger"><span>2</span><div>免費來源可能延遲、缺漏或改版，因此每個欄位都保留 source、published_at、available_at 與 fetched_at。</div></div><div class="banner danger"><span>3</span><div>Qwen 0.6B 是小型模型，適合整理與結構化，不應被當成專業投資研究員。</div></div><div class="banner danger"><span>4</span><div>Google Sheets 同步碼不是完整帳號系統，適合個人使用，不適合公開多人服務或敏感資料。</div></div></div></section>`;
}

function renderSettings() {
  app.innerHTML = `
    ${header("Google Sheets 同步設定", "網站本身不需要後端；Favorites 透過你自己的 Google Apps Script Web App 寫入 Google Sheet。")}
    <div class="detail-grid">
      <div class="card"><h2 style="margin-top:0">連線資料</h2><div class="field"><label for="endpoint-input">Apps Script Web App 網址</label><input id="endpoint-input" value="${escapeHtml(state.settings.endpoint)}" placeholder="https://script.google.com/macros/s/.../exec"><small>請貼上部署後以 /exec 結尾的網址。未設定時仍可使用瀏覽器本機保存。</small></div><div class="form-grid" style="margin-top:14px"><div class="field"><label for="sync-id-input">同步帳號/裝置群組</label><input id="sync-id-input" value="${escapeHtml(state.settings.syncId)}"><small>多個裝置填同一個值即可看到同一份最愛。</small></div><div class="field"><label for="password-input">同步金鑰</label><input id="password-input" type="password" value="${escapeHtml(state.settings.password)}" autocomplete="current-password"><small>必須與 Apps Script 的 setSyncPassword() 相同。</small></div></div><label class="check-card" style="margin-top:14px"><input id="auto-sync-input" type="checkbox" ${state.settings.autoSync ? "checked" : ""}><span><strong>自動同步</strong><small>加入、移除或修改備註時同步 Google Sheets；失敗會保留本機資料。</small></span></label><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px"><button class="button primary" data-action="save-settings" type="button">儲存並測試</button><button class="button" data-action="sync-favorites" type="button">讀取雲端最愛</button><button class="button danger" data-action="clear-cloud-settings" type="button">清除雲端設定</button></div></div>
      <div class="card"><h2 style="margin-top:0">建立 Google Sheet</h2><div class="steps"><div class="step"><h3>建立空白 Google 試算表</h3><p>名稱可用 StockLab Favorites，不必公開分享試算表。</p></div><div class="step"><h3>開啟「擴充功能 → Apps Script」</h3><p>把專案內 google-apps-script/Code.gs 全部貼上並儲存。</p></div><div class="step"><h3>執行 setup 與 setSyncPassword</h3><p>先執行 setup() 建立欄位，再在編輯器執行 setSyncPassword("你的長隨機金鑰")。</p></div><div class="step"><h3>部署為網頁應用程式</h3><p>執行身分選「我」，存取權選可使用連結的人；將 /exec 網址貼到左側。</p></div></div></div>
    </div>
    <section class="section"><div class="banner"><span>🔐</span><div><strong>安全提醒：</strong>這是個人免費同步方案，不是完整 OAuth 登入。請使用專用長隨機金鑰，不要使用 Google 帳號密碼；不要在公開畫面展示同步碼與密碼。</div></div></section>`;
}

function renderActiveView() {
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === state.activeView));
  if (!state.data) return;
  const views = {
    overview: renderOverview,
    daily: renderDaily,
    news: renderNews,
    scanner: renderScanner,
    traditional: renderTraditional,
    favorites: renderFavorites,
    validation: renderValidation,
    method: renderMethod,
    settings: renderSettings,
  };
  (views[state.activeView] || renderOverview)();
  app.focus({ preventScroll: true });
}

function navigate(view) {
  state.activeView = view;
  history.replaceState(null, "", `#${view}`);
  document.querySelector("#sidebar").classList.remove("open");
  renderActiveView();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function stockDialogHtml(stock) {
  return `<header class="page-header"><div><h1>${escapeHtml(stock.name)} <small style="color:var(--muted)">${escapeHtml(stock.symbol)}</small></h1><p>${escapeHtml(stock.industry || "")} · 資料日 ${escapeHtml(stock.price?.date || "")}</p></div><div class="header-actions">${favoriteButton(stock)}</div></header>
  <div class="detail-grid"><div class="card"><div class="stock-main"><div><div class="stock-price">${formatNumber(stock.price?.close,2)}</div><span class="change ${changeClass(stock.price?.change_pct)}">${formatPct(stock.price?.change_pct,2,true)}</span></div><div class="composite-score ${scoreTone(stock.scores?.composite)}">${formatNumber(stock.scores?.composite)}</div></div>${sparkline(stock.price?.history || [],800,220,"big-chart sparkline")}</div><div class="card"><h3 style="margin-top:0">模型結論</h3><span class="recommendation ${directionClass(stock.recommendation?.direction)}">${escapeHtml(stock.recommendation?.label || "資料觀察")}</span><p class="reason">${escapeHtml(stock.recommendation?.reason || "")}</p><p class="reason"><strong>主要風險：</strong>${escapeHtml((stock.recommendation?.risks || []).join("、") || "無足夠資料")}</p></div></div>
  <section class="section"><div class="grid cols-4">${metric("新聞分",stock.scores?.news,"事件加權")}${metric("技術分",stock.scores?.technical,"趨勢與動能")}${metric("基本分",stock.scores?.fundamental,"營收與估值")}${metric("籌碼分",stock.scores?.institutional,"三大法人")}</div></section>
  <section class="section"><div class="section-heading"><div><h2>關鍵新聞</h2></div></div><div class="grid">${(stock.news || []).slice(0,5).map((item)=>newsCard({...item,stock_symbol:stock.symbol,stock_name:stock.name})).join("") || '<div class="empty">沒有關聯新聞。</div>'}</div></section>
  <button class="button primary" data-action="go-traditional" data-symbol="${escapeHtml(stock.symbol)}" type="button">前往完整傳統分析</button>`;
}

function openStock(symbol) {
  const stock = findStock(symbol, state.snapshot || state.data) || findStock(symbol);
  if (!stock) return;
  dialogContent.innerHTML = stockDialogHtml(stock);
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}

function savePreset() {
  const name = prompt("請輸入條件名稱，例如：新聞利多＋站上月線");
  if (!name) return;
  const presets = loadPresets();
  presets.push({ name: name.slice(0, 40), scanner: { ...state.scanner } });
  localStorage.setItem(SCANNER_PRESETS_KEY, JSON.stringify(presets));
  showToast("篩選條件已儲存");
  renderScanner();
}

function loadPreset() {
  const select = document.querySelector("#preset-select");
  const index = Number(select?.value);
  const presets = loadPresets();
  if (!Number.isInteger(index) || !presets[index]) return showToast("請先選擇一組條件");
  state.scanner = { ...state.scanner, ...presets[index].scanner };
  renderScanner();
}

function deletePreset() {
  const select = document.querySelector("#preset-select");
  const index = Number(select?.value);
  const presets = loadPresets();
  if (!Number.isInteger(index) || !presets[index]) return showToast("請先選擇一組條件");
  presets.splice(index, 1);
  localStorage.setItem(SCANNER_PRESETS_KEY, JSON.stringify(presets));
  showToast("已刪除條件");
  renderScanner();
}

function setupSearch() {
  const input = document.querySelector("#stock-search");
  const results = document.querySelector("#search-results");
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    if (!q || !state.data) {
      results.hidden = true;
      return;
    }
    const matches = (state.data.stocks || []).filter((stock) => String(stock.symbol).toLowerCase().includes(q) || String(stock.name).toLowerCase().includes(q) || String(stock.industry || "").toLowerCase().includes(q)).slice(0, 8);
    results.innerHTML = matches.length ? matches.map((stock) => `<button class="search-result" data-action="search-stock" data-symbol="${escapeHtml(stock.symbol)}" type="button"><span><strong>${escapeHtml(stock.symbol)}</strong> ${escapeHtml(stock.name)}</span><small>綜合分 ${formatNumber(stock.scores?.composite)}</small></button>`).join("") : `<div class="search-result"><span>找不到符合項目</span></div>`;
    results.hidden = false;
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") results.hidden = true;
    if (event.key === "Enter") {
      const first = results.querySelector("[data-symbol]");
      if (first) openStock(first.dataset.symbol);
    }
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".global-search")) results.hidden = true;
  });
}

async function handleAction(target) {
  const action = target.dataset.action;
  if (target.dataset.view) return navigate(target.dataset.view);
  if (!action) return;
  if (action === "open-stock") return openStock(target.dataset.symbol);
  if (action === "toggle-favorite") {
    return toggleFavorite(target.dataset.symbol);
  }
  if (action === "close-dialog") return dialog.close();
  if (action === "search-stock") {
    document.querySelector("#search-results").hidden = true;
    return openStock(target.dataset.symbol);
  }
  if (action === "news-filter") {
    state.newsFilter = target.dataset.filter;
    return renderNews();
  }
  if (action === "sync-favorites") {
    await syncFavorites();
    return renderActiveView();
  }
  if (action === "save-note") {
    const note = document.querySelector(`[data-favorite-note="${CSS.escape(target.dataset.symbol)}"]`)?.value || "";
    return saveFavoriteNote(target.dataset.symbol, note.slice(0, 500));
  }
  if (action === "save-preset") return savePreset();
  if (action === "load-preset") return loadPreset();
  if (action === "delete-preset") return deletePreset();
  if (action === "reveal-result") return revealResult(target.dataset.date);
  if (action === "go-traditional") {
    state.selectedStock = findStock(target.dataset.symbol);
    dialog.close();
    return navigate("traditional");
  }
  if (action === "save-settings") {
    state.settings.endpoint = document.querySelector("#endpoint-input")?.value.trim() || "";
    state.settings.syncId = document.querySelector("#sync-id-input")?.value.trim() || state.settings.syncId;
    state.settings.password = document.querySelector("#password-input")?.value || "";
    state.settings.autoSync = Boolean(document.querySelector("#auto-sync-input")?.checked);
    saveSettings();
    if (state.settings.endpoint) {
      try {
        const result = await favoriteRemote("ping");
        state.remoteAvailable = true;
        showToast(`連線成功：${result.message || "Google Sheets 可用"}`);
        await syncFavorites({ silent: true });
      } catch (error) {
        state.remoteAvailable = false;
        showToast(`設定已儲存，但測試失敗：${error.message}`);
      }
    } else {
      showToast("已改用本機保存");
    }
    return renderSettings();
  }
  if (action === "clear-cloud-settings") {
    state.settings.endpoint = "";
    state.settings.password = "";
    state.remoteAvailable = false;
    saveSettings();
    showToast("已清除雲端設定，本機最愛仍保留");
    return renderSettings();
  }
}

function setupEvents() {
  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-action], [data-view]");
    if (target) handleAction(target);
  });
  document.addEventListener("change", (event) => {
    const target = event.target;
    if (target.matches("[data-scanner]")) {
      state.scanner[target.dataset.scanner] = target.checked;
      renderScanner();
    }
    if (target.matches("[data-scanner-range]")) {
      state.scanner[target.dataset.scannerRange] = Number(target.value);
      renderScanner();
    }
    if (target.id === "traditional-stock-select") {
      state.selectedStock = findStock(target.value);
      renderTraditional();
    }
    if (target.id === "snapshot-select" && target.value) loadSnapshot(target.value);
  });
  document.querySelector("#mobile-menu").addEventListener("click", () => document.querySelector("#sidebar").classList.toggle("open"));
  dialog.addEventListener("click", (event) => {
    const rect = dialog.getBoundingClientRect();
    const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
    if (outside) dialog.close();
  });
  window.addEventListener("hashchange", () => {
    const view = location.hash.replace("#", "");
    if (view) navigate(view);
  });
}

function updateStatus() {
  const node = document.querySelector("#data-status");
  const isDemo = state.data?.mode === "demo";
  node.className = `status-pill ${isDemo ? "demo" : "live"}`;
  node.textContent = `${isDemo ? "示範" : "已更新"} · ${state.data?.as_of || "未知日期"}`;
}

async function bootstrap() {
  state.favorites = loadLocalFavorites();
  state.tombstones = loadLocalTombstones();
  updateFavoriteCount();
  setupEvents();
  setupSearch();
  try {
    const [data, manifest] = await Promise.all([fetchJson(DATA_URL), fetchJson(MANIFEST_URL).catch(() => ({ snapshots: [] }))]);
    state.data = data;
    state.manifest = manifest;
    state.selectedStock = data.stocks?.[0] || null;
    updateStatus();
    if (!Object.keys({ overview:1,daily:1,news:1,scanner:1,traditional:1,favorites:1,validation:1,method:1,settings:1 }).includes(state.activeView)) state.activeView = "overview";
    renderActiveView();
    syncFavorites({ silent: true }).then(() => {
      if (state.activeView === "favorites") renderFavorites();
    });
  } catch (error) {
    document.querySelector("#data-status").textContent = "資料讀取失敗";
    app.innerHTML = `<div class="empty"><strong>無法載入 data/latest.json</strong><p>${escapeHtml(error.message)}</p><p>請使用 HTTP 伺服器開啟，而不是直接雙擊 index.html。可執行 <code>python -m http.server 8000</code>。</p></div>`;
  }
}

bootstrap();
