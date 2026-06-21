/* 親子活動雷達 — Service Worker
   策略：network-first（拿最新版），離線時回退快取。
   原因：資料每天更新、前端也常迭代，cache-first 會讓使用者卡在舊版。
   離線仍可用（最後一次成功載入的內容會留在快取）。 */
const CACHE = "kar-v2";
const SHELL = [
  ".", "index.html", "category.html", "activity.html",
  "assets/style.css", "assets/app.js", "assets/icon.svg",
  "favicon.svg", "manifest.json", "activities.json",
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return; // 第三方（字型/地圖磚）交給瀏覽器

  // network-first：永遠先抓最新，成功就順手更新快取；失敗（離線）才用快取
  e.respondWith(
    fetch(req).then(res => {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(req, copy));
      return res;
    }).catch(() => caches.match(req).then(hit => hit || caches.match("index.html")))
  );
});
