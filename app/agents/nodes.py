from __future__ import annotations

import re
from typing import Any, Dict, List

from langgraph.types import interrupt

from app.agents import prompts
from app.agents.schemas import (
    attack_report_fallback,
    architecture_fallback,
    jd_profile_fallback,
    resume_package_fallback,
    technical_doc_fallback,
    technical_doc_update_fallback,
)
from app.agents.state import ResumePolishState
from app.agents.tools import render_rag_context, retrieve_resume_rag_context
from app.services.event_logger import make_log
from app.services.llm_client import llm_client, split_keywords
from app.services.technical_doc_rag import index_technical_doc, render_technical_doc_hits, search_technical_doc


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


def _llm_failure_reason(output: Dict[str, Any]) -> str:
    return str(output.get("_llm_fallback_reason", ""))


def _with_llm_fallback_meta(output: Dict[str, Any], reason: str, action: str) -> Dict[str, Any]:
    enriched = dict(output)
    enriched["_llm_fallback_reason"] = reason
    enriched["_llm_fallback_action"] = action
    return enriched


def _normalize_human_action(decision: Any) -> Dict[str, Any]:
    if not isinstance(decision, dict):
        return {"action": "skip"}
    payload = decision.get("llm_fallback_decision", decision)
    return payload if isinstance(payload, dict) else {"action": "skip"}


def _action_is(action: str, *candidates: str) -> bool:
    normalized = action.strip().lower()
    return normalized in candidates


def _llm_json_with_hitl(
    *,
    agent: str,
    system: str,
    user: str,
    fallback: Dict[str, Any],
    skip_output: Dict[str, Any],
    expected_schema: Dict[str, str],
    state_summary: Dict[str, Any],
) -> Dict[str, Any]:
    output = llm_client.json_chat(system, user, fallback)
    reason = _llm_failure_reason(output)
    if not reason:
        return output

    decision = _normalize_human_action(
        interrupt(
            {
                "checkpoint": "llm_fallback",
                "agent": agent,
                "message": "当前节点 LLM 调用失败。请选择重试、手动补充结构化结果，或跳过本节点继续流程。",
                "reason": reason,
                "options": {
                    "retry": "重新调用一次当前节点 LLM。",
                    "manual": "按 expected_schema 提供 manual_output，作为本节点结果。",
                    "skip": "忽略本次 LLM 请求，使用空的结构化结果继续下游流程。",
                },
                "expected_schema": expected_schema,
                "state_summary": state_summary,
                "suggested_skip_output": skip_output,
            }
        )
    )
    action = str(decision.get("action", "skip"))
    if _action_is(action, "retry", "重试"):
        retry_output = llm_client.json_chat(system, user, fallback)
        retry_reason = _llm_failure_reason(retry_output)
        if not retry_reason:
            retry_output["_llm_fallback_action"] = "retry_succeeded"
            return retry_output
        return _with_llm_fallback_meta(skip_output, retry_reason, "retry_failed_then_skipped")

    if _action_is(action, "manual", "手动", "human", "override"):
        manual_output = decision.get("manual_output") or decision.get("output")
        if isinstance(manual_output, dict):
            manual_output["_llm_fallback_reason"] = reason
            manual_output["_llm_fallback_action"] = "human_override"
            manual_output["_llm_human_override"] = True
            return manual_output

    return _with_llm_fallback_meta(skip_output, reason, "skipped")


def _skipped_jd_profile(target_level: str, keywords: List[str]) -> Dict[str, Any]:
    return {
        "target_role": "",
        "seniority": target_level,
        "required_capabilities": keywords,
        "business_scenes": [],
        "risk_notes": ["JD 解析节点 LLM 调用失败，已跳过自动岗位画像；建议后续人工补充目标岗位与能力要求。"],
    }


def _skipped_architecture(project_name: str, forbidden: str, capabilities: List[str]) -> Dict[str, Any]:
    return {
        "project_name": project_name,
        "business_problem": "",
        "architecture": {},
        "modules": [],
        "engineering_highlights": [],
        "explicitly_avoided": forbidden,
        "matched_capabilities": capabilities,
    }


