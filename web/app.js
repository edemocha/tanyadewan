// TanyaDewan chat. Plain JS, no build step. Chats are kept in this browser only (localStorage).
// The jokes live in the loading lines; answers stay neutral and cited.
const LOADING = [
  "Menyelak Penyata Rasmi…",
  "Mencari di bawah timbunan kertas kerja…",
  "Pustakawan sedang memakai cermin mata…",
  "Membaca dengan penuh berkecuali…",
  "Melangkau semua [Tepuk] dan [Dewan riuh]…",
  "Menyemak siapa cakap apa, dua kali…",
];
const STORE = "td_chats";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const app = $(".app");
const thread = $("#thread");
let speakers = [];
let chats = load();
let current = null; // id of the open chat
let busy = false;

// ── storage (never required: the page works if localStorage is blocked) ──────
function load() { try { return JSON.parse(localStorage.getItem(STORE) || "[]"); } catch { return []; } }
function save() { try { localStorage.setItem(STORE, JSON.stringify(chats.slice(0, 50))); } catch { /* private mode */ } }

// ── composer (one form, moved between the empty state and the dock) ─────────
const composer = $("#tpl-composer").content.firstElementChild.cloneNode(true);
const q = $("textarea", composer);
const send = $(".send", composer);
function placeComposer() {
  const inChat = current !== null;
  (inChat ? $("#composer-dock") : $("#composer-home")).append(composer);
  $("#empty").hidden = inChat;
  $("#conversation").hidden = !inChat;
  $("#dock").hidden = !inChat;
  send.disabled = busy || !q.value.trim();
}
q.addEventListener("input", () => {
  q.style.height = "auto";
  q.style.height = Math.min(q.scrollHeight, 180) + "px";
  send.disabled = busy || !q.value.trim();
});
q.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); composer.requestSubmit(); } });
composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = q.value.trim();
  if (text.length < 2 || busy) return;
  q.value = ""; q.style.height = "";
  ask(text);
});

// ── sidebar ─────────────────────────────────────────────────────────────────
function renderList() {
  const list = $("#chat-list");
  if (!chats.length) { list.innerHTML = '<p class="empty-list">Belum ada sembang. Soalan pertama sentiasa paling susah.</p>'; return; }
  list.innerHTML = chats.map((c) => `
    <div class="chat-item${c.id === current ? " active" : ""}" data-id="${c.id}">
      <button type="button" class="open" title="${esc(c.title)}">${esc(c.title)}</button>
      <button type="button" class="icon-btn del" aria-label="Padam sembang">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M10 11v6M14 11v6M6 7l1 12h10l1-12M9 7V4h6v3"/></svg>
      </button>
    </div>`).join("");
}
$("#chat-list").addEventListener("click", (e) => {
  const item = e.target.closest(".chat-item");
  if (!item) return;
  if (e.target.closest(".del")) {
    chats = chats.filter((c) => c.id !== item.dataset.id);
    save();
    if (current === item.dataset.id) newChat(); else renderList();
    return;
  }
  openChat(item.dataset.id);
  if (matchMedia("(max-width: 800px)").matches) app.classList.add("collapsed");
});
function newChat() {
  if (busy) return;
  current = null;
  thread.innerHTML = ""; closePanel();
  renderList(); placeComposer();
  q.focus();
}
function openChat(id) {
  if (busy) return;
  const chat = chats.find((c) => c.id === id);
  if (!chat) return;
  current = id;
  thread.innerHTML = ""; closePanel();
  for (const t of chat.turns) thread.append(renderStoredTurn(t));
  renderList(); placeComposer();
  $("#conversation").scrollTop = $("#conversation").scrollHeight;
}
$("#new-chat").addEventListener("click", newChat);
$("#new-chat-top").addEventListener("click", newChat);
$("#hide-sidebar").addEventListener("click", () => app.classList.add("collapsed"));
$("#show-sidebar").addEventListener("click", () => app.classList.remove("collapsed"));
$("#scrim").addEventListener("click", () => app.classList.add("collapsed"));
if (matchMedia("(max-width: 800px)").matches) app.classList.add("collapsed");

$("#theme").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("td_theme", next); } catch { /* fine */ }
});
$("#suggestions").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b && !busy) ask(b.textContent); });

