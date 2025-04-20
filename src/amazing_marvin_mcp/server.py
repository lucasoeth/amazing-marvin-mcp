from mcp.server import Server
import mcp.server.stdio
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Create server
server = Server("amazing-marvin-mcp", "0.1.0")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )