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

You can create tasks with various properties and place them in specific projects.
"""

UPDATE_TASK_DESCRIPTION = """Update an existing task in Amazing Marvin.

You can update any properties of a task using its friendly ID (t1, t2, etc.).
"""

TEST_CONNECTION_DESCRIPTION = """Test the connection to the Amazing Marvin database.

This tool helps verify that the MCP server can communicate with the Amazing Marvin CouchDB database.
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
            "description": "Optional ID of the parent project. Can use a friendly ID (p1, p2, etc.) or the full UUID. Defaults to 'unassigned' (Inbox)."
        },
        "day": {
            "type": "string",
            "description": "Optional day for the task (YYYY-MM-DD)"
        },
        "due_date": {
            "type": "string",
            "description": "Optional due date for the task (YYYY-MM-DD)"
        },
        "time_estimate": {
            "type": "string",
            "description": "Optional time estimate in human-readable format (e.g., '30m', '1.5h', '1h 30m')"
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
            "description": "New parent project ID (can use friendly ID p1, p2, etc.)"
        },
        "done": {
            "type": "boolean",
            "description": "Mark the task as done or not done"
        },
        "day": {
            "type": "string",
            "description": "New day for the task (YYYY-MM-DD)"
        },
        "due_date": {
            "type": "string",
            "description": "New due date for the task (YYYY-MM-DD)"
        },
        "time_estimate": {
            "type": "string",
            "description": "New time estimate in human-readable format (e.g., '30m', '1.5h', '1h 30m')"
        }
    },
    "required": ["task_id"]
}

TEST_CONNECTION_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": []
}