async function loadStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    const range = s.from ? ` · ${s.from} hingga ${s.to}` : "";
    const busyIdx = s.sittings_indexed < s.sittings_total ? " (masih membaca…)" : "";
    $("#status").textContent = `${s.sittings_indexed}/${s.sittings_total} persidangan diindeks${range}${busyIdx}`;
    $("#eyebrow-text").textContent = `Penyata Rasmi Dewan Rakyat · Parlimen ke-15 · ${s.sittings_indexed} persidangan`;
    $("#status").title = `${s.chunks.toLocaleString()} petikan · jawapan oleh ${s.engine}`;
  } catch { $("#status").textContent = "Pelayan belum hidup?"; }
}
async function loadSpeakers() {
  try {
    speakers = await (await fetch("/api/speakers")).json();
    $("#speakers").innerHTML = speakers.map((s) => `<option value="${esc(s.label)}"></option>`).join("");
  } catch { /* the filter just stays empty */ }
}

// ── rendering a turn ────────────────────────────────────────────────────────
// A quoted passage (6+ words) becomes a blockquote whose <cite> names the speaker of the source it cites.
// Same structure as the Astryx Blockquote: bare <cite> after the quote (no <footer>), styled from our tokens.
const QUOTE = /(?:&quot;|“)((?:(?!&quot;|“|”)[^\n]){12,700}?)(?:&quot;|”)[ \t]*((?:\[\d{1,2}\])*)[.,;]?/g;
const QUOTE_MIN_WORDS = 6;
const norm = (s) => s.replace(/\s+/g, " ").trim();
const unesc = (s) => s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");

function renderAnswer(el, text, sources = [], bad = new Set(), unverified = []) {
  // Escape everything first; then only bold, bullets, quotes and [n] citation buttons become markup.
  const nSources = sources.length;
  const shaky = new Set(unverified.map(norm));
  let safe = esc(text).replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>").replace(/^\s*[*-]\s+/gm, "• ");
  safe = safe.replace(QUOTE, (m, quote, cites) => {
    if (quote.trim().split(/\s+/).length < QUOTE_MIN_WORDS) return m;
    const first = /\[(\d{1,2})\]/.exec(cites)?.[1];
    const src = first ? sources[Number(first) - 1] : null;
    const who = src ? `${avatarHtml(src, "sm")}${esc(src.speaker)} · ${esc(src.date_display)}` : "";
    const isShaky = shaky.has(norm(unesc(quote)));
    const flag = isShaky ? ' <span class="bq-flag">tidak disahkan: bukan petikan kata demi kata</span>' : "";
    const cite = who || cites || flag ? `<cite>${who}${cites ? " " + cites : ""}${flag}</cite>` : "";
    return `<blockquote class="bq${isShaky ? " unverified" : ""}">${quote.trim()}${cite}</blockquote>`;
  });
  el.innerHTML = safe.replace(/\[(\d{1,2})\]/g, (m, n) => {
    const i = Number(n);
    const cls = i >= 1 && i <= nSources && !bad.has(i) ? "cite" : "cite bad";
    return `<button type="button" class="${cls}" data-n="${i}" title="Sumber ${i}">${i}</button>`;
  });
}
// ── sources: one right-hand panel, showing the sources of whichever answer you open ──
const panel = $("#source-panel");
let panelTurn = null;
// Avatar (after the Astryx Avatar): thumbnail of the official portrait, linked to the parlimen.gov.my profile;
// name as the accessible label; initials (from the registry, sent by the API) when there's no confirmed photo.
// No status dot: "online/busy" means nothing for a transcript, and a coloured dot beside an MP reads as a judgement.
function avatarHtml(c, size = "md") {
  const alt = esc(c.speaker || "");
  const named = c.speaker_id && !c.unattributed;
  const fallback = `<span class="av-fallback" aria-hidden="true">${named ? esc(c.initials || "?") : "?"}</span>`;
  const img = c.photo_url
    ? `<img src="${esc(c.photo_url)}" alt="" loading="lazy" onerror="this.remove()">`
    : "";
  return `<span class="av av-${size}" role="img" aria-label="${alt}">${fallback}${img}</span>`;
}
function avatarStack(cards, max = 4) {
  const seen = new Map();
  for (const c of cards) if (!c.unattributed && c.speaker_id && !seen.has(c.speaker_id)) seen.set(c.speaker_id, c);
  const people = [...seen.values()];
  if (!people.length) return "";
  const extra = people.length > max ? `<span class="av av-xs av-more">+${people.length - max}</span>` : "";
  return `<span class="av-stack" aria-hidden="true">${people.slice(0, max).map((c) => avatarHtml(c, "xs")).join("")}${extra}</span>`;
}

