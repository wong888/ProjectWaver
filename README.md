# ProjectWaver
A multi-agent project designed for polishing projects in programmers' CV.

# Multi-Agent程序员简历项目闭环打磨系统

一个轻量化、可本地演示、可写进简历的 Multi-Agent 项目：用 Python + LangGraph 编排六个智能体，结合本地 Milvus 轻量 RAG、Streamlit 前端和 JSON 持久化记忆，完成从岗位 JD 到简历项目段落、架构说明、面试话术、漏洞修复溯源的闭环。

## 核心能力

- 六大 Agent：岗位 JD 解析、后端架构共创、简历工程包装、资深攻防面试官、项目迭代修复、合规风控收口。
- Human-in-the-Loop：开局人工约束项目范围；攻防漏洞产出后人工指定修复边界。
- 三轮自动迭代：面试官找漏洞，修复 Agent 补强，最多三轮后强制进入合规收口。
- 技术文档记忆：为当前项目维护一份全局技术文档，面试官每轮通过 RAG 检索相关章节后再攻防，修复后反哺更新文档。
- 手动精细化补打磨：不重跑全流程，单独针对架构、性能、线上故障、部署运维、团队协作加厚细节。
- 模拟面试验收：内置八股 + 业务追问入口，直接根据攻防 Agent 的问题进行演练。
- 本地记忆与日志：`data/memory` 保存会话版本，`data/logs` 保存链路日志。
- LLM 双模式：默认 `mock` 无 Key 可跑；配置 `LLM_BASE_URL` 后可切 OpenAI 或国内兼容接口。

## 目录结构

```text
multi-agent-resume-polisher/
  app/
    agents/              # LangGraph State、节点和图编排
    core/                # 配置
    services/            # LLM、Milvus RAG、JSON记忆、日志
    ui/                  # Streamlit页面
  data/
    memory/              # 本地会话持久化
    logs/                # JSONL链路日志
    rag/                 # 内置知识片段
  scripts/
    start-local.sh
    start-docker.sh
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

## 本地启动

```bash
cd /home/jamtingwang/multi-agent-resume-polisher
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
bash scripts/start-local.sh
```

浏览器打开：<http://localhost:8501>

本地模式下如果 Milvus 没启动，系统会自动使用内置知识库降级，保证演示不断链。

## FastAPI 调用 Agent

如果不想依赖 Streamlit 页面，可以直接启动 API 服务：

```bash
cd /home/jamtingwang/multi-agent-resume-polisher
docker compose up -d api
```

API 文档：

```text
http://localhost:18000/docs
```

健康检查：

```bash
curl http://localhost:18000/health
```

执行完整六 Agent 闭环：

```bash
curl -X POST http://localhost:18000/api/v1/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "jd_text": "招聘Python后端工程师，要求熟悉RAG、向量数据库、Docker部署和可观测性。",
    "personal_stack": "Python LangGraph Milvus FastAPI Streamlit Docker Redis MySQL",
    "target_level": "中级",
    "human_constraints": {
      "project_name": "Multi-Agent程序员简历项目闭环打磨系统",
      "highlight_focus": "真实RAG、LangGraph编排、日志追踪、部署运维",
      "forbidden_directions": "不编造大厂亿级流量，不伪造真实公司线上系统"
    },
    "attack_human_decision": {
      "decision": "允许自动修复",
      "note": "重点追问真实RAG、故障降级和部署"
    }
  }'
```

原生 Human-in-the-Loop interrupt/resume 流程：

```bash
curl -X POST http://localhost:18000/api/v1/pipeline/start-hitl \
  -H "Content-Type: application/json" \
  -d '{
    "jd_text": "招聘Python后端工程师，要求熟悉RAG、向量数据库、Docker部署和可观测性。",
    "personal_stack": "Python LangGraph Milvus FastAPI Docker",
    "target_level": "中级"
  }'
```

第一次会在 JD 解析后中断，返回 `session_id` 和 `interrupts`。用同一个 `session_id` 恢复：

```bash
curl -X POST http://localhost:18000/api/v1/pipeline/resume \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "替换成start-hitl返回的session_id",
    "resume_value": {
      "project_name": "Multi-Agent程序员简历项目闭环打磨系统",
      "highlight_focus": "真实RAG、LangGraph checkpoint、interrupt/resume",
      "forbidden_directions": "不编造大厂亿级流量"
    }
  }'
```

第二次会在攻防报告产出后中断，再恢复：

```bash
curl -X POST http://localhost:18000/api/v1/pipeline/resume \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "同一个session_id",
    "resume_value": {
      "decision": "允许自动修复",
      "note": "重点补强真实RAG、故障降级和部署运维"
    }
  }'
