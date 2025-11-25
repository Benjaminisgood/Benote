# Benort

Benort 是一个围绕 LaTeX Beamer 演示创作构建的全栈平台：后端基于 Flask，前端使用单页 `editor.html` 整合 CodeMirror、PDF.js、Markdown 渲染与 Bootstrap 交互，同时对接主流 LLM、TTS 能力。除了传统的幻灯片编写，它也适合写讲稿、学术笔记甚至博客。

最新版本已将所有“项目”存储迁移为 **`.benort` SQLite 容器工作区**。一个 `.benort` 文件就是完整的项目（页面、模板、附件、资源、学习记录等都封装进去），可以像 VS Code 打开文件夹一样随时切换，并支持本地与远程（OSS）双工作区。

> 如果系统看到 `demo.benort` 旁边多了 `demo.benort-wal`/`demo.benort-shm`，那是 SQLite WAL 模式的正常产物，连接关闭或进行 checkpoint 后就会被自动清理。

---

## 核心特性

- **双模式编辑器**：共享一个界面即可在 LaTeX 和 Markdown 之间切换，并实时查看对应的 PDF/HTML 预览。
- **滚动同步**：通过“主导者”机制记录是谁在滚动，另一侧再按阈值跟随，抖动感很低。
- **AI 工作流**：
  - 页面级别的 LaTeX/Markdown/Script 优化按钮；
  - “AI 学习”支持后台运行，LLM 完成后结果会自动以弹窗方式出现，可立即收藏、分类或一键写入当前页面；
  - “AI 复习”面板可以按分类 / 收藏 / 关键词检索所有历史学习记录，收藏的内容会长期保留。
  - **AI 助理（可选 RAG）**：导航栏 “AI助理” 支持直接对话；勾选“使用 RAG”后会检索当前已解锁工作区的 Markdown 笔记（仅索引 `.benort` 内的 Markdown，不上传附件/LaTeX），命中片段会随回答返回。
- **语音与音频缓存**：支持使用 OpenAI TTS 生成整套讲稿或某页脚本的 MP3，并自动缓存到 `.benort` 容器中。
- **模板体系**：内置 `temps/` 目录的 LaTeX/Markdown 模板库，可在界面上套用并增补自定义段落。
- **访问加密**：每个 `.benort` 工作区都可以设置访问密码，密码会以 `projectSecurity` 形式保存在容器的 `meta` 表中；密码留空即视为未加密，任何人都可直接打开。
- **附件与资源管理**：在单个 `.benort` 内保存二进制文件，计划中的逻辑会避免在多个页面引用时被误删。
- **工作区入口**：导航栏左侧的下拉菜单包含“打开本地工作区 / 打开远程工作区”按钮。本地模式直接在磁盘上读写 `.benort` 文件；远程模式会列出 OSS 上的 `.benort` 包，可在线选择、创建并自动同步。

---

## 目录与组件概览

```
Benort/
├─ benort/
│  ├─ __init__.py        # Flask 工厂 & .env 加载
│  ├─ package.py         # `.benort` SQLite 容器读写
│  ├─ workspace.py       # 运行时工作区注册/切换
│  ├─ views.py           # Flask 蓝图（API + 模板渲染）
│  ├─ templates/
│  │   └─ editor.html   # 唯一的前端页面，内含所有 JS/CSS
│  └─ ...
├─ temps/                # 默认模板（YAML）
├─ README.md
└─ pyproject.toml
```

### 额外资源 & 清理脚本
- `node_modules/` & `package(-lock).json`：前端调试依赖，只有运行 `npm install` 后才会出现。如不需要，可执行 `scripts/clean_workspace.py --include-node` 一键移除。
- `.pytest_cache/`、`__pycache__/`、`build/`、`benort.egg-info/` 等目录仅由测试/打包流程生成，Benort 在启动时会自动清掉这些临时目录（设置 `BENORT_DISABLE_AUTO_CLEAN=1` 可关闭此行为），也可以执行 `scripts/clean_workspace.py` 手动清理。
- `scripts/clean_workspace.py`：统一的工作区清理工具，默认移除 Python 缓存与构建产物；加上 `--include-node` 参数可连同 `node_modules` 一并删除。

---

## 环境准备

