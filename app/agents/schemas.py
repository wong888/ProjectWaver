from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class HumanScopeDecision(BaseModel):
    project_name: str = Field("", description="用户确认或指定的项目名称")
    highlight_focus: str = Field("", description="用户指定要强化的工程亮点")
    forbidden_directions: str = Field("", description="用户否决的不合理架构方向")


class AttackHumanDecision(BaseModel):
    decision: str = Field("允许自动修复", description="是否允许自动修复、是否限制架构复杂度")
    note: str = Field("", description="人工补充的攻防关注点")


def jd_profile_fallback(target_level: str, keywords: List[str]) -> Dict[str, Any]:
    return {
        "target_role": "后端开发工程师",
        "seniority": target_level,
        "required_capabilities": keywords or ["接口设计", "数据库建模", "缓存优化", "稳定性治理", "工程协作"],
        "business_scenes": ["招聘匹配", "内容平台", "交易订单", "企业内部效率工具"],
        "risk_notes": ["不要编造真实线上用户量", "优先选择能本地复现和压测的场景"],
    }


def architecture_fallback(project_name: str, forbidden: str, capabilities: List[str]) -> Dict[str, Any]:
    return {
        "project_name": project_name,
        "business_problem": "研发团队知识分散、历史故障经验难复用、需求与缺陷流转缺少可追踪闭环。",
        "architecture": {
            "frontend": "Streamlit 管理台用于演示流程和结果验收",
            "backend": "Python 服务层组织业务编排、RAG 检索、异步修复建议生成",
            "storage": "JSON 本地记忆保存会话版本，Milvus 保存工程知识向量",
            "observability": "结构化日志记录 Agent 输入输出、迭代轮次和风险收口",
        },
        "modules": ["JD 能力抽取", "项目架构共创", "简历包装", "攻防面试", "迭代修复", "合规风控", "模拟面试验收"],
        "engineering_highlights": [
            "LangGraph 有状态多 Agent 编排",
            "Human-in-the-Loop 人工卡点控制架构方向",
            "Milvus 本地向量库轻量 RAG 降低幻觉",
            "JSON 版本化记忆与链路日志",
            "三轮漏洞驱动迭代闭环",
        ],
        "explicitly_avoided": forbidden,
        "matched_capabilities": capabilities,
    }


def technical_doc_fallback(jd_profile: Dict[str, Any], constraints: Dict[str, Any], blueprint: Dict[str, Any]) -> Dict[str, Any]:
    project_name = blueprint.get("project_name") or constraints.get("project_name") or "多 Agent 简历项目闭环打磨系统"
    capabilities = jd_profile.get("required_capabilities", [])
    return {
        "version": 1,
        "project_overview": {
            "project_name": project_name,
            "business_problem": blueprint.get("business_problem", "围绕岗位 JD 把候选人的真实技术栈沉淀成可验证、可面试追问的项目表达。"),
            "target_users": "准备后端岗位面试、需要打磨简历项目和面试话术的程序员。",
            "scope_boundary": constraints.get("forbidden_directions", "不编造真实公司线上经历，不声称无法证明的超大规模流量。"),
        },
        "architecture_design": {
            "overall_architecture": blueprint.get("architecture", {}),
            "modules": blueprint.get("modules", []),
            "data_flow": "JD 与个人技术栈进入 LangGraph 全局 State，经架构共创、简历包装、攻防、修复和合规收口逐步沉淀为最终输出。",
            "state_management": "使用 LangGraph StateGraph 保存会话级状态，checkpoint 支持 Human-in-the-Loop interrupt/resume。",
            "deployment_topology": "本地 Streamlit/FastAPI 应用连接 Milvus，JSON 文件保存会话记忆和链路日志。",
        },
        "core_tech_stack": [
            {"name": "LangGraph", "usage": "编排多 Agent 状态机和条件路由", "reason": "需要显式状态、可恢复中断和多轮迭代", "interview_basics": "说明 State、节点、边、checkpoint 和 interrupt/resume 的作用。"},
            {"name": "RAG/Milvus", "usage": "检索工程知识和技术文档片段", "reason": "减少长上下文注入和 LLM 幻觉", "interview_basics": "说明 chunk、embedding、向量检索、fallback 和命中片段如何进入 prompt。"},
            {"name": "JSON Memory", "usage": "保存会话版本、技术文档和迭代历史", "reason": "便于复盘攻防修复链路", "interview_basics": "说明本地持久化和可审计变更记录。"},
        ],
        "design_decisions": [
            {"decision": "把技术文档作为权威记忆，RAG 作为检索视图", "alternatives": ["每轮注入完整技术文档", "只存向量库不保留原文"], "tradeoff": "兼顾可展示、可回溯和上下文控制", "risk": "需要保证索引版本与文档版本一致。"},
            {"decision": "最多三轮攻防修复后进入合规收口", "alternatives": ["无限迭代", "单轮生成"], "tradeoff": "避免演示时间失控，同时保留漏洞驱动补强过程", "risk": "复杂问题可能需要人工继续补打磨。"},
        ],
        "failure_handling": {
            "llm_json_failure": "LLM 输出非法 JSON 时使用结构化 fallback，保证页面和 API 仍返回可读结果。",
            "vector_db_unavailable": "Milvus 不可用时降级到内置知识片段或本地技术文档关键词检索。",
            "llm_timeout": "LLM 客户端配置超时和低重试次数，失败后记录 fallback 原因。",
            "empty_retrieval": "RAG 无命中时使用项目蓝图和当前技术文档摘要继续生成，不阻断主流程。",
        },
        "observability": {
            "logs": "每个 Agent 记录工具调用、命中来源、输出规模和 fallback 状态。",
            "memory": "data/memory 保存最终 State、技术文档和迭代历史。",
            "checkpoint": "LangGraph InMemorySaver 支持 HITL 中断恢复和 checkpoint 快照查看。",
            "debug_trace": "final_output.trace_logs 汇总链路日志，便于复盘每轮决策依据。",
        },
        "interview_defense": {
            "key_talking_points": blueprint.get("engineering_highlights", []),
            "likely_questions": ["为什么需要全局技术文档？", "技术文档过长时如何避免上下文爆炸？", "RAG 检索不准时如何兜底？"],
            "answer_boundaries": ["只描述本地可演示和可验证能力", "性能指标必须来自真实压测", "不伪造公司内部系统或线上规模。"],
        },
        "known_risks": ["技术文档 RAG 命中质量需要通过真实问题持续观察。"],
        "evidence_needed": ["补充本地压测截图、日志样例、Milvus 不可用时的降级演示截图。"],
        "change_log": [{"version": 1, "summary": "基于岗位画像、人工约束和项目蓝图初始化技术文档。"}],
    }