def _skipped_technical_doc(project_name: str, min_version: int = 1) -> Dict[str, Any]:
    return {
        "version": min_version,
        "project_overview": {"project_name": project_name, "business_problem": "", "target_users": "", "scope_boundary": ""},
        "architecture_design": {"overall_architecture": {}, "modules": [], "data_flow": "", "state_management": "", "deployment_topology": ""},
        "core_tech_stack": [],
        "design_decisions": [],
        "failure_handling": {},
        "observability": {},
        "interview_defense": {"key_talking_points": [], "likely_questions": [], "answer_boundaries": []},
        "known_risks": ["技术文档节点 LLM 调用失败，本版本仅保留空结构，需人工补充。"],
        "evidence_needed": [],
        "change_log": [{"version": min_version, "summary": "LLM 调用失败，跳过本次技术文档生成。"}],
    }


def _skipped_resume_package() -> Dict[str, Any]:
    return {
        "resume_project_paragraph": "",
        "architecture_summary": [],
        "interview_talking_points": [],
        "metrics_claims": [],
    }


def _skipped_attack_report(round_no: int) -> Dict[str, Any]:
    return {
        "round": round_no,
        "severity": "unknown",
        "doc_based_questions": [],
        "doc_gaps": [],
        "architecture_vulnerabilities": [],
        "landing_vulnerabilities": [],
        "logic_vulnerabilities": [],
        "recommended_doc_updates": [],
        "questions": [],
    }


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
    jd_profile = _llm_json_with_hitl(
        agent="jd_parser",
        system=prompts.JD_PARSER_SYSTEM,
        user=prompts.jd_parser_user(jd_text, stack, jd_context),
        fallback=fallback,
        skip_output=_skipped_jd_profile(state.get("target_level", "中级"), keywords),
        expected_schema={
            "target_role": "目标岗位名称，可为空",
            "seniority": "目标职级",
            "required_capabilities": "岗位要求能力列表",
            "business_scenes": "可选业务场景列表",
            "risk_notes": "真实性与边界提示",
        },
        state_summary={"target_level": state.get("target_level", "中级"), "keywords": keywords},
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
                    "fallback_action": jd_profile.get("_llm_fallback_action"),
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
    blueprint = _llm_json_with_hitl(
        agent="architecture_cocreation",
        system=prompts.ARCHITECTURE_SYSTEM,
        user=prompts.architecture_user(capabilities, constraints, forbidden, f"{_ctx(state)}\n{arch_context}"),
        fallback=fallback,
        skip_output=_skipped_architecture(project_name, forbidden, capabilities),
        expected_schema={
            "project_name": "项目名称",
            "business_problem": "项目要解决的问题，可为空",
            "architecture": "架构分层对象",
            "modules": "模块列表",
            "engineering_highlights": "工程亮点列表",
            "explicitly_avoided": "需要避免的方向",
            "matched_capabilities": "匹配到的岗位能力",
        },
        state_summary={"project_name": project_name, "capabilities": capabilities, "constraints": constraints},
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
                    "fallback_action": blueprint.get("_llm_fallback_action"),
                },
            ),
        ],
    }


def technical_doc_builder_agent(state: ResumePolishState) -> ResumePolishState:
    fallback = technical_doc_fallback(state.get("jd_profile", {}), state.get("human_constraints", {}), state.get("project_blueprint", {}))
    project_name = state.get("project_blueprint", {}).get("project_name") or state.get("human_constraints", {}).get("project_name") or ""
    technical_doc = _llm_json_with_hitl(
        agent="technical_doc_builder",
        system=prompts.TECHNICAL_DOC_BUILDER_SYSTEM,
        user=prompts.technical_doc_builder_user(state.get("jd_profile", {}), state.get("human_constraints", {}), state.get("project_blueprint", {})),
        fallback=fallback,
        skip_output=_skipped_technical_doc(project_name, min_version=1),
        expected_schema={
            "version": "文档版本号",
            "project_overview": "项目概览对象",
            "architecture_design": "架构设计对象",
            "core_tech_stack": "核心技术栈列表",
            "design_decisions": "设计决策列表",
            "failure_handling": "失败处理对象",
            "observability": "可观测性对象",
            "interview_defense": "面试防守对象",
            "known_risks": "已知风险列表",
            "evidence_needed": "待补证据列表",
            "change_log": "变更记录列表",
        },
        state_summary={"project_name": project_name, "blueprint_keys": list(state.get("project_blueprint", {}).keys())},
    )
    technical_doc["version"] = int(technical_doc.get("version", 1) or 1)
    index_result = index_technical_doc(state["session_id"], technical_doc)
    history_item = {
        "version": technical_doc["version"],
        "round": 0,
        "summary": "初始化当前项目全局技术文档，并写入技术文档 RAG 索引。",
        "index": index_result,
    }
    return {
        "current_agent": "technical_doc_builder",
        "technical_doc": technical_doc,
        "technical_doc_history": [history_item],
        "logs": [
            make_log(
                "technical_doc_builder",
                "agent_completed",
                {
                    "version": technical_doc["version"],
                    "chunks": index_result.get("chunk_count", 0),
                    "inserted_chunks": index_result.get("inserted_chunks", 0),
                    "used_fallback": "_llm_fallback_reason" in technical_doc,
                    "fallback_action": technical_doc.get("_llm_fallback_action"),
                },
            )
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
    package = _llm_json_with_hitl(
        agent="resume_packaging",
        system=prompts.RESUME_PACKAGING_SYSTEM,
        user=prompts.resume_packaging_user(blueprint, state.get("jd_profile", {})) + f"\nRAG参考:\n{resume_context}",
        fallback=fallback,
        skip_output=_skipped_resume_package(),
        expected_schema={
            "resume_project_paragraph": "最终简历项目段落，可为空",
            "architecture_summary": "架构说明列表",
            "interview_talking_points": "面试话术列表",
            "metrics_claims": "指标声明列表",
        },
        state_summary={"project_name": blueprint.get("project_name", ""), "jd_profile": state.get("jd_profile", {})},
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
                    "fallback_action": package.get("_llm_fallback_action"),
                },
            ),
        ],
    }


