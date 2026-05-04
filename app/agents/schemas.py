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
        "architecture_vulnerabilities": ["Milvus 不可用时是否有降级策略和用户提示？", "LLM 输出 JSON 失败时如何保证页面不崩溃？"],
        "landing_vulnerabilities": ["本地 Docker 首次启动 Milvus 较慢，需要健康检查和 README 说明。", "简历中的压测指标不能直接写死，必须来自真实验证。"],
        "logic_vulnerabilities": ["三轮迭代停止条件需要清晰，否则用户会误解为无限自动优化。", "人工否决架构方向后，后续 Agent 必须继续遵守该约束。"],
        "questions": ["如果向量库宕机，系统还能输出什么级别的结果？", "你如何证明这个项目不是简单 prompt 拼接？", "线上出现 LLM 响应超时，你会如何降级？"],
    }
