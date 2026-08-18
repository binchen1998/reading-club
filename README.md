# 袋鼠英语阅读

读 coding61 章节书（Fly Guy / Nate the Great / 神奇树屋等）。目前只开放 **Nate the Great · Hungry Book Club · 第一章** 做实验。

- **前端**：Vue 3 + Vite + TypeScript + Tailwind
- **后端**：FastAPI 托管 `frontend/dist`（生产只跑 uvicorn）
- **部署**：服务器 `npm run deploy` 构建并把 JS/CSS 传到七牛，HTML 仍由 FastAPI 提供

## 数据库

启动过程**不会**建库建表。请先手工建好 MySQL 库和用户，再单独跑迁移：

```powershell
cd D:\git\reading-club\backend
# backend/.env 里设置：
# DB_TYPE=mysql
# MYSQL_URL=mysql+aiomysql://reading_club:你的密码@localhost/reading_club?charset=utf8mb4
python -m migrations.run
```

也可分步：`python -m migrations.0001_init`，再按序号跑 `0002` / `0003` / `0004_social`（关注、作品评论、留言板、通知）。

本地仍可用 SQLite：`DB_TYPE=sqlite`（默认），同样要先跑一次迁移。

## 启动

后端（conda 环境即可）：

```powershell
cd D:\git\reading-club
$env:PYTHONPATH = "D:\git\reading-club"
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

前端开发：

```powershell
cd D:\git\reading-club\frontend
npm install
npm run dev
```

打开 http://localhost:5174

管理后台：`/admin`，默认账号 `admin` / 密码 `coding61`。留言审核在「留言」页。

广场列表快照由 **独立 worker 进程** 定时覆盖（上传完成不会立刻失效快照）。必须另开一个终端启动：

```powershell
cd D:\git\reading-club
$env:PYTHONPATH = "D:\git\reading-club"
cd backend
python run_background_workers.py
```

启动后会立刻刷一次广场快照，之后默认每 60 秒覆盖（`SQUARE_SNAPSHOT_REFRESH_INTERVAL_SECONDS`）。锁文件 `backend/.background-workers.lock`，同一台机器只跑一份。Redis 开着时快照会同时写入 Redis。

本机预览 FastAPI 托管的页面（资源走本地 `/assets`，不要当生产流程）：

```powershell
cd frontend
npm run build
# 然后只开后端，访问 http://127.0.0.1:8001
```

## 部署

生产流程（本机只改代码；服务器构建并上传七牛）：

```powershell
# 1. 本机：提交源码并推送（不要提交 frontend/dist，不要在本机 npm run deploy）
git add ...; git commit -m "..."; git push

# 2. 服务器：
cd ~/git/reading-club
git pull
cd frontend
npm run deploy          # 生成本地 dist，并上传 JS/CSS 到七牛（HTML 指向 CDN）
```

复制 `backend/.env.example` → `backend/.env`（或仓库根 `.env`），填好 `QINIU_*`。`QINIU_FRONTEND_PREFIX` 默认 `reading-club`。

生产只跑 uvicorn 即可（服务 `frontend/dist`，由服务器 `npm run deploy` 生成，不进 git）。

## 预生成课稿 / TTS / OCR

不要在对话里替你跑。书先下载到 `content/books`，再指定范围：

```powershell
cd D:\git\reading-club
$env:PYTHONPATH = "D:\git\reading-club"
python -m scripts.prebuild_content --all
python -m scripts.prebuild_content --series NateTheGreat
python -m scripts.prebuild_content --series NateTheGreat --book hungry-book-club
python -m scripts.prebuild_content --series NateTheGreat --book "Hungry Book Club" --chapter 1
python -m scripts.prebuild_content --series NateTheGreat --book hungry-book-club --only tts
```

`--only` 可以是 `all`（默认，课稿+TTS+OCR）、`lesson`、`tts`、`ocr`。已有 `ch01.json` 默认不覆盖，加 `--force` 才重生成。生成课稿时会看上一页没写完的半句和下一页开头，避免把跨页句子拆错。需要 `QWEN_API_KEY`。

## 下载更多书

书目页显示「仅书目」= 本地还没有 `content/books/{系列}/{slug}/book.json`（页图和页 JSON 也还没下）。先拉书目，再按下基本页资源。**这个脚本不会生成讲解、OCR、TTS**，那些等用户打开阅读页后再由 worker 按需跑。不要用上面的 `prebuild_content` 来「开书」。

```powershell
$env:PYTHONPATH = "D:\git\reading-club"
python -m scripts.fetch_catalog
python -m scripts.fetch_book --series FancyNancy
python -m scripts.fetch_book --series FancyNancy --book "Fancy NANCY and the Boy from Paris"
python -m scripts.fetch_book --all
```

已有 `book.json` 默认跳过，加 `--force` 才重下。下载完成后刷新书目页，即可点进去读。
