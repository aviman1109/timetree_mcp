# TimeTree Multi-Account MCP

這個專案參考 `garmin_mcp/project` 的做法，建立一套給 `ChatGPT Web` / 其他 MCP client 使用的多帳號 TimeTree MCP server。

## 相關專案

- [ehs208/TimeTree-MCP](https://github.com/ehs208/TimeTree-MCP) — TypeScript 實作的 TimeTree MCP server，使用 email/password 認證 + rate limiting，本專案的 `web` provider 架構概念與此類似。本專案以 Python FastMCP 實作，並額外加入多帳號管理與 SDK provider 支援。

核心目標：

- 多帳號 YAML 設定檔
- 每次 tool 都必須明確帶入 `account_id`
- 優先支援 Python SDK
- 沒有官方 API 存取權時，退回 unofficial web API provider
- 可先用 `stdio`，也可切成遠端 HTTP / SSE

## 重要現況

TimeTree 目前有兩種很不一樣的整合路徑：

1. `sdk` provider

- 使用 `timetree-sdk-python`
- 程式碼中有 read / write 方法
- 但官方 API 在 2023 年後已不再對新整合開放，因此不保證仍可用
- 適合已經有歷史 access token 或舊 app 憑證的人

2. `web` provider

- 使用 reverse-engineered 的 TimeTree web API
- 以 email / password 登入，靠 session cookie 與 CSRF token 做讀寫
- 實務上更可能是目前可用路徑
- 但這是 unofficial 做法，未來可能隨時失效

## 專案結構

```text
project/
├── config/
│   └── accounts.example.yaml
├── src/
│   └── timetree_multi_mcp/
├── README.md
└── pyproject.toml
```

## 安裝

在 `project/` 目錄內：

```bash
pip install -e .
```

如果你要啟用 `sdk` provider，建議另外安裝或指向本地 SDK：

```bash
pip install -e ../timetree-sdk-python
```

或設定：

```bash
export TIMETREE_SDK_PATH=/absolute/path/to/timetree-sdk-python
```

## 建立帳號設定檔

先複製範例：

```bash
cp config/accounts.example.yaml config/accounts.yaml
```

範例：

```yaml
default_account_id: family_web

accounts:
  - account_id: family_web
    label: Family TimeTree
    provider: web
    default_calendar_id: "123456789"
    email_file: /run/secrets/timetree_family_email
    password_file: /run/secrets/timetree_family_password

  - account_id: legacy_sdk
    label: Legacy Official API Account
    provider: sdk
    access_token_file: /run/secrets/timetree_legacy_access_token
```

## Provider 說明

### `provider: web`

必填欄位：

- `email` 或 `email_file`
- `password` 或 `password_file`

行為：

- 啟動後在需要時登入 TimeTree web
- session cookie 僅保留在記憶體內
- 寫入操作會自動抓 CSRF token

### `provider: sdk`

必填欄位：

- `access_token` 或 `access_token_file`

行為：

- 透過 Python SDK 呼叫 legacy official API
- `get_events` 目前以 `upcoming_events` 近似實作
- 若官方 API 不再接受該憑證，驗證會直接失敗

## 驗證單一帳號

先驗證帳號設定與 provider 能否登入：

```bash
timetree-multi-mcp-auth --accounts-file config/accounts.yaml --account-id family_web
timetree-multi-mcp-auth --accounts-file config/accounts.yaml --account-id legacy_sdk
```

若要看完整 JSON：

```bash
timetree-multi-mcp-auth --accounts-file config/accounts.yaml --account-id family_web --json
```

## 啟動 MCP Server

### 本機 `stdio`

```bash
export TIMETREE_ACCOUNTS_FILE=config/accounts.yaml
timetree-multi-mcp
```

### 遠端 HTTP

```bash
export TIMETREE_ACCOUNTS_FILE=config/accounts.yaml
export MCP_TRANSPORT=http
export MCP_HOST=0.0.0.0
export PORT=38081
export MCP_ALLOWED_HOSTS="192.168.1.10:*,example.com,example.com:*"
export MCP_ALLOWED_ORIGINS="https://chatgpt.com,https://chat.openai.com,https://example.com"
timetree-multi-mcp
```

預設遠端 MCP 入口：

```text
http://localhost:38081/mcp
```

### Docker Compose

先準備：

```bash
cp config/accounts.example.yaml config/accounts.yaml
docker compose up --build -d
```

注意：

- 目前 Dockerfile 預設適合 `web` provider
- 如果你要在 container 內使用 `sdk` provider，請另外把 `timetree-sdk-python` 安裝進 image，或提供 `timetree_sdk` 套件

## 目前提供的工具

- `list_accounts`
- `get_account_status`
- `list_calendars`
- `get_events`
- `get_updated_events`
- `create_event`
- `update_event`
- `delete_event`

每個 tool 都要求 `account_id`，避免操作到錯的帳號。

## 風險與限制

- `sdk` provider 雖然結構完整，但官方 API 已停止對新整合開放，不保證可用
- `web` provider 屬於 unofficial reverse-engineered 做法，TimeTree 只要改版就可能失效
- `sdk` provider 的事件查詢目前偏向 upcoming events，未必涵蓋完整歷史資料
- all-day event、timezone、刪除事件等行為都仰賴 TimeTree 現行 payload 規則，未來可能變動

## 環境變數

- `TIMETREE_ACCOUNTS_FILE`
- `TIMETREE_DEFAULT_ACCOUNT_ID`
- `TIMETREE_SDK_PATH`
- `TIMETREE_WEB_TIMEOUT_SECONDS`
- `TIMETREE_WEB_MAX_REQUESTS_PER_SECOND`
- `MCP_TRANSPORT`
- `MCP_HOST`
- `PORT`
- `MCP_PATH`
- `MCP_ALLOWED_HOSTS`
- `MCP_ALLOWED_ORIGINS`

## 建議使用方式

- 若你沒有歷史官方 API 憑證，優先使用 `provider: web`
- 若你有舊的 access token，再額外配置 `provider: sdk` 帳號做驗證
- 在 MCP client 內先呼叫 `list_accounts` 與 `get_account_status`
- 寫入前先用 `list_calendars` 找對 calendar，再進行 `create_event` / `update_event` / `delete_event`
