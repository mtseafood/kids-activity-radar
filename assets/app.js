"use strict";
/* ============================================================
   親子活動雷達 — 共用資料定義與卡片渲染
   index.html（Hub）與 category.html（詳情）共用
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

// 單張活動卡片；detailed=true 時多顯示活動摘要（詳情頁用）
function card(a, i, detailed) {
  const el = document.createElement("article");
  el.className = "card";
  el.style.animationDelay = (Math.min(i, 12) * 35) + "ms";

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
    <div class="card-top">
      ${dateHtml}
      <h3><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a></h3>
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
  return el;
}
