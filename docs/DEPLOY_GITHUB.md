# 部署到 GitHub Pages

前提：你有 GitHub 账号；本机不需要安装 Node/git，网页上传即可（也可以用自己的 git 客户端）。

## 1. 创建仓库并上传

1. GitHub → New repository → 名称如 `merge2-intel` → Public → Create。
2. 把本项目文件上传：
   - 网页端：Add file → Upload files，把仓库需要的文件/文件夹拖进去（可以拖文件夹）。
   - **不要上传**：`qa/`、`tools/logs/`、`tools/secrets.json`、`data/reports/`、`.edge-profile/`、`发布包-*.zip`。
   - 必须包含：`site/`、`data/`、`tools/`、`.github/workflows/pages.yml`、`docs/`、`scripts/`、`README.md`。
3. 提交到 `main` 分支。

## 2. 打开 Pages

- 仓库 Settings → Pages。
- Build and deployment → Source 选择 **GitHub Actions**（不要选 Deploy from a branch）。

## 3. 允许 Actions 写回数据

- Settings → Actions → General。
- Workflow permissions 选择 **Read and write permissions**，保存。
- 这是为了每日采集后把 `data/` 与 `site/data/` 的新数据提交回仓库。

## 4. 配置 DeepSeek（可选）

- Settings → Secrets and variables → Actions → New repository secret。
- Name：`DEEPSEEK_API_KEY`；Value：你的 key。
- 不配置也能正常运行；采集端会自动降级。

## 5. 首次运行

- 仓库 Actions → `build-and-deploy` → Run workflow → Run。
- 等待 1–3 分钟；成功后 Pages 地址为：

```
https://<你的用户名>.github.io/<仓库名>/
```

- 之后每天北京时间 07:00 自动运行（cron `0 23 * * *` UTC）。
- 定时任务只在默认分支上生效；首次必须手动 Run 一次。

## 6. 更新内容

- 自动数据：Actions 每天采集并提交。
- 你手工改了 `data/curated/` 后：直接 push/上传，push 会触发一次构建部署（push 事件不采集，只构建）。
- 也可以随时在 Actions 里手动 Run。

## 常见问题

**Actions 报 `Resource not accessible by integration`**
→ 第 3 步 Workflow permissions 没设成 Read and write。

**Pages 404**
→ 确认 Pages Source 是 GitHub Actions；确认 `build` 与 `deploy` 两个 job 都成功；首次部署需要 1–2 分钟生效。

**页面数据没更新**
→ 看 Actions 最近一次运行是否成功；看仓库根目录 `site/data/kb.js` 的 `buildId` 是否变化；浏览器强刷（Ctrl+F5）。

**国内访问慢/打不开**
→ GitHub Pages 在国内不稳定。备选：
1. `scripts\生成发布包.bat` 生成 zip，解压后上传 Vercel / Cloudflare Pages / 自己的服务器。
2. 使用自己的域名 + CDN。

**手机安装到桌面**
→ GitHub Pages 是 https，支持 PWA：Android Chrome 菜单 → 添加到主屏幕；iOS Safari → 分享 → 添加到主屏幕。

**站点被搜索引擎收录**
→ 默认 `site/index.html` 里有 `<meta name="robots" content="noindex,nofollow">`；如要公开收录，删掉这一行。