1. **Python**：建议 Python 3.11+。
2. **虚拟环境与依赖**：

   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install --upgrade pip
   pip install .                   # 按 pyproject 安装依赖
   ```

3. **配置环境变量**：在仓库根目录放置 `.env`（Flask 启动时自动加载），示例：

   ```ini
   FLASK_DEBUG=1
   OPENAI_API_KEY=sk-xxxx

   # UI 主题
   BENORT_COLOR_MODE=dark
   BENORT_NAVBAR_PRESET=modern
   BENORT_NAVBAR_STYLE=palette
   BENORT_NAVBAR_VARIANT=solid

   # OSS/远程工作区
   ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
   ALIYUN_OSS_ACCESS_KEY_ID=xxx
   ALIYUN_OSS_ACCESS_KEY_SECRET=xxx
   ALIYUN_OSS_BUCKET=benort
   ALIYUN_OSS_PREFIX=workspaces
   ```

---

## 运行

```bash
flask --app benort run    # http://localhost:5000
```

生产环境可直接：

```bash
gunicorn -w 4 -b 0.0.0.0:5555 benort:app
```

---

## 工作区使用指南

1. **打开下拉菜单**：导航栏左上角的按钮显示当前工作区名。点击后可见：
   - `📁 打开本地工作区`：直接列出应用项目根目录（与本 README 同级）下的所有 `.benort` 文件，点选即可加载。
   - `☁️ 打开远程工作区`：使用 OSS 同步弹窗选择云端 `.benort`。

2. **本地工作区**：
   - Benort 会自动扫描项目根目录的 `.benort` 文件，刷新后立即更新列表。
   - 使用“新建本地工作区”表单输入文件名（自动追加 `.benort`），即可在根目录创建并立即打开；也可手动复制 `.benort` 文件后点击“刷新列表”。

3. **远程工作区（基于 OSS）**：
   - 需要在 `.env` 中配置 OSS 相关变量。
   - “打开远程工作区”会复用原有的 OSS 同步面板（计划升级为真正的在线工作区选择器）。

4. **WAL 文件提示**：当 `.benort` 打开时，SQLite 可能创建 `xxx.benort-wal` 与 `xxx.benort-shm`。这是写前日志机制的一部分，禁用 WAL 将牺牲性能与一致性，因此推荐保留。

---

## `.benort` 架构简述

- 底层是一个 SQLite 数据库，关键表：
  - `meta`：仅保存 `.benort` 的基础项目信息、时间戳与标志位。
  - `pages`：维护页顺序及更新时间；正文内容拆分到其他表。
  - `page_latex` / `page_markdown` / `page_notes`：分别存储单页的 LaTeX 正稿、Markdown 笔记与讲稿/演讲笔记。
  - `page_resources` / `page_references`：记录每页引用的资源文件、文献条目（以序号保持顺序）。
  - `project_resources` / `project_references`：项目级资源与引用清单，便于全局导出。
  - `attachments` / `resource_files`：真正的二进制附件与静态资源数据表，区分作用域。
  - `learning_prompts` / `learning_records`：学习助手的提示词与记录，记录行内可设置学习方法（`method`）、分类（`category`）与收藏标记（`favorite`），后端会自动清理 30 天未收藏的历史记录。
  - 其他业务表：`templates`（默认/自定义模板）、`settings` 等。
- `benort/package.py` 封装了所有读写逻辑（加载/保存项目、附件、模板等），前端 API 只需操作 `/workspaces/<id>/project`。
- 支持 WAL 以获得更好的并发写入与崩溃恢复。

---

## `.env` 关键项汇总

| 变量 | 说明 |
| ---- | ---- |
| `OPENAI_API_KEY` | Chat/TTS 等 AI 功能所需 |
| `ALIYUN_OSS_*` | 远程工作区 & OSS 同步 |
| `BENORT_*` | UI 主题、导航样式等 |

---

## 常用命令

| 命令 | 说明 |
| ---- | ---- |
| `pip install .` | 安装依赖 |
| `flask --app benort run` | 开发模式启动 |
| `gunicorn benort:app` | 生产部署示例 |
| `python -m compileall benort` | 快速语法检查 |

---

### AI 助理 & RAG

- 范围与缓存：仅索引当前已解锁 `.benort` 的 Markdown 笔记，索引与向量存放在本机临时目录，不会上传。
- 默认向量化：使用当前 LLM 提供方的 embedding 接口（默认 OpenAI `text-embedding-3-large`，路径 `/embeddings`）。不会在本机跑模型，除非你把 base_url 指向自己的服务。
- 自定义：可通过环境变量覆写 `LLM_BASE_URL`、`LLM_EMBEDDING_PATH`（默认 `/embeddings`）、`LLM_EMBEDDING_MODEL`、`LLM_PROVIDER`、`LLM_CHAT_PATH`、`LLM_MODEL` 等；前端请求也会带上 provider/model。
- 前端开关：导航栏 “AI助理” -> 勾/不勾 “使用 RAG” 切换是否检索笔记；未命中上下文自动回退为普通对话。
- 配额提醒：所选 provider 的 API Key 需有可用额度，否则会返回 `insufficient_quota`。

---

### 编辑体验

- [ ] 手机端窄屏适配：默认进入 Markdown 编辑模式，仅在 default 工作区暴露少量功能（换页/编辑）。
- [ ] 允许页面拖拽跨项目，并支持悬停预览缩略图。
- [ ] 双击导航栏页码跳转到当前项目第一页，用作目录页。
- [ ] Markdown 插入对话框新增常用模板（博客 Front Matter、日记、记账、笔记等），Front Matter 采用 YAML 示例。
- [ ] Markdown ↔ 预览滚动同步：继续维护“主导权 + 阈值 + 定时器防抖”的机制，减少抖动。

---

## 贡献指南

1. Fork & 新建分支。
2. 提交前运行最基本的 `python -m compileall benort` 确保语法无误。
3. 附加说明（如影响现有 `.benort` 文件）请写在 PR 描述。

如果你想讨论新的工作区特性、AI 工作流，直接在 Issue 区留言即可。谢谢！ ***