function cardsHtml(cards) {
  return cards.map((c) => `
    <li class="card" data-n="${c.n}">
      <header>
        <span class="n">${c.n}</span>
        ${c.profile_url ? `<a class="av-link" href="${esc(c.profile_url)}" target="_blank" rel="noopener" title="Profil rasmi di parlimen.gov.my">${avatarHtml(c)}</a>` : avatarHtml(c)}
        <span class="who">${esc(c.speaker)}</span>
        ${c.unattributed ? '<span class="badge">ahli tidak dinamakan</span>' : ""}
        ${c.is_draft ? '<span class="badge draft">draf: belum disemak</span>' : ""}
        ${c.ocr ? '<span class="badge ocr">OCR</span>' : ""}
        <span class="when">${esc(c.date_display)} · ${esc(c.section_heading || c.section || "")} · hlm. ${esc(c.page_label ?? "?")}</span>
      </header>
      <p class="excerpt">${esc(c.text)}</p>
      <div class="links">
        <a href="${esc(c.pdf_url)}" target="_blank" rel="noopener">PDF rasmi ↗</a>
        <button type="button" class="more">Petikan penuh</button>
      </div>
    </li>`).join("");
}
function renderSources(turn, cards) {
  turn._sources = cards;
  $(".count", turn).textContent = cards.length;
  $(".av-slot", turn).innerHTML = avatarStack(cards);
  $(".src-btn", turn).hidden = !cards.length;
  if (panelTurn === turn) openPanel(turn); // keep an open panel in step while sources arrive
}
function openPanel(turn, n = null) {
  panelTurn = turn;
  document.querySelectorAll(".turn.panel-open").forEach((t) => t.classList.remove("panel-open"));
  turn.classList.add("panel-open");
  $("#panel-q").textContent = $(".q", turn).textContent;
  $("#panel-cards").innerHTML = cardsHtml(turn._sources || []);
  panel.hidden = false;
  app.classList.add("panel-on");
  if (n !== null) {
    const card = $(`#panel-cards .card[data-n="${n}"]`);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      card.classList.add("hl");
      setTimeout(() => card.classList.remove("hl"), 1600);
    }
  } else {
    $("#panel-cards").scrollTop = 0;
  }
}
function closePanel() {
  panel.hidden = true;
  app.classList.remove("panel-on");
  panelTurn?.classList.remove("panel-open");
  panelTurn = null;
}
$("#close-panel").addEventListener("click", closePanel);
$("#panel-scrim").addEventListener("click", closePanel);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) closePanel(); });
$("#panel-cards").addEventListener("click", (e) => {
  const more = e.target.closest(".more");
  if (more) more.closest(".card").classList.toggle("open");
});
function renderChecks(turn, check) {
  if (!check) return;
  const notes = [];
  if (check.unverified_quotes?.length) notes.push(`Petikan ini tidak dijumpai kata demi kata dalam sumber, anggap sebagai parafrasa: ${check.unverified_quotes.map((x) => `<q>${esc(x)}</q>`).join(", ")}`);
  if (check.missing_sources?.length) notes.push(`Rujukan tanpa sumber: [${check.missing_sources.join("], [")}]`);
  $(".checks", turn).innerHTML = notes.join("<br>");
  $(".checks", turn).hidden = !notes.length;
}
function copyText(turn) {
  const srcs = (turn._sources || []).map((s) => `[${s.n}] ${s.speaker} · ${s.date_display} · ${s.pdf_url}`);
  return [turn._answer || "", "", "Sumber (Penyata Rasmi Dewan Rakyat):", ...srcs].join("\n");
}
function setAnswerText(turn, text) {
  turn._answer = text;
  $(".copy-btn", turn).hidden = !text;
}
function turnShell(question) {
  const turn = $("#tpl-turn").content.firstElementChild.cloneNode(true);
  $(".q", turn).textContent = question;
  turn.addEventListener("click", async (e) => {
    const copy = e.target.closest(".copy-btn");
    if (copy) {
      try { await navigator.clipboard.writeText(copyText(turn)); copy.classList.add("done"); $(".copy-label", copy).textContent = "Disalin"; }
      catch { $(".copy-label", copy).textContent = "Tak dapat salin"; }
      setTimeout(() => { copy.classList.remove("done"); $(".copy-label", copy).textContent = "Salin"; }, 1600);
      return;
    }
    const c = e.target.closest(".cite");
    if (c && (turn._sources || []).some((s) => String(s.n) === c.dataset.n)) openPanel(turn, c.dataset.n);
    if (e.target.closest(".src-btn")) {
      if (panelTurn === turn && !panel.hidden) closePanel(); else openPanel(turn);
    }
  });
  return turn;
}
function renderStoredTurn(t) {
  const turn = turnShell(t.question);
  $(".thinking", turn).hidden = true;
  renderSources(turn, t.sources || []);
  renderAnswer($(".answer", turn), t.answer || "", t.sources || [], new Set(t.check?.missing_sources || []), t.check?.unverified_quotes || []);
  setAnswerText(turn, t.answer || "");
  renderChecks(turn, t.check);
  if (t.error) { $(".error", turn).textContent = t.error; $(".error", turn).hidden = false; }
  $(".meta", turn).textContent = t.meta || "";
  return turn;
}

