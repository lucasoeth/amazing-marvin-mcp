from mcp.server import Server
import mcp.server.stdio
from mcp import types
import json
import logging

from .adapter import (
    MarvinAdapter
)
from .descriptions import (
    LIST_TASKS_DESCRIPTION, CREATE_TASK_DESCRIPTION, 
    CREATE_PROJECT_DESCRIPTION, UPDATE_TASK_DESCRIPTION, 
    SCHEDULE_TASK_DESCRIPTION, GET_DAY_TASKS_DESCRIPTION,
    CREATE_CATEGORY_DESCRIPTION,
    LIST_TASKS_SCHEMA, CREATE_TASK_SCHEMA, CREATE_PROJECT_SCHEMA,
    UPDATE_TASK_SCHEMA, SCHEDULE_TASK_SCHEMA, GET_DAY_TASKS_SCHEMA,
    CREATE_CATEGORY_SCHEMA
)

# Create server
server = Server("amazing-marvin-mcp", "0.1.0")
marvin_adapter = MarvinAdapter()

# Separate functions for each tool implementation
async def handle_list_tasks(arguments: dict) -> list[types.TextContent]:
    """
    Handle the list_tasks tool. Gets the hierarchical structure of projects and tasks.
    """
    # Get the hierarchical structure using the adapter
    hierarchy_str = marvin_adapter.build_hierarchy_string()
    
    return [types.TextContent(
        type="text", 
        text=hierarchy_str
    )]

async def handle_create_task(arguments: dict) -> list[types.TextContent]:
    """
    Handle the create_task tool. Creates a new task in Amazing Marvin.
    """
    title = arguments.get("title", "")
    parent_id = arguments.get("parent_id", "") or "p0"
    due_date = arguments.get("due_date", None)
    time_estimate = arguments.get("time_estimate", None)
    priority = arguments.get("priority", None)
    
    # Use the adapter to create the task with LLM-friendly parameters
    result = marvin_adapter.create_task(
        title=title,
        parent_id=parent_id,
        due_date=due_date,
        time_estimate=time_estimate,
        priority=priority
    )
    
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

async def handle_schedule_task(arguments: dict) -> list[types.TextContent]:
    """
    Handle the schedule_task tool. Schedules a task for a specific day.
    """
    task_id = arguments.get("task_id", "")
    day = arguments.get("day", "")
    
    # Use the adapter to schedule the task
    result = marvin_adapter.schedule_task(task_id, day)
    
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

async def handle_create_project(arguments: dict) -> list[types.TextContent]:
    """
    Handle the create_project tool. Creates a new project in Amazing Marvin.
    """
    title = arguments.get("title", "")
    parent_id = arguments.get("parent_id", "") or "p0"
    due_date = arguments.get("due_date", None)
    priority = arguments.get("priority", None)
    
    # Use the adapter to create the project with LLM-friendly parameters
    result = marvin_adapter.create_project(
        title=title,
        parent_id=parent_id,
        due_date=due_date,
        priority=priority
    )
    
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

async def handle_update_task(arguments: dict) -> list[types.TextContent]:
    """
    Handle the update_task tool. Updates an existing task in Amazing Marvin.
    """
    task_id = arguments.get("task_id", "")
    title = arguments.get("title", None)
    parent_id = arguments.get("parent_id", None)
    due_date = arguments.get("due_date", None)
    time_estimate = arguments.get("time_estimate", None)
    priority = arguments.get("priority", None)
    
    # Use the adapter to update the task with explicit parameters
    try:
        result = marvin_adapter.update_task(
            task_id=task_id,
            title=title,
            parent_id=parent_id,
            due_date=due_date,
            time_estimate=time_estimate,
            priority=priority
        )
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        error_message = {
            "error": str(e),
            "message": "Failed to update task"
        }
        return [types.TextContent(type="text", text=json.dumps(error_message, indent=2))]

async def handle_get_day_tasks(arguments: dict) -> list[types.TextContent]:
    """
    Handle the get_day_tasks tool. Gets all tasks scheduled for a specific day.
    """
    day = arguments.get("day", "")
    
    try:
        # Use the adapter to get the day's tasks
        day_tasks_str = marvin_adapter.get_day_tasks(day=day)
        
        return [types.TextContent(type="text", text=day_tasks_str)]
    except Exception as e:
        error_message = {
            "error": str(e),
            "message": f"Failed to get tasks for day: {day}"
        }
        return [types.TextContent(type="text", text=json.dumps(error_message, indent=2))]

async def handle_create_category(arguments: dict) -> list[types.TextContent]:
    """
    Handle the create_category tool. Creates a new category in Amazing Marvin.
    """
    title = arguments.get("title", "")
    parent_id = arguments.get("parent_id", "") 
    due_date = arguments.get("due_date", None)
    priority = arguments.get("priority", None)
    
    # Use the adapter to create the category with LLM-friendly parameters
    try:
        result = marvin_adapter.create_category(
            title=title,
            parent_id=parent_id,
            due_date=due_date,
            priority=priority
        )
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        error_message = {
            "error": str(e),
            "message": "Failed to create category"
        }
        return [types.TextContent(type="text", text=json.dumps(error_message, indent=2))]

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
        ),
        types.Tool(
            name="get_day_tasks",
            description=GET_DAY_TASKS_DESCRIPTION,
            inputSchema=GET_DAY_TASKS_SCHEMA
        ),
        types.Tool(
            name="create_category",
            description=CREATE_CATEGORY_DESCRIPTION,
            inputSchema=CREATE_CATEGORY_SCHEMA
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
    elif name == "get_day_tasks":
        return await handle_get_day_tasks(arguments)
    elif name == "create_category":
        return await handle_create_category(arguments)
    else:
        raise ValueError(f"Tool not found: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )