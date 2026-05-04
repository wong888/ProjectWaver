from __future__ import annotations

import re
from typing import Any, Dict, List

from langgraph.types import interrupt

from app.agents import prompts
from app.agents.schemas import attack_report_fallback, architecture_fallback, jd_profile_fallback, resume_package_fallback
from app.agents.state import ResumePolishState
from app.agents.tools import render_rag_context, retrieve_resume_rag_context
from app.services.event_logger import make_log
from app.services.llm_client import llm_client, split_keywords


def _ctx(state: ResumePolishState) -> str:
    return render_rag_context.invoke({"rag_context": state.get("rag_context", []), "max_chars": 900})


def _retrieve_for_agent(agent: str, query: str, limit: int = 3) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    hits = retrieve_resume_rag_context.invoke({"query": query, "limit": limit})
    trace = {
        "tool": "retrieve_resume_rag_context",
        "query": query[:160],
        "hit_count": len(hits),
        "sources": [hit.get("source") for hit in hits],
        "top_scores": [hit.get("score") for hit in hits],
    }
    return hits, make_log(agent, "tool_invoked", trace)


def _render_context_for_agent(agent: str, hits: List[Dict[str, Any]]) -> tuple[str, Dict[str, Any]]:
    context = render_rag_context.invoke({"rag_context": hits, "max_chars": 900})
    return context, make_log(agent, "tool_invoked", {"tool": "render_rag_context", "chars": len(context)})


def _sanitize_resume_package(package: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    sanitized = dict(package)
    paragraph = str(sanitized.get("resume_project_paragraph", ""))
    removed: List[str] = []
    patterns = [
        (r"累计支持\d+\+?份简历迭代优化，?", "删除不可证明的累计简历数量"),
        (r"平均迭代\d+轮即可满足岗位匹配要求。?", "删除不可证明的平均达标轮次"),
        (r"匹配度[^，。]*提升\d+(\.\d+)?%[，。]?", "删除不可证明的匹配度提升比例"),
        (r"通过率[^，。]*提升\d+(\.\d+)?%[，。]?", "删除不可证明的通过率提升比例"),
        (r"幻觉率[^，。]*降低\d+(\.\d+)?%[，。]?", "删除不可证明的幻觉率下降比例"),
    ]
    for pattern, reason in patterns:
        paragraph, count = re.subn(pattern, "", paragraph)
        if count:
            removed.append(reason)
    sanitized["resume_project_paragraph"] = paragraph.strip()
    return sanitized, removed


def jd_parser_agent(state: ResumePolishState) -> ResumePolishState:
    jd_text = state["jd_text"]
    stack = state["personal_stack"]
    keywords = split_keywords(jd_text, stack)
    rag_context, rag_log = _retrieve_for_agent("jd_parser", f"岗位能力解析 JD:{jd_text}\n候选人技术栈:{stack}", limit=4)
    jd_context, render_log = _render_context_for_agent("jd_parser", rag_context)
    fallback = jd_profile_fallback(state.get("target_level", "中级"), keywords)
    jd_profile = llm_client.json_chat(
        prompts.JD_PARSER_SYSTEM,
        prompts.jd_parser_user(jd_text, stack, jd_context),
        fallback,
    )
    return {
        "current_agent": "jd_parser",
        "jd_profile": jd_profile,
        "rag_context": rag_context,
        "logs": [
            rag_log,
            render_log,
            make_log(
                "jd_parser",
                "agent_completed",
                {
                    "target_role": jd_profile.get("target_role"),
                    "capabilities": jd_profile.get("required_capabilities", []),
                    "used_fallback": "_llm_fallback_reason" in jd_profile,
                },
            ),
        ],
    }


def scope_human_gate(state: ResumePolishState) -> ResumePolishState:
    if state.get("human_constraints"):
        return {
            "current_agent": "human_scope_gate",
            "logs": [make_log("human_scope_gate", "scope_constraints_preapproved", {"human_constraints": state.get("human_constraints", {})})],
        }

    decision = interrupt(
        {
            "checkpoint": "scope_constraints",
            "message": "请确认项目技术范围、工程亮点和需要否决的架构方向。",
            "jd_profile": state.get("jd_profile", {}),
            "personal_stack": state.get("personal_stack", ""),
            "expected_schema": {
                "project_name": "项目名称",
                "highlight_focus": "要强化的工程亮点",
                "forbidden_directions": "明确否决的不合理架构方向",
            },
        }
    )
    constraints = decision.get("human_constraints", decision) if isinstance(decision, dict) else {}
    return {
        "current_agent": "human_scope_gate",
        "human_constraints": constraints,
        "logs": [make_log("human_scope_gate", "scope_constraints_resumed", {"human_constraints": constraints})],
    }


def architecture_cocreation_agent(state: ResumePolishState) -> ResumePolishState:
    constraints = state.get("human_constraints", {})
    capabilities = state.get("jd_profile", {}).get("required_capabilities", [])
    forbidden = constraints.get("forbidden_directions", "")
    project_name = constraints.get("project_name") or "智能研发效能工单与知识检索平台"
    arch_hits, rag_log = _retrieve_for_agent(
        "architecture_cocreation",
        f"后端架构设计 部署 稳定性 真实落地 能力:{capabilities} 约束:{constraints}",
    )
    arch_context, render_log = _render_context_for_agent("architecture_cocreation", arch_hits)
    fallback = architecture_fallback(project_name, forbidden, capabilities)
    blueprint = llm_client.json_chat(
        prompts.ARCHITECTURE_SYSTEM,
        prompts.architecture_user(capabilities, constraints, forbidden, f"{_ctx(state)}\n{arch_context}"),
        fallback,
    )
    return {
        "current_agent": "architecture_cocreation",
        "project_blueprint": blueprint,
        "logs": [
            rag_log,
            render_log,
            make_log(
                "architecture_cocreation",
                "agent_completed",
                {
                    "project_name": blueprint.get("project_name"),
                    "modules": len(blueprint.get("modules", [])),
                    "used_fallback": "_llm_fallback_reason" in blueprint,
                },
            ),
        ],
    }


def resume_packaging_agent(state: ResumePolishState) -> ResumePolishState:
    blueprint = state.get("project_blueprint", {})
    resume_hits, rag_log = _retrieve_for_agent(
        "resume_packaging",
        f"简历项目表达 面试话术 合规指标 项目:{blueprint.get('project_name', '')}",
    )
    resume_context, render_log = _render_context_for_agent("resume_packaging", resume_hits)
    fallback = resume_package_fallback(blueprint.get("project_name", "多 Agent 简历项目闭环打磨系统"))
    package = llm_client.json_chat(
        prompts.RESUME_PACKAGING_SYSTEM,
        prompts.resume_packaging_user(blueprint, state.get("jd_profile", {})) + f"\nRAG参考:\n{resume_context}",
        fallback,
    )
    return {
        "current_agent": "resume_packaging",
        "resume_package": package,
        "logs": [
            rag_log,
            render_log,
            make_log(
                "resume_packaging",
                "agent_completed",
                {
                    "talking_points": len(package.get("interview_talking_points", [])),
                    "has_resume_paragraph": bool(package.get("resume_project_paragraph")),
                    "used_fallback": "_llm_fallback_reason" in package,
                },
            ),
        ],
    }


def senior_interviewer_agent(state: ResumePolishState) -> ResumePolishState:
    round_no = int(state.get("iteration_round", 0)) + 1
    attack_hits, rag_log = _retrieve_for_agent(
        "senior_interviewer",
        f"面试攻防 架构漏洞 落地漏洞 线上故障 第{round_no}轮 项目:{state.get('project_blueprint', {}).get('project_name', '')}",
    )
    attack_context, render_log = _render_context_for_agent("senior_interviewer", attack_hits)
    fallback = attack_report_fallback(round_no)
    report = llm_client.json_chat(
        prompts.SENIOR_INTERVIEWER_SYSTEM,
        prompts.senior_interviewer_user(round_no, state.get("project_blueprint", {}), state.get("resume_package", {}), state.get("attack_human_decision", {}))
        + f"\nRAG攻防参考:\n{attack_context}",
        fallback,
    )
    return {
        "current_agent": "senior_interviewer",
        "attack_report": report,
        "iteration_round": round_no,
        "logs": [
            rag_log,
            render_log,
            make_log(
                "senior_interviewer",
                "agent_completed",
                {
                    "round": round_no,
                    "severity": report.get("severity"),
                    "questions": len(report.get("questions", [])),
                    "used_fallback": "_llm_fallback_reason" in report,
                },
            ),
        ],
    }


def attack_human_gate(state: ResumePolishState) -> ResumePolishState:
    if state.get("attack_human_decision"):
        return {
            "current_agent": "human_attack_gate",
            "logs": [make_log("human_attack_gate", "attack_decision_preapproved", {"attack_human_decision": state.get("attack_human_decision", {})})],
        }

    decision = interrupt(
        {
            "checkpoint": "attack_review",
            "message": "请审阅攻防漏洞，决定是否允许自动修复以及修复边界。",
            "attack_report": state.get("attack_report", {}),
            "expected_schema": {
                "decision": "允许自动修复/只保守修复/否决当前架构方向",
                "note": "人工补充攻防关注点",
            },
        }
    )
    attack_decision = decision.get("attack_human_decision", decision) if isinstance(decision, dict) else {}
    return {
        "current_agent": "human_attack_gate",
        "attack_human_decision": attack_decision,
        "logs": [make_log("human_attack_gate", "attack_decision_resumed", {"attack_human_decision": attack_decision})],
    }


def iteration_repair_agent(state: ResumePolishState) -> ResumePolishState:
    attack = state.get("attack_report", {})
    repair_hits, rag_log = _retrieve_for_agent(
        "iteration_repair",
        f"项目修复 降级 观测 部署 运维 攻防问题:{attack}",
    )
    repair = {
        "round": state.get("iteration_round", 1),
        "fixed_points": [
            "补充 Milvus 不可用时的内置知识库降级路径。",
            "补充 LLM JSON 解析失败 fallback，确保页面仍返回结构化结果。",
            "在 README 明确压测指标需本地验证后填写，避免简历夸大。",
            "人工约束进入全局 State，后续 Agent 持续读取。",
        ],
        "resume_delta": "将项目亮点从泛泛 AI 包装改为：有状态编排、人工卡点、RAG 约束、版本记忆、日志追踪、故障降级。",
        "remaining_risks": ["真实性能数据仍需用户在本机或目标环境压测后补充。"] if state.get("iteration_round", 1) >= 3 else ["继续追问降级、部署和协作细节。"],
        "source_attack": attack,
    }
    return {
        "current_agent": "iteration_repair",
        "iteration_history": [repair],
        "logs": [
            rag_log,
            make_log(
                "iteration_repair",
                "agent_completed",
                {"round": repair["round"], "fixed": len(repair["fixed_points"]), "rag_sources": [hit.get("source") for hit in repair_hits]},
            ),
        ],
    }


def compliance_risk_agent(state: ResumePolishState) -> ResumePolishState:
    compliance_hits, rag_log = _retrieve_for_agent(
        "compliance_risk",
        f"简历合规 风险收口 不夸大 不造假 项目:{state.get('project_blueprint', {}).get('project_name', '')}",
    )
    sanitized_resume_package, sanitized_claims = _sanitize_resume_package(state.get("resume_package", {}))
    report = {
        "compliance_status": "pass_with_notes",
        "removed_or_softened_claims": [
            "未写死 DAU、QPS、营收、公司内部系统等不可证明信息。",
            "将所有性能收益表述为可验证方法或待压测指标。",
        ]
        + sanitized_claims,
        "safe_resume_rules": [
            "只说自己实现过的模块，不冒充真实线上公司项目。",
            "指标必须来自本地压测、日志截图或演示环境。",
            "架构复杂度与个人经历匹配，避免过度包装成大厂中台。",
        ],
    }
    log = make_log("compliance_risk", "compliance_closed", {"status": report["compliance_status"]})
    trace_logs = list(state.get("logs", [])) + [rag_log, log]
    final_output = {
        "jd_profile": state.get("jd_profile", {}),
        "project_blueprint": state.get("project_blueprint", {}),
        "resume_package": sanitized_resume_package,
        "attack_report": state.get("attack_report", {}),
        "iteration_history": state.get("iteration_history", []),
        "compliance_report": report,
        "trace_logs": trace_logs,
    }
    return {
        "current_agent": "compliance_risk",
        "compliance_report": report,
        "final_output": final_output,
        "logs": [
            rag_log,
            make_log(
                "compliance_risk",
                "agent_completed",
                {
                    "status": report["compliance_status"],
                    "rules": len(report.get("safe_resume_rules", [])),
                    "rag_sources": [hit.get("source") for hit in compliance_hits],
                },
            ),
        ],
    }


def should_continue_iteration(state: ResumePolishState) -> str:
    return "continue" if int(state.get("iteration_round", 0)) < 3 else "finish"


def manual_polish_agent(state: ResumePolishState) -> ResumePolishState:
    focus = state.get("manual_focus") or "架构"
    user_input = state.get("manual_input") or ""
    polish_hits, rag_log = _retrieve_for_agent("manual_polish", f"{focus} 单点补打磨 {user_input}", limit=3)
    output = {
        "focus": focus,
        "deepened_details": [
            f"围绕「{focus}」补充问题背景、设计取舍、失败预案和可验证证据。",
            "把回答拆成：场景 -> 决策 -> 方案 -> 风险 -> 验证 -> 复盘，便于面试展开。",
            "保持克制表达，不编造无法证明的线上规模。",
        ],
        "resume_patch": f"补充{focus}专项：{user_input or '从架构边界、性能验证、故障恢复和协作流程四类证据补强。'}",
        "interview_answer": f"面试回答建议：我在这个项目中针对{focus}做过专项设计，先明确约束，再落到实现细节，最后用日志、版本记录或压测结果证明效果。",
    }
    return {
        "manual_polish_output": output,
        "logs": [
            rag_log,
            make_log(
                "manual_polish",
                "agent_completed",
                {"focus": focus, "rag_sources": [hit.get("source") for hit in polish_hits]},
            ),
        ],
    }
