from __future__ import annotations

import json
from typing import Any, Dict

import streamlit as st

from app.agents.graph import run_full_pipeline, run_manual_polish
from app.services.json_memory import list_sessions, load_session
from app.services.vector_store import vector_store


st.set_page_config(page_title="Multi-Agent 简历项目闭环打磨", page_icon="🧠", layout="wide")


STYLE = """
<style>
.block-container {padding-top: 1.8rem; max-width: 1280px;}
.hero {border-radius: 24px; padding: 28px 32px; background: linear-gradient(135deg,#0f172a,#164e63); color: white;}
.hero h1 {font-size: 34px; margin-bottom: 8px;}
.hero p {font-size: 16px; opacity: .92;}
.metric-card {border:1px solid #e5e7eb; border-radius:18px; padding:18px; background:#ffffff;}
.risk {border-left: 5px solid #f97316; padding: 12px 16px; background:#fff7ed; border-radius: 12px;}
.ok {border-left: 5px solid #22c55e; padding: 12px 16px; background:#f0fdf4; border-radius: 12px;}
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


def show_json(title: str, data: Dict[str, Any]) -> None:
    with st.expander(title, expanded=False):
        st.json(data)


def render_result(state: Dict[str, Any]) -> None:
    final_output = state.get("final_output", {})
    resume_package = final_output.get("resume_package", state.get("resume_package", {}))
    blueprint = final_output.get("project_blueprint", state.get("project_blueprint", {}))

    st.subheader("最终简历项目段落")
    st.success(resume_package.get("resume_project_paragraph", "暂无输出"))

    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.subheader("简易架构说明")
        for item in resume_package.get("architecture_summary", []):
            st.markdown(f"- {item}")
        st.subheader("工程亮点")
        for item in blueprint.get("engineering_highlights", []):
            st.markdown(f"- {item}")
    with col2:
        st.subheader("面试应答话术")
        for item in resume_package.get("interview_talking_points", []):
            st.markdown(f"- {item}")

    st.subheader("漏洞优化溯源日志")
    for item in final_output.get("iteration_history", state.get("iteration_history", [])):
        st.markdown(f"**第 {item.get('round')} 轮修复**")
        st.info(item.get("resume_delta", ""))
        for fixed in item.get("fixed_points", []):
            st.markdown(f"- {fixed}")

    compliance = final_output.get("compliance_report", state.get("compliance_report", {}))
    st.markdown("<div class='ok'><b>合规风控收口：</b>{}</div>".format(compliance.get("compliance_status", "unknown")), unsafe_allow_html=True)

    st.subheader("RAG 命中文档")
    for item in state.get("rag_context", []):
        st.markdown(
            f"- **{item.get('title')}** | source=`{item.get('source', 'unknown')}` | "
            f"score=`{item.get('score', 0)}` | mode=`{item.get('retrieval_mode', 'unknown')}`"
        )
        st.caption(item.get("content", "")[:220])
    show_json("完整结构化 JSON 输出", final_output or state)


def render_interview(state: Dict[str, Any]) -> None:
    st.subheader("八股 + 业务全真模拟面试验收")
    attack = state.get("attack_report", {})
    questions = attack.get("questions", [])
    default_questions = [
        "LangGraph 在这个项目里解决了什么问题？",
        "Milvus 不可用时你的降级策略是什么？",
        "如何证明简历项目不是虚构线上经历？",
        "如果 LLM 输出非法 JSON，系统如何兜底？",
    ]
    for index, question in enumerate(questions or default_questions, start=1):
        answer = st.text_area(f"Q{index}: {question}", key=f"mock_answer_{index}")
        if answer:
            st.caption("验收建议：回答中需要包含场景、方案、权衡、验证证据和失败预案。")


st.markdown(
    """
<div class="hero">
  <h1>Multi-Agent程序员简历项目闭环打磨系统</h1>
  <p>JD 解析、架构共创、简历包装、攻防面试、三轮迭代修复、合规收口，一页完成可演示闭环。</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("本地会话记忆")
    sessions = list_sessions()
    if sessions:
        selected = st.selectbox("加载历史版本", ["不加载"] + [f"{s['session_id']} | {s['title']}" for s in sessions])
        if selected != "不加载" and st.button("加载会话"):
            st.session_state["state"] = load_session(selected.split(" | ")[0])
            st.rerun()
    st.caption("所有版本保存在 data/memory/*.json，可用于复盘迭代链路。")

tab_run, tab_manual, tab_interview, tab_rag = st.tabs(["主流程闭环", "手动精细化补打磨", "模拟面试验收", "RAG健康检查"])

with tab_run:
    st.subheader("开局 Human-in-the-Loop 人工约束卡点")
    with st.form("pipeline_form"):
        jd_text = st.text_area("岗位 JD", height=180, placeholder="粘贴目标岗位 JD，系统会自动抽取能力要求。")
        personal_stack = st.text_area("个人技术栈", height=120, placeholder="例如：Python / FastAPI / Redis / MySQL / Docker / LangGraph / Milvus")
        target_level = st.selectbox("目标职级", ["初级", "中级", "高级", "资深"], index=1)
        project_name = st.text_input("可选：指定项目名称", value="Multi-Agent程序员简历项目闭环打磨系统")
        highlight_focus = st.text_input("指定要强化的工程亮点", value="LangGraph 多Agent编排、RAG 降幻觉、Human-in-the-Loop、故障降级、日志追踪")
        forbidden_directions = st.text_input("否决不合理架构方向", value="不写大厂亿级流量，不伪造真实公司线上系统")
        st.subheader("攻防漏洞产出 Human-in-the-Loop 卡点")
        attack_decision = st.radio("面试官产出漏洞后是否允许自动三轮修复？", ["允许自动修复", "只保守修复，不扩大架构复杂度"], horizontal=True)
        attack_note = st.text_input("人工补充攻防关注点", value="重点追问部署、性能、线上故障、团队协作")
        submitted = st.form_submit_button("启动六Agent闭环打磨", type="primary")

    if submitted:
        if not jd_text.strip() or not personal_stack.strip():
            st.error("请填写岗位 JD 和个人技术栈。")
        else:
            payload = {
                "jd_text": jd_text,
                "personal_stack": personal_stack,
                "target_level": target_level,
                "human_constraints": {
                    "project_name": project_name,
                    "highlight_focus": highlight_focus,
                    "forbidden_directions": forbidden_directions,
                },
                "attack_human_decision": {"decision": attack_decision, "note": attack_note},
            }
            with st.spinner("六个 Agent 正在协同打磨，最多三轮自动攻防修复..."):
                st.session_state["state"] = run_full_pipeline(payload)
            st.success("闭环打磨完成，已写入本地 JSON 记忆。")

    if "state" in st.session_state:
        render_result(st.session_state["state"])

with tab_manual:
    st.subheader("不用重跑全流程的单点深度补打磨")
    state = st.session_state.get("state")
    if not state:
        st.warning("请先运行主流程或从侧边栏加载一个历史会话。")
    else:
        focus = st.selectbox("选择补强方向", ["架构", "性能", "线上故障", "部署运维", "团队协作"])
        manual_input = st.text_area("补充你的真实经历或想强化的问题", height=120)
        if st.button("执行单点精细化补打磨", type="primary"):
            with st.spinner("正在基于历史状态单点加厚，不重跑主流程..."):
                st.session_state["state"] = run_manual_polish(state, focus, manual_input)
            st.success("补打磨完成，已保存新版本。")
        if st.session_state.get("state", {}).get("manual_polish_output"):
            st.json(st.session_state["state"]["manual_polish_output"])

with tab_interview:
    if "state" not in st.session_state:
        st.warning("请先运行主流程或加载历史会话。")
    else:
        render_interview(st.session_state["state"])

with tab_rag:
    st.subheader("真实 RAG 运行状态")
    health = vector_store.health()
    col1, col2, col3 = st.columns(3)
    col1.metric("Milvus", "可用" if health.get("milvus_available") else "不可用")
    col2.metric("文档 Chunk 数", health.get("doc_count", 0))
    col3.metric("向量维度", health.get("dimension", 0))
    embedding = health.get("embedding", {})
    if isinstance(embedding, dict):
        if embedding.get("mode") == "remote":
            st.success(f"Embedding 正在使用真实远程模型：{embedding.get('model')}")
        else:
            st.warning(f"Embedding 当前为 `{embedding.get('mode')}`，请检查 EMBEDDING_MODEL/API 是否可用。")
        if embedding.get("last_error"):
            st.code(str(embedding.get("last_error")))
    st.json(health)

    query = st.text_input("测试 RAG 检索", value="LangGraph Milvus RAG 后端项目如何降低幻觉")
    if st.button("检索知识库"):
        hits = vector_store.search(query, limit=5)
        for hit in hits:
            st.markdown(
                f"**{hit.get('title')}** | source=`{hit.get('source')}` | "
                f"score=`{hit.get('score')}` | mode=`{hit.get('retrieval_mode')}`"
            )
            st.write(hit.get("content"))