// ── asking ──────────────────────────────────────────────────────────────────
async function ask(question) {
  if (current === null) {
    current = `c${Date.now()}`;
    chats.unshift({ id: current, title: question.slice(0, 80), turns: [] });
  }
  const chat = chats.find((c) => c.id === current);
  const record = { question, answer: "", sources: [], check: null, meta: "", error: "" };
  chat.turns.push(record);
  renderList(); placeComposer();

  const turn = turnShell(question);
  turn.classList.add("enter", "streaming");
  thread.append(turn);
  turn.scrollIntoView({ behavior: "smooth", block: "start" });
  const thinking = $(".thinking", turn), msg = $(".msg", turn), answerEl = $(".answer", turn), errEl = $(".error", turn);
  let tick = 0;
  msg.textContent = LOADING[0];
  const rot = setInterval(() => { msg.textContent = LOADING[++tick % LOADING.length]; }, 1800);
  const fail = (m) => { record.error = `Alamak, pustakawan tersadung: ${m}`; errEl.textContent = record.error; errEl.hidden = false; };

  const fd = new FormData($("#filter-form"));
  const sp = speakers.find((s) => s.label === fd.get("speaker"));
  const body = { question, date_from: fd.get("date_from") || null, date_to: fd.get("date_to") || null, speaker_id: sp ? sp.id : null };
  let engine = "";
  busy = true; send.disabled = true;
  try {
    const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, i); buf = buf.slice(i + 2);
        const ev = /^event: (.+)$/m.exec(block)?.[1];
        const data = JSON.parse(/^data: (.*)$/m.exec(block)?.[1] ?? "null");
        if (ev === "sources") { record.sources = data; renderSources(turn, data); thinking.dataset.state = "composing"; }
        else if (ev === "token") {
          if (!record.answer) { clearInterval(rot); thinking.hidden = true; }
          record.answer += data;
          renderAnswer(answerEl, record.answer, record.sources);
        }
        else if (ev === "engine") engine = data;
        else if (ev === "check") {
          record.check = data;
          if (record.answer) renderAnswer(answerEl, record.answer, record.sources, new Set(data.missing_sources), data.unverified_quotes);
          renderChecks(turn, data);
        }
        else if (ev === "error") fail(data);
        else if (ev === "done" && data.retrieve_ms !== undefined) {
          record.meta = `${engine || "tiada model"} · carian ${data.retrieve_ms} ms · jawapan ${(data.generate_ms / 1000).toFixed(1)} s`;
          $(".meta", turn).textContent = record.meta;
        }
      }
    }
  } catch (err) {
    fail(`${err.message}. Cuba lagi.`);
  } finally {
    clearInterval(rot);
    thinking.hidden = true;
    turn.classList.remove("streaming");
    setAnswerText(turn, record.answer);
    busy = false;
    send.disabled = !q.value.trim();
    save();
    q.focus();
  }
}

// hairline under the top bar only once the thread has scrolled under it
$("#conversation").addEventListener("scroll", (e) => $(".main").classList.toggle("scrolled", e.target.scrollTop > 4), { passive: true });

renderList(); placeComposer(); loadStatus(); loadSpeakers();
setInterval(loadStatus, 30000);