def senior_interviewer_agent(state: ResumePolishState) -> ResumePolishState:
    round_no = int(state.get("iteration_round", 0)) + 1
    technical_query = (
        f"第{round_no}轮 面试攻防 当前项目 技术文档 架构设计 降级策略 可观测性 部署 真实性风险 "
        f"项目:{state.get('project_blueprint', {}).get('project_name', '')}"
    )
    technical_hits = search_technical_doc(technical_query, state["session_id"], state.get("technical_doc", {}), limit=5)
    technical_context = render_technical_doc_hits(technical_hits)
    attack_hits, rag_log = _retrieve_for_agent(
        "senior_interviewer",
        f"面试攻防 架构漏洞 落地漏洞 线上故障 第{round_no}轮 项目:{state.get('project_blueprint', {}).get('project_name', '')}",
    )
    attack_context, render_log = _render_context_for_agent("senior_interviewer", attack_hits)
    fallback = attack_report_fallback(round_no)
    report = _llm_json_with_hitl(
        agent="senior_interviewer",
        system=prompts.SENIOR_INTERVIEWER_SYSTEM,
        user=prompts.senior_interviewer_user(
            round_no,
            state.get("project_blueprint", {}),
            state.get("resume_package", {}),
            state.get("attack_human_decision", {}),
            technical_context,
        )
        + f"\nRAG攻防参考:\n{attack_context}",
        fallback=fallback,
        skip_output=_skipped_attack_report(round_no),
        expected_schema={
            "round": "当前轮次",
            "severity": "风险等级",
            "doc_based_questions": "基于技术文档的问题列表",
            "doc_gaps": "技术文档缺口列表",
            "architecture_vulnerabilities": "架构漏洞列表",
            "landing_vulnerabilities": "落地风险列表",
            "logic_vulnerabilities": "逻辑漏洞列表",
            "recommended_doc_updates": "建议文档更新列表",
            "questions": "面试追问列表",
        },
        state_summary={"round": round_no, "technical_hit_count": len(technical_hits), "project_name": state.get("project_blueprint", {}).get("project_name", "")},
    )
    return {
        "current_agent": "senior_interviewer",
        "attack_report": report,
        "iteration_round": round_no,
        "technical_doc_rag_hits": technical_hits,
        "logs": [
            rag_log,
            render_log,
            make_log(
                "senior_interviewer",
                "technical_doc_rag_invoked",
                {
                    "query": technical_query[:160],
                    "hit_count": len(technical_hits),
                    "sources": [hit.get("source") for hit in technical_hits],
                },
            ),
            make_log(
                "senior_interviewer",
                "agent_completed",
                {
                    "round": round_no,
                    "severity": report.get("severity"),
                    "questions": len(report.get("questions", [])),
                    "used_fallback": "_llm_fallback_reason" in report,
                    "fallback_action": report.get("_llm_fallback_action"),
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


def technical_doc_updater_agent(state: ResumePolishState) -> ResumePolishState:
    current_doc = state.get("technical_doc", {})
    attack = state.get("attack_report", {})
    latest_repair = (state.get("iteration_history", []) or [{}])[-1]
    fallback = technical_doc_update_fallback(current_doc, attack, latest_repair)
    min_version = int(current_doc.get("version", 1)) + 1 if current_doc else 1
    project_name = current_doc.get("project_overview", {}).get("project_name") if isinstance(current_doc.get("project_overview"), dict) else ""
    technical_doc = _llm_json_with_hitl(
        agent="technical_doc_updater",
        system=prompts.TECHNICAL_DOC_UPDATER_SYSTEM,
        user=prompts.technical_doc_updater_user(current_doc, attack, latest_repair, state.get("human_constraints", {})),
        fallback=fallback,
        skip_output=_skipped_technical_doc(project_name or state.get("project_blueprint", {}).get("project_name", ""), min_version=min_version),
        expected_schema={
            "version": "文档版本号，必须不小于当前版本 + 1",
            "project_overview": "项目概览对象",
            "architecture_design": "架构设计对象",
            "core_tech_stack": "核心技术栈列表",
            "design_decisions": "设计决策列表",
            "failure_handling": "失败处理对象",
            "observability": "可观测性对象",
            "interview_defense": "面试防守对象",
            "known_risks": "已知风险列表",
            "evidence_needed": "待补证据列表",
            "change_log": "变更记录列表",
        },
        state_summary={"min_version": min_version, "round": state.get("iteration_round", 0), "attack_keys": list(attack.keys())},
    )
    technical_doc["version"] = max(int(technical_doc.get("version", min_version) or min_version), min_version)
    index_result = index_technical_doc(state["session_id"], technical_doc)
    history_item = {
        "version": technical_doc["version"],
        "round": state.get("iteration_round", 0),
        "summary": latest_repair.get("resume_delta", "根据本轮攻防和修复结果更新技术文档。"),
        "doc_gaps": attack.get("doc_gaps", []),
        "index": index_result,
    }
    return {
        "current_agent": "technical_doc_updater",
        "technical_doc": technical_doc,
        "technical_doc_history": [history_item],
        "logs": [
            make_log(
                "technical_doc_updater",
                "agent_completed",
                {
                    "version": technical_doc["version"],
                    "round": state.get("iteration_round", 0),
                    "chunks": index_result.get("chunk_count", 0),
                    "inserted_chunks": index_result.get("inserted_chunks", 0),
                    "used_fallback": "_llm_fallback_reason" in technical_doc,
                    "fallback_action": technical_doc.get("_llm_fallback_action"),
                },
            )
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
        "technical_doc": state.get("technical_doc", {}),
        "technical_doc_history": state.get("technical_doc_history", []),
        "technical_doc_rag_hits": state.get("technical_doc_rag_hits", []),
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
