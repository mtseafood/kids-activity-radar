# 台灣親子體驗活動爬蟲

自動搜集台灣近期（預設未來 60 天）適合 2~4 歲幼兒的親子體驗活動，
輸出為 `activities.json`。

## 資料來源

| 來源 | 方式 |
|---|---|
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

[index.html](index.html) 是零依賴的單頁瀏覽器，直接讀取 `activities.json`：

```bash
python scraper.py            # 先產生資料
python -m http.server 8000   # 在專案根目錄啟動
# 開啟 http://localhost:8000
```

功能：關鍵字搜尋、縣市/孩子年齡下拉、活動類型標籤（職業體驗、DIY 手作…）、
只看免費/只看有確定日期切換、推薦/日期/價格排序、免費貼紙與票價標示，
支援手機版面。所有篩選都在前端即時運算，不需後端。

## 二次篩選

```bash
python filter_activities.py --city 台中市 --free-only
python filter_activities.py --max-price 500 --age 3
python filter_activities.py --tag DIY手作 --output diy.json
```

## 篩選邏輯

- 只保留今天起 N 天內的活動（KKday 長期體驗等無固定日期者保留）
- 排除：純線上活動、無互動體驗的演講型活動、明確標示 12 歲以上的活動
- 自動標 tag 並優先排序：體驗課、職業體驗、DIY 手作、農場體驗、烹飪課、藝術課、感統課
- 指定縣市的活動排最前面

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
scraper.py             # 主程式（--city / --days / --sources / --output）
filters.py             # 篩選與排序邏輯
filter_activities.py   # 對 JSON 結果做二次篩選
sources/
  base.py              # Activity 資料結構、HTTP 工具、日期/年齡/價格解析
  accupass.py
  kkday.py
  epochtimes.py
  taichung_culture.py
```
