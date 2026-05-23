# Knowledge Workbench

一个本地优先的知识工作台，把文档导入、语义检索、引用问答和资料管理整合到同一套 Vue + FastAPI 工作流中。

[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Vue 3](https://img.shields.io/badge/frontend-Vue%203-42b883.svg)](frontend/package.json)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)](backend/requirements.txt)
[![Local First](https://img.shields.io/badge/storage-local%20first-1f2937.svg)](backend/app/main.py)

## 快速开始

### 1. 克隆项目

```powershell
git clone https://github.com/kankan158/knowledge-workbench-local.git
cd knowledge-workbench-local
```

### 2. 安装依赖

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

前端：

```powershell
cd frontend
npm install
```

### 3. 启动服务

后端：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm run dev
```

### 4. 访问地址

| 服务 | 地址 |
| --- | --- |
| 前端界面 | http://localhost:4173 |
| 后端 API 文档 | http://127.0.0.1:8000/docs |
| 健康检查 | http://127.0.0.1:8000/health |

## 核心特性

| 特性 | 说明 |
| --- | --- |
| 文档导入 | 支持 TXT、PDF、DOCX、CSV、JSON、Excel 等格式导入 |
| 语义检索 | 基于 Chroma 的本地向量检索与关键词/混合检索 |
| 引用问答 | 通过 `/ask` 接口返回带来源的答案 |
| 本地优先 | 数据与索引保存在本地，不依赖外部数据库服务 |
| 可回退 RAG | 未配置 DeepSeek 时，仍可使用来源检索模式 |
| 可视化管理 | 前端支持目录、标签、搜索、预览和上下文菜单操作 |

## 详细用法

### 文档导入

上传文件后，后端会自动完成文本抽取、分块与入库。前端会同步返回文件分块与元数据，便于继续做标签、目录和检索管理。

### 搜索与问答

1. 在前端输入检索词并选择检索模式。
2. 点击“运行检索”查看结果。
3. 在问答区域输入问题并发送，系统会基于检索上下文生成回答。

### 目录与标签

1. 使用左侧目录管理文件夹层级。
2. 使用标签筛选文档。
3. 上传时可直接为新文件添加标签。

### 文件操作

文件条目支持右键菜单，常用操作包括复制文件名、复制内容、重命名和删除。

## CLI / API 参考

### 启动命令

本项目没有独立的自定义 CLI；推荐直接使用下面的本地启动命令或 VS Code 任务。

| 命令 | 作用 |
| --- | --- |
| `pip install -r requirements.txt` | 安装后端依赖 |
| `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` | 启动 FastAPI 后端 |
| `npm install` | 安装前端依赖 |
| `npm run dev` | 启动 Vite 前端 |
| `npm run build` | 构建前端生产包 |

### 后端 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 查看服务状态与文档数量 |
| `GET` | `/documents` | 列出当前已入库文档 |
| `POST` | `/documents` | 手动新增一条文档记录 |
| `DELETE` | `/documents/{document_id}` | 删除指定文档 |
| `POST` | `/documents/upload` | 上传文件并自动分块入库 |
| `GET` | `/search` | 执行语义/混合检索 |
| `POST` | `/ask` | 基于检索上下文生成答案 |
| `GET` | `/workspace/state` | 读取工作区状态（目录、标签、元数据） |
| `PATCH` | `/workspace/state` | 更新工作区状态 |

`/ask` 现在还支持可选的 `api_key` 字段，前端右上角的 `API` 按钮会把你本地保存的 DeepSeek 个人 key 一并带给后端。

### 典型请求示例

```powershell
curl "http://127.0.0.1:8000/search?q=知识工作台&top_k=5"
```

```powershell
curl -X POST "http://127.0.0.1:8000/ask" `
	-H "Content-Type: application/json" `
	-d "{`"question`":`"如何导入文档？`",`"top_k`":3,`"search_type`":`"hybrid`"}"
```

## 配置说明

## 一键启动（Windows）

项目根目录下提供了两个方便的启动方式：

- 手动分别启动（适合调试）

	1. 打开一个终端，进入 `backend` 并启动后端：

	```powershell
	cd backend
	.\.venv\Scripts\Activate.ps1
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
	```

	2. 再打开另一个终端，进入 `frontend` 并启动前端：

	```powershell
	cd frontend
	npm run dev
	```

- 双击启动（适合快速演示）

	在项目根目录双击 `start.bat`（或以管理员身份运行 `start.ps1`），脚本会在新窗口中依次启动后端与前端，并自动打开浏览器到 `http://localhost:4173/`。

	说明：`start.bat` 会尝试激活 `backend/.venv`（如果存在），并以 `127.0.0.1:8000` 启动后端；前端绑定到 `0.0.0.0:4173`，以便在本地网络环境与调试工具中更容易访问。


当前可配置项主要来自 [`.env.example`](.env.example)。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | `sk-your-api-key-here` | DeepSeek API Key；不设置时系统回退到本地来源检索模式 |
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` | DeepSeek API 基础地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 问答生成所使用的模型名 |
| `DEEPSEEK_TEMPERATURE` | 未启用 | 采样温度，可按需打开 |
| `DEEPSEEK_MAX_TOKENS` | 未启用 | 输出 token 上限，可按需打开 |

建议将敏感配置放在本地环境变量中，不要提交到仓库。

## 贡献指南

欢迎提交 Issue 和 Pull Request。建议流程如下：

1. Fork 仓库并创建分支。
2. 本地完成修改后运行 `npm run build` 和后端启动验证。
3. 提交清晰的 commit message，并在 PR 中说明变更范围与验证结果。
4. 如果涉及 API 或配置变更，请同步更新 README 与示例配置。

## 许可证

本项目采用 MIT License，详见 [LICENSE](LICENSE)。

## 项目结构

| 路径 | 说明 |
| --- | --- |
| `backend/app/main.py` | FastAPI 路由与上传/检索/问答入口 |
| `backend/app/store.py` | Chroma 存储、文档解析与检索逻辑 |
| `backend/app/rag.py` | DeepSeek 问答生成逻辑 |
| `frontend/src/App.vue` | 前端主界面与交互逻辑 |
| `data/` | 本地索引与工作区状态 |
| `.vscode/tasks.json` | 一键安装和运行任务 |
