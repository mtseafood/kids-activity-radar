"use strict";
/* ============================================================
   親子活動雷達 — 共用資料定義、收藏、卡片渲染
   index.html / category.html / activity.html 共用
   ============================================================ */

// 活動類型 → 主題色
const TAG_COLORS = {
  "職業體驗": "var(--red)",
  "體驗課":   "var(--blue)",
  "DIY手作":  "var(--orange)",
  "農場體驗": "var(--green)",
  "烹飪課":   "var(--yellow)",
  "藝術課":   "var(--pink)",
  "感統課":   "var(--purple)",
  "室內":     "var(--gray)",
};

// Hub 上呈現的分類（依資料中的 tags 篩選），順序即顯示順序
const CATEGORIES = [
  { key: "職業體驗", icon: "👷", color: "var(--red)",    blurb: "扮演各行各業，當一日小小職人" },
  { key: "DIY手作",  icon: "✂️", color: "var(--orange)", blurb: "親手做出獨一無二的小作品" },
  { key: "體驗課",   icon: "🎯", color: "var(--blue)",   blurb: "五花八門的親子體驗課程" },
  { key: "烹飪課",   icon: "🍳", color: "var(--yellow)", blurb: "揉麵團、做點心的小廚師時光" },
  { key: "藝術課",   icon: "🎨", color: "var(--pink)",   blurb: "畫畫、捏陶、玩色彩的創作課" },
  { key: "感統課",   icon: "🤸", color: "var(--purple)", blurb: "用遊戲鍛鍊感官與大小肌肉" },
  { key: "室內",     icon: "☔",  color: "var(--gray)",   blurb: "雨天備案！不怕天氣的室內活動" },
];

// 特別企劃（靜態頁，不從活動資料來）
const SPECIAL = [
  { key: "farm", icon: "🐑", color: "var(--green)", href: "farm/",
    name: "中部親子農場地圖",
    blurb: "台中・苗栗・彰化・南投 親子農牧場、餵小動物" },
];

const esc = s => String(s ?? "").replace(/[&<>"]/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---- 穩定 ID（跨頁一致，供收藏與詳情頁使用）----
// 注意：部分來源（如台中文化局）多個活動共用同一網址，故不能只用 url，
// 需混入標題/地點/日期才能唯一識別。
function actId(a) {
  const s = [a.url, a.title, a.location_address, a.date_start]
    .map(x => x || "").join("");
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return "a" + (h >>> 0).toString(36);
}

// ---- 收藏（localStorage）----
const FAV_KEY = "kar_favs";
function getFavs() {
  try { return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]")); }
  catch (e) { return new Set(); }
}
function isFav(id) { return getFavs().has(id); }
function toggleFav(id) {
  const f = getFavs();
  f.has(id) ? f.delete(id) : f.add(id);
  localStorage.setItem(FAV_KEY, JSON.stringify([...f]));
  return f.has(id);
}
function favCount() { return getFavs().size; }

// ---- 日期工具 ----
function todayISO() {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") +
    "-" + String(d.getDate()).padStart(2, "0");
}
// 取得「本週末」(週六、週日) 的日期區間 [六, 日]
function weekendRange() {
  const d = new Date(); d.setHours(0, 0, 0, 0);
  const dow = d.getDay();               // 0=日..6=六
  const toSat = (6 - dow + 7) % 7;      // 距離下一個週六
  const sat = new Date(d); sat.setDate(d.getDate() + toSat);
  const sun = new Date(sat); sun.setDate(sat.getDate() + 1);
  const f = x => x.getFullYear() + "-" + String(x.getMonth() + 1).padStart(2, "0") +
    "-" + String(x.getDate()).padStart(2, "0");
  return [f(sat), f(sun)];
}
function plusDaysISO(n) {
  const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + n);
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") +
    "-" + String(d.getDate()).padStart(2, "0");
}

// 單張活動卡片；detailed=true 時多顯示活動摘要（詳情頁/分類頁用）
function card(a, i, detailed) {
  const el = document.createElement("article");
  el.className = "card";
  el.style.animationDelay = (Math.min(i, 12) * 35) + "ms";
  const id = actId(a);

  // 日期方塊
  let dateHtml;
  if (a.date_start) {
    const [, m, d] = a.date_start.split("-");
    const range = a.date_end && a.date_end !== a.date_start
      ? `~ ${a.date_end.slice(5).replace("-", "/")}` : "&nbsp;";
    dateHtml = `<div class="date-block"><div class="m">${+m} 月</div><div class="d">${+d}</div><div class="range">${range}</div></div>`;
  } else {
    dateHtml = `<div class="date-block unknown"><div class="m">日期</div><div class="d">常駐<br>體驗</div></div>`;
  }

  // 價格貼紙
  const sticker = a.is_free
    ? `<div class="free-sticker">免費</div>`
    : (a.price != null ? `<div class="price-sticker">$${a.price}</div>` : "");

  // 年齡
  const ageText = a.age_min != null
    ? `${a.age_min}${a.age_max != null ? "~" + a.age_max : "+"} 歲`
    : "年齡未標示";

  const tagHtml = (a.tags || []).map(t =>
    `<span class="tag" style="background:${TAG_COLORS[t] || "var(--paper-deep)"};color:${t in TAG_COLORS && t !== "室內" ? "var(--card)" : "var(--ink)"}">${esc(t)}</span>`
  ).join("");

  const place = [a.location_city, a.location_address].filter(Boolean);
  const placeHtml = place.length
    ? `<span class="city-tag">${esc(place[0])}</span>${place[1] && place[1] !== place[0] ? " " + esc(detailed ? place[1] : place[1].slice(0, 30)) : ""}`
    : "地點請見活動頁";

  const summaryHtml = (detailed && a.summary)
    ? `<div class="summary">${esc(a.summary)}</div>` : "";

  el.innerHTML = `
    ${sticker}
    <button class="fav-btn${isFav(id) ? " on" : ""}" data-id="${id}" title="加入收藏" aria-label="加入收藏">${isFav(id) ? "♥" : "♡"}</button>
    <div class="card-top">
      ${dateHtml}
      <h3><a href="activity.html?id=${id}">${esc(a.title)}</a></h3>
    </div>
    <div class="meta">
      <div class="line"><span class="ico">📍</span><span>${placeHtml}</span></div>
      <div class="line"><span class="ico">🎈</span><span>${ageText}</span></div>
      ${a.organizer ? `<div class="line"><span class="ico">🏠</span><span>${esc(a.organizer)}</span></div>` : ""}
    </div>
    ${summaryHtml}
    <div class="tag-list">${tagHtml}</div>
    <div class="card-foot">
      <span>來源：${esc(a.source)}</span>
      <a class="go-link" href="${esc(a.url)}" target="_blank" rel="noopener">前往報名 →</a>
    </div>`;

  // 收藏按鈕：就地切換，不導頁
  const btn = el.querySelector(".fav-btn");
  btn.addEventListener("click", e => {
    e.preventDefault(); e.stopPropagation();
    const on = toggleFav(id);
    btn.classList.toggle("on", on);
    btn.textContent = on ? "♥" : "♡";
    el.dispatchEvent(new CustomEvent("fav-changed", { bubbles: true, detail: { id, on } }));
  });
  return el;
}

// 服務工作者（PWA）— 各頁呼叫一次
function registerSW() {
  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    window.addEventListener("load", () =>
      navigator.serviceWorker.register("sw.js").catch(() => {}));
  }
}
