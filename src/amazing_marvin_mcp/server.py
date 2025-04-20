from mcp.server import Server
import mcp.server.stdio
from mcp import types
import json

from .adapter import MarvinAdapter
from .descriptions import (
    LIST_TASKS_DESCRIPTION, CREATE_TASK_DESCRIPTION, 
    CREATE_PROJECT_DESCRIPTION, UPDATE_TASK_DESCRIPTION, 
    SCHEDULE_TASK_DESCRIPTION, 
    LIST_TASKS_SCHEMA, CREATE_TASK_SCHEMA, CREATE_PROJECT_SCHEMA,
    UPDATE_TASK_SCHEMA, SCHEDULE_TASK_SCHEMA
)

# Create server
server = Server("amazing-marvin-mcp", "0.1.0")
marvin_adapter = MarvinAdapter()

# Separate functions for each tool implementation
async def handle_list_tasks(arguments: dict) -> list[types.TextContent]:
    """
    Handle the list_tasks tool. Gets the hierarchical structure of projects and tasks.
    """
    try:
        # Get the hierarchical structure using the adapter
        hierarchy_str = marvin_adapter.build_hierarchy_string()
        
        return [types.TextContent(
            type="text", 
            text=hierarchy_str
        )]
    except Exception as e:
        error_msg = {"error": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]

async def handle_create_task(arguments: dict) -> list[types.TextContent]:
    """
    Handle the create_task tool. Creates a new task in Amazing Marvin.
    """
    title = arguments.get("title", "")
    parent_id = arguments.get("parent_id", "unassigned")
    due_date = arguments.get("due_date", None)
    time_estimate = arguments.get("time_estimate", None)
    
    if not title:
        error_msg = {"error": "Title is required"}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]
    
    try:
        # Use the adapter to create the task with LLM-friendly parameters
        result = marvin_adapter.create_task(
            title=title,
            parent_id=parent_id,
            due_date=due_date,
            time_estimate=time_estimate
        )
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        error_msg = {"error": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]

async def handle_schedule_task(arguments: dict) -> list[types.TextContent]:
    """
    Handle the schedule_task tool. Schedules a task for a specific day.
    """
    task_id = arguments.get("task_id", "")
    day = arguments.get("day", "")
    
    if not task_id:
        error_msg = {"error": "Task ID is required"}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]
    
    if not day:
        error_msg = {"error": "Day is required (format: YYYY-MM-DD)"}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]
    
    try:
        # Use the adapter to schedule the task
        result = marvin_adapter.schedule_task(task_id, day)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        error_msg = {"error": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]

async def handle_create_project(arguments: dict) -> list[types.TextContent]:
    """
    Handle the create_project tool. Creates a new project in Amazing Marvin.
    """
    title = arguments.get("title", "")
    parent_id = arguments.get("parent_id", "unassigned")
    due_date = arguments.get("due_date", None)
    priority = arguments.get("priority", None)
    
    if not title:
        error_msg = {"error": "Title is required"}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]
    
    try:
        # Use the adapter to create the project with LLM-friendly parameters
        result = marvin_adapter.create_project(
            title=title,
            parent_id=parent_id,
            due_date=due_date,
            priority=priority
        )
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        error_msg = {"error": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]

async def handle_update_task(arguments: dict) -> list[types.TextContent]:
    """
    Handle the update_task tool. Updates an existing task in Amazing Marvin.
    """
    task_id = arguments.get("task_id", "")
    
    if not task_id:
        error_msg = {"error": "Task ID is required"}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]
    
    # Create updates dictionary from all other arguments
    updates = {k: v for k, v in arguments.items() if k != "task_id"}
    
    if not updates:
        error_msg = {"error": "No updates provided"}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]
    
    try:
        # Use the adapter to update the task
        result = marvin_adapter.update_task(task_id, updates)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        error_msg = {"error": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_msg, indent=2))]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="list_tasks",
            description=LIST_TASKS_DESCRIPTION,
            inputSchema=LIST_TASKS_SCHEMA
        ),
        types.Tool(
            name="create_task",
            description=CREATE_TASK_DESCRIPTION,
            inputSchema=CREATE_TASK_SCHEMA
        ),
        types.Tool(
            name="create_project",
            description=CREATE_PROJECT_DESCRIPTION,
            inputSchema=CREATE_PROJECT_SCHEMA
        ),
        types.Tool(
            name="update_task",
            description=UPDATE_TASK_DESCRIPTION,
            inputSchema=UPDATE_TASK_SCHEMA
        ),
        types.Tool(
            name="schedule_task",
            description=SCHEDULE_TASK_DESCRIPTION,
            inputSchema=SCHEDULE_TASK_SCHEMA
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
    elif name == "create_project":
        return await handle_create_project(arguments)
    elif name == "update_task":
        return await handle_update_task(arguments)
    elif name == "schedule_task":
        return await handle_schedule_task(arguments)
    else:
        raise ValueError(f"Tool not found: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )