# Tool QA Report

| Field | Value |
|-------|-------|
| **Date** | 2026-03-03 |
| **API URL** | https://svc-ai.paradigm.xyz |
| **Scope** | All 56 registered tools (556 methods) |

## Summary

| Status | Count |
|--------|-------|
| ✅ Pass | 125 |
| ❌ Fail (auth/creds) | 168 |
| ❌ Fail (runtime/schema) | 25 |
| ⏭️ Skip | 148 |
| ⚠️ Warn | 13 |
| **Total tested** | **479** |

---

## 🟢 Fully Working Tools (22)

| Tool | Methods | Pass | Notes |
|------|---------|------|-------|
| demo | 2 | 2 | ✅ echo + ping |
| reth | 1 | 1 | ✅ execution timings |
| googlenews | 3 | 3 | ✅ headlines, search, topic |
| websearch | 1 | 1 | ✅ search (deep_research skipped) |
| kalshi | 7 | 7 | ✅ All methods pass |
| snapshot | 6 | 6 | ✅ All methods pass |
| theblock | 1 | 1 | ✅ news (search empty) |
| fedreg | 5 | 4 | ✅ 4/5 read methods + 1 bug |
| nano-banana | 1 | 1 | ✅ list_models |
| veo3 | 1 | 1 | ✅ list_models |
| opentable | 8 | 8 | ✅ 8/9 (search needs browser) |
| social-monitor | 1 | 1 | ✅ stats (others empty/write) |
| termsheet | 0 | 0 | ⚠️ list_deals empty but no error |

## 🟡 Partially Working Tools (15)

| Tool | Methods | Pass | Fail | Notes |
|------|---------|------|------|-------|
| **paradigmdb** | 32 | 32 | 0 | ✅ All fixed earlier today |
| **twitter** | 8 | 5 | 0 | get_usage returns null; 2 skipped |
| **slack** | 19 | 9 | 2 | list_usergroups missing scope, search_files wrong token type |
| **polymarket** | 11 | 6 | 3 | get_price/get_prices bad params, get_trades no API key |
| **defillama** | 21 | 16 | 5 | Bridge endpoints 429 rate limited; pro endpoints need key |
| **messari** | 8 | 2 | 5 | data.messari.io API deprecated — only metrics+timeseries work |
| **grafana** | 13 | 1 | 11 | health OK, all others 401 — GRAFANA_API_KEY missing |
| **loki** | 5 | 4 | 0 | query needs explicit start param |
| **tardis** | 3 | 2 | 1 | get_instruments doesn't accept limit param |
| **bitgo** | 17 | 4 | 8 | Staking endpoints 404; wallet lookups need coin type |
| **dune** | 6 | 1 | 2 | raw_request **kwargs bug; 3 skipped |
| **transcriber** | 10 | 4 | 2 | faster_whisper not installed; sox missing |
| **confmonitor** | 9 | 1 | 2 | gsuite CLI binary missing in container |
| **coindesk** | 2 | 0 | 2 | RSS feed blocked |
| **profslice** | 3 | 0 | 0 | Needs real profile URLs |

## 🔴 Fully Broken Tools — Missing Credentials (19)

| Tool | Missing Secret | Methods Blocked |
|------|---------------|-----------------|
| **newsapi** | `NEWSAPI_KEY` | 3 |
| **youtube** | `YOUTUBE_API_KEY` | 3 |
| **listennotes** | `LISTENNOTES_KEY` | 3 |
| **debank** | `DEBANK_API_KEY` | 17 |
| **arkham** | `ARKHAM_API_KEY` | 37 |
| **nansen** | `NANSEN_API_KEY` | 15 |
| **anchorage** | `ANCHORAGE_API_KEY` | 12 |
| **coinbase** | Credential parsing bug | 14 |
| **unit410** | `UNIT410_API_KEY` | 4 |
| **falconx** | `FALCONX_API_KEY` | 7 |
| **coinmetrics** | `COINMETRICS_API_KEY` | 9 |
| **bloomberg** | `BLOOMBERG_API_KEY` | 13 |
| **crunchbase** | `CRUNCHBASE_API_KEY` | 15 |
| **harmonic** | `HARMONIC_API_KEY` | 13 |
| **standard-metrics** | `STANDARD_METRICS_CLIENT_ID/SECRET` | 8 |
| **sensortower** | `SENSORTOWER_AUTH_TOKEN` | 6 |
| **similarweb** | `SIMILARWEB_API_KEY` | 21 |
| **posthog** | `POSTHOG_PROJECT_ID` | 5 |
| **sigma** | `SIGMA_CLIENT_ID/SECRET` | 7 |
| **congress** | `DATAGOV_API_KEY` | 7 |
| **openfec** | `DATAGOV_API_KEY` | 6 |
| **legistorm** | `LEGISTORM_API_KEY` | 10 |
| **alphasense** | `ALPHASENSE_API_KEY` | 9 |
| **karma** | API breaking change | 5 |
| **gsuite** | OAuth creds not deployed | 49 |
| **pylon** | `PYLON_API_KEY` | 20 |
| **archiver** | `PARCHIVER_DATABASE_URL` | 10 |

