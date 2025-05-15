"""
Tool descriptions for the Amazing Marvin MCP server.

This module contains detailed descriptions of the tools available in the MCP server,
including input schemas and explanations of return values.
"""

LIST_TASKS_DESCRIPTION = """Get the hierarchical structure of projects and tasks from Amazing Marvin.
            
The output structure uses the following abbreviations:
- "t": Title of the task
- "due": Due date (YYYY-MM-DD)
- "est": Time estimate (e.g., "30m" for 30 minutes, "2h" for 2 hours)
- "pri": Priority level (1-3, with 3 being highest priority)
- "sub": Subprojects contained within this project
- "tasks": List of tasks within this project
- "id": Friendly ID for referencing this task or project (e.g., "t1" for tasks, "p1" for projects)

To refer to a specific task or project in other API calls, use these friendly IDs.
Tasks are identified as "t1", "t2", etc. and projects as "p1", "p2", etc.

Example output structure:
{
  "Project A": {
    "id": "p1",
    "pri": 3,
    "due": "2025-05-01",
    "tasks": [
      {"t": "Task 1", "id": "t1", "due": "2025-04-25", "est": "2h", "pri": 2},
      {"t": "Task 2", "id": "t2", "est": "30m"}
    ],
    "sub": {
      "Subproject 1": {
        "id": "p2",
        "tasks": [
          {"t": "Subtask 1", "id": "t3", "due": "2025-04-22"}
        ]
      }
    }
  },
  "Inbox": {
    "id": "p3",
    "tasks": [
      {"t": "Unsorted task", "id": "t4", "est": "1h"}
    ]
  }
}"""

CREATE_TASK_DESCRIPTION = """Create a new task in Amazing Marvin.

You can create tasks with various properties and place them in specific projects using their IDs.
Time estimates can be specified in human-readable format like "30m", "1.5h", or "1h 30m".
Priority can be set from 1-3, with 3 being the highest priority.
"""

CREATE_PROJECT_DESCRIPTION = """Create a new project in Amazing Marvin.

You can create projects with various properties and place them within other projects using IDs.
Projects can contain tasks and other subprojects.
"""

UPDATE_TASK_DESCRIPTION = """Update an existing task in Amazing Marvin.

You can update basic properties of a task such as its title, parent project, due date, time estimate, and priority.
For scheduling tasks to specific days, use the schedule_task tool instead.
"""

SCHEDULE_TASK_DESCRIPTION = """Schedule a task for a specific day in Amazing Marvin.

This tool allows you to specify which day a task should be worked on (as opposed to when it's due).
"""

GET_DAY_TASKS_DESCRIPTION = """Get all tasks scheduled for a specific day.

This tool returns all tasks (both completed and incomplete) that are scheduled for the requested day.
You can use this to review what tasks are set for a particular date.

Required format for the day parameter is YYYY-MM-DD (e.g., 2025-05-14).

The response includes a list of tasks with their completion status, due dates, time estimates, and priorities.
"""

CREATE_CATEGORY_DESCRIPTION = """Create a new category in Amazing Marvin.

Categories are static folders that organize projects and tasks into logical groups.
They represent areas of responsibility or life domains like "Work", "Health", or "Household".
You can nest categories within other categories to create a hierarchical structure.

Example uses:
- Creating main areas of responsibility like "Work" or "Health"
- Organizing projects into logical groups
- Creating a hierarchical structure for your tasks

The response includes the created category information and its new ID.
"""

# Input schemas for each tool
LIST_TASKS_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": []
}

CREATE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "The title of the task"
        },
        "parent_id": {
            "type": "string",
            "description": """Optional ID of the parent project (e.g., "p1", "p2") where the task should be created. 
  * Must be a valid project ID in the format "p1", "p2", etc.
  * If this parameter is not provided, the task will be created in the Inbox.
"""
        },
        "due_date": {
            "type": "string",
            "description": "Optional due date for the task (YYYY-MM-DD)"
        },
        "time_estimate": {
            "type": "string",
            "description": "Optional time estimate in human-readable format (e.g., '30m', '1.5h', '1h 30m')"
        },
        "priority": {
            "type": "string",
            "description": "Optional priority level (1-3, with 3 being highest)"
        }
    },
    "required": ["title"]
}

CREATE_PROJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "The title of the project"
        },
        "parent_id": {
            "type": "string",
            "description": """Optional ID of the parent project (e.g., "p1", "p2") where the task should be created. 
  * Must be a valid project ID in the format "p1", "p2", etc.
  * If this parameter is not provided, the task will be created in the Inbox.
"""
        },
        "due_date": {
            "type": "string",
            "description": "Optional due date for the project (YYYY-MM-DD)"
        },
        "priority": {
            "type": "string",
            "description": "Optional priority level (1-3, with 3 being highest)"
        }
    },
    "required": ["title"]
}

UPDATE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "The friendly ID (t1, t2, etc.) of the task to update"
        },
        "title": {
            "type": "string",
            "description": "New title for the task"
        },
        "parent_id": {
            "type": "string",
            "description": "New parent project friendly ID (p1, p2, etc.)"
        },
        "due_date": {
            "type": "string",
            "description": "New due date for the task (YYYY-MM-DD)"
        },
        "time_estimate": {
            "type": "string",
            "description": "New time estimate in human-readable format (e.g., '30m', '1.5h', '1h 30m')"
        },
        "priority": {
            "type": "string",
            "description": "New priority level (1-3, with 3 being highest)"
        }
    },
    "required": ["task_id"]
}

SCHEDULE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "The friendly ID (t1, t2, etc.) of the task to schedule"
        },
        "day": {
            "type": "string",
            "description": "The day to schedule the task for (YYYY-MM-DD)"
        }
    },
    "required": ["task_id", "day"]
}

GET_DAY_TASKS_SCHEMA = {
    "type": "object",
    "properties": {
        "day": {
            "type": "string",
            "description": "The day to fetch tasks for in YYYY-MM-DD format (e.g., 2025-05-14)."
        }
    },
    "required": ["day"]
}

CREATE_CATEGORY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "The title of the category"
        },
        "parent_id": {
            "type": "string",
            "description": """Optional ID of the parent category or project (e.g., "p1", "p2") where the category should be created. 
  * Must be a valid project/category ID in the format "p1", "p2", etc.
  * If this parameter is not provided, the category will be created at the root level.
"""
        },
        "due_date": {
            "type": "string",
            "description": "Optional due date for the category (YYYY-MM-DD)"
        },
        "priority": {
            "type": "string",
            "description": "Optional priority level (1-3, with 3 being highest)"
        }
    },
    "required": ["title"]
}