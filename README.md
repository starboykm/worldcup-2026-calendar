# 2026 World Cup Beijing-Time ICS Calendar

这个项目生成可订阅的 2026 年世界杯 `.ics` 日历，比赛时间统一转换为北京时间。

## 日历内容

- 比赛时间：北京时间 `Asia/Shanghai`
- 比赛标题：比赛队伍；如果已有比分，会显示比分
- 描述：比赛场地、阶段/小组、比赛状态
- 完赛后：描述里会尽量包含进球队员和进球时间
- 输出文件：`public/worldcup-2026.ics`

## 本地生成

```powershell
python -m venv .venv
.\.venv\Scripts\python -m worldcup_calendar update
```

## 启动可更新服务

```powershell
$env:UPDATE_TOKEN="change-me"
.\.venv\Scripts\python -m worldcup_calendar serve --host 0.0.0.0 --port 8080
```

接口：

- `GET /worldcup-2026.ics`：日历订阅文件
- `GET /matches.json`：结构化赛程数据
- `GET /health`：健康检查
- `POST /update?token=change-me`：手动更新

## GitHub Actions 自动更新

`.github/workflows/update-calendar.yml` 已配置每天北京时间 12:00 自动运行。

## 新建 GitHub 仓库并推送

当前目录已经是 Git 仓库。由于本机没有安装 `gh` 命令行，自动创建 GitHub 项目需要你先在 GitHub 网页中新建一个空仓库，然后运行：

```powershell
git remote add origin https://github.com/<your-name>/<repo-name>.git
git push -u origin main
```

第一次推送后，GitHub Actions 会自动生成 `public/worldcup-2026.ics` 和 `public/matches.json`。

在 GitHub 仓库里启用 Pages：

1. 打开 `Settings -> Pages`
2. Source 选 `Deploy from a branch`
3. Branch 选 `main`，目录选 `/public`
4. 保存后得到公开访问地址

Google 日历订阅：

1. 打开 Google Calendar
2. 选择 `其他日历 -> 通过网址添加`
3. 填入 GitHub Pages 上的 `worldcup-2026.ics` URL

## Docker 部署

```powershell
docker build -t worldcup-2026-calendar .
docker run -p 8080:8080 -e UPDATE_TOKEN=change-me worldcup-2026-calendar
```

订阅地址：

```text
http://your-server:8080/worldcup-2026.ics
```

## 手动修正

公开页面有延迟时，可以编辑 `data/overrides.json`，按 `match_id` 覆盖信息。

```json
{
  "M001": {
    "home_score": 2,
    "away_score": 1,
    "status": "completed",
    "goals": [
      {"team": "Canada", "player": "Example Player", "minute": "12'"}
    ]
  }
}
```
