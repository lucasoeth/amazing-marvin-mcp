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


class MarvinAdapterError(Exception):
    """Base exception class for MarvinAdapter errors."""
    pass


class InvalidProjectIDError(MarvinAdapterError):
    """Error raised when an invalid parent ID is provided."""
    def __init__(self, parent_id: str, message: Optional[str] = None):
        self.parent_id = parent_id
        if message is None:
            message = f"Invalid project ID: '{parent_id}'. Use a valid project ID (p1, p2, etc.) from list_tasks results."
        super().__init__(message)


class InvalidTaskIDError(MarvinAdapterError):
    """Error raised when an invalid task ID is provided."""
    def __init__(self, task_id: str, message: Optional[str] = None):
        self.task_id = task_id
        if message is None:
            message = f"Invalid task ID: '{task_id}'. Use a valid task ID (t1, t2, etc.) from list_tasks results."
        super().__init__(message)


class InvalidTimeEstimateError(MarvinAdapterError):
    """Error raised when an invalid time estimate format is provided."""
    def __init__(self, time_estimate: str, message: Optional[str] = None):
        self.time_estimate = time_estimate
        if message is None:
            message = f"Invalid time estimate format: '{time_estimate}'. Use formats like '30m', '1.5h', or '1h 30m'."
        super().__init__(message)


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
        # Maps real UUIDs to friendly IDs (p1, p2, etc.)
        self._project_id_map = {}
        self._project_id_reverse_map = {}  # Maps friendly IDs back to real UUIDs
        # Maps real UUIDs to friendly IDs (c1, c2, etc.)
        self._category_id_map = {}
        self._category_id_reverse_map = {}  # Maps friendly IDs back to real UUIDs
        # Maps real UUIDs to friendly IDs (t1, t2, etc.)
        self._task_id_map = {}
        self._task_id_reverse_map = {}  # Maps friendly IDs back to real UUIDs
        self._next_project_id = 1  # Start from p1 (p0 is reserved for Inbox)
        self._next_category_id = 1  # Start from c1
        self._next_task_id = 1
        
        # Add p0 as a special ID for the Inbox/unassigned
        self._project_id_reverse_map["p0"] = "unassigned"
        self._project_id_map["unassigned"] = "p0"
        
        # Initialize ID maps deterministically based on creation date
        self.initialize_id_maps()

    def initialize_id_maps(self):
        """
        Initialize ID maps deterministically by sorting tasks, projects, and categories by createdAt timestamp.
        This ensures consistent ID assignments between sessions.
        """
        self.logger.info("Initializing ID maps deterministically based on createdAt timestamp")
        
        # Fetch all categories and tasks
        try:
            categories = self.api.get_categories()
            tasks = self.api.get_tasks()
            
            # Separate categories and projects
            cat_categories = [c for c in categories if c.get("type") == "category"]
            cat_projects = [c for c in categories if c.get("type") != "category"]
            
            # Sort categories by createdAt timestamp (oldest first)
            sorted_categories = sorted(cat_categories, key=lambda c: c.get('createdAt', 0))
            
            # Assign category IDs based on sorted order
            for category in sorted_categories:
                self._get_friendly_category_id(category["_id"])
                
            # Sort projects by createdAt timestamp (oldest first)
            sorted_projects = sorted(cat_projects, key=lambda c: c.get('createdAt', 0))
            
            # Assign project IDs based on sorted order
            for project in sorted_projects:
                self._get_friendly_project_id(project["_id"])
                
            # Sort tasks by createdAt timestamp (oldest first)
            sorted_tasks = sorted(tasks, key=lambda t: t.get('createdAt', 0))
            
            # Assign task IDs based on sorted order
            for task in sorted_tasks:
                self._get_friendly_task_id(task["_id"])
                
            self.logger.info(f"Successfully initialized ID maps with {len(self._project_id_map)} projects, {len(self._category_id_map)} categories, and {len(self._task_id_map)} tasks")
        except Exception as e:
            self.logger.error(f"Error initializing ID maps: {str(e)}")
            # Continue with empty maps, they will be populated as needed
            pass

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

    def _get_friendly_category_id(self, uuid: str) -> str:
        """
        Get a friendly category ID (c1, c2, etc.) for a UUID.
        If the UUID doesn't have a friendly ID yet, create one.
        """
        if not uuid:
            return ""

        if uuid not in self._category_id_map:
            friendly_id = f"c{self._next_category_id}"
            self._category_id_map[uuid] = friendly_id
            self._category_id_reverse_map[friendly_id] = uuid
            self._next_category_id += 1
        return self._category_id_map[uuid]

    def get_real_project_id(self, friendly_id: str) -> str:
        """
        Convert a project friendly ID (p0, p1, etc.) back to the real UUID.
        
        Args:
            friendly_id: A project friendly ID.
            
        Returns:
            The real UUID.
            
        Raises:
            InvalidProjectIDError: If friendly_id is invalid.
        """
        if not friendly_id:
            raise MarvinAdapterError("Project ID cannot be empty.")
            
        if friendly_id in self._project_id_reverse_map:
            return self._project_id_reverse_map[friendly_id]
        else:
            raise InvalidProjectIDError(friendly_id)
            
    def get_real_task_id(self, friendly_id: str) -> str:
        """
        Convert a task friendly ID (t1, t2, etc.) back to the real UUID.
        
        Args:
            friendly_id: A task friendly ID.
            
        Returns:
            The real UUID.
            
        Raises:
            InvalidTaskIDError: If friendly_id is invalid.
        """
        if not friendly_id:
            raise MarvinAdapterError("Task ID cannot be empty.")
        
        # Task ID must start with t
        if not friendly_id.startswith('t'):
            raise InvalidTaskIDError(friendly_id)
            
        if friendly_id in self._task_id_reverse_map:
            return self._task_id_reverse_map[friendly_id]
        else:
            raise InvalidTaskIDError(friendly_id)

    def get_real_category_id(self, friendly_id: str) -> str:
        """
        Convert a category friendly ID (c1, c2, etc.) back to the real UUID.
        
        Args:
            friendly_id: A category friendly ID.
            
        Returns:
            The real UUID.
            
        Raises:
            MarvinAdapterError: If friendly_id is invalid.
        """
        if not friendly_id:
            raise MarvinAdapterError("Category ID cannot be empty.")
            
        # Category ID must start with c
        if not friendly_id.startswith('c'):
            raise MarvinAdapterError(f"Invalid category ID: '{friendly_id}'. Use a valid category ID (c1, c2, etc.)")
            
        if friendly_id in self._category_id_reverse_map:
            return self._category_id_reverse_map[friendly_id]
        else:
            raise MarvinAdapterError(f"Invalid category ID: '{friendly_id}'. Use a valid category ID (c1, c2, etc.)")

    def parse_time_estimate(self, time_str: str) -> Optional[int]:
        """
        Parse a human-readable time estimate string (e.g., "30m", "1.5h") 
        and convert it to milliseconds for the API.

        Args:
            time_str: A string like "30m", "1.5h", "1h 30m"

        Returns:
            Time in milliseconds
            
        Raises:
            InvalidTimeEstimateError: If the time estimate format is invalid
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
                    raise InvalidTimeEstimateError(time_str)
        else:
            # Handle single unit like "1.5h" or "30m"
            minutes = self._parse_single_time_part(time_str)
            if minutes is not None:
                total_minutes = minutes
            else:
                raise InvalidTimeEstimateError(time_str)

        if total_minutes > 0:
            # Convert minutes to milliseconds
            return int(total_minutes * 60 * 1000)
        
        raise InvalidTimeEstimateError(time_str)

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

    def _process_task_with_completion(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task into a compact format with a friendly ID and completion status."""
        # Start with the basic task processing
        result = self._process_task(task)
        
        # Add completion status
        result["done"] = task.get("done", False)
        
        # Add day field if it exists
        if task.get("day") and task.get("day") != "unassigned":
            result["day"] = task.get("day")
            
        return result

    def _process_category(self, cat: Dict[str, Any]) -> Dict[str, Any]:
        """Process a category/project into a compact format with a friendly ID."""
        is_category = cat.get("type") == "category"
        
        if is_category:
            friendly_id = self._get_friendly_category_id(cat["_id"])
        else:
            friendly_id = self._get_friendly_project_id(cat["_id"])
            
        data: Dict[str, Any] = {
            "id": friendly_id
        }

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
        def process_category_recursive(item: Dict[str, Any]) -> Dict[str, Any]:
            item_id = item["_id"]
            item_data = self._process_category(item)

            # Add tasks for both projects and categories
            tlist = [self._process_task(t)
                    for t in tasks if t.get("parentId") == item_id]
            if tlist:
                item_data["tasks"] = tlist

            # Add subcategories and subprojects
            subs = [c for c in categories if c.get("parentId") == item_id]
            
            if subs:
                item_data["sub"] = {}
                
                # Process all sub-items
                for sub in subs:
                    sub_title = sub.get("title", "Untitled")
                    item_data["sub"][sub_title] = process_category_recursive(sub)

            return item_data

        hierarchy = {}

        # Add synthetic Inbox for categories and tasks with parentId 'unassigned'
        if inbox_categories or inbox_tasks:
            inbox_dict = {"id": "p0"}  # Assign p0 ID to the Inbox
            if inbox_categories:
                inbox_dict["sub"] = {}
                for cat in inbox_categories:
                    cat_title = cat.get("title", "Untitled Category")
                    inbox_dict["sub"][cat_title] = process_category_recursive(cat)
            
            if inbox_tasks:
                inbox_dict["tasks"] = [
                    self._process_task(t) for t in inbox_tasks]
            hierarchy["Inbox"] = inbox_dict

        # Add root categories/projects
        for rc in root_categories:
            rc_title = rc.get("title", "Untitled")
            hierarchy[rc_title] = process_category_recursive(rc)

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

    def create_task(self, title: str, parent_id: str, due_date: Optional[str] = None, 
                    time_estimate: Optional[str] = None, priority: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new task with LLM-friendly parameters.

        Args:
            title: The title of the task
            parent_id: Friendly ID (p1 or c1) for the parent project or category
            due_date: Optional due date for the task (YYYY-MM-DD)
            time_estimate: Optional time estimate in human format (e.g., "30m", "1.5h")
            priority: Optional priority level (1-3, with 3 being highest)

        Returns:
            Dictionary with the created task info and its friendly ID
            
        Raises:
            MarvinAdapterError: If any parameters are invalid
        """
        if not title:
            raise MarvinAdapterError("Task title cannot be empty")
            
        # Convert parent_id from friendly ID to real ID
        real_parent_id = "unassigned"
        if parent_id:
            if parent_id.startswith('c'):
                # Parent is a category
                real_parent_id = self.get_real_category_id(parent_id)
            elif parent_id.startswith('p'):
                # Parent is a project
                real_parent_id = self.get_real_project_id(parent_id)
            else:
                raise MarvinAdapterError(f"Invalid parent ID: '{parent_id}'. Must start with 'c' for categories or 'p' for projects.")

        # Convert time estimate from human-readable to milliseconds
        time_ms = None
        if time_estimate:
            time_ms = self.parse_time_estimate(time_estimate)
            
        # Validate priority if provided
        if priority and priority not in ["1", "2", "3", 1, 2, 3]:
            raise MarvinAdapterError(f"Invalid priority value: {priority}. Must be 1, 2, or 3 (with 3 being highest).")

        # Create the task using the API
        api_result = self.api.create_task(
            title=title,
            parent_id=real_parent_id,
            due_date=due_date,
            time_estimate=time_ms,
            priority=priority
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
                "due_date": due_date,
                "time_estimate": time_estimate,
                "priority": priority
            },
            "message": f"Task '{title}' created successfully with ID {friendly_id}"
        }

    def create_project(self, title: str, parent_id: str,
                       due_date: Optional[str] = None, priority: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new project with LLM-friendly parameters.

        Args:
            title: The title of the project
            parent_id: Friendly ID (p1 or c1) for the parent project or category
            due_date: Optional due date for the project (YYYY-MM-DD)
            priority: Optional priority level (1-3, with 3 being highest)

        Returns:
            Dictionary with the created project info and its friendly ID
            
        Raises:
            MarvinAdapterError: If any parameters are invalid
        """
        if not title:
            raise MarvinAdapterError("Project title cannot be empty")
            
        # Convert parent_id from friendly ID to real ID
        real_parent_id = "root"
        if parent_id:
            if parent_id.startswith('c'):
                # Parent is a category
                real_parent_id = self.get_real_category_id(parent_id)
            elif parent_id.startswith('p'):
                # Parent is a project
                real_parent_id = self.get_real_project_id(parent_id)
            else:
                raise MarvinAdapterError(f"Invalid parent ID: '{parent_id}'. Must start with 'c' for categories or 'p' for projects.")

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

    def create_category(self, title: str, parent_id: str,
                      due_date: Optional[str] = None, priority: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new category with LLM-friendly parameters.

        Args:
            title: The title of the category
            parent_id: Friendly ID (p1 or c1) for the parent category/project
            due_date: Optional due date for the category (YYYY-MM-DD)
            priority: Optional priority level (1-3, with 3 being highest)

        Returns:
            Dictionary with the created category info and its friendly ID
            
        Raises:
            MarvinAdapterError: If any parameters are invalid
        """
        if not title:
            raise MarvinAdapterError("Category title cannot be empty")
            
        # Convert parent_id from friendly ID to real ID
        real_parent_id = "root"
        if parent_id:
            if parent_id.startswith('c'):
                # Parent is a category
                real_parent_id = self.get_real_category_id(parent_id)
            elif parent_id.startswith('p'):
                # Parent is a project
                real_parent_id = self.get_real_project_id(parent_id)
            else:
                raise MarvinAdapterError(f"Invalid parent ID: '{parent_id}'. Must start with 'c' for categories or 'p' for projects.")

        # Validate priority if provided
        if priority and priority not in ["1", "2", "3", 1, 2, 3]:
            raise MarvinAdapterError(f"Invalid priority value: {priority}. Must be 1, 2, or 3 (with 3 being highest).")

        # Create the category using the API
        api_result = self.api.create_category(
            title=title,
            parent_id=real_parent_id,
            due_date=due_date,
            priority=priority
        )

        # Get the category ID and assign a friendly ID
        category_id = api_result.get("id", "")
        friendly_id = self._get_friendly_category_id(category_id)

        # Return LLM-friendly result
        return {
            "category": {
                "title": title,
                "id": friendly_id,
                "parent_id": parent_id if parent_id else "root",
                "due_date": due_date,
                "priority": priority
            },
            "message": f"Category '{title}' created successfully with ID {friendly_id}"
        }

    def update_task(self, task_id: str, title: Optional[str] = None, parent_id: Optional[str] = None, 
                   due_date: Optional[str] = None, time_estimate: Optional[str] = None, 
                   priority: Optional[str] = None) -> Dict[str, Any]:
        """
        Update a task using its friendly ID.

        Args:
            task_id: The friendly ID (t1) of the task to update
            title: New title for the task
            parent_id: New parent project friendly ID (p1, p2, etc.)
            due_date: New due date for the task (YYYY-MM-DD)
            time_estimate: New time estimate in human-readable format (e.g., '30m', '1.5h')
            priority: New priority level (1-3, with 3 being highest)

        Returns:
            Dictionary with the updated task info
            
        Raises:
            MarvinAdapterError: If any parameters are invalid
        """
        if not task_id:
            raise MarvinAdapterError("Task ID cannot be empty")
            
        # Convert task_id from friendly ID to real ID
        real_task_id = self.get_real_task_id(task_id)

        # Process special fields and build API updates
        api_updates = {}

        # Handle title if provided
        if title is not None:
            if not title:
                raise MarvinAdapterError("Task title cannot be empty")
            api_updates["title"] = title

        # Handle time_estimate if provided
        if time_estimate is not None:
            if time_estimate:
                time_ms = self.parse_time_estimate(time_estimate)
                api_updates["timeEstimate"] = time_ms
            else:
                api_updates["timeEstimate"] = None
            
        # Handle parent_id if provided
        if parent_id is not None:
            if parent_id:
                if parent_id.startswith('c'):
                    # Parent is a category
                    real_parent_id = self.get_real_category_id(parent_id)
                elif parent_id.startswith('p'):
                    # Parent is a project
                    real_parent_id = self.get_real_project_id(parent_id) 
                else:
                    raise MarvinAdapterError(f"Invalid parent ID: '{parent_id}'. Must start with 'c' for categories or 'p' for projects.")
                api_updates["parentId"] = real_parent_id
            else:
                api_updates["parentId"] = "unassigned"
                
        # Handle due_date if provided
        if due_date is not None:
            api_updates["dueDate"] = due_date
            
        # Handle priority if provided
        if priority is not None:
            if priority and priority not in ["1", "2", "3", 1, 2, 3]:
                raise MarvinAdapterError(f"Invalid priority value: {priority}. Must be 1, 2, or 3 (with 3 being highest).")
            api_updates["isStarred"] = priority

        # Update the task using the API
        api_result = self.api.update_task(real_task_id, api_updates)

        # Get the task ID and assign a friendly ID
        friendly_id = self._get_friendly_task_id(real_task_id)

        # Return LLM-friendly result with only the fields that were updated
        response = {
            "task": {
                "id": friendly_id,
                "title": api_result.get("title", "")
            },
            "message": f"Task updated successfully"
        }

        # Add updated fields to the response
        if title is not None:
            response["task"]["title"] = title
        
        if parent_id is not None:
            response["task"]["parent_id"] = parent_id
            
        if due_date is not None:
            response["task"]["due_date"] = due_date
            
        if time_estimate is not None:
            response["task"]["time_estimate"] = time_estimate
            
        if priority is not None:
            response["task"]["priority"] = priority

        return response

    def schedule_task(self, task_id: str, day: str) -> Dict[str, Any]:
        """
        Schedule a task for a specific day.

        Args:
            task_id: The friendly ID (t1) of the task to schedule
            day: The day to schedule the task for (YYYY-MM-DD)

        Returns:
            Dictionary with the scheduled task info
            
        Raises:
            MarvinAdapterError: If any parameters are invalid
        """
        if not task_id:
            raise MarvinAdapterError("Task ID cannot be empty")
            
        if not day:
            raise MarvinAdapterError("Day cannot be empty and must be in YYYY-MM-DD format")
            
        # Convert task_id from friendly ID to real ID
        real_task_id = self.get_real_task_id(task_id)

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

    def get_day_tasks(self, day: str) -> Dict[str, Any]:
        """
        Get all tasks scheduled for a specific day in YYYY-MM-DD format.

        Args:
            day: The day to fetch tasks for in YYYY-MM-DD format

        Returns:
            Dictionary with the date and list of tasks
            
        Raises:
            MarvinAdapterError: If the day format is invalid
        """
        # Validate date format
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', day):
            raise MarvinAdapterError(f"Invalid date format: {day}. Use YYYY-MM-DD format.")
            
        # Get tasks for the day from API
        tasks = self.api.get_tasks_by_day(day)
        
        # Process tasks with completion status
        processed_tasks = [self._process_task_with_completion(task) for task in tasks]
        
        # Return simple result
        return {
            "date": day,
            "tasks": processed_tasks
        }