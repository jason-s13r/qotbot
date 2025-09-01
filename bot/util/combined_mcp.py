import logging
from typing import Any, Dict, List, Sequence, Union
from fastmcp import Client, FastMCP
import mcp

logger = logging.getLogger(__name__)

class CombinedTools(Client):
    """Proxy that delegates method calls to multiple MCP sources"""
    
    def __init__(self, *sources: Union[FastMCP, Client]):
        self._sources: Sequence[Client] = []
        for source in sources:
            if isinstance(source, FastMCP):
                self._sources.append(Client(source))
            elif isinstance(source, Client):
                self._sources.append(source)
            else:
                raise ValueError(f"Unsupported source type: {type(source)}")
    
    async def list_tools(self):
        """Aggregate tools from all sources"""
        tools: List[mcp.Tool] = []
        for source in self._sources:
            try:
                result = await source.list_tools()
                tools.extend(result)
            except Exception as error:
                logger.error(f"Warning: list_tools failed on source {source.name}", error)
        return tools
    
    async def call_tool(self, name: str, parameters: Dict[str, Any]):
        """Try each source until one succeeds"""
        for source in self._sources:
            tools = await source.list_tools_mcp()
            for tool in tools.tools:
                if tool.name == name:
                    return await source.call_tool(name, parameters)
        
        raise ValueError(f"Tool '{name}' not found in any source")
    
    def __getattr__(self, method_name: str):
        """Fallback for other methods - delegate to first available source"""
        for source in self._sources:
            if hasattr(source, method_name):
                return getattr(source, method_name)
        
        raise AttributeError(f"No source has method '{method_name}'")
    
    async def __aenter__(self):
        for source in self._sources:
            if hasattr(source, '__aenter__'):
                await source.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for source in self._sources:
            if hasattr(source, '__aexit__'):
                await source.__aexit__(exc_type, exc_val, exc_tb)