"""
TaskPilot AI - Core Agent Engine
Orchestrates natural language intent parsing, multi-step planning, missing info clarification,
human approval gates, tool execution, state verification, and audit timeline tracking.
Supports dual modes: Real LLM API Mode & Labeled Deterministic Demo Engine.
"""

import os
import json
import re
import datetime
import requests
from typing import Dict, List, Any, Optional, Tuple

from tools import (
    TOOLS_REGISTRY,
    tool_create_task,
    tool_list_tasks,
    tool_update_task,
    tool_prioritize_tasks,
    tool_generate_schedule,
    tool_generate_study_plan,
    tool_verify_actions,
    validate_date_string
)
from database import db_list_tasks, db_get_task

class AgentEngine:
    """Core TaskPilot AI Agent Engine."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.history: List[Dict[str, Any]] = []
        self.timeline_logs: List[Dict[str, Any]] = []
        self.current_plan: List[Dict[str, Any]] = []
        self.pending_clarification: Optional[str] = None
        self.mode = self._detect_mode()

    def _detect_mode(self) -> str:
        """Check if an API key is configured in environment variables."""
        if os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
            return "LLM"
        return "DEMO"

    def log_timeline(self, phase: str, description: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Append an entry to the agent execution timeline audit trail."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "phase": phase.upper(),
            "description": description,
            "details": details or {}
        }
        self.timeline_logs.append(entry)

    def process_user_request(self, user_input: str) -> Dict[str, Any]:
        """
        Main entry point to handle user prompt.
        Extracts intent, checks for missing info, generates structured plan, and logs timeline.
        """
        user_input_clean = user_input.strip()
        if not user_input_clean:
            return {"status": "error", "message": "Empty input."}

        self.log_timeline("PLANNING", f"Received user prompt: '{user_input_clean}'")

        # 1. Check active mode
        self.mode = self._detect_mode()
        self.log_timeline("PLANNING", f"Operating in mode: [{self.mode} MODE]")

        # 2. Extract intent and construct plan
        if self.mode == "LLM":
            plan_res = self._plan_with_llm(user_input_clean)
        else:
            plan_res = self._plan_deterministic_demo(user_input_clean)

        if plan_res.get("clarification_needed"):
            self.pending_clarification = plan_res["clarification_needed"]
            self.log_timeline("PLANNING", f"Clarification required: {self.pending_clarification}")
            return {
                "status": "clarification_needed",
                "message": self.pending_clarification,
                "mode": self.mode,
                "plan": []
            }

        self.pending_clarification = None
        self.current_plan = plan_res.get("plan", [])

        # Log tools selected in plan
        tool_names = [step["tool"] for step in self.current_plan]
        self.log_timeline("TOOL_SELECTION", f"Selected {len(tool_names)} tool steps: {', '.join(tool_names)}")

        # Check if any step requires human approval
        has_approval_required = any(step.get("requires_approval") for step in self.current_plan)

        if has_approval_required:
            self.log_timeline("APPROVAL_REQUEST", "Proposed plan contains state-changing actions. Awaiting user approval.")

        # Execute non-approval steps automatically (e.g., list_tasks, prioritize)
        self._auto_execute_read_steps()

        return {
            "status": "plan_generated",
            "mode": self.mode,
            "explanation": plan_res.get("explanation", ""),
            "plan": self.current_plan,
            "has_pending_approvals": any(s["status"] == "pending_approval" for s in self.current_plan)
        }

    def _plan_deterministic_demo(self, prompt: str) -> Dict[str, Any]:
        """
        Deterministic, robust fallback engine demonstrating full multi-step reasoning,
        clarification checks, tool selection, and verification without requiring an LLM API key.
        """
        p_lower = prompt.lower()
        today_str = datetime.date.today().isoformat()
        tomorrow_str = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        # Check Scenario A: Missing vital info for Task Creation
        if any(kw in p_lower for kw in ["create task", "add task", "new task"]) and not any(kw in p_lower for kw in ["study", "schedule", "prioritize", "list"]):
            # Check if title is missing
            title_match = re.search(r'(?:title|called|named|task)\s+["\']?([^"\',]+)["\']?', prompt, re.IGNORECASE)
            if not title_match and len(prompt.split()) < 4:
                return {
                    "clarification_needed": "Could you please specify the **title** of the task you would like to create?"
                }

        # Scenario 1: Multi-step Organized Study & Schedule (Assignments + Study Plan)
        if ("study" in p_lower and "schedule" in p_lower) or ("organize" in p_lower and ("assignment" in p_lower or "exam" in p_lower or "subject" in p_lower)):
            subject = "Computer Science & AI"

            if "computer networks" in p_lower or "computer network" in p_lower:
                subject = "Computer Networks"
            elif "machine learning" in p_lower or re.search(r"\bml\b", p_lower):
                subject = "Machine Learning"
            elif "operating system" in p_lower or re.search(r"\bos\b", p_lower):
                subject = "Operating Systems"
            elif "data structure" in p_lower or re.search(r"\balgo\b", p_lower):
                subject = "Data Structures & Algorithms"

            return {
                "explanation": f"[DEMO MODE: Deterministic Fallback Engine] Decomposed request to organize assignments for **{subject}** and create a balanced daily schedule.",
                "plan": [
                    {
                        "id": "step_1",
                        "title": f"Generate Study Breakdown for '{subject}'",
                        "tool": "generate_study_plan",
                        "args": {"subject": subject, "available_time": 6.0, "create_tasks_in_db": True},
                        "requires_approval": True,
                        "status": "pending_approval",
                        "result": None,
                        "verification": None
                    },
                    {
                        "id": "step_2",
                        "title": "Prioritize All Pending Tasks (Including New Study Modules)",
                        "tool": "prioritize_tasks",
                        "args": {},
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    },
                    {
                        "id": "step_3",
                        "title": "Generate 8-Hour Time-Block Schedule",
                        "tool": "generate_schedule",
                        "args": {"available_hours": 8.0},
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    },
                    {
                        "id": "step_4",
                        "title": "Verify Database Task Creation & Schedule Integrity",
                        "tool": "verify_actions",
                        "args": {"expected_action_type": "study_plan", "count": 4},
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    }
                ]
            }

        # Scenario 2: Create Single Task
        if any(kw in p_lower for kw in ["create", "add", "new task", "remind me"]):
            # Extract title
            title = prompt
            for kw in ["create a task to", "create task", "add task to", "add task", "remind me to", "new task"]:
                if kw in p_lower:
                    idx = p_lower.find(kw) + len(kw)
                    title = prompt[idx:].strip(" :.")
                    break

            # Extract priority if mentioned
            priority = "Medium"
            if "urgent" in p_lower:
                priority = "Urgent"
            elif "high priority" in p_lower or "high" in p_lower:
                priority = "High"
            elif "low" in p_lower:
                priority = "Low"

            # Extract deadline
            deadline = tomorrow_str
            if "today" in p_lower:
                deadline = today_str
            elif "next week" in p_lower:
                deadline = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()

            # Extract duration
            duration = 1.0
            dur_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hour|hrs|hr)', p_lower)
            if dur_match:
                duration = float(dur_match.group(1))

            category = "General"
            if "study" in p_lower or "exam" in p_lower:
                category = "Academic"
            elif "work" in p_lower or "bug" in p_lower or "code" in p_lower:
                category = "Work"

            return {
                "explanation": f"[DEMO MODE: Deterministic Fallback Engine] Decomposed request to create task: '{title}'.",
                "plan": [
                    {
                        "id": "step_1",
                        "title": f"Create Task: '{title}'",
                        "tool": "create_task",
                        "args": {
                            "title": title,
                            "deadline": deadline,
                            "duration": duration,
                            "priority": priority,
                            "category": category
                        },
                        "requires_approval": True,
                        "status": "pending_approval",
                        "result": None,
                        "verification": None
                    },
                    {
                        "id": "step_2",
                        "title": f"Verify Task Persistence in SQLite",
                        "tool": "verify_actions",
                        "args": {"expected_action_type": "create", "count": 1},
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    }
                ]
            }

        # Scenario 3: Update Task / Mark Completed
        if any(kw in p_lower for kw in ["complete", "mark complete", "done", "update task"]):
            # Extract task id
            id_match = re.search(r'#?(\d+)', prompt)
            task_id = int(id_match.group(1)) if id_match else 1

            new_status = "Completed" if any(kw in p_lower for kw in ["complete", "done", "finished"]) else "Pending"

            return {
                "explanation": f"[DEMO MODE: Deterministic Fallback Engine] Proposed update to task #{task_id} (status -> '{new_status}').",
                "plan": [
                    {
                        "id": "step_1",
                        "title": f"Update Task #{task_id} Status to {new_status}",
                        "tool": "update_task",
                        "args": {
                            "task_id": task_id,
                            "updates": {"status": new_status}
                        },
                        "requires_approval": True,
                        "status": "pending_approval",
                        "result": None,
                        "verification": None
                    },
                    {
                        "id": "step_2",
                        "title": f"Verify Database State for Task #{task_id}",
                        "tool": "verify_actions",
                        "args": {
                            "expected_action_type": "update",
                            "target_ids": [task_id],
                            "details": {"status": new_status}
                        },
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    }
                ]
            }

        # Scenario 4: Prioritize Tasks
        if any(kw in p_lower for kw in ["prioritize", "priority", "what should i do", "what next"]):
            return {
                "explanation": "[DEMO MODE: Deterministic Fallback Engine] Evaluating pending tasks by urgency, deadline, and duration.",
                "plan": [
                    {
                        "id": "step_1",
                        "title": "Calculate Algorithmic Task Priorities",
                        "tool": "prioritize_tasks",
                        "args": {},
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    }
                ]
            }

        # Scenario 5: Generate Schedule
        if any(kw in p_lower for kw in ["schedule", "time block", "today's schedule"]):
            dur_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hour|hrs|hr)', p_lower)
            hrs = float(dur_match.group(1)) if dur_match else 8.0

            return {
                "explanation": f"[DEMO MODE: Deterministic Fallback Engine] Generating visual schedule for {hrs} available hours.",
                "plan": [
                    {
                        "id": "step_1",
                        "title": f"Generate {hrs}-Hour Daily Schedule",
                        "tool": "generate_schedule",
                        "args": {"available_hours": hrs},
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    }
                ]
            }

        # Scenario 6: List / Show Tasks
        if any(kw in p_lower for kw in ["list", "show", "get tasks", "view tasks", "overview"]):
            status_filter = None
            if "pending" in p_lower:
                status_filter = "Pending"
            elif "completed" in p_lower:
                status_filter = "Completed"

            return {
                "explanation": "[DEMO MODE: Deterministic Fallback Engine] Listing tasks from SQLite database.",
                "plan": [
                    {
                        "id": "step_1",
                        "title": "Fetch Tasks from SQLite Database",
                        "tool": "list_tasks",
                        "args": {"status": status_filter},
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    }
                ]
            }

        # Scenario 7: Generate Study Plan
        if "study plan" in p_lower or "study" in p_lower:
            # Extract subject
            subject = "Computer Science"
            sub_match = re.search(r'for\s+([a-zA-Z0-9\s]+)', prompt, re.IGNORECASE)
            if sub_match:
                subject = sub_match.group(1).strip()

            return {
                "explanation": f"[DEMO MODE: Deterministic Fallback Engine] Decomposed study plan generation for '{subject}'.",
                "plan": [
                    {
                        "id": "step_1",
                        "title": f"Generate Study Breakdown & Tasks for '{subject}'",
                        "tool": "generate_study_plan",
                        "args": {"subject": subject, "available_time": 5.0, "create_tasks_in_db": True},
                        "requires_approval": True,
                        "status": "pending_approval",
                        "result": None,
                        "verification": None
                    },
                    {
                        "id": "step_2",
                        "title": f"Verify Study Tasks Created in SQLite",
                        "tool": "verify_actions",
                        "args": {"expected_action_type": "create", "count": 4},
                        "requires_approval": False,
                        "status": "pending",
                        "result": None,
                        "verification": None
                    }
                ]
            }

        # Fallback General Intent
        return {
            "explanation": f"[DEMO MODE: Deterministic Fallback Engine] Analyzing request: '{prompt}'.",
            "plan": [
                {
                    "id": "step_1",
                    "title": f"Process Task Pilot Request: '{prompt}'",
                    "tool": "create_task",
                    "args": {"title": prompt, "priority": "Medium", "category": "General"},
                    "requires_approval": True,
                    "status": "pending_approval",
                    "result": None,
                    "verification": None
                },
                {
                    "id": "step_2",
                    "title": "Verify Task Creation",
                    "tool": "verify_actions",
                    "args": {"expected_action_type": "create", "count": 1},
                    "requires_approval": False,
                    "status": "pending",
                    "result": None,
                    "verification": None
                }
            ]
        }

    def _plan_with_llm(self, prompt: str) -> Dict[str, Any]:
        """Call configured LLM API (OpenAI or Gemini) for structured multi-step planning."""
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")

        system_prompt = """You are TaskPilot AI, an autonomous personal productivity agent.
