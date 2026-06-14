# 2026 FIFA World Cup Beijing-Time Calendar

[中文](#中文说明) | [日本語](#日本語) | [English](#english)

Public `.ics` calendar for the 2026 FIFA World Cup. Match times use Beijing time (`Asia/Shanghai`).

ICS URL after GitHub Pages is enabled:

```text
https://starboykm.github.io/worldcup-2026-calendar/worldcup-2026.ics
```

## 中文说明

这是一个 2026 年世界杯赛程日历项目，生成可订阅的 `.ics` 文件，适用于 Google 日历、Apple 日历、Outlook 等应用。

### 包含内容

- 全部 104 场比赛
- 北京时间开球时间
- 队名格式：`中文（English）`
- 完赛后标题显示比分
- 描述中显示阶段、状态、场地和两队进球信息
- 进球队员尽量显示为 `中文（English）`
- 小组赛完成后，淘汰赛的 `Winner Group A` / `Runner-up Group A` 等占位队伍会随数据源或本地小组排名自动更新为实际球队

### 输出文件

```text
docs/worldcup-2026.ics
docs/matches.json
```

### 自动更新

GitHub Actions 已配置：

- 每天 UTC 04:00 运行
- 对应北京时间每天 12:00
- 可在 GitHub Actions 页面手动运行
- 只更新 `docs/worldcup-2026.ics` 和 `docs/matches.json`

日常不需要手动处理。启用 GitHub Pages 并订阅 `.ics` 地址后，比分、进球和淘汰赛球队会随每日更新同步。

### GitHub Pages

1. 打开仓库 `Settings -> Pages`
2. Source 选择 `Deploy from a branch`
3. Branch 选择 `main`
4. Folder 选择 `/docs`
5. 保存

### 本地生成

```powershell
python -m worldcup_calendar update
```

### 服务器部署

```powershell
$env:UPDATE_TOKEN="change-me"
python -m worldcup_calendar serve --host 0.0.0.0 --port 8080
```

接口：

- `GET /worldcup-2026.ics`
- `GET /matches.json`
- `GET /health`
- `POST /update?token=change-me`

### Google 日历订阅

Google Calendar -> 其他日历 -> 通过网址添加 -> 填入 GitHub Pages 的 `.ics` 地址。

Google 会缓存外部 ICS，因此更新可能不会立刻显示。

## 日本語

このプロジェクトは、2026 FIFA ワールドカップの日程を購読用 `.ics` カレンダーとして生成します。試合時間は北京時間（`Asia/Shanghai`）です。

### 内容

- 全 104 試合
- 北京時間のキックオフ時刻
- チーム名は `中国語（English）` 形式
- 試合終了後はタイトルにスコアを表示
- 説明欄にラウンド、状態、会場、両チームの得点情報を表示
- 得点者名は可能な範囲で `中国語（English）` 形式
- グループステージ終了後、`Winner Group A` / `Runner-up Group A` などの決勝トーナメント枠は、データソースまたはローカル順位計算により実際のチーム名へ更新

### ファイル

```text
docs/worldcup-2026.ics
docs/matches.json
```

### 更新

GitHub Actions は UTC 04:00、北京時間 12:00 に毎日実行されます。Actions ページから手動実行もできます。

### 公開

GitHub Pages で branch `main`、folder `/docs` を選択してください。その後、次の URL をカレンダーに追加します。

```text
https://starboykm.github.io/worldcup-2026-calendar/worldcup-2026.ics
```

### ローカル生成

```powershell
python -m worldcup_calendar update
```

## English

This project generates a public `.ics` calendar for the 2026 FIFA World Cup.

### Contents

- All 104 matches
- Kickoff times in Beijing time
- Team names as `Chinese（English）`
- Scores in event titles after matches finish
- Venue, match status, and goal details in descriptions
- Goal scorers shown as `Chinese（English）` when available
- Knockout placeholders such as `Winner Group A` and `Runner-up Group A` are updated to real teams once the source or completed group standings provide enough information

### Files

```text
docs/worldcup-2026.ics
docs/matches.json
```

### Updates

GitHub Actions runs daily at UTC 04:00, which is 12:00 Beijing time. It can also be triggered manually from the Actions page.

### Publish

Enable GitHub Pages from branch `main`, folder `/docs`, then subscribe to:

```text
https://starboykm.github.io/worldcup-2026-calendar/worldcup-2026.ics
```

### Local Use

```powershell
python -m worldcup_calendar update
```

### Server

```powershell
$env:UPDATE_TOKEN="change-me"
python -m worldcup_calendar serve --host 0.0.0.0 --port 8080
```
