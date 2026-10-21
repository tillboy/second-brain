import asyncio
import json
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    params = StdioServerParameters(
        command="docker",
        args=[
            "exec", "-i", "-e", "SECONDBRAIN_DATA_DIR=/data/cortex",
            "-e", "SECONDBRAIN_DB_FILENAME=brain.db", "secondbrain-cortex",
            "python", "-c",
            "import secondbrain.mcp_server as m; from pathlib import Path; from secondbrain.config import load_config; c=load_config(); c.data_dir=Path('/data/cortex'); c.database_filename='brain.db'; m.load_config=lambda: c; E=type('E',(),{'dim':768,'name':'acceptance','embed_documents':lambda self,texts:[[0.0]*768 for _ in texts],'embed_query':lambda self,text:[0.0]*768}); m.make_embedder=lambda cfg:E(); m.run()",
        ],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            key = "codex-repair-2026-10-20"
            if "remember_fact" not in names or "recall_memories" not in names:
                raise RuntimeError(f"required tools missing: {sorted(names)}")
            saved = await session.call_tool(
                "remember_fact",
                {"key": key, "content": "Docker WSL repair acceptance marker", "kind": "fact"},
            )
            recalled = await session.call_tool(
                "recall_memories", {"query": "Docker WSL repair acceptance marker", "limit": 5}
            )
            status = await session.call_tool("index_status", {})
            status_text = status.structuredContent.get("result", "") if status.structuredContent else ""
            if "Files: 0" in status_text:
                raise RuntimeError(f"MCP opened an empty database: {status_text}")
            print(json.dumps({"tools": sorted(names), "saved": saved.model_dump(), "recalled": recalled.model_dump(), "index_status": status.model_dump()}))


asyncio.run(main())
