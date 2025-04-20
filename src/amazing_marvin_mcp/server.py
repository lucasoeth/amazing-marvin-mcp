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
    parent_id = arguments.get("parent_id", "unassigned")
    day = arguments.get("day", None)
    due_date = arguments.get("due_date", None)
    time_estimate_param = arguments.get("time_estimate", None)
    
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
        response = {
            "task": result,
            "message": f"Task '{title}' created successfully"
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
            description="Get the hierarchical structure of projects and tasks from Amazing Marvin",
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
                        "description": "Optional ID of the parent project"
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