Decompose the user's request into a structured execution plan.
Available tools:
- create_task(title, deadline, duration, priority, category) [requires_approval: true]
- list_tasks(status, search, priority, category) [requires_approval: false]
- update_task(task_id, updates) [requires_approval: true]
- prioritize_tasks() [requires_approval: false]
- generate_schedule(available_hours) [requires_approval: false]
- generate_study_plan(subject, available_time, create_tasks_in_db) [requires_approval: true]
- verify_actions(expected_action_type, target_ids, count, details) [requires_approval: false]

If essential info is missing (e.g. creating task without title, study plan without subject), return JSON with "clarification_needed".
Otherwise, return JSON with keys "explanation" and "plan" (array of step objects).
Each step object must have: id, title, tool, args, requires_approval (bool), status ("pending_approval" if requires_approval else "pending")."""

        try:
            if os.getenv("OPENAI_API_KEY"):
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=10)
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)

            elif os.getenv("GEMINI_API_KEY"):
                # Gemini API HTTP endpoint
                gemini_key = os.getenv("GEMINI_API_KEY")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\nUser Prompt: {prompt}\n\nReturn raw valid JSON only."}]}]
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=10)
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                # Clean code blocks if present
                raw_text = re.sub(r'```json\s*|\s*```', '', raw_text).strip()
                return json.loads(raw_text)

        except Exception as e:
            self.log_timeline("PLANNING", f"LLM API call failed ({str(e)}). Falling back to Deterministic Engine.")
            return self._plan_deterministic_demo(prompt)

        return self._plan_deterministic_demo(prompt)

    def _auto_execute_read_steps(self) -> None:
        """Automatically execute eligible steps in current_plan whose preceding prerequisites have succeeded."""
        for idx, step in enumerate(self.current_plan):
            if not step.get("requires_approval") and step["status"] == "pending":
                # Ensure all preceding steps have reached "executed" status
                blocked = False
                for prior_step in self.current_plan[:idx]:
                    if prior_step.get("status") != "executed":
                        blocked = True
                        break
                if not blocked:
                    self.execute_step(step["id"])

    def approve_step(self, step_id: str) -> Dict[str, Any]:
        """Approve a state-changing step in the active plan and immediately execute it if prerequisites permit."""
        target_idx = None
        target_step = None
        for idx, step in enumerate(self.current_plan):
            if step["id"] == step_id:
                target_idx = idx
                target_step = step
                break

        if not target_step:
            return {"success": False, "error": f"Step #{step_id} not found."}

        # Check prerequisite ordering before approval
        for prior_step in self.current_plan[:target_idx]:
            if prior_step.get("status") != "executed":
                return {
                    "success": False,
                    "error": f"Cannot approve step #{step_id}: Prerequisite step #{prior_step['id']} ('{prior_step['title']}') has not succeeded (status: {prior_step.get('status')})."
                }

        target_step["status"] = "approved"
        self.log_timeline("APPROVED", f"Human user APPROVED step: {target_step['title']}", {"step_id": step_id})
        res = self.execute_step(step_id)
        # After executing, auto-run any subsequent eligible pending steps
        self._auto_execute_read_steps()
        return res

    def edit_step_args(self, step_id: str, new_args: Dict[str, Any]) -> Dict[str, Any]:
        """Edit arguments of a step before approval."""
        for step in self.current_plan:
            if step["id"] == step_id:
                step["args"].update(new_args)
                self.log_timeline("PLANNING", f"Human user EDITED parameters for step: {step['title']}", {"new_args": new_args})
                return {"success": True, "step": step}
        return {"success": False, "error": f"Step #{step_id} not found."}

    def reject_step(self, step_id: str) -> Dict[str, Any]:
        """Reject a proposed step and cancel dependent downstream steps. Ensures NO state change occurs in SQLite."""
        target_idx = None
        for idx, step in enumerate(self.current_plan):
            if step["id"] == step_id:
                target_idx = idx
                step["status"] = "rejected"
                step["result"] = {"success": False, "message": "Step REJECTED by human supervisor. No database modifications made."}
                self.log_timeline("REJECTED", f"Human user REJECTED step: {step['title']} (State preserved)", {"step_id": step_id})
                break

        if target_idx is None:
            return {"success": False, "error": f"Step #{step_id} not found."}

        # Cancel subsequent dependent steps
        for sub_step in self.current_plan[target_idx + 1:]:
            curr_status = sub_step.get("status")
            if curr_status in ["pending", "pending_approval"]:
                sub_step["status"] = "cancelled"
                sub_step["result"] = {"success": False, "message": f"Step CANCELLED due to rejection of prerequisite step #{step_id}."}
                self.log_timeline("CANCELLED", f"Cancelled dependent step: {sub_step['title']} due to rejection of step #{step_id}", {"step_id": sub_step["id"]})
            elif curr_status == "executed":
                # Preserve historical truth if an action already executed
                self.log_timeline("WARNING", f"Downstream step #{sub_step['id']} was already executed prior to rejection of step #{step_id}.", {"step_id": sub_step["id"]})

        return {"success": True, "step": self.current_plan[target_idx]}

    def execute_step(self, step_id: str) -> Dict[str, Any]:
        """Execute a tool step against Python tool functions and SQLite database, enforcing approval & prerequisite boundary guards."""
        target_idx = None
        target_step = None
        for idx, step in enumerate(self.current_plan):
            if step["id"] == step_id:
                target_idx = idx
                target_step = step
                break

        if not target_step:
            return {"success": False, "error": f"Step #{step_id} not found."}

        # EXECUTION BOUNDARY GUARD 1: Require approval if required and not approved/executing
        if target_step.get("requires_approval") and target_step["status"] not in ["approved", "in_progress"]:
            err_msg = f"Cannot execute step #{step_id}: Requires human approval before execution (status: {target_step['status']})."
            target_step["result"] = {"success": False, "error": err_msg}
            self.log_timeline("EXECUTION_BLOCKED", err_msg, {"step_id": step_id})
            return target_step["result"]

        # EXECUTION BOUNDARY GUARD 2: Prerequisite execution check
        for prior_step in self.current_plan[:target_idx]:
            if prior_step.get("status") != "executed":
                err_msg = f"Cannot execute step #{step_id}: Prerequisite step #{prior_step['id']} ('{prior_step['title']}') has not succeeded (status: {prior_step.get('status')})."
                target_step["result"] = {"success": False, "error": err_msg}
                self.log_timeline("EXECUTION_BLOCKED", err_msg, {"step_id": step_id})
                return target_step["result"]

        tool_name = target_step["tool"]
        tool_meta = TOOLS_REGISTRY.get(tool_name)

        if not tool_meta:
            target_step["status"] = "failed"
            target_step["result"] = {"success": False, "error": f"Unknown tool: '{tool_name}'"}
            self.log_timeline("EXECUTION", f"Failed step {step_id}: Unknown tool '{tool_name}'")
            self._cancel_downstream_steps(target_idx, step_id)
            return target_step["result"]

        self.log_timeline("EXECUTION", f"Executing tool function '{tool_name}' for step: {target_step['title']}", target_step["args"])

        try:
            func = tool_meta["function"]
            args = dict(target_step["args"])
            if "db_path" in func.__code__.co_varnames:
                args["db_path"] = self.db_path

            result = func(**args)
            success = result.get("success", False)
            target_step["status"] = "executed" if success else "failed"
            target_step["result"] = result

            self.log_timeline(
                "EXECUTION",
                f"Completed '{tool_name}' execution (Status: {target_step['status'].upper()})",
                {"result_summary": result.get("message") or result.get("error")}
            )

            if not success:
                self._cancel_downstream_steps(target_idx, step_id)

            # Check if this tool produces created task IDs for verification
            created_id = None
            if tool_name == "create_task" and result.get("task"):
                created_id = result["task"]["id"]

            if created_id:
                for next_step in self.current_plan[target_idx + 1:]:
                    if next_step["tool"] == "verify_actions":
                        next_step["args"]["target_ids"] = [created_id]

            return result

        except Exception as e:
            target_step["status"] = "failed"
            target_step["result"] = {"success": False, "error": str(e)}
            self.log_timeline("EXECUTION", f"Error executing tool '{tool_name}': {str(e)}")
            self._cancel_downstream_steps(target_idx, step_id)
            return target_step["result"]

    def _cancel_downstream_steps(self, from_idx: int, failed_step_id: str) -> None:
        """Cancel downstream pending steps after a failure."""
        for sub_step in self.current_plan[from_idx + 1:]:
            curr_status = sub_step.get("status")
            if curr_status in ["pending", "pending_approval"]:
                sub_step["status"] = "cancelled"
                sub_step["result"] = {"success": False, "message": f"Step CANCELLED due to failure of prerequisite step #{failed_step_id}."}
                self.log_timeline("CANCELLED", f"Cancelled dependent step: {sub_step['title']} due to failure of step #{failed_step_id}", {"step_id": sub_step["id"]})

    def run_all_approved(self) -> List[Dict[str, Any]]:
        """Approve and execute all pending steps in the current plan."""
        results = []
        for step in self.current_plan:
            if step["status"] == "pending_approval":
                res = self.approve_step(step["id"])
                results.append(res)
        return results