---

## Code Bugs Found (10)

### 1. polymarket/get_price — missing `side` param
- **Error:** `API error: 400 - Invalid side`
- **Fix:** Add `side` param (default `"buy"`) to method signature

### 2. polymarket/get_prices — wrong payload format
- **Error:** `API error: 400 - Invalid payload`
- **Fix:** Send array instead of comma-joined string

### 3. tardis/get_instruments — unexpected `limit` kwarg
- **Error:** `got an unexpected keyword argument 'limit'`
- **Fix:** Either add limit support or remove from schema

### 4. dune/raw_request — `**kwargs` serialization bug
- **Error:** kwargs serialized as literal key instead of being unpacked
- **Fix:** Fix argument unpacking in raw_request method

### 5. karma — upstream API breaking change
- **Error:** All 5 endpoints return 404
- **Fix:** API moved from `/api/daos` → `/api/dao`, path params → query params

### 6. messari — API deprecated
- **Error:** `data.messari.io API has been disabled`
- **Fix:** Migrate to new API (docs.messari.io); only metrics+timeseries still work

### 7. fedreg/search_open_comments — deprecated filter
- **Error:** `commenting_on is not a valid field`
- **Fix:** Update to current Federal Register API filter syntax

### 8. coindesk — RSS feed blocked
- **Error:** `Failed to parse feed. CoinDesk may be blocking automated requests.`
- **Fix:** Add user-agent header or switch to alternative scraping

### 9. coinbase — credential parsing bug
- **Error:** Secret manager returns concatenated multi-section blob
- **🚨 CRITICAL:** Full API credentials leaked in error responses. Rotate keys.
- **Fix:** Fix credential parsing in secret resolution

### 10. slack — 2 scope issues
- `list_usergroups`: needs `usergroups:read` OAuth scope
- `search_files`: needs user token, not bot token

---

## Missing Credentials Summary (27 distinct secrets)

| Secret | Tools Affected |
|--------|---------------|
| `NEWSAPI_KEY` | newsapi |
| `YOUTUBE_API_KEY` | youtube |
| `LISTENNOTES_KEY` | listennotes |
| `DEBANK_API_KEY` | debank |
| `ARKHAM_API_KEY` | arkham |
| `NANSEN_API_KEY` | nansen |
| `ANCHORAGE_API_KEY` | anchorage |
| `UNIT410_API_KEY` | unit410 |
| `FALCONX_API_KEY` | falconx |
| `COINMETRICS_API_KEY` | coinmetrics |
| `BLOOMBERG_API_KEY` | bloomberg |
| `CRUNCHBASE_API_KEY` | crunchbase |
| `HARMONIC_API_KEY` | harmonic |
| `STANDARD_METRICS_CLIENT_ID` | standard-metrics |
| `STANDARD_METRICS_CLIENT_SECRET` | standard-metrics |
| `SENSORTOWER_AUTH_TOKEN` | sensortower |
| `SIMILARWEB_API_KEY` | similarweb |
| `POSTHOG_PROJECT_ID` | posthog |
| `POSTHOG_API_KEY` | posthog |
| `SIGMA_CLIENT_ID` | sigma |
| `SIGMA_CLIENT_SECRET` | sigma |
| `DATAGOV_API_KEY` | congress, openfec |
| `LEGISTORM_API_KEY` | legistorm |
| `ALPHASENSE_API_KEY` | alphasense |
| `GRAFANA_API_KEY` | grafana |
| `PYLON_API_KEY` | pylon |
| `PARCHIVER_DATABASE_URL` | archiver |

---

## Tools Skipped (infrastructure-only)

| Tool | Reason |
|------|--------|
| reth-log-analyzer | Requires log file input |
| profslice | Requires real Firefox profile URLs |