```

查看 checkpoint 快照：

```bash
curl http://localhost:18000/api/v1/pipeline/checkpoints/替换成session_id
```

RAG 检索：

```bash
curl -X POST http://localhost:18000/api/v1/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query":"LangGraph Milvus RAG 如何降低幻觉","limit":3}'
```

检索当前会话的技术文档 RAG：

```bash
curl -X POST http://localhost:18000/api/v1/technical-doc/search \
  -H "Content-Type: application/json" \
  -d '{"session_id":"替换成真实session_id","query":"Milvus 不可用时系统如何降级","limit":5}'
```

查看历史会话：

```bash
curl http://localhost:18000/api/v1/sessions
```

基于历史会话做单点补打磨：

```bash
curl -X POST http://localhost:18000/api/v1/manual-polish \
  -H "Content-Type: application/json" \
  -d '{"session_id":"替换成真实session_id","focus":"性能","manual_input":"补充压测、p95、降级策略和慢查询治理"}'
```

## Docker 启动 Milvus + 应用

```bash
cd /home/jamtingwang/multi-agent-resume-polisher
cp .env.example .env
bash scripts/start-docker.sh
```

首次启动 Milvus 需要等待容器初始化。页面打开后输入 JD 和个人技术栈即可运行完整闭环。

如果本机已有 Milvus 占用 `19530`，本项目默认把 Docker 内 Milvus 映射到宿主机 `19531`，应用容器内部仍使用 `milvus:19530` 通信。MinIO 和 Milvus 指标端口也默认避开常见冲突。需要改宿主机端口时，编辑 `.env`：

```env
MILVUS_HOST_PORT=19532
MILVUS_METRICS_HOST_PORT=19092
MINIO_API_HOST_PORT=19002
MINIO_CONSOLE_HOST_PORT=19003
```

## 切换大模型接口

编辑 `.env`：

```env
LLM_PROVIDER=compatible
LLM_API_KEY=你的API_KEY
LLM_BASE_URL=https://你的兼容接口/v1
LLM_MODEL=你的模型名
```

真实 RAG 还需要配置 Embedding。默认使用 `fastembed` 加载本地 ONNX 版 BGE 小模型，不依赖云端 embedding 权限，也避免 GPU 版 PyTorch 大依赖：

```env
EMBEDDING_PROVIDER=local
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DIM=512
```

首次启动会下载轻量 ONNX embedding 模型；如果远程开发机无法访问模型仓库，可以改回云端兼容 embedding，或把模型缓存提前放到机器上。

如果你的 LLM 服务商提供 OpenAI 兼容 embedding，可以切到云端 embedding：

```env
EMBEDDING_PROVIDER=compatible
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
```

如果 chat 和 embedding 放在同一个 OpenAI 兼容地址，`EMBEDDING_API_KEY` 和 `EMBEDDING_BASE_URL` 可以留空，系统会自动复用 LLM 配置。若 embedding 调用失败，页面的「RAG健康检查」会显示 fallback 和错误原因。

火山方舟可尝试：

```env
EMBEDDING_MODEL=doubao-embedding-250615
EMBEDDING_DIM=1024
```

OpenAI 官方接口示例：

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

## 简历可写亮点

- 基于 LangGraph StateGraph 设计有状态多 Agent 编排，使用条件路由控制三轮攻防修复和合规收口。
- 引入 Human-in-the-Loop 人工卡点，把项目技术范围、强化亮点和架构否决项写入全局状态，减少 Agent 偏航。
- 使用 Milvus 本地向量库构建轻量 RAG，LLM 输出前检索工程知识，降低简历包装中的幻觉和夸大。
- 增加项目级技术文档记忆，把完整设计作为权威文档保存，再切片写入 RAG 索引，面试官按需召回片段追问，避免长文档撑爆上下文。
- 通过攻防结果反哺技术文档，每轮修复后沉淀设计取舍、降级策略、证据缺口和面试防守口径。
- 通过 JSON 持久化记忆保存多轮迭代版本，配合 JSONL 链路日志支持问题溯源和面试复盘。
- 前端提供主流程、单点补打磨和模拟面试验收三个入口，适合截图展示完整产品闭环。

## 导入 RAG 知识库

把 `.md`、`.txt` 或 `.json` 文件放到 `data/rag/`，然后执行：

```bash
docker compose exec app python scripts/ingest_rag.py
```

脚本会自动切分文本、调用真实 embedding、写入 Milvus，并输出 collection、向量维度、chunk 数和 embedding 模式。

## 合规提醒

本项目默认不编造真实公司、真实 DAU、真实 QPS、营收收益等不可证明信息。压测指标、线上故障案例和团队协作经历建议在你真实验证后再补充到简历。
