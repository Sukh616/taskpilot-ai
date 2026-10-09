"""
TaskPilot AI - Streamlit Web Dashboard
Modern, responsive AI productivity interface featuring real-time agent execution,
human approval controls, task manager, schedule visualization, and activity logs.
"""

import os
import datetime
import streamlit as st

# Ensure database and agent imports work
from database import (
    init_db,
    db_list_tasks,
    db_get_dashboard_stats,
    db_update_task,
    db_delete_task,
    db_create_task,
    db_clear_all,
    db_load_sample_scenario
)
from tools import (
    tool_list_tasks,
    tool_prioritize_tasks,
    tool_generate_schedule,
    tool_generate_study_plan
)
from agent import AgentEngine

# ---------------------------------------------------------------------------
# Streamlit Page Configuration & Custom CSS System
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TaskPilot AI | Autonomous Personal Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern Dark Glassmorphism CSS Design System

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&family=DM+Sans:wght@400;500;600;700&display=swap');

    :root {
        --peach: #F8DFD7;
        --peach-strong: #E9A998;
        --blush: #F7E8EB;
        --ivory: #FFF9F5;
        --sage: #E9F0E6;
        --ink: #533B39;
        --muted: #987E79;
        --line: #F0DCD5;
        --white: #FFFFFF;
    }

    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family: 'Nunito', 'DM Sans', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(ellipse at 8% 0%, #FCE9E1 0%, transparent 36%),
            radial-gradient(ellipse at 95% 12%, #F8E9EF 0%, transparent 30%),
            var(--ivory);
        color: var(--ink);
    }

    [data-testid="stHeader"] {
        background: rgba(255, 249, 245, 0.88);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFF1EB 0%, #FFF9F5 100%);
        border-right: 1px solid var(--line);
    }

    [data-testid="stSidebar"] * {
        color: var(--ink);
    }

    h1, h2, h3, h4 {
        color: var(--ink) !important;
        font-family: 'Nunito', sans-serif !important;
        letter-spacing: -0.025em;
    }

    p, label, [data-testid="stCaptionContainer"] {
        color: var(--muted);
    }

    hr {
        border-color: var(--line);
    }

    .glass-card {
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid #F0DDD6;
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 12px;
        box-shadow: 0 6px 24px rgba(157, 103, 88, 0.07);
        transition: transform 180ms ease, box-shadow 180ms ease,
                    border-color 180ms ease;
    }

    .glass-card:hover {
        transform: translateY(-2px);
        border-color: #E9B8AA;
        box-shadow: 0 10px 28px rgba(157, 103, 88, 0.12);
    }

    .badge-demo, .badge-llm {
        padding: 6px 12px;
        border-radius: 999px;
        font-weight: 800;
        font-size: 0.78rem;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    .badge-demo {
        background: #FFF0D8;
        color: #94652B;
        border: 1px solid #F0D6A9;
    }

    .badge-llm {
        background: #E5F3E7;
        color: #39754A;
        border: 1px solid #C5E2CA;
    }

    .metric-container {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: center;
        min-height: 94px;
        background: rgba(255, 255, 255, 0.92);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 16px;
        text-align: left;
        box-shadow: 0 4px 18px rgba(157, 103, 88, 0.05);
        transition: transform 180ms ease, box-shadow 180ms ease;
    }

    .metric-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(157, 103, 88, 0.10);
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #B96E60;
        line-height: 1.2;
    }

    .metric-label {
        font-size: 0.72rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 800;
        margin-top: 5px;
    }

    .priority-urgent, .priority-high, .priority-medium, .priority-low {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 800;
    }

    .priority-urgent {
        background: #FCE1DF;
        color: #A43F3A;
        border: 1px solid #F3C0BC;
    }

    .priority-high {
        background: #FFF0D8;
        color: #94652B;
        border: 1px solid #F0D6A9;
    }

    .priority-medium {
        background: #F0E7FA;
        color: #7954A3;
        border: 1px solid #DDCBF0;
    }

    .priority-low {
        background: #E7F1E5;
        color: #4E7749;
        border: 1px solid #CFE2CB;
    }

    .timeline-item {
        border-left: 3px solid #E9B2A4;
        padding: 4px 0 8px 16px;
        margin-bottom: 16px;
        position: relative;
    }

    .timeline-phase {
        font-size: 0.75rem;
        font-weight: 800;
        color: #B96E60;
        letter-spacing: 0.05em;
    }

    .timeline-time {
        font-size: 0.72rem;
        color: var(--muted);
        float: right;
    }

    .timeline-desc {
        font-size: 0.9rem;
        color: var(--ink);
        margin-top: 3px;
    }

    div.stButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        border-radius: 12px;
        border: 1px solid #EBCBC1;
        background: #FFFFFF;
        color: #77514A;
        font-weight: 800;
        transition: transform 160ms ease, background 160ms ease,
                    box-shadow 160ms ease;
    }

    div.stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        background: #FCE9E2;
        border-color: #E5AA9A;
        color: #68423C;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(157, 103, 88, 0.10);
    }

    div.stButton > button:focus-visible {
        outline: 3px solid #DDA99C;
        outline-offset: 2px;
    }

    [data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 12px 16px;
    }

    [data-testid="stChatInput"] {
        border-radius: 16px;
    }

    input, textarea {
        border-radius: 10px !important;
    }

    [data-baseweb="tab-list"] {
        gap: 6px;
    }

    [data-baseweb="tab"] {
        border-radius: 12px 12px 0 0;
    }

    [data-baseweb="tab-highlight"] {
        background-color: #D99584;
    }

    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 14px;
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            transition-duration: 0.01ms !important;
            scroll-behavior: auto !important;
        }
    }

    @media (max-width: 768px) {
        .metric-container {
            padding: 12px;
            min-height: 78px;
        }

        .metric-value {
            font-size: 1.45rem;
        }

        .glass-card {
            padding: 15px;
            border-radius: 16px;
        }
    }

    /* RAINBOW UI OVERRIDES — presentation only */
    :root {
        --rb-pink: #f8cdeb;
        --rb-lavender: #dcd2ff;
        --rb-blue: #c8e7ff;
        --rb-mint: #c8f0dd;
        --rb-peach: #ffd8c2;
        --rb-butter: #fff0b8;
        --rb-ink: #51465f;
        --rb-muted: #81758d;
        --rb-line: #eee3f2;
        --rb-white: #fffaff;
    }

    .stApp {
        background:
            radial-gradient(ellipse at 5% 4%, #f8cdeb66, transparent 28%),
            radial-gradient(ellipse at 94% 8%, #c8e7ff70, transparent 28%),
            radial-gradient(ellipse at 80% 92%, #c8f0dd55, transparent 30%),
            linear-gradient(145deg, #fffaff 0%, #fff7f5 50%, #f8f5ff 100%);
        color: var(--rb-ink);
    }

    [data-testid="stHeader"] {
        background: rgba(255, 250, 255, 0.8);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f4eaff 0%, #fff0f6 55%, #edf8ff 100%);
        border-right: 1px solid var(--rb-line);
    }

    [data-testid="stSidebar"] * {
        color: var(--rb-ink);
    }

    h1, h2, h3, h4, p, label,
    [data-testid="stMarkdownContainer"] {
        color: var(--rb-ink);
    }

    .glass-card,
    .metric-container {
        background: linear-gradient(145deg, #ffffff 0%, #fff9fe 100%);
        border: 1px solid rgba(222, 205, 237, 0.9);
        border-radius: 20px;
        box-shadow:
            0 5px 0 rgba(221, 205, 237, 0.45),
            0 12px 28px rgba(133, 103, 158, 0.10);
        transition: transform 220ms ease, box-shadow 220ms ease;
    }

    .glass-card:hover,
    .metric-container:hover {
        transform: translateY(-3px);
        box-shadow:
            0 7px 0 rgba(221, 205, 237, 0.42),
            0 17px 30px rgba(133, 103, 158, 0.15);
    }

    .metric-container {
        min-height: 105px;
        padding: 16px 10px;
        text-align: center;
    }

    .metric-value {
        color: #7863a9 !important;
        font-weight: 800;
    }

    .metric-label {
        color: var(--rb-muted) !important;
        font-weight: 600;
    }

    .badge-demo, .badge-llm {
        display: inline-block;
        border-radius: 999px;
        padding: 6px 12px;
        font-weight: 800;
        border: 1px solid #e5d8f4;
        background: #f3eaff;
        color: #665184;
    }

    .badge-llm {
        background: #def7e9;
        border-color: #bce8d0;
        color: #286c50;
    }

    .badge-demo {
        background: #fff1c8;
        border-color: #f2df9d;
        color: #7b6020;
    }

    .priority-high, .priority-medium, .priority-low {
        display: inline-block;
        border-radius: 999px;
        padding: 3px 9px;
        font-size: 0.75rem;
        font-weight: 800;
    }

    .priority-high {
        background: #ffe0e5;
        color: #9b4058;
    }

    .priority-medium {
        background: #fff0c7;
        color: #80601c;
    }

    .priority-low {
        background: #dff5e8;
        color: #356d51;
    }

    /* Restyle existing inline dark cards without changing their Python logic. */
    div[style*="rgba(30,41,59"] {
        background: linear-gradient(135deg, #f2eaff, #fff0f7) !important;
        border-color: #d9c9f0 !important;
        border-radius: 16px !important;
        box-shadow: 0 5px 0 #e8dcf4 !important;
    }

    div[style*="rgba(30,41,59"] strong,
    div[style*="rgba(30,41,59"] div[style*="color: #94a3b8"] {
        color: #51465f !important;
    }

    div[style*="background:rgba(255,255,255,0.05)"] {
        background: #f0eaff !important;
        color: #665184 !important;
    }

    div[style*="rgba(99, 102, 241, 0.1)"] {
        background: linear-gradient(135deg, #e7e0ff, #e1f3ff) !important;
        border-left-color: #b7a4f3 !important;
        border-radius: 15px !important;
        box-shadow: 0 4px 0 #e3d9f4 !important;
    }

    div[style*="rgba(99, 102, 241, 0.1)"] div {
        color: #51465f !important;
    }

    /* Inputs and buttons */
    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input,
    .stDateInput input,
    .stSelectbox [data-baseweb="select"] > div {
        background: #fffaff !important;
        color: var(--rb-ink) !important;
        border-color: #e4d6f0 !important;
        border-radius: 13px !important;
    }

    .stButton button,
    .stFormSubmitButton button {
        border: 1px solid #dfd0f1;
        border-radius: 14px;
        background: linear-gradient(135deg, #e5d9ff, #f8d9ef);
        color: #514465;
        font-weight: 750;
        box-shadow: 0 4px 0 #dfd2ee;
        transition: transform 160ms ease, box-shadow 160ms ease;
    }

    .stButton button:hover,
    .stFormSubmitButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 0 #dfd2ee;
        border-color: #cbb8e8;
        color: #40344f;
    }

    .stButton button:active,
    .stFormSubmitButton button:active {
        transform: translateY(1px);
        box-shadow: 0 2px 0 #dfd2ee;
    }

    [data-testid="stTabs"] button {
        border-radius: 12px 12px 0 0;
        transition: background 180ms ease;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        background: #f0e8ff;
        color: #665184;
    }

    [data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid var(--rb-line);
        border-radius: 18px;
        box-shadow: 0 4px 0 rgba(221, 205, 237, 0.35);
        animation: rb-pop-in 350ms ease both;
    }

    .timeline-item {
        border-left-color: #cbb8f2 !important;
    }

    .timeline-phase {
        color: #8068b0 !important;
    }

    /* Gentle motion only — no JavaScript and no agent interaction changes. */
    @keyframes rb-pop-in {
        from { opacity: 0; transform: translateY(7px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    @keyframes rb-float {
        0%, 100% { transform: translateY(0); }
        50%      { transform: translateY(-3px); }
    }

    .metric-container {
        animation: rb-float 5s ease-in-out infinite;
    }

    .metric-container:nth-child(2n) {
        animation-delay: -1.7s;
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation: none !important;
            transition: none !important;
            scroll-behavior: auto !important;
        }
    }

    @media (max-width: 900px) {
        .metric-container {
            padding: 12px 6px;
            min-height: 80px;
        }

        .metric-value {
            font-size: 1.35rem;
        }
    }

</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State & Agent Initialization
# ---------------------------------------------------------------------------
if "db_path" not in st.session_state:
    st.session_state.db_path = "taskpilot.db"

init_db(st.session_state.db_path)

if "agent" not in st.session_state:
    st.session_state.agent = AgentEngine(db_path=st.session_state.db_path)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------------------------------------------------------------------
# Header Component
# ---------------------------------------------------------------------------
top_col1, top_col2 = st.columns([3, 1])

with top_col1:
    st.title("⚡ TaskPilot AI")
    st.caption("Autonomous Agentic Task Manager | Multi-Step Reasoning • Tool Execution • Human Oversight")

with top_col2:
    mode = st.session_state.agent.mode
    if mode == "LLM":
        st.markdown('<div style="text-align: right;"><span class="badge-llm">🟢 LLM ACTIVE</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="text-align: right;"><span class="badge-demo">🟡 DEMO MODE (Deterministic)</span></div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.75rem; color:#94a3b8; text-align:right; margin-top:4px;">No API Key detected → Fallback active</div>' if mode == "DEMO" else '<div style="font-size:0.75rem; color:#34d399; text-align:right; margin-top:4px;">Connected to LLM API</div>', unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Dashboard Metrics Banner
# ---------------------------------------------------------------------------
stats = db_get_dashboard_stats(st.session_state.db_path)
m1, m2, m3, m4, m5, m6 = st.columns(6)

with m1:
    st.markdown(f'<div class="metric-container"><div class="metric-value">{stats["total"]}</div><div class="metric-label">Total Tasks</div></div>', unsafe_allow_html=True)
with m2:
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:#34d399;">{stats["completed"]}</div><div class="metric-label">Completed</div></div>', unsafe_allow_html=True)
with m3:
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:#fbbf24;">{stats["pending"]}</div><div class="metric-label">Pending</div></div>', unsafe_allow_html=True)
with m4:
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:#f87171;">{stats["high_priority"]}</div><div class="metric-label">High Priority</div></div>', unsafe_allow_html=True)
with m5:
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:#a78bfa;">{stats["upcoming_deadlines"]}</div><div class="metric-label">Upcoming Due</div></div>', unsafe_allow_html=True)
with m6:
    st.markdown(f'<div class="metric-container"><div class="metric-value" style="color:#38bdf8;">{stats["completion_rate"]}%</div><div class="metric-label">Completion</div></div>', unsafe_allow_html=True)

st.write("")

# ---------------------------------------------------------------------------
# Sidebar Controls & API Settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Agent Settings")

    env_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
    user_key = st.text_input("API Key (OpenAI / Gemini)", value=env_key or "", type="password", help="Leave empty to use deterministic Demo Mode.")
    if user_key:
        os.environ["OPENAI_API_KEY"] = user_key
        st.session_state.agent.mode = "LLM"
        st.success("API Key applied. LLM Mode Active.")

    st.markdown("---")
    st.subheader("🛠️ Quick Scenario Injector")
    st.caption("Load realistic test scenarios with explicit confirmation:")

    scenario_choice = st.selectbox("Select Scenario", ["finals_week", "product_launch", "freelance_sprint"], format_func=lambda x: x.replace("_", " ").title())
    if st.button("🚀 Load Selected Scenario"):
        loaded = db_load_sample_scenario(scenario_choice, db_path=st.session_state.db_path)
        st.success(f"Loaded {loaded} sample tasks into SQLite!")
        st.rerun()

    st.markdown("---")
    st.subheader("🧹 Maintenance")
    if st.button("⚠️ Reset All Tasks"):
        db_clear_all(st.session_state.db_path)
        st.session_state.agent.timeline_logs.clear()
        st.session_state.agent.current_plan.clear()
        st.session_state.chat_history.clear()
        st.warning("Database reset complete.")
        st.rerun()

# ---------------------------------------------------------------------------
# Main Layout: Left Column (Chat & Agent Execution) vs Right Column (Hub)
# ---------------------------------------------------------------------------
chat_col, hub_col = st.columns([7, 5])

# ---------------------------------------------------------------------------
# LEFT COLUMN: Interactive Chat & Agent Execution Timeline
# ---------------------------------------------------------------------------
with chat_col:
    st.subheader("💬 Agent Conversation & Execution Workspace")

    # Preset Prompt Chips
    st.write("💡 **Try prompt presets:**")
    chip_col1, chip_col2, chip_col3 = st.columns(3)
    preset_prompt = None

    with chip_col1:
        if st.button("📚 Study & Schedule OS Exam"):
            preset_prompt = "Organize my assignments and prepare a study schedule for Operating Systems"
    with chip_col2:
        if st.button("🚨 Create Urgent Task"):
            preset_prompt = "Create an urgent task to fix authentication timeout bug deadline tomorrow 2 hours"
    with chip_col3:
        if st.button("📊 Prioritize Pending Tasks"):
            preset_prompt = "Prioritize all my pending tasks and show recommendations"

    # User Input Form
    user_prompt = st.chat_input("Ask TaskPilot AI to plan, schedule, or manage your tasks...")
    if preset_prompt:
        user_prompt = preset_prompt

    if user_prompt:
        # Add user message to history
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})

        # Process request through agent
        with st.spinner("Analyzing intent, evaluating constraints, and constructing execution plan..."):
            res = st.session_state.agent.process_user_request(user_prompt)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": res.get("explanation") or res.get("message"),
                "status": res["status"],
                "plan": st.session_state.agent.current_plan
            })

    # Display Chat History & Active Plan Cards
    for idx, msg in enumerate(st.session_state.chat_history):
        if msg["role"] == "user":
            st.chat_message("user").write(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.write(msg["content"])

    # Active Execution & Human Approval Gate Card
    current_plan = st.session_state.agent.current_plan
    if current_plan:
        st.markdown("### 📋 Active Agent Execution Plan")

        for step in current_plan:
            st_id = step["id"]
            st_status = step["status"]
            st_title = step["title"]
            st_tool = step["tool"]
            st_args = step["args"]
            requires_appr = step.get("requires_approval", False)

            card_border = "#6366f1"
            if st_status == "approved": card_border = "#34d399"
            elif st_status == "executed": card_border = "#10b981"
            elif st_status == "rejected": card_border = "#ef4444"
            elif st_status == "pending_approval": card_border = "#f59e0b"

            with st.container():
                st.markdown(
                    f"""
                    <div style="border-left: 4px solid {card_border}; background: rgba(30,41,59,0.5); padding: 12px 16px; border-radius: 8px; margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong style="font-size: 0.95rem; color: #f8fafc;">{st_title}</strong>
                            <span style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: {card_border};">{st_status.replace('_', ' ')}</span>
                        </div>
                        <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 4px;">
                            Tool: <code>{st_tool}</code> | Requires Human Approval: <strong>{requires_appr}</strong>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # HUMAN APPROVAL CONTROLS
                if st_status == "pending_approval":
                    btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 2])

                    with btn_col1:
                        if st.button(f"✅ Approve & Execute", key=f"appr_{st_id}"):
                            st.session_state.agent.approve_step(st_id)
                            st.rerun()

                    with btn_col2:
                        with st.popover(f"✏️ Edit Args"):
                            st.write(f"Edit arguments for step: {st_title}")
                            edited_args = {}
                            for k, v in st_args.items():
                                edited_args[k] = st.text_input(f"{k}", value=str(v), key=f"edit_{st_id}_{k}")
                            if st.button("Save & Update", key=f"save_{st_id}"):
                                st.session_state.agent.edit_step_args(st_id, edited_args)
                                st.success("Arguments updated.")
                                st.rerun()

                    with btn_col3:
                        if st.button(f"❌ Reject Plan", key=f"rej_{st_id}"):
                            st.session_state.agent.reject_step(st_id)
                            st.rerun()

                # Display Execution / Verification Result if available
                if step.get("result"):
                    res_obj = step["result"]
                    if res_obj.get("success"):
                        st.success(f"Execution Output: {res_obj.get('message') or res_obj}")
                    else:
                        st.error(f"Execution Error: {res_obj.get('error') or res_obj}")

    # Agent Audit Timeline
    st.markdown("---")
    st.subheader("⏱️ Real-time Execution Timeline")
    logs = st.session_state.agent.timeline_logs
    if not logs:
        st.caption("No agent timeline logs generated yet. Submit a prompt above.")
    else:
        for log in reversed(logs[-8:]):
            st.markdown(
                f"""
                <div class="timeline-item">
                    <span class="timeline-time">{log["timestamp"]}</span>
                    <div class="timeline-phase">[{log["phase"]}]</div>
                    <div class="timeline-desc">{log["description"]}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

# ---------------------------------------------------------------------------
# RIGHT COLUMN: Task Pilot Hub (Task Manager, Schedule, Logs)
# ---------------------------------------------------------------------------
with hub_col:
    tab1, tab2, tab3 = st.tabs(["📌 Task Manager", "📅 Visual Schedule", "📜 Audit Logs"])

    # TAB 1: Task Manager & Overview
    with tab1:
        st.subheader("Tasks Overview")

        # Filters
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            status_filter = st.selectbox("Status Filter", ["All", "Pending", "Completed", "In Progress"])
        with f_col2:
            priority_filter = st.selectbox("Priority Filter", ["All", "Urgent", "High", "Medium", "Low"])

        search_query = st.text_input("🔍 Search tasks by title or category...", value="")

        # List Tasks
        task_list = db_list_tasks(
            status=status_filter,
            priority=priority_filter,
            search=search_query,
            db_path=st.session_state.db_path
        )

        st.caption(f"Showing {len(task_list)} tasks")

        for t in task_list:
            p_class = f"priority-{t['priority'].lower()}" if t['priority'] else "priority-medium"
            is_done = t["status"] == "Completed"

            with st.container():
                st.markdown(
                    f"""
                    <div class="glass-card">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div>
                                <span style="font-size: 1.05rem; font-weight: 600; text-decoration: {'line-through' if is_done else 'none'}; color: {'#81758d' if is_done else '#51465f'};">
                                    #{t['id']} {t['title']}
                                </span>
                                <div style="margin-top: 6px; display:flex; gap: 8px; align-items:center;">
                                    <span class="{p_class}">{t['priority']}</span>
                                    <span style="font-size:0.75rem; background:#f2eaff; padding:3px 7px; border-radius:6px; color:#51465f;">📁 {t['category']}</span>
                                    <span style="font-size:0.75rem; color:#665b73;">⏳ {t['duration']} hrs</span>
                                    <span style="font-size:0.75rem; color:#665b73;">📅 {t['deadline'] or 'No deadline'}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Inline action buttons
                act_c1, act_c2 = st.columns([3, 1])
                with act_c1:
                    new_status = "Pending" if is_done else "Completed"
                    btn_label = "↩️ Mark Pending" if is_done else "✅ Mark Complete"
                    if st.button(btn_label, key=f"t_toggle_{t['id']}"):
                        db_update_task(t["id"], {"status": new_status}, db_path=st.session_state.db_path)
                        st.rerun()
                with act_c2:
                    if st.button("🗑️", key=f"t_del_{t['id']}", help="Delete Task"):
                        db_delete_task(t["id"], db_path=st.session_state.db_path)
                        st.rerun()

        # Add Manual Task Modal/Expander
        with st.expander("➕ Add Task Manually"):
            with st.form("manual_task_form"):
                m_title = st.text_input("Task Title")
                m_deadline = st.date_input("Deadline", datetime.date.today() + datetime.timedelta(days=1))
                m_duration = st.number_input("Duration (hours)", min_value=0.25, max_value=24.0, value=1.0, step=0.5)
                m_priority = st.selectbox("Priority", ["Low", "Medium", "High", "Urgent"], index=1)
                m_category = st.selectbox("Category", ["General", "Academic", "Work", "Personal", "Study"], index=0)

                if st.form_submit_button("Save Task to Database"):
                    if m_title.strip():
                        db_create_task(
                            title=m_title.strip(),
                            deadline=m_deadline.isoformat(),
                            duration=m_duration,
                            priority=m_priority,
                            category=m_category,
                            db_path=st.session_state.db_path
                        )
                        st.success("Task created manually!")
                        st.rerun()
                    else:
                        st.error("Title cannot be empty.")

    # TAB 2: Visual Schedule
    with tab2:
        st.subheader("📅 Generated Time-Block Schedule")
        hrs_input = st.slider("Available Work Hours Today", min_value=1.0, max_value=12.0, value=8.0, step=0.5)

        if st.button("⚡ Generate / Refresh Schedule"):
            sched_res = tool_generate_schedule(available_hours=hrs_input, db_path=st.session_state.db_path)
            st.session_state.current_schedule = sched_res

        sched_data = st.session_state.get("current_schedule")
        if not sched_data or not sched_data.get("schedule"):
            st.info("Click button above to compute your optimal daily schedule based on task priorities.")
        else:
            st.success(sched_data["message"])
            for slot in sched_data["schedule"]:
                st.markdown(
                    f"""
                    <div style="background: rgba(99, 102, 241, 0.1); border-left: 4px solid #6366f1; padding: 12px; border-radius: 8px; margin-bottom: 8px;">
                        <div style="font-weight: 700; color: #818cf8;">🕒 {slot['time_slot']} ({slot['duration']} hrs)</div>
                        <div style="font-size: 1rem; color: #f8fafc; font-weight:600;">{slot['title']}</div>
                        <div style="font-size: 0.8rem; color: #94a3b8;">Priority: {slot['priority']} | Deadline: {slot['deadline']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # TAB 3: Audit Logs
    with tab3:
        st.subheader("📜 Complete Timeline Audit Log")
        st.caption("JSON log trace of all agent decisions and tool executions.")
        st.json(st.session_state.agent.timeline_logs)
