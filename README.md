# 英语阅读俱乐部

读 coding61 章节书（Fly Guy / Nate the Great / 神奇树屋等）。目前只开放 **Nate the Great · Hungry Book Club · 第一章** 做实验。

- **前端**：Vue 3 + Vite + TypeScript + Tailwind
- **后端**：FastAPI 托管 `frontend/dist`（生产只跑 uvicorn）
- **部署**：服务器 `npm run deploy` 构建并把 JS/CSS 传到七牛，HTML 仍由 FastAPI 提供

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

管理后台：`/admin`，默认账号 `admin` / 密码 `coding61`。

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

## 下载更多书

```powershell
$env:PYTHONPATH = "D:\git\reading-club"
python -m scripts.fetch_catalog
python -m scripts.fetch_book --series NateTheGreat --book "Hungry Book Club"
```

全书目已导入；其它系列图片先不下载。
