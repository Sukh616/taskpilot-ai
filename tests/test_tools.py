"""
Unit tests for tools.py (Executable Python tools & verification engine).
"""

import os
import pytest
import tempfile
from database import init_db
from tools import (
    tool_create_task,
    tool_list_tasks,
    tool_update_task,
    tool_prioritize_tasks,
    tool_generate_schedule,
    tool_generate_study_plan,
    tool_verify_actions,
    validate_date_string
)

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_validate_date_string():
    assert validate_date_string("2026-12-31") == "2026-12-31"
    assert validate_date_string("today") is not None
    assert validate_date_string(None) is None

def test_tool_create_task(temp_db):
    res = tool_create_task("Finish Report", deadline="2026-10-20", duration=2.5, priority="High", db_path=temp_db)
    assert res["success"] is True
    assert res["task"]["title"] == "Finish Report"
    assert res["task"]["priority"] == "High"
    assert res["task"]["duration"] == 2.5

def test_tool_create_task_invalid_title(temp_db):
    res = tool_create_task("   ", db_path=temp_db)
    assert res["success"] is False
    assert "error" in res

def test_tool_list_tasks(temp_db):
    tool_create_task("Task 1", priority="Urgent", db_path=temp_db)
    tool_create_task("Task 2", priority="Low", db_path=temp_db)
    res = tool_list_tasks(db_path=temp_db)
    assert res["success"] is True
    assert res["count"] == 2

def test_tool_prioritize_tasks(temp_db):
    tool_create_task("Low Priority Task", priority="Low", duration=3.0, db_path=temp_db)
    tool_create_task("Urgent Task", priority="Urgent", deadline="today", duration=0.5, db_path=temp_db)

    res = tool_prioritize_tasks(db_path=temp_db)
    assert res["success"] is True
    tasks = res["prioritized_tasks"]
    assert len(tasks) == 2
    assert tasks[0]["title"] == "Urgent Task" # Should be ranked first

def test_tool_generate_schedule(temp_db):
    tool_create_task("Study Math", duration=2.0, priority="High", db_path=temp_db)
    tool_create_task("Write Essay", duration=3.0, priority="Medium", db_path=temp_db)

    res = tool_generate_schedule(available_hours=6.0, db_path=temp_db)
    assert res["success"] is True
    assert len(res["schedule"]) == 2
    assert res["total_allocated_hours"] == 5.0

def test_tool_generate_study_plan(temp_db):
    res = tool_generate_study_plan("Algorithms", available_time=8.0, create_tasks_in_db=True, db_path=temp_db)
    assert res["success"] is True
    assert res["subject"] == "Algorithms"
    assert len(res["modules"]) == 4
    assert len(res["created_tasks"]) == 4

def test_tool_verify_actions(temp_db):
    c_res = tool_create_task("Verified Task", db_path=temp_db)
    task_id = c_res["task"]["id"]

    # Verify task existence
    v_res = tool_verify_actions("create", target_ids=[task_id], db_path=temp_db)
    assert v_res["success"] is True
    assert v_res["verified"] is True

    # Verify missing ID
    v_missing = tool_verify_actions("create", target_ids=[999], db_path=temp_db)
    assert v_missing["verified"] is False

def test_verify_actions_study_plan_with_real_db_check(temp_db):
    """REGRESSION TEST FIX 3: Verify study_plan verifies real SQLite DB count when count is specified."""
    # 1. When DB is empty, expecting 4 tasks should return verified=False
    v_fail = tool_verify_actions("study_plan", count=4, db_path=temp_db)
    assert v_fail["success"] is True
    assert v_fail["verified"] is False

    # 2. Generate study plan creating tasks in DB
    tool_generate_study_plan("OS", available_time=6.0, create_tasks_in_db=True, db_path=temp_db)

    # 3. Now DB has 4 tasks, expecting 4 tasks returns verified=True
    v_pass = tool_verify_actions("study_plan", count=4, db_path=temp_db)
    assert v_pass["success"] is True
    assert v_pass["verified"] is True

def test_verify_actions_study_plan_without_db_mutations(temp_db):
    """REGRESSION TEST FIX 3: Verify study_plan without count or target_ids verifies in-memory plan generation."""
    v_res = tool_verify_actions("study_plan", db_path=temp_db)
    assert v_res["success"] is True
    assert v_res["verified"] is True
    assert "in-memory" in v_res["message"]
