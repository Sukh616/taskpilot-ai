"""
Unit tests for database.py (SQLite task storage engine).
"""

import os
import pytest
import tempfile
from database import (
    init_db,
    db_create_task,
    db_get_task,
    db_list_tasks,
    db_update_task,
    db_delete_task,
    db_clear_all,
    db_get_dashboard_stats,
    db_load_sample_scenario
)

@pytest.fixture
def temp_db():
    """Create a temporary SQLite database file for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_init_and_create_task(temp_db):
    task = db_create_task(
        title="Test Task 1",
        deadline="2026-10-15",
        duration=2.0,
        priority="High",
        category="Work",
        db_path=temp_db
    )
    assert task is not None
    assert task["id"] == 1
    assert task["title"] == "Test Task 1"
    assert task["priority"] == "High"
    assert task["status"] == "Pending"
    assert task["duration"] == 2.0

def test_empty_title_raises_error(temp_db):
    with pytest.raises(ValueError):
        db_create_task(title="", db_path=temp_db)

def test_get_and_list_tasks(temp_db):
    db_create_task(title="Task A", priority="Urgent", status="Pending", db_path=temp_db)
    db_create_task(title="Task B", priority="Low", status="Completed", db_path=temp_db)

    task_a = db_get_task(1, db_path=temp_db)
    assert task_a["title"] == "Task A"

    pending_tasks = db_list_tasks(status="Pending", db_path=temp_db)
    assert len(pending_tasks) == 1
    assert pending_tasks[0]["title"] == "Task A"

    completed_tasks = db_list_tasks(status="Completed", db_path=temp_db)
    assert len(completed_tasks) == 1
    assert completed_tasks[0]["title"] == "Task B"

def test_update_task(temp_db):
    t = db_create_task(title="Original Title", priority="Low", db_path=temp_db)
    updated = db_update_task(t["id"], {"title": "New Title", "status": "Completed", "priority": "High"}, db_path=temp_db)
    assert updated["title"] == "New Title"
    assert updated["status"] == "Completed"
    assert updated["priority"] == "High"

def test_delete_task(temp_db):
    t = db_create_task(title="To Delete", db_path=temp_db)
    assert db_delete_task(t["id"], db_path=temp_db) is True
    assert db_get_task(t["id"], db_path=temp_db) is None

def test_dashboard_stats(temp_db):
    db_create_task(title="Task 1", status="Pending", priority="High", db_path=temp_db)
    db_create_task(title="Task 2", status="Completed", priority="Low", db_path=temp_db)
    stats = db_get_dashboard_stats(db_path=temp_db)
    assert stats["total"] == 2
    assert stats["completed"] == 1
    assert stats["pending"] == 1
    assert stats["completion_rate"] == 50.0

def test_load_sample_scenario(temp_db):
    count = db_load_sample_scenario("finals_week", db_path=temp_db)
    assert count == 4
    tasks = db_list_tasks(db_path=temp_db)
    assert len(tasks) == 4