def technical_doc_update_fallback(current_doc: Dict[str, Any], attack_report: Dict[str, Any], repair_result: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(current_doc) if current_doc else {"version": 1}
    version = int(updated.get("version", 1)) + 1
    updated["version"] = version
    known_risks = list(updated.get("known_risks", []))
    known_risks.extend(attack_report.get("doc_gaps", []) or attack_report.get("architecture_vulnerabilities", []))
    updated["known_risks"] = list(dict.fromkeys(str(item) for item in known_risks if item))
    evidence_needed = list(updated.get("evidence_needed", []))
    evidence_needed.extend(repair_result.get("remaining_risks", []))
    updated["evidence_needed"] = list(dict.fromkeys(str(item) for item in evidence_needed if item))
    change_log = list(updated.get("change_log", []))
    change_log.append(
        {
            "version": version,
            "summary": repair_result.get("resume_delta", "根据本轮攻防报告补充技术文档风险、修复点和面试防守口径。"),
            "round": repair_result.get("round", attack_report.get("round")),
        }
    )
    updated["change_log"] = change_log
    return updated


def resume_package_fallback(project_name: str) -> Dict[str, Any]:
    return {
        "resume_project_paragraph": (
            f"{project_name}：基于 Python、LangGraph、Milvus 与 Streamlit "
            "实现岗位 JD 解析、项目架构共创、攻防面试、迭代修复和合规收口的多 Agent 闭环系统。"
            "本人负责全链路状态编排、轻量 RAG、Human-in-the-Loop 卡点、JSON 持久化记忆和可观测日志建设，"
            "通过三轮漏洞驱动迭代将项目表达沉淀为简历段落、架构说明和面试应答话术。"
        ),
        "architecture_summary": [
            "前端 Streamlit 负责表单输入、人工介入、结果渲染与模拟面试。",
            "LangGraph StateGraph 串联六个 Agent，所有节点共享全局状态并输出结构化 JSON。",
            "Milvus 保存工程知识片段，LLM 生成前先检索约束，降低脱离真实场景的幻觉。",
            "本地 JSON 保存每次迭代版本，日志可追踪每个 Agent 的决策依据。",
        ],
        "interview_talking_points": [
            "为什么选择 LangGraph：需要显式状态、条件路由和可恢复的多 Agent 工作流。",
            "如何降低幻觉：RAG 检索工程知识、人工卡点约束技术范围、合规 Agent 删除不可证明表述。",
            "如何体现上线能力：包含日志、版本化记忆、Docker 本地部署、错误降级和可观测性。",
        ],
        "metrics_claims": ["本地压测和演示指标需由用户后续实际补充，不默认编造。"],
    }


def attack_report_fallback(round_no: int) -> Dict[str, Any]:
    return {
        "round": round_no,
        "severity": "high" if round_no == 1 else "medium",
        "doc_based_questions": ["技术文档里如何证明 RAG 不是简单 prompt 拼接？", "技术文档的降级策略是否覆盖 Milvus 和 LLM 双故障？"],
        "doc_gaps": ["技术文档需要明确每个关键设计的验证证据和失败预案。"],
        "architecture_vulnerabilities": ["Milvus 不可用时是否有降级策略和用户提示？", "LLM 输出 JSON 失败时如何保证页面不崩溃？"],
        "landing_vulnerabilities": ["本地 Docker 首次启动 Milvus 较慢，需要健康检查和 README 说明。", "简历中的压测指标不能直接写死，必须来自真实验证。"],
        "logic_vulnerabilities": ["三轮迭代停止条件需要清晰，否则用户会误解为无限自动优化。", "人工否决架构方向后，后续 Agent 必须继续遵守该约束。"],
        "recommended_doc_updates": ["补充技术文档 RAG 的 chunk 策略、检索范围和 Milvus 不可用时的本地检索 fallback。"],
        "questions": ["如果向量库宕机，系统还能输出什么级别的结果？", "你如何证明这个项目不是简单 prompt 拼接？", "线上出现 LLM 响应超时，你会如何降级？"],
    }
