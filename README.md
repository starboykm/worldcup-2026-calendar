# 2026 FIFA World Cup Beijing-Time ICS Calendar

[中文](#中文说明) | [English](#english)

Public ICS calendar for the 2026 FIFA World Cup. Match times are converted to Beijing time (`Asia/Shanghai`). The calendar includes teams, kickoff time, venue, scores when available, and goal details when available from the source.

订阅文件：`public/worldcup-2026.ics`

---

## 中文说明

### 项目简介

这是一个 2026 年 FIFA 世界杯赛程日历项目，会自动生成可被 Google 日历、Apple 日历、Outlook 等应用订阅的 `.ics` 文件。

日历默认使用北京时间，适合中文用户直接订阅查看。项目已包含完整 104 场比赛事件，并配置了 GitHub Actions 每天北京时间 12:00 自动更新。

### 日历内容

每场比赛会生成一个日历事件，包含：

- 比赛时间：北京时间 `Asia/Shanghai`
- 比赛标题：参赛队伍
- 完赛后标题：参赛队伍和比分，例如 `Mexico 2-0 South Africa`
- 描述信息：阶段/小组、比赛状态、比赛场地、数据来源
- 完赛后描述：进球队员和进球时间，取决于公开数据源是否已经更新
- 地点信息：球场和城市

### 输出文件

```text
public/worldcup-2026.ics
public/matches.json
```

`worldcup-2026.ics` 用于日历订阅，`matches.json` 用于查看结构化赛程数据或调试。

### 数据来源

默认数据来源为 Wikipedia 的 2026 FIFA World Cup 相关页面。程序会解析页面中的赛程表、比分、场地和进球信息。

如果公开页面暂时没有更新，日历也会暂时保持旧数据。GitHub Actions 会在下一次运行时继续尝试更新。

### 本地生成

Windows PowerShell 示例：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m worldcup_calendar update
```

如果本机没有可用的 `python` 命令，可以使用任意 Python 3.12+ 环境运行：

```powershell
python -m worldcup_calendar update
```

### 本地代理

如果直连外网失败，程序会自动尝试常见本地代理端口，包括 FlClash 常用的：

```text
http://127.0.0.1:7070
```

也可以手动指定代理：

```powershell
$env:HTTPS_PROXY="http://127.0.0.1:7070"
$env:HTTP_PROXY="http://127.0.0.1:7070"
python -m worldcup_calendar update
```

### 启动可更新服务

项目内置一个轻量 HTTP 服务，可用于部署到服务器：

```powershell
$env:UPDATE_TOKEN="change-me"
python -m worldcup_calendar serve --host 0.0.0.0 --port 8080
```

接口：

- `GET /worldcup-2026.ics`：获取日历订阅文件
- `GET /matches.json`：获取结构化赛程数据
- `GET /health`：健康检查
- `POST /update?token=change-me`：手动触发更新

### Docker 部署

```powershell
docker build -t worldcup-2026-calendar .
docker run -p 8080:8080 -e UPDATE_TOKEN=change-me worldcup-2026-calendar
```

部署后订阅地址示例：

```text
http://your-server:8080/worldcup-2026.ics
```

### GitHub Actions 自动更新

`.github/workflows/update-calendar.yml` 已配置自动更新：

- 每天 UTC 04:00 运行
- 对应北京时间每天 12:00
- 支持手动运行 `workflow_dispatch`
- 生成并提交 `public/worldcup-2026.ics` 和 `public/matches.json`

### GitHub Pages 发布

推送到 GitHub 后，可以通过 GitHub Pages 提供公开订阅地址：

1. 打开 GitHub 仓库
2. 进入 `Settings -> Pages`
3. Source 选择 `Deploy from a branch`
4. Branch 选择 `main`
5. Folder 选择 `/public`
6. 保存

启用后，ICS 地址通常为：

```text
https://starboykm.github.io/worldcup-2026-calendar/worldcup-2026.ics
```

### Google 日历订阅

1. 打开 Google Calendar
2. 点击 `其他日历`
3. 选择 `通过网址添加`
4. 填入 GitHub Pages 的 `.ics` 地址
5. 保存后即可订阅

注意：Google 日历对外部 ICS 的刷新频率由 Google 控制，可能不是实时刷新。

### 手动修正数据

如果公开数据源有延迟，可以编辑 `data/overrides.json` 按 `match_id` 覆盖信息。

示例：

```json
{
  "M001": {
    "home_score": 2,
    "away_score": 1,
    "status": "completed",
    "goals": [
      {"team": "Mexico", "player": "Example Player", "minute": "12'"}
    ]
  }
}
```

### 常见问题

**为什么本地更新失败？**

通常是网络无法访问外部数据源。请确认代理是否开启，或在服务器/GitHub Actions 上运行。

**为什么 Google 日历没有马上更新？**

Google 会缓存外部 ICS 订阅，刷新时间由 Google 决定。

**为什么部分淘汰赛队伍是 Winner/Runner-up？**

这是赛前公开赛程的正常占位。比赛完成或晋级队伍确定后，数据源更新，日历下一次运行会同步更新。

---

## English

### Overview

This project generates a public `.ics` calendar for the 2026 FIFA World Cup. It is designed for subscription in Google Calendar, Apple Calendar, Outlook, and other calendar apps.

All kickoff times are converted to Beijing time (`Asia/Shanghai`). The repository currently contains all 104 match events and includes a GitHub Actions workflow that updates the calendar every day at 12:00 Beijing time.

### Calendar Contents

Each match is rendered as one calendar event with:

- Kickoff time in Beijing time
- Match teams
- Score in the event title when available
- Stage/group and match status
- Venue and city
- Source URL
- Goal scorers and goal minutes when available from the public source

### Output Files

```text
public/worldcup-2026.ics
public/matches.json
```

Use `worldcup-2026.ics` for calendar subscription. Use `matches.json` for structured data inspection or debugging.

### Data Source

The default source is the 2026 FIFA World Cup pages on Wikipedia. The parser extracts match schedule, teams, scores, venues, and goal details from the public match tables.

If the source page has not updated yet, the generated calendar will keep the latest available data and update again on the next scheduled run.

### Generate Locally

```powershell
python -m venv .venv
.\.venv\Scripts\python -m worldcup_calendar update
```

Or run with any Python 3.12+ environment:

```powershell
python -m worldcup_calendar update
```

### Proxy Support

If direct internet access fails, the script automatically tries common local proxy endpoints, including the FlClash default:

```text
http://127.0.0.1:7070
```

You can also set proxy variables manually:

```powershell
$env:HTTPS_PROXY="http://127.0.0.1:7070"
$env:HTTP_PROXY="http://127.0.0.1:7070"
python -m worldcup_calendar update
```

### Run the Update Server

```powershell
$env:UPDATE_TOKEN="change-me"
python -m worldcup_calendar serve --host 0.0.0.0 --port 8080
```

Endpoints:

- `GET /worldcup-2026.ics`: calendar subscription file
- `GET /matches.json`: structured match data
- `GET /health`: health check
- `POST /update?token=change-me`: trigger an update manually

### Docker Deployment

```powershell
docker build -t worldcup-2026-calendar .
docker run -p 8080:8080 -e UPDATE_TOKEN=change-me worldcup-2026-calendar
```

Subscription URL example:

```text
http://your-server:8080/worldcup-2026.ics
```

### GitHub Actions

The workflow in `.github/workflows/update-calendar.yml`:

- Runs daily at UTC 04:00
- Equals 12:00 Beijing time
- Supports manual dispatch
- Regenerates and commits `public/worldcup-2026.ics` and `public/matches.json`

### Publish with GitHub Pages

1. Open the GitHub repository
2. Go to `Settings -> Pages`
3. Choose `Deploy from a branch`
4. Select branch `main`
5. Select folder `/public`
6. Save

The ICS URL should look like:

```text
https://starboykm.github.io/worldcup-2026-calendar/worldcup-2026.ics
```

### Subscribe in Google Calendar

1. Open Google Calendar
2. Click `Other calendars`
3. Choose `From URL`
4. Paste the GitHub Pages `.ics` URL
5. Save

Google controls the refresh frequency for subscribed external ICS calendars, so updates may not appear instantly.

### Manual Overrides

If the public source lags behind, edit `data/overrides.json` and override fields by `match_id`.

Example:

```json
{
  "M001": {
    "home_score": 2,
    "away_score": 1,
    "status": "completed",
    "goals": [
      {"team": "Mexico", "player": "Example Player", "minute": "12'"}
    ]
  }
}
```

### FAQ

**Why does local update fail?**

Usually because the machine cannot reach the public source directly. Enable a local proxy, set `HTTPS_PROXY`, or run the workflow on GitHub Actions.

**Why does Google Calendar not update immediately?**

Google caches subscribed ICS calendars and controls the refresh interval.

**Why do some knockout matches show Winner/Runner-up placeholders?**

Those are normal pre-match placeholders from the public schedule. Once teams are decided and the source updates, the next run will update the calendar.
