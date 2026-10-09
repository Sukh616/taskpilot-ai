"""
TaskPilot AI - SQLite Database Manager
Provides persistent task storage, CRUD operations, stats aggregation,
and sample scenario loading with strict input validation.
"""

import sqlite3
import os
import datetime
from typing import Dict, List, Any, Optional

DEFAULT_DB_PATH = os.getenv("TASKPILOT_DB_PATH", "taskpilot.db")

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    """Initialize the SQLite database schema if tables do not exist."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                deadline TEXT,
                duration REAL DEFAULT 1.0,
                priority TEXT DEFAULT 'Medium',
                status TEXT DEFAULT 'Pending',
                category TEXT DEFAULT 'General',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def task_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert SQLite Row object to python dictionary."""
    if not row:
        return {}
    return {
        "id": row["id"],
        "title": row["title"],
        "deadline": row["deadline"],
        "duration": row["duration"],
        "priority": row["priority"],
        "status": row["status"],
        "category": row["category"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

def db_create_task(
    title: str,
    deadline: Optional[str] = None,
    duration: float = 1.0,
    priority: str = "Medium",
    status: str = "Pending",
    category: str = "General",
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new task in the database."""
    init_db(db_path)
    title = str(title).strip()
    if not title:
        raise ValueError("Task title cannot be empty.")

    # Normalize priority
    priority = priority.capitalize() if priority else "Medium"
    if priority not in ["Low", "Medium", "High", "Urgent"]:
        priority = "Medium"

    # Normalize status
    status = status.capitalize() if status else "Pending"
    if status not in ["Pending", "In Progress", "Completed", "Cancelled"]:
        status = "Pending"

    duration = max(0.25, float(duration))

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (title, deadline, duration, priority, status, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, deadline, duration, priority, status, category, now, now)
        )
        conn.commit()
        task_id = cursor.lastrowid
        return db_get_task(task_id, db_path)

def db_get_task(task_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single task by ID."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return task_row_to_dict(row) if row else None

def db_list_tasks(
    status: Optional[str] = None,
    search: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List tasks filtered by status, search keyword, priority, or category."""
    init_db(db_path)
    query = "SELECT * FROM tasks WHERE 1=1"
    params: List[Any] = []

    if status and status != "All":
        query += " AND status = ?"
        params.append(status.capitalize())

    if priority and priority != "All":
        query += " AND priority = ?"
        params.append(priority.capitalize())

    if category and category != "All":
        query += " AND category = ?"
        params.append(category)

    if search and search.strip():
        query += " AND (title LIKE ? OR category LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term])

    # Order by deadline ascending (nulls last), then priority
    query += """ ORDER BY
        CASE WHEN deadline IS NULL OR deadline = '' THEN 1 ELSE 0 END,
        deadline ASC,
        CASE priority
            WHEN 'Urgent' THEN 1
            WHEN 'High' THEN 2
            WHEN 'Medium' THEN 3
            WHEN 'Low' THEN 4
            ELSE 5
        END ASC,
        created_at DESC"""

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [task_row_to_dict(r) for r in rows]

def db_update_task(
    task_id: int,
    updates: Dict[str, Any],
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update fields of an existing task."""
    init_db(db_path)
    allowed_keys = {"title", "deadline", "duration", "priority", "status", "category"}
    fields_to_update = {k: v for k, v in updates.items() if k in allowed_keys}

    if not fields_to_update:
        return db_get_task(task_id, db_path)

    if "title" in fields_to_update and not str(fields_to_update["title"]).strip():
        raise ValueError("Task title cannot be empty.")

    if "priority" in fields_to_update and fields_to_update["priority"]:
        fields_to_update["priority"] = str(fields_to_update["priority"]).capitalize()

    if "status" in fields_to_update and fields_to_update["status"]:
        fields_to_update["status"] = str(fields_to_update["status"]).capitalize()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fields_to_update["updated_at"] = now

    set_clause = ", ".join([f"{k} = ?" for k in fields_to_update.keys()])
    values = list(fields_to_update.values()) + [task_id]

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return db_get_task(task_id, db_path)

def db_delete_task(task_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a task by ID."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0

def db_clear_all(db_path: Optional[str] = None) -> None:
    """Clear all tasks from the database."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks")
        conn.commit()

def db_get_dashboard_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Calculate aggregate task statistics for the dashboard."""
    init_db(db_path)
    tasks = db_list_tasks(db_path=db_path)
    total = len(tasks)
    completed = sum(1 for t in tasks if t["status"] == "Completed")
    pending = sum(1 for t in tasks if t["status"] == "Pending")
    in_progress = sum(1 for t in tasks if t["status"] == "In Progress")
    high_urgent = sum(1 for t in tasks if t["priority"] in ["High", "Urgent"] and t["status"] != "Completed")

    # Calculate upcoming deadlines (due within 3 days or overdue)
    today = datetime.date.today()
    three_days_later = (today + datetime.timedelta(days=3)).isoformat()
    today_str = today.isoformat()

    upcoming_count = 0
    for t in tasks:
        if t["status"] != "Completed" and t["deadline"]:
            dl = t["deadline"].split("T")[0].split(" ")[0]
            if dl <= three_days_later:
                upcoming_count += 1

    priority_counts = {
        "Urgent": sum(1 for t in tasks if t["priority"] == "Urgent"),
        "High": sum(1 for t in tasks if t["priority"] == "High"),
        "Medium": sum(1 for t in tasks if t["priority"] == "Medium"),
        "Low": sum(1 for t in tasks if t["priority"] == "Low"),
    }

    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "in_progress": in_progress,
        "high_priority": high_urgent,
        "upcoming_deadlines": upcoming_count,
        "priority_distribution": priority_counts,
        "completion_rate": round((completed / total * 100), 1) if total > 0 else 0.0
    }

def db_load_sample_scenario(scenario_key: str = "finals_week", db_path: Optional[str] = None) -> int:
    """Explicitly load a curated sample scenario into database without removing existing user tasks unless requested."""
    init_db(db_path)
    today = datetime.date.today()

    scenarios = {
        "finals_week": [
            {
                "title": "Study Operating Systems Virtual Memory & Paging",
                "deadline": (today + datetime.timedelta(days=1)).isoformat(),
                "duration": 3.0,
                "priority": "Urgent",
                "category": "Academic"
            },
            {
                "title": "Complete Algorithms Graph Theory Problem Set",
                "deadline": (today + datetime.timedelta(days=2)).isoformat(),
                "duration": 4.0,
                "priority": "High",
                "category": "Academic"
            },
            {
                "title": "Prepare AI Agent Presentation Deck",
                "deadline": (today + datetime.timedelta(days=4)).isoformat(),
                "duration": 2.5,
                "priority": "Medium",
                "category": "Academic"
            },
            {
                "title": "Review Machine Learning Neural Nets Chapter 8",
                "deadline": (today + datetime.timedelta(days=5)).isoformat(),
                "duration": 2.0,
                "priority": "Low",
                "category": "Academic"
            }
        ],
        "product_launch": [
            {
                "title": "Fix Critical Authentication Timeout Bug",
                "deadline": today.isoformat(),
                "duration": 2.0,
                "priority": "Urgent",
                "category": "Work"
            },
            {
                "title": "Write Product Hunt Launch Announcement",
                "deadline": (today + datetime.timedelta(days=1)).isoformat(),
                "duration": 1.5,
                "priority": "High",
                "category": "Work"
            },
            {
                "title": "Record 2-Minute App Demo Walkthrough Video",
                "deadline": (today + datetime.timedelta(days=2)).isoformat(),
                "duration": 3.0,
                "priority": "High",
                "category": "Work"
            },
            {
                "title": "Configure Stripe Webhook Security Keys",
                "deadline": (today + datetime.timedelta(days=3)).isoformat(),
                "duration": 1.0,
                "priority": "Medium",
                "category": "Work"
            }
        ],
        "freelance_sprint": [
            {
                "title": "Design Mobile Wireframes for E-commerce Client",
                "deadline": (today + datetime.timedelta(days=1)).isoformat(),
                "duration": 4.0,
                "priority": "High",
                "category": "Freelance"
            },
            {
                "title": "Migrate PostgreSQL Database Schema",
                "deadline": (today + datetime.timedelta(days=3)).isoformat(),
                "duration": 2.5,
                "priority": "Medium",
                "category": "Freelance"
            },
            {
                "title": "Submit Milestone 2 Invoice",
                "deadline": (today + datetime.timedelta(days=4)).isoformat(),
                "duration": 0.5,
                "priority": "Low",
                "category": "Admin"
            }
        ]
    }

    selected = scenarios.get(scenario_key, scenarios["finals_week"])
    count = 0
    for task in selected:
        db_create_task(
            title=task["title"],
            deadline=task.get("deadline"),
            duration=task.get("duration", 1.0),
            priority=task.get("priority", "Medium"),
            category=task.get("category", "General"),
            db_path=db_path
        )
        count += 1
    return count
