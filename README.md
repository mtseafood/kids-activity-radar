# 台灣親子體驗活動爬蟲

自動搜集台灣近期（預設未來 60 天）適合 2~4 歲幼兒的親子體驗活動，
輸出為 `activities.json`。

## 資料來源

| 來源 | 方式 |
|---|---|
| 品牌職業體驗（brands） | 麥當勞小麥麥體驗營、Mister Donut 小小烘焙師（官網台中門市場次直接解析）、全家小小店長 |
| Niceday 玩體驗 | 民間親子體驗平台。分類/主題頁 SSR 直接解析；站內搜尋需 Playwright |
| Pinkoi 體驗 | 手作工作坊（陶藝/皮革/繪畫…）。公開 JSON API（apiv2/search）+ 台中地區碼過濾 |
| BeClass 線上報名 | 小型工作室/協會的報名平台。先取 CSRF token 再 POST 站內搜尋 |
| Accupass 活動通 | 搜尋頁為 SSR，requests + BeautifulSoup 解析卡片；改版時 fallback 到 Playwright |
| KKday | 受 DataDome 反爬蟲保護，需 Playwright 真實瀏覽器渲染（未裝 Playwright 則略過） |
| 大紀元（台灣） | 副刊/文化/地方版面，requests + BeautifulSoup + 親子關鍵字過濾 |
| 台中市政府文化局 | 官方開放資料 JSON（activity.culture.taichung.gov.tw/_DataAction） |

## 安裝

需要 Python 3.10+。

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium      # 動態頁面 fallback 用，可略過（略過則只用 API/靜態）
```

## 執行

```bash
python scraper.py                          # 預設：台中市、未來 60 天
python scraper.py --city 台北市 --days 30
python scraper.py --sources accupass kkday # 只跑指定來源
python scraper.py -v                       # 顯示 debug log
```

輸出：
- `activities.json` — 篩選排序後的活動清單
- `scraper_errors.log` — 錯誤記錄（單頁失敗不會中斷整體爬取）

## 瀏覽 UI

零依賴的多頁前端，直接讀取 `activities.json`，採「分類入口 Hub + 詳情子頁」結構：

```bash
python scraper.py            # 先產生資料
python -m http.server 8000   # 在專案根目錄啟動
# 開啟 http://localhost:8000
```

- [index.html](index.html)：**分類 Hub**，依資料即時統計各活動類型數量，列出分類磚與特別企劃。
- [category.html](category.html)：**分類詳情頁**，以 `?cat=<類型>` 帶入（`all` 為全部）。
  關鍵字搜尋、縣市/孩子年齡下拉、只看免費/只看有確定日期、推薦/日期/價格排序、
  免費貼紙與票價標示，並顯示活動摘要細節。
- [farm/index.html](farm/index.html)：**特別企劃**，中部四縣市親子農牧場地圖（縣市 × 特色雙軸篩選）。
- [assets/style.css](assets/style.css)、[assets/app.js](assets/app.js)：三頁共用的樣式與卡片渲染。

所有篩選都在前端即時運算，不需後端，支援手機版面。

## 每日自動更新（GitHub Actions）

[.github/workflows/daily-scrape.yml](.github/workflows/daily-scrape.yml) 每天台灣時間
早上 6:00 自動執行：爬取 → 比對新增活動並推播 Telegram → commit 更新資料 →
GitHub Pages 自動重新發布。

- 線上版：https://mtseafood.github.io/kids-activity-radar/
- 手動觸發：`gh workflow run daily-scrape`
- Telegram 推播需要 repo secrets：`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`
  （沒設定時自動跳過），推播邏輯在 [notify_telegram.py](notify_telegram.py)

## 二次篩選

```bash
python filter_activities.py --city 台中市 --free-only
python filter_activities.py --max-price 500 --age 3
python filter_activities.py --tag DIY手作 --output diy.json
```

## 篩選邏輯

- 只保留今天起 N 天內的活動（KKday 長期體驗等無固定日期者保留）
- 只保留指定縣市的活動；台中另限縮為「市區」八區（中/東/西/南/北/西屯/南屯/北屯），
  清水、沙鹿等海線/山線/外圍區一律排除——區名清單在 `filters.py` 開頭可自行調整
- 同系列活動去重：每月/每週開課、只差日期的同名活動只留最近一場（文化局讀經班類大幅減量）
- 排除：純線上活動、無互動體驗的演講型活動、明確標示 12 歲以上的活動
- 自動標 tag 並優先排序：體驗課、職業體驗、DIY 手作、農場體驗、烹飪課、藝術課、感統課
- 民間品牌/體驗平台（brands、niceday、pinkoi、beclass）優先於政府場館排序

## 注意事項

- **選擇器與 API 端點可能隨網站改版失效。** 各 scraper 都是 best-effort 設計，
  失敗會記在 `scraper_errors.log` 而不中斷其他來源；改版時請更新對應的
  `sources/*.py`。
- 已內建 User-Agent 偽裝與每次請求間 1~3 秒隨機延遲。請遵守各網站
  robots.txt 與服務條款，僅作個人非商業用途，勿提高頻率或大量平行抓取。
- 年齡、價格、日期是從文字中以 regex 解析，未標示者欄位為 `null`，
  建議人工複核後再報名。

## 專案結構

```
index.html             # 前端：分類入口 Hub
category.html          # 前端：分類詳情頁（?cat=）
farm/index.html        # 前端：中部親子農場地圖（特別企劃）
assets/style.css       # 前端：共用樣式
assets/app.js          # 前端：共用分類定義與卡片渲染
scraper.py             # 主程式（--city / --days / --sources / --output）
filters.py             # 篩選與排序邏輯
filter_activities.py   # 對 JSON 結果做二次篩選
sources/
  base.py              # Activity 資料結構、HTTP 工具、日期/年齡/價格解析
  brands.py            # 麥當勞 / Mister Donut / 全家 品牌職業體驗
  niceday.py           # Niceday 玩體驗
  pinkoi.py            # Pinkoi 體驗（手作工作坊）
  beclass.py           # BeClass 線上報名
  accupass.py
  kkday.py
  epochtimes.py
  taichung_culture.py
```
