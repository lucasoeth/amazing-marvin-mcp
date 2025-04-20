from mcp.server import Server
import mcp.server.stdio
from mcp import types
import json

from .marvin import MarvinAPI

# Create server
server = Server("amazing-marvin-mcp", "0.1.0")
marvin_api = MarvinAPI()

# Separate functions for each tool implementation
async def handle_list_tasks(arguments: dict) -> list[types.TextContent]:
    """
    Handle the list_tasks tool. Gets the hierarchical structure of projects and tasks.
    """
    try:
        # Get the hierarchical structure instead of just tasks
        hierarchy = marvin_api.build_hierarchy_string()
        
        return [types.TextContent(
            type="text", 
            text=hierarchy
        )]
    except Exception as e:
        error_msg = {"error": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]

async def handle_create_task(arguments: dict) -> list[types.TextContent]:
    """
    Handle the create_task tool. Creates a new task in Amazing Marvin.
    """
    title = arguments.get("title", "")
    parent_id_input = arguments.get("parent_id", "unassigned")
    day = arguments.get("day", None)
    due_date = arguments.get("due_date", None)
    time_estimate_param = arguments.get("time_estimate", None)
    
    # Handle parent_id - convert from friendly ID if needed
    parent_id = parent_id_input
    if parent_id.startswith('p'):
        # It's a friendly ID, get the real UUID
        real_id = marvin_api.get_real_id(parent_id)
        if real_id:
            parent_id = real_id
    
    # Handle time estimate
    time_estimate = None
    if time_estimate_param:
        try:
            time_estimate = int(time_estimate_param)
        except ValueError:
            error_msg = {"error": "time_estimate must be a number in milliseconds"}
            return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]
    
    if not title:
        error_msg = {"error": "Title is required"}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]
    
    try:
        result = marvin_api.create_task(
            title=title,
            parent_id=parent_id,
            day=day,
            due_date=due_date,
            time_estimate=time_estimate
        )
        
        # Get the friendly ID for the newly created task
        task_id = result.get("id", "")
        friendly_id = marvin_api._get_friendly_task_id(task_id)
        
        response = {
            "task": {
                "title": title,
                "id": friendly_id
            },
            "message": f"Task '{title}' created successfully with ID {friendly_id}"
        }
        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]
    except Exception as e:
        error_msg = {"error": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="list_tasks",
            description="""Get the hierarchical structure of projects and tasks from Amazing Marvin.
            
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
}""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="create_task",
            description="Create a new task in Amazing Marvin",
            inputSchema={
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
                        "description": "Optional time estimate in milliseconds"
                    }
                },
                "required": ["title"]
            }
        )
    ]

@server.call_tool()
async def call_tool(
    name: str,
    arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Main dispatcher for tool calls. Delegates to specific handler functions."""
    if name == "list_tasks":
        return await handle_list_tasks(arguments)
    elif name == "create_task":
        return await handle_create_task(arguments)
    else:
        raise ValueError(f"Tool not found: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )