"""
Adapter module that provides a bridge between the raw MarvinAPI and the MCP server.

This module handles the translation between the raw API data and LLM-friendly formats,
including friendly ID mapping, time estimate formatting, and hierarchy generation.
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple

from .marvin import MarvinAPI

class MarvinAdapter:
    """
    Adapter class that provides LLM-friendly interfaces to the MarvinAPI.
    
    This class handles:
    1. Friendly ID mapping (t1, p1, etc.) for tasks and projects
    2. Formatting of time estimates in human-readable format
    3. Generation of LLM-friendly hierarchy structures
    4. Translation between LLM formats and API formats
    """
    
    def __init__(self, marvin_api: MarvinAPI = None, log_level=None):
        """
        Initialize the MarvinAdapter with a MarvinAPI instance.
        
        Args:
            marvin_api: An instance of MarvinAPI. If None, a new instance will be created.
            log_level: Optional logging level.
        """
        self.logger = logging.getLogger('MarvinAdapter')
        if log_level is not None:
            self.logger.setLevel(log_level)
            
        self.api = marvin_api if marvin_api else MarvinAPI()
        
        # Initialize ID mappings
        self._project_id_map = {}  # Maps real UUIDs to friendly IDs (p1, p2, etc.)
        self._project_id_reverse_map = {}  # Maps friendly IDs back to real UUIDs
        self._task_id_map = {}  # Maps real UUIDs to friendly IDs (t1, t2, etc.)
        self._task_id_reverse_map = {}  # Maps friendly IDs back to real UUIDs
        self._next_project_id = 1
        self._next_task_id = 1
    
    def _get_friendly_project_id(self, uuid: str) -> str:
        """
        Get a friendly project ID (p1, p2, etc.) for a UUID.
        If the UUID doesn't have a friendly ID yet, create one.
        """
        if not uuid:
            return ""
            
        if uuid not in self._project_id_map:
            friendly_id = f"p{self._next_project_id}"
            self._project_id_map[uuid] = friendly_id
            self._project_id_reverse_map[friendly_id] = uuid
            self._next_project_id += 1
        return self._project_id_map[uuid]
    
    def _get_friendly_task_id(self, uuid: str) -> str:
        """
        Get a friendly task ID (t1, t2, etc.) for a UUID.
        If the UUID doesn't have a friendly ID yet, create one.
        """
        if not uuid:
            return ""
            
        if uuid not in self._task_id_map:
            friendly_id = f"t{self._next_task_id}"
            self._task_id_map[uuid] = friendly_id
            self._task_id_reverse_map[friendly_id] = uuid
            self._next_task_id += 1
        return self._task_id_map[uuid]
    
    def get_real_id(self, friendly_id: str) -> Optional[str]:
        """
        Convert a friendly ID (p1, t1, etc.) back to the real UUID.
        Returns None if the friendly ID is not found.
        """
        if not friendly_id:
            return None
            
        if friendly_id.startswith('p') and friendly_id in self._project_id_reverse_map:
            return self._project_id_reverse_map[friendly_id]
        elif friendly_id.startswith('t') and friendly_id in self._task_id_reverse_map:
            return self._task_id_reverse_map[friendly_id]
        return None
    
    def parse_time_estimate(self, time_str: str) -> Optional[int]:
        """
        Parse a human-readable time estimate string (e.g., "30m", "1.5h") 
        and convert it to milliseconds for the API.
        
        Args:
            time_str: A string like "30m", "1.5h", "1h 30m"
            
        Returns:
            Time in milliseconds or None if parsing fails
        """
        if not time_str:
            return None
            
        total_minutes = 0
        
        # Handle combined format like "1h 30m"
        if " " in time_str:
            parts = time_str.split()
            for part in parts:
                minutes = self._parse_single_time_part(part)
                if minutes is not None:
                    total_minutes += minutes
        else:
            # Handle single unit like "1.5h" or "30m"
            minutes = self._parse_single_time_part(time_str)
            if minutes is not None:
                total_minutes = minutes
        
        if total_minutes > 0:
            return int(total_minutes * 60 * 1000)  # Convert minutes to milliseconds
        return None
    
    def _parse_single_time_part(self, part: str) -> Optional[float]:
        """Parse a single time part like "1.5h" or "30m" into minutes."""
        try:
            if part.endswith('h'):
                hours = float(part[:-1])
                return hours * 60
            elif part.endswith('m'):
                return float(part[:-1])
            else:
                # Try to interpret as minutes if no unit is specified
                return float(part)
        except ValueError:
            return None
    
    def format_time_estimate(self, milliseconds: Optional[int]) -> Optional[str]:
        """
        Format a time estimate from milliseconds to a human-readable string.
        
        Args:
            milliseconds: Time in milliseconds
            
        Returns:
            A string like "30m" or "1.5h" or None if input is None
        """
        if milliseconds is None:
            return None
            
        hours = milliseconds / (1000 * 60 * 60)
        
        # Less than an hour, show in minutes
        if hours < 1:
            minutes = milliseconds / (1000 * 60)
            return f"{int(minutes)}m"
        
        # Whole hours
        if hours.is_integer():
            return f"{int(hours)}h"
        
        # Partial hours
        return f"{hours:.1f}h"
    
    def _process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task into a compact format with a friendly ID."""
        friendly_id = self._get_friendly_task_id(task["_id"])
        res = {
            "t": task.get("title", "Untitled Task"),
            "id": friendly_id
        }
        
        if task.get("dueDate"):
            res["due"] = task["dueDate"]
            
        # Format time estimate
        if task.get("timeEstimate"):
            est = self.format_time_estimate(task.get("timeEstimate"))
            if est:
                res["est"] = est
                
        if task.get("isStarred"):
            res["pri"] = task.get("isStarred")
            
        return res
    
    def _process_category(self, cat: Dict[str, Any]) -> Dict[str, Any]:
        """Process a category/project into a compact format with a friendly ID."""
        friendly_id = self._get_friendly_project_id(cat["_id"])
        data: Dict[str, Any] = {"id": friendly_id}
        
        if cat.get("priority"):
            data["pri"] = cat["priority"]
            
        if cat.get("dueDate"):
            data["due"] = cat["dueDate"]
            
        return data
    
    def build_hierarchy(self) -> Dict[str, Any]:
        """
        Build the hierarchical structure of categories and tasks.
        
        Returns:
            A dictionary with the LLM-friendly hierarchy
        """
        # Fetch all categories and tasks
        categories = self.api.get_categories()
        tasks = self.api.get_tasks()

        # Find root categories (parentId is "root" or missing)
        root_categories = [cat for cat in categories if cat.get(
            "parentId") == "root" or not cat.get("parentId")]
            
        # Find categories with parentId 'unassigned' (should go under Inbox)
        inbox_categories = [cat for cat in categories if cat.get(
            "parentId") == "unassigned"]
        inbox_tasks = [t for t in tasks if t.get("parentId") == "unassigned"]

        # Build the hierarchy with compact entries
        def process_category_recursive(category: Dict[str, Any]) -> Dict[str, Any]:
            cid = category["_id"]
            cdata = self._process_category(category)
            
            # Add tasks
            tlist = [self._process_task(t)
                     for t in tasks if t.get("parentId") == cid]
            if tlist:
                cdata["tasks"] = tlist
                
            # Add subcategories
            subs = [c for c in categories if c.get("parentId") == cid]
            if subs:
                cdata["sub"] = {
                    s.get("title", "Untitled"): process_category_recursive(s) for s in subs}
                    
            return cdata

        hierarchy = {rc.get("title", "Untitled Category"): process_category_recursive(
            rc) for rc in root_categories}

        # Add synthetic Inbox for categories and tasks with parentId 'unassigned'
        if inbox_categories or inbox_tasks:
            inbox_dict = {}
            if inbox_categories:
                inbox_dict["sub"] = {cat.get("title", "Untitled Category"): process_category_recursive(
                    cat) for cat in inbox_categories}
            if inbox_tasks:
                inbox_dict["tasks"] = [
                    self._process_task(t) for t in inbox_tasks]
            hierarchy["Inbox"] = inbox_dict

        return hierarchy
    
    def build_hierarchy_string(self) -> str:
        """
        Build the hierarchical structure and return as a formatted JSON string.
        
        Returns:
            JSON string with the hierarchy and tasks in compact format
        """
        hierarchy = self.build_hierarchy()
        
        # Convert to JSON with initial indentation
        json_str = json.dumps(hierarchy, indent=2)

        # Use regex to compact the task arrays for better readability
        def compact_tasks(match):
            tasks = json.loads(match.group(2))
            if not tasks:
                return '"tasks": []'
                
            prefix = match.group(1)
            task_indent = prefix + '  '
            lines = [prefix + '"tasks": [']
            
            for i, task in enumerate(tasks):
                line = task_indent + json.dumps(task, separators=(',', ':'))
                if i < len(tasks) - 1:
                    line += ','
                lines.append(line)
                
            lines.append(prefix + ']')
            return '\n'.join(lines)
            
        pattern = r'^(\s*)"tasks": (\[[\s\S]*?\])'
        json_str = re.sub(pattern, compact_tasks, json_str, flags=re.MULTILINE)
        
        return json_str
    
    def create_task(self, title: str, parent_id: str = "unassigned", 
                   day: Optional[str] = None, due_date: Optional[str] = None, 
                   time_estimate: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new task with LLM-friendly parameters.
        
        Args:
            title: The title of the task
            parent_id: Optional friendly ID (p1) or UUID of the parent project
            day: Optional day for the task (YYYY-MM-DD)
            due_date: Optional due date for the task (YYYY-MM-DD)
            time_estimate: Optional time estimate in human format (e.g., "30m", "1.5h")
            
        Returns:
            Dictionary with the created task info and its friendly ID
        """
        # Convert parent_id from friendly ID if needed
        real_parent_id = parent_id
        if parent_id and parent_id.startswith('p'):
            converted_id = self.get_real_id(parent_id)
            if converted_id:
                real_parent_id = converted_id
        
        # Convert time estimate from human-readable to milliseconds
        time_ms = None
        if time_estimate:
            time_ms = self.parse_time_estimate(time_estimate)
        
        # Create the task using the API
        api_result = self.api.create_task(
            title=title,
            parent_id=real_parent_id,
            day=day,
            due_date=due_date,
            time_estimate=time_ms
        )
        
        # Get the task ID and assign a friendly ID
        task_id = api_result.get("id", "")
        friendly_id = self._get_friendly_task_id(task_id)
        
        # Return LLM-friendly result
        return {
            "task": {
                "title": title,
                "id": friendly_id,
                "parent_id": parent_id,
                "day": day,
                "due_date": due_date,
                "time_estimate": time_estimate
            },
            "message": f"Task '{title}' created successfully with ID {friendly_id}"
        }
    
    def create_project(self, title: str, parent_id: str = "unassigned",
                      due_date: Optional[str] = None, priority: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new project with LLM-friendly parameters.
        
        Args:
            title: The title of the project
            parent_id: Optional friendly ID (p1) or UUID of the parent project
            due_date: Optional due date for the project (YYYY-MM-DD)
            priority: Optional priority level (1-3, with 3 being highest)
            
        Returns:
            Dictionary with the created project info and its friendly ID
        """
        # Convert parent_id from friendly ID if needed
        real_parent_id = parent_id
        if parent_id and parent_id.startswith('p'):
            converted_id = self.get_real_id(parent_id)
            if converted_id:
                real_parent_id = converted_id
        
        # Create the project using the API
        api_result = self.api.create_project(
            title=title,
            parent_id=real_parent_id,
            due_date=due_date,
            priority=priority
        )
        
        # Get the project ID and assign a friendly ID
        project_id = api_result.get("id", "")
        friendly_id = self._get_friendly_project_id(project_id)
        
        # Return LLM-friendly result
        return {
            "project": {
                "title": title,
                "id": friendly_id,
                "parent_id": parent_id,
                "due_date": due_date,
                "priority": priority
            },
            "message": f"Project '{title}' created successfully with ID {friendly_id}"
        }
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a task using its friendly ID or UUID.
        
        Args:
            task_id: The friendly ID (t1) or UUID of the task to update
            updates: Dictionary with fields to update
            
        Returns:
            Dictionary with the updated task info
        """
        # Convert task_id from friendly ID if needed
        real_task_id = task_id
        if task_id and task_id.startswith('t'):
            converted_id = self.get_real_id(task_id)
            if converted_id:
                real_task_id = converted_id
            else:
                raise ValueError(f"Task with friendly ID {task_id} not found")
        
        # Process special fields like time_estimate
        api_updates = updates.copy()
        
        if "time_estimate" in updates:
            time_str = updates["time_estimate"]
            time_ms = self.parse_time_estimate(time_str)
            api_updates["timeEstimate"] = time_ms
            del api_updates["time_estimate"]
        
        # Update the task using the API
        api_result = self.api.update_task(real_task_id, api_updates)
        
        # Get the friendly ID
        friendly_id = self._get_friendly_task_id(real_task_id)
        
        # Create LLM-friendly response
        response = {
            "task": {
                "title": api_result.get("title", ""),
                "id": friendly_id
            },
            "message": f"Task updated successfully"
        }
        
        # Add any updated fields to the response
        for key, value in updates.items():
            response["task"][key] = value
        
        return response
    
    def schedule_task(self, task_id: str, day: str) -> Dict[str, Any]:
        """
        Schedule a task for a specific day.
        
        Args:
            task_id: The friendly ID (t1) of the task to schedule
            day: The day to schedule the task for (YYYY-MM-DD)
            
        Returns:
            Dictionary with the scheduled task info
        """
        # Convert task_id from friendly ID
        real_task_id = task_id
        if task_id and task_id.startswith('t'):
            converted_id = self.get_real_id(task_id)
            if converted_id:
                real_task_id = converted_id
            else:
                raise ValueError(f"Task with friendly ID {task_id} not found")
        
        # Create update with just the day field
        updates = {"day": day}
        
        # Update the task using the API
        api_result = self.api.update_task(real_task_id, updates)
        
        # Get the friendly ID
        friendly_id = self._get_friendly_task_id(real_task_id)
        
        # Create LLM-friendly response
        response = {
            "task": {
                "title": api_result.get("title", ""),
                "id": friendly_id,
                "day": day
            },
            "message": f"Task scheduled for {day}"
        }
        
        return response
    
    def test_connection(self) -> Dict[str, str]:
        """
        Test the connection to the Amazing Marvin CouchDB server.
        
        Returns:
            Dictionary with status and message
        """
        success = self.api.test_connection()
        if success:
            return {
                "status": "success",
                "message": "Connection to Amazing Marvin database successful"
            }
        else:
            return {
                "status": "failure",
                "message": "Connection to Amazing Marvin database failed"
            }