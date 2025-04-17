import os
import logging
import uvicorn
from core import mcp

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    protocol = os.getenv("MCP_PROTOCOL", "stdio").lower()
    logger.error(f"Starting MCP Coco Database Server in {protocol} mode")
    if protocol == "sse":
        host = os.getenv("MCP_SSE_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_SSE_PORT", "8000"))
        uvicorn.run(app=mcp.sse_app(), host=host, port=port)
    else:
        mcp.run() 