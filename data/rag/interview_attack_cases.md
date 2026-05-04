# 面试攻防案例库

## JSON 输出失败

风险：LLM 可能返回 Markdown、半截 JSON 或字段缺失。工程方案是使用 JSON mode、解析失败提取 JSON 片段、仍失败则走结构化 fallback，并把错误写入日志。

## Milvus 不可用

风险：向量库启动慢或连接失败导致主流程阻塞。工程方案是启动时探测连接，失败时降级到内置知识库，并在页面健康检查中显示当前 retrieval mode，避免误导用户。

## Embedding 模型切换

风险：不同 embedding 模型维度不同，复用旧 collection 会出现维度不匹配。工程方案是按 provider、mode、dimension 创建 collection 名称，避免新旧向量混写。

## 人工卡点

风险：用户否决的架构方向被后续 Agent 忽略。工程方案是把人工约束写入 LangGraph 全局 State，后续每个 Agent 都读取约束并在日志中保留决策依据。

## 简历合规

风险：为了显得高级而编造线上用户量、QPS、公司内部系统和收益。工程方案是合规 Agent 做最终收口，只保留可证明的设计、压测和演示指标。
