# Game Room Scraper

獨立專案：登入後抓取「選擇機台」列表（機台號、百分比、佔用／鎖定、底部詳情），寫入 **SQLite**，並透過 **JSON API** 給另一個頁面使用。

> 僅供你本人合法帳號、且遵守目標站服務條款的個人資料同步。網站 URL／CSS 選擇器之後再填。

## 架構

```
登入 →（優先）攔截機台列表 API JSON
     →（否則）Playwright 解析網格 DOM
     → 可選：點進每台讀底部詳情
     → upsert SQLite
     → GET /machines 給前端／另一服務
```

## 快速開始

```bash
cd game-room-scraper
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
cp config.example.json config.json
# 之後補上真實 URL、帳密、selectors / api_intercept.url_substring
```

### 先用不需網站的 demo 資料打通 JSON

```bash
python main.py scrape --demo --json-out data/last.json
python main.py serve
# GET http://127.0.0.1:8090/machines
# POST http://127.0.0.1:8090/scrape?demo=true
```

### 真實站點（URL 備好後）

1. 瀏覽器登入後打開「選擇機台」，DevTools → **Network**，找回傳機台列表的 XHR。
2. 把該 API path 片段寫進 `config.json` → `api_intercept.url_substring`。
3. 若沒有穩定 API，再依實際 DOM 調整 `selectors`。
4. 填好 `.env` / `config.json` 的帳密與 URL 後：

```bash
python main.py scrape
python main.py serve
```

## JSON 欄位

| 欄位 | 說明 |
|------|------|
| `machine_id` | 機台號（如 `207`） |
| `percent` | 網格百分比 |
| `occupied` / `locked` | 佔用／鎖定 |
| `spins_since_win` / `prev1_spins` / `prev2_spins` | 未開／前一／前二 |
| `today_bet` / `today_rate` | 今日總下注、得分率 |
| `days30_bet` / `days30_rate` | 近 30 天 |
| `scraped_at` | 抓取時間（UTC ISO） |

## API

| Method | Path | 說明 |
|--------|------|------|
| GET | `/health` | 健康檢查 |
| GET | `/machines` | 全部機台 JSON |
| GET | `/machines/{id}` | 單機 |
| POST | `/scrape` | 立刻抓一次並寫庫 |
| POST | `/scrape?demo=true` | 寫入示範資料 |
| GET | `/runs/latest` | 最近一次抓取紀錄 |

另一個頁面可直接 `fetch('http://127.0.0.1:8090/machines')`。

## 測試

```bash
pytest -q
```

## 你後續需要提供的資訊

1. 登入頁／機台列表頁完整 URL  
2. Network 裡機台列表 API 的 URL 與一筆回應範例（可打碼敏感欄位）  
3. 登入是否有驗證碼／OTP（有的話需改成手動登入一次存 `storage_state.json`）
