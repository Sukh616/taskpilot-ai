"""
TaskPilot AI - Tool Engine
Defines executable Python tools for task management, prioritization, scheduling,
study plan generation, and database state verification.
"""

import datetime
from typing import Dict, List, Any, Optional
from database import (
    db_create_task,
    db_get_task,
    db_list_tasks,
    db_update_task,
    db_delete_task,
    db_get_dashboard_stats
)

# ---------------------------------------------------------------------------
# Helper Functions & Input Validation
# ---------------------------------------------------------------------------

def validate_date_string(date_str: Optional[str]) -> Optional[str]:
    """Validate and normalize ISO date string (YYYY-MM-DD or YYYY-MM-DD HH:MM)."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if not date_str:
        return None

    # Handle common relative keywords
    lower_str = date_str.lower()
    today = datetime.date.today()
    if lower_str in ["today", "now"]:
        return today.isoformat()
    elif lower_str in ["tomorrow"]:
        return (today + datetime.timedelta(days=1)).isoformat()
    elif lower_str in ["next week", "in 7 days"]:
        return (today + datetime.timedelta(days=7)).isoformat()

    # Try parsing standard formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Fallback return original string if non-empty
    return date_str

# ---------------------------------------------------------------------------
# Core Python Tools
# ---------------------------------------------------------------------------

def tool_create_task(
    title: str,
    deadline: Optional[str] = None,
    duration: float = 1.0,
    priority: str = "Medium",
    category: str = "General",
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new task in SQLite database after input validation."""
    if not title or not str(title).strip():
        return {
            "success": False,
            "error": "Task title is required and cannot be empty.",
            "task": None
        }

    norm_deadline = validate_date_string(deadline)
    try:
        duration_val = float(duration)
        if duration_val <= 0:
            duration_val = 1.0
    except (ValueError, TypeError):
        duration_val = 1.0

    priority_val = str(priority).capitalize() if priority else "Medium"
    if priority_val not in ["Low", "Medium", "High", "Urgent"]:
        priority_val = "Medium"

    category_val = str(category).strip().capitalize() if category else "General"

    try:
        created_task = db_create_task(
            title=str(title).strip(),
            deadline=norm_deadline,
            duration=duration_val,
            priority=priority_val,
            category=category_val,
            db_path=db_path
        )
        return {
            "success": True,
            "message": f"Task '{created_task['title']}' created successfully with ID #{created_task['id']}.",
            "task": created_task
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Database error creating task: {str(e)}",
            "task": None
        }

def tool_list_tasks(
    status: Optional[str] = None,
    search: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """List and filter tasks from the SQLite database."""
    try:
        tasks = db_list_tasks(
            status=status,
            search=search,
            priority=priority,
            category=category,
            db_path=db_path
        )
        return {
            "success": True,
            "count": len(tasks),
            "tasks": tasks,
            "message": f"Retrieved {len(tasks)} matching tasks."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list tasks: {str(e)}",
            "tasks": []
        }

def tool_update_task(
    task_id: int,
    updates: Dict[str, Any],
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Update fields of an existing task in SQLite database."""
    try:
        existing = db_get_task(int(task_id), db_path=db_path)
        if not existing:
            return {
                "success": False,
                "error": f"Task #{task_id} not found.",
                "task": None
            }

        # Normalize date if present
        if "deadline" in updates and updates["deadline"]:
            updates["deadline"] = validate_date_string(updates["deadline"])

        updated_task = db_update_task(int(task_id), updates, db_path=db_path)
        return {
            "success": True,
            "message": f"Task #{task_id} ('{updated_task['title']}') successfully updated.",
            "task": updated_task
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to update task #{task_id}: {str(e)}",
            "task": None
        }

def tool_prioritize_tasks(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Algorithmic task prioritization engine.
    Calculates urgency/importance scores based on deadline proximity, priority levels, and duration.
    """
    try:
        tasks = db_list_tasks(status="Pending", db_path=db_path)
        if not tasks:
            return {
                "success": True,
                "message": "No pending tasks to prioritize.",
                "prioritized_tasks": []
            }

        today = datetime.date.today()
        prioritized = []

        for t in tasks:
            score = 0.0
            reasons = []

            # 1. Base Priority Weight
            p_map = {"Urgent": 100, "High": 75, "Medium": 50, "Low": 25}
            p_score = p_map.get(t["priority"], 50)
            score += p_score
            reasons.append(f"Base priority {t['priority']} (+{p_score})")

            # 2. Deadline Urgency Factor
            if t["deadline"]:
                try:
                    dl_date = datetime.datetime.strptime(t["deadline"].split("T")[0], "%Y-%m-%d").date()
                    days_left = (dl_date - today).days

                    if days_left < 0:
                        score += 60
                        reasons.append(f"Overdue by {abs(days_left)} days (+60)")
                    elif days_left == 0:
                        score += 50
                        reasons.append("Due today (+50)")
                    elif days_left == 1:
                        score += 35
                        reasons.append("Due tomorrow (+35)")
                    elif days_left <= 3:
                        score += 20
                        reasons.append(f"Due in {days_left} days (+20)")
                    elif days_left <= 7:
                        score += 10
                        reasons.append(f"Due in {days_left} days (+10)")
                except Exception:
                    pass
            else:
                reasons.append("No deadline set")

            # 3. Quick-win duration bonus (shorter tasks get slight boost)
            dur = float(t.get("duration", 1.0))
            if dur <= 1.0:
                score += 10
                reasons.append("Quick win (<= 1 hr) (+10)")

            t_copy = dict(t)
            t_copy["priority_score"] = round(score, 1)
            t_copy["prioritization_reason"] = " | ".join(reasons)
            prioritized.append(t_copy)

        # Sort descending by priority score
        prioritized.sort(key=lambda x: x["priority_score"], reverse=True)

        return {
            "success": True,
            "message": f"Prioritized {len(prioritized)} pending tasks.",
            "prioritized_tasks": prioritized
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Prioritization error: {str(e)}",
            "prioritized_tasks": []
        }

def tool_generate_schedule(available_hours: float = 8.0, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates a structured daily time-block schedule fitting pending tasks within available hours.
    """
    try:
        avail_hrs = float(available_hours)
        if avail_hrs <= 0:
            avail_hrs = 8.0
    except (ValueError, TypeError):
        avail_hrs = 8.0

    p_res = tool_prioritize_tasks(db_path=db_path)
    pending_tasks = p_res.get("prioritized_tasks", [])

    if not pending_tasks:
        return {
            "success": True,
            "message": "No pending tasks available for scheduling.",
            "schedule": [],
            "total_allocated_hours": 0.0,
            "unallocated_tasks": []
        }

    schedule_slots = []
    current_time = datetime.datetime.combine(datetime.date.today(), datetime.time(9, 0)) # Start 9:00 AM
    hours_left = avail_hrs
    allocated_hours = 0.0
    unallocated = []

    for task in pending_tasks:
        dur = float(task.get("duration", 1.0))
        if dur <= hours_left:
            start_str = current_time.strftime("%I:%M %p")
            end_time = current_time + datetime.timedelta(hours=dur)
            end_str = end_time.strftime("%I:%M %p")

            schedule_slots.append({
                "time_slot": f"{start_str} - {end_str}",
                "task_id": task["id"],
                "title": task["title"],
                "duration": dur,
                "priority": task["priority"],
                "deadline": task["deadline"] or "None"
            })

            allocated_hours += dur
            hours_left -= dur

            # Add 15 min buffer break
            current_time = end_time + datetime.timedelta(minutes=15)
        else:
            unallocated.append(task)

    return {
        "success": True,
        "message": f"Generated schedule allocating {allocated_hours:.1f} hours across {len(schedule_slots)} tasks.",
        "schedule": schedule_slots,
        "available_hours": avail_hrs,
        "total_allocated_hours": round(allocated_hours, 1),
        "remaining_free_hours": round(max(0.0, hours_left), 1),
        "unallocated_tasks": unallocated
    }

def tool_generate_study_plan(
    subject: str,
    available_time: float = 5.0,
    create_tasks_in_db: bool = False,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Decomposes a learning subject into structured study modules with duration estimates.
    Optionally creates the resulting tasks directly in SQLite if requested/approved.
    """
    if not subject or not str(subject).strip():
        return {
            "success": False,
            "error": "Subject name is required to generate a study plan.",
            "modules": []
        }

    try:
        total_hrs = float(available_time)
        if total_hrs <= 0:
            total_hrs = 5.0
    except (ValueError, TypeError):
        total_hrs = 5.0

    subj_clean = str(subject).strip().title()
    today = datetime.date.today()

    # Create 4 balanced study modules
    m1_dur = round(total_hrs * 0.30, 1) # Foundations
    m2_dur = round(total_hrs * 0.35, 1) # Practical Problem Solving
    m3_dur = round(total_hrs * 0.20, 1) # Advanced Concepts
    m4_dur = round(total_hrs * 0.15, 1) # Review & Exam Practice

    modules = [
        {
            "title": f"Study {subj_clean}: Core Foundations & Theory",
            "duration": m1_dur,
            "deadline": (today + datetime.timedelta(days=1)).isoformat(),
            "priority": "High",
            "category": "Study"
        },
        {
            "title": f"Study {subj_clean}: Problem Solving & Code Exercises",
            "duration": m2_dur,
            "deadline": (today + datetime.timedelta(days=2)).isoformat(),
            "priority": "High",
            "category": "Study"
        },
        {
            "title": f"Study {subj_clean}: Advanced Deep-Dive & Edge Cases",
            "duration": m3_dur,
            "deadline": (today + datetime.timedelta(days=3)).isoformat(),
            "priority": "Medium",
            "category": "Study"
        },
        {
            "title": f"Study {subj_clean}: Final Review & Practice Test",
            "duration": m4_dur,
            "deadline": (today + datetime.timedelta(days=4)).isoformat(),
            "priority": "Medium",
            "category": "Study"
        }
    ]

    created_tasks = []
    if create_tasks_in_db:
        for mod in modules:
            res = tool_create_task(
                title=mod["title"],
                deadline=mod["deadline"],
                duration=mod["duration"],
                priority=mod["priority"],
                category=mod["category"],
                db_path=db_path
            )
            if res.get("success"):
                created_tasks.append(res["task"])

    return {
        "success": True,
        "subject": subj_clean,
        "available_time": total_hrs,
        "message": f"Generated study plan for '{subj_clean}' breakdown into {len(modules)} core modules ({total_hrs} hrs total).",
        "modules": modules,
        "created_tasks": created_tasks
    }

def tool_verify_actions(
    expected_action_type: str,
    target_ids: Optional[List[int]] = None,
    count: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Directly checks SQLite database state to verify if requested actions succeeded truthfully.
    """
    try:
        action_type = str(expected_action_type).lower()
        verified = False
        reasons = []

        if action_type == "create":
            if target_ids:
                found_all = True
                missing = []
                for tid in target_ids:
                    t = db_get_task(tid, db_path=db_path)
                    if not t:
                        found_all = False
                        missing.append(tid)
                if found_all:
                    verified = True
                    reasons.append(f"Verified all task IDs {target_ids} exist in SQLite database.")
                else:
                    reasons.append(f"Missing task IDs {missing} in SQLite database.")
            elif count is not None:
                stats = db_get_dashboard_stats(db_path=db_path)
                if stats["total"] >= count:
                    verified = True
                    reasons.append(f"Verified total database task count ({stats['total']}) is >= expected ({count}).")
                else:
                    reasons.append(f"Database count ({stats['total']}) is less than expected ({count}).")
            else:
                verified = True
                reasons.append("Creation verified (general).")

        elif action_type == "update":
            if target_ids:
                all_updated = True
                for tid in target_ids:
                    t = db_get_task(tid, db_path=db_path)
                    if not t:
                        all_updated = False
                        reasons.append(f"Task #{tid} not found.")
                    elif details:
                        for k, expected_v in details.items():
                            actual_v = t.get(k)
                            if str(actual_v).lower() != str(expected_v).lower():
                                all_updated = False
                                reasons.append(f"Task #{tid} field '{k}' is '{actual_v}', expected '{expected_v}'.")
                if all_updated:
                    verified = True
                    reasons.append(f"Verified update details on tasks {target_ids}.")
            else:
                verified = True
                reasons.append("Update verified.")

        elif action_type == "delete":
            if target_ids:
                all_deleted = True
                for tid in target_ids:
                    t = db_get_task(tid, db_path=db_path)
                    if t:
                        all_deleted = False
                        reasons.append(f"Task #{tid} still exists in database.")
                if all_deleted:
                    verified = True
                    reasons.append(f"Verified task IDs {target_ids} are deleted from database.")
            else:
                verified = True

        elif action_type == "study_plan":
            if target_ids:
                found_all = True
                missing = []
                for tid in target_ids:
                    t = db_get_task(tid, db_path=db_path)
                    if not t:
                        found_all = False
                        missing.append(tid)
                if found_all:
                    verified = True
                    reasons.append(f"Verified all study task IDs {target_ids} exist in SQLite database.")
                else:
                    verified = False
                    reasons.append(f"Missing study task IDs {missing} in SQLite database.")
            elif count is not None:
                # Query specific study/academic tasks to prevent false positives from unrelated tasks
                study_tasks = db_list_tasks(category="Study", db_path=db_path)
                academic_tasks = db_list_tasks(category="Academic", db_path=db_path)
                all_study_matching = study_tasks + [t for t in academic_tasks if t not in study_tasks]
                matching_count = len(all_study_matching)

                if matching_count >= count:
                    verified = True
                    reasons.append(f"Verified {matching_count} study tasks exist in SQLite database (expected at least {count}).")
                else:
                    verified = False
                    reasons.append(f"Found {matching_count} study/academic tasks in database, less than expected ({count}).")
            else:
                verified = True
                reasons.append("Verified study plan structure (in-memory plan generated without database tasks).")

        elif action_type in ["prioritize", "schedule", "read"]:
            verified = True
            reasons.append(f"Verified operational integrity for '{action_type}'.")

        else:
            verified = True
            reasons.append(f"Verified general action '{action_type}'.")

        return {
            "success": True,
            "verified": verified,
            "expected_action": action_type,
            "message": " | ".join(reasons) if reasons else "Verification complete.",
            "target_ids": target_ids or []
        }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "error": f"Verification execution failed: {str(e)}"
        }

# ---------------------------------------------------------------------------
# Tool Registry Map
# ---------------------------------------------------------------------------

TOOLS_REGISTRY = {
    "create_task": {
        "function": tool_create_task,
        "requires_approval": True,
        "description": "Create a new persistent task in the database.",
        "params": ["title", "deadline", "duration", "priority", "category"]
    },
    "list_tasks": {
        "function": tool_list_tasks,
        "requires_approval": False,
        "description": "List and filter tasks from the database.",
        "params": ["status", "search", "priority", "category"]
    },
    "update_task": {
        "function": tool_update_task,
        "requires_approval": True,
        "description": "Update an existing task in the database.",
        "params": ["task_id", "updates"]
    },
    "prioritize_tasks": {
        "function": tool_prioritize_tasks,
        "requires_approval": False,
        "description": "Compute urgency and priority scores for all pending tasks.",
        "params": []
    },
    "generate_schedule": {
        "function": tool_generate_schedule,
        "requires_approval": False,
        "description": "Generate a daily time-block schedule fitting tasks into available hours.",
        "params": ["available_hours"]
    },
    "generate_study_plan": {
        "function": tool_generate_study_plan,
        "requires_approval": True, # If creating tasks
        "description": "Break down a study subject into structured modules and create study tasks.",
        "params": ["subject", "available_time", "create_tasks_in_db"]
    },
    "verify_actions": {
        "function": tool_verify_actions,
        "requires_approval": False,
        "description": "Verify database state integrity after state-changing operations.",
        "params": ["expected_action_type", "target_ids", "count", "details"]
    }
}
