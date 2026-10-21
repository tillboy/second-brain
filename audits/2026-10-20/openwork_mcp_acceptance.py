import asyncio
import json
import os
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    params = StdioServerParameters(
        command=r"D:\source\projects\ods-conductor\.venv\Scripts\python.exe",
        args=["-m", "conductor.server"],
        cwd=r"D:\source\projects\ods-conductor",
        env={
            **os.environ,
            "CONDUCTOR_CONFIG": r"D:\source\projects\ods-conductor\config\runtime.toml",
            "CONDUCTOR_ROLE": "operator",
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            policy = await session.call_tool("conductor_policy", {})
            key = "openwork-cortex-2026-10-21"
            saved = await session.call_tool(
                "remember_fact",
                {"key": key, "content": "OpenWork Cortex bridge acceptance marker", "kind": "fact"},
            )
            recalled = await session.call_tool(
                "recall_memories", {"query": "OpenWork Cortex bridge acceptance marker", "limit": 5}
            )
            print(json.dumps({
                "tools": names,
                "policy": policy.model_dump(),
                "saved": saved.model_dump(),
                "recalled": recalled.model_dump(),
            }))


asyncio.run(main())
