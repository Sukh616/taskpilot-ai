"""
Unit tests for agent.py (Agent Engine, approval workflow, rejection safety, and timeline).
"""

import os
import pytest
import tempfile
from database import init_db, db_list_tasks
from agent import AgentEngine

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def agent(temp_db):
    return AgentEngine(db_path=temp_db)

def test_agent_init(agent):
    assert agent.db_path is not None
    assert agent.mode in ["LLM", "DEMO"]

def test_missing_info_clarification(agent):
    res = agent.process_user_request("create a task")
    # Missing title triggers clarification request
    assert res["status"] in ["clarification_needed", "plan_generated"]

def test_plan_generation_and_approval_workflow(agent, temp_db):
    res = agent.process_user_request("create task Finish Homework deadline tomorrow high priority")
    assert res["status"] == "plan_generated"
    assert len(agent.current_plan) >= 2
    assert res["has_pending_approvals"] is True

    # Check step 1 is pending approval
    step_1 = agent.current_plan[0]
    assert step_1["status"] == "pending_approval"
    assert step_1["requires_approval"] is True

    # Approve step 1
    approve_res = agent.approve_step(step_1["id"])
    assert approve_res.get("success") is True
    assert step_1["status"] == "executed"

    # Verify task was actually created in DB
    tasks = db_list_tasks(db_path=temp_db)
    assert len(tasks) >= 1
    assert "Homework" in tasks[0]["title"]

def test_rejection_safety_prevents_db_mutation(agent, temp_db):
    """
    CRITICAL REQUIREMENT: A rejected plan MUST NOT modify stored task data.
    """
    # 1. Start with clean DB
    initial_tasks = db_list_tasks(db_path=temp_db)
    assert len(initial_tasks) == 0

    # 2. Process user request to create task
    res = agent.process_user_request("create task Secret Mission deadline today urgent priority")
    step_1 = agent.current_plan[0]
    assert step_1["status"] == "pending_approval"

    # 3. Reject step 1
    reject_res = agent.reject_step(step_1["id"])
    assert reject_res["success"] is True
    assert step_1["status"] == "rejected"

    # 4. Verify DB remains completely empty!
    final_tasks = db_list_tasks(db_path=temp_db)
    assert len(final_tasks) == 0, "Rejected task MUST NOT modify SQLite database!"

def test_edit_step_args(agent):
    agent.process_user_request("create task Draft Presentation")
    step_1 = agent.current_plan[0]

    edit_res = agent.edit_step_args(step_1["id"], {"priority": "Urgent", "duration": 4.0})
    assert edit_res["success"] is True
    assert step_1["args"]["priority"] == "Urgent"
    assert step_1["args"]["duration"] == 4.0

def test_multistep_organize_and_schedule_workflow(agent, temp_db):
    res = agent.process_user_request("organize my assignments and prepare a study schedule for Operating Systems")
    assert res["status"] == "plan_generated"
    assert len(agent.current_plan) == 4

    # Step 1 is generate study plan (requires approval)
    step_1 = agent.current_plan[0]
    assert step_1["tool"] == "generate_study_plan"
    assert step_1["status"] == "pending_approval"

    # Step 2, 3, 4 MUST remain pending and NOT execute before step 1 is approved!
    assert agent.current_plan[1]["status"] == "pending"
    assert agent.current_plan[2]["status"] == "pending"
    assert agent.current_plan[3]["status"] == "pending"

    # Approve step 1
    agent.approve_step(step_1["id"])

    # Now step 1 is executed, and subsequent eligible steps 2, 3, 4 automatically run to execution
    assert step_1["status"] == "executed"
    assert agent.current_plan[1]["status"] == "executed"
    assert agent.current_plan[2]["status"] == "executed"
    assert agent.current_plan[3]["status"] == "executed"

    # Verify execution timeline recorded events
    assert len(agent.timeline_logs) > 0
    phases = [log["phase"] for log in agent.timeline_logs]
    assert "PLANNING" in phases
    assert "APPROVED" in phases
    assert "EXECUTION" in phases

def test_prerequisite_enforcement_prevents_premature_execution(agent):
    """REGRESSION TEST FIX 1: Verify downstream steps do NOT execute while prerequisite is pending approval."""
    res = agent.process_user_request("organize my assignments and prepare a study schedule for Operating Systems")
    plan = agent.current_plan
    assert plan[0]["status"] == "pending_approval"
    assert plan[1]["status"] == "pending"
    assert plan[2]["status"] == "pending"
    assert plan[3]["status"] == "pending"

def test_rejection_cancels_dependent_steps_and_records_timeline(agent, temp_db):
    """REGRESSION TEST FIX 2: Verify rejecting prerequisite step cancels downstream steps and logs CANCELLED event."""
    res = agent.process_user_request("organize my assignments and prepare a study schedule for Operating Systems")
    step_1 = agent.current_plan[0]

    # Reject step 1
    agent.reject_step(step_1["id"])

    # Step 1 is rejected; subsequent steps MUST be cancelled
    assert step_1["status"] == "rejected"
    assert agent.current_plan[1]["status"] == "cancelled"
    assert agent.current_plan[2]["status"] == "cancelled"
    assert agent.current_plan[3]["status"] == "cancelled"

    # Verify timeline records CANCELLED phase
    phases = [log["phase"] for log in agent.timeline_logs]
    assert "REJECTED" in phases
    assert "CANCELLED" in phases

    # Verify DB has 0 tasks
    tasks = db_list_tasks(db_path=temp_db)
    assert len(tasks) == 0

def test_failed_prerequisite_prevents_downstream_execution(agent):
    """REGRESSION TEST FIX 1: Verify a failed prerequisite blocks downstream steps."""
    agent.current_plan = [
        {
            "id": "step_1",
            "title": "Invalid Tool Step",
            "tool": "non_existent_tool",
            "args": {},
            "requires_approval": False,
            "status": "pending"
        },
        {
            "id": "step_2",
            "title": "Downstream Read Step",
            "tool": "list_tasks",
            "args": {},
            "requires_approval": False,
            "status": "pending"
        }
    ]
    agent._auto_execute_read_steps()
    assert agent.current_plan[0]["status"] == "failed"
    assert agent.current_plan[1]["status"] == "cancelled" # Downstream cancelled due to failure!

def test_direct_execution_boundary_guard_blocks_unapproved_or_unmet_prerequisites(agent):
    """REGRESSION TEST FIX 1: Verify direct calls to execute_step and approve_step cannot bypass prerequisite/approval gates."""
    res = agent.process_user_request("organize my assignments and prepare a study schedule for Operating Systems")
    plan = agent.current_plan
    assert plan[0]["status"] == "pending_approval"
    assert plan[1]["status"] == "pending"

    # Direct call to execute_step on unapproved step_1 must fail
    ex_res1 = agent.execute_step("step_1")
    assert ex_res1["success"] is False
    assert "Requires human approval" in ex_res1["error"]
    assert plan[0]["status"] == "pending_approval"

    # Direct call to approve_step or execute_step on downstream step_2 while step_1 is pending_approval must fail
    appr_res2 = agent.approve_step("step_2")
    assert appr_res2["success"] is False
    assert "has not succeeded" in appr_res2["error"]
    assert plan[1]["status"] == "pending"

@pytest.mark.parametrize(
    ("prompt", "expected_subject"),
    [
        (
            "organize my assignments and prepare a study schedule for Computer Networks",
            "Computer Networks",
        ),
        (
            "organize my assignments and prepare a study schedule for Operating Systems",
            "Operating Systems",
        ),
        (
            "organize my assignments and prepare a study schedule for Machine Learning",
            "Machine Learning",
        ),
        (
            "organize my assignments and prepare a study schedule for Data Structures",
            "Data Structures & Algorithms",
        ),
        (
            "organize my assignments and prepare a study schedule",
            "Computer Science & AI",
        ),
    ],
)
def test_deterministic_planner_selects_expected_subject(
    agent, prompt, expected_subject
):
    result = agent._plan_deterministic_demo(prompt)

    assert "plan" in result
    assert result["plan"][0]["tool"] == "generate_study_plan"
    assert result["plan"][0]["args"]["subject"] == expected_subject
