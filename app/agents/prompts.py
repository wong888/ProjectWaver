from __future__ import annotations


JD_PARSER_SYSTEM = "你是岗位 JD 解析 Agent，负责把岗位要求拆成可验证能力模型。"

ARCHITECTURE_SYSTEM = "你是后端架构共创 Agent，只能设计本地可运行、可解释、贴近真实互联网后端的项目。"

TECHNICAL_DOC_BUILDER_SYSTEM = "你是项目技术文档 Agent，负责把项目蓝图沉淀为可被 RAG 检索的结构化技术文档。"

RESUME_PACKAGING_SYSTEM = "你是简历工程包装 Agent，负责把架构方案写成真实、克制、可面试追问的简历项目。"

SENIOR_INTERVIEWER_SYSTEM = "你是资深攻防面试官 Agent，必须尖锐找架构、落地和逻辑漏洞。"

ITERATION_REPAIR_SYSTEM = "你是项目迭代修复 Agent，根据攻防报告补强项目设计，但不能扩大到无法真实实现的架构。"

TECHNICAL_DOC_UPDATER_SYSTEM = "你是技术文档更新 Agent，负责把攻防发现和修复结果合并回当前项目技术文档。"

COMPLIANCE_RISK_SYSTEM = "你是合规风控收口 Agent，负责删除夸大、虚假和无法证明的简历表述。"

MANUAL_POLISH_SYSTEM = "你是手动精细化补打磨 Agent，只针对用户指定的单点加厚细节，不重跑全流程。"


def jd_parser_user(jd_text: str, stack: str, rag_context: object) -> str:
    return (
        f"JD:\n{jd_text}\n\n候选人技术栈:\n{stack}\n\nRAG参考:\n{rag_context}\n"
        "只输出JSON字段: target_role, seniority, required_capabilities, business_scenes, risk_notes。"
    )


def architecture_user(capabilities: object, constraints: object, forbidden: str, rag_context: str) -> str:
    return (
        f"岗位能力:{capabilities}\n人工约束:{constraints}\n禁止方向:{forbidden}\nRAG参考:{rag_context}\n"
        "只输出JSON字段: project_name, business_problem, architecture, modules, engineering_highlights, explicitly_avoided, matched_capabilities。"
    )


def technical_doc_builder_user(jd_profile: object, constraints: object, blueprint: object) -> str:
    return (
        f"岗位画像:{jd_profile}\n人工约束:{constraints}\n项目蓝图:{blueprint}\n"
        "生成当前项目的全局技术文档。要求: 结构化、克制、可本地验证、便于面试官按章节 RAG 检索。"
        "只输出JSON字段: version, project_overview, architecture_design, core_tech_stack, "
        "design_decisions, failure_handling, observability, interview_defense, known_risks, evidence_needed, change_log。"
    )


def resume_packaging_user(blueprint: object, jd_profile: object) -> str:
    return f"项目蓝图:{blueprint}\n岗位画像:{jd_profile}\n只输出JSON字段: resume_project_paragraph, architecture_summary, interview_talking_points, metrics_claims。"


def senior_interviewer_user(round_no: int, blueprint: object, resume_package: object, decision: object, technical_doc_context: str) -> str:
    return (
        f"当前轮次:{round_no}\n项目:{blueprint}\n简历包装:{resume_package}\n人工攻防决策:{decision}\n"
        f"技术文档RAG命中片段:\n{technical_doc_context}\n"
        "必须优先基于技术文档片段追问，指出文档设计纰漏、缺失证据或待改进点。"
        "只输出JSON字段: round, severity, doc_based_questions, doc_gaps, architecture_vulnerabilities, "
        "landing_vulnerabilities, logic_vulnerabilities, recommended_doc_updates, questions。"
    )


def technical_doc_updater_user(current_doc: object, attack_report: object, repair_result: object, constraints: object) -> str:
    return (
        f"当前技术文档:{current_doc}\n攻防报告:{attack_report}\n修复结果:{repair_result}\n人工约束:{constraints}\n"
        "请把已确认的修复点合并到对应技术文档章节，把未解决问题写入 known_risks/evidence_needed，"
        "并在 change_log 记录本轮变更。不得编造不可证明的线上规模，不得扩大到人工约束否决的方向。"
        "只输出JSON字段: version, project_overview, architecture_design, core_tech_stack, "
        "design_decisions, failure_handling, observability, interview_defense, known_risks, evidence_needed, change_log。"
    )
