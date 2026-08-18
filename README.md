# 英语阅读俱乐部

读 coding61 章节书（Fly Guy / Nate the Great / 神奇树屋等）。目前只开放 **Nate the Great · Hungry Book Club · 第一章** 做实验。

## 启动

后端（conda 环境即可）：

```powershell
cd D:\git\reading-club
$env:PYTHONPATH = "D:\git\reading-club"
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

前端：

```powershell
cd D:\git\reading-club\frontend
npm install
npm run dev
```

打开 http://localhost:5174

## 下载更多书

```powershell
$env:PYTHONPATH = "D:\git\reading-club"
python -m scripts.fetch_catalog
python -m scripts.fetch_book --series NateTheGreat --book "Hungry Book Club"
```

全书目已导入；其它系列图片先不下载。
