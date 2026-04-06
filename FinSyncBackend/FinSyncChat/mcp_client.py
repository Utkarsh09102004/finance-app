import os
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional

import litellm
from litellm import experimental_mcp_client

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from FinSyncIntegrations.models import Integration
from FinSyncIntegrations.providers.zohobooks.utils import get_valid_access_token

logger = logging.getLogger(__name__)


class FinSyncMCPClient:
    """
    MCP client for connecting to financial data sources like Zoho Books
    """
    
    def __init__(self, organization):
        self.organization = organization
        self.mcp_session = None
        self.tools_cache = None
        self.server_url = "http://localhost:8002"  # Zoho Books MCP server
        
    async def get_zoho_credentials(self) -> Dict[str, str]:
        """
        Get Zoho credentials from existing integration
        """
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_credentials():
            integration = Integration.objects.filter(
                organization=self.organization,
                provider='zohobooks',
                connection_status__in=['Connected', 'NeedsReauth']
            ).first()
            
            if not integration:
                raise ValueError(f"No Zoho Books integration found for organization {self.organization.name}")
            
            # Use existing token refresh logic from FinSyncIntegrations
            access_token = get_valid_access_token(integration)
            
            if not access_token:
                raise ValueError("Unable to get valid access token for Zoho Books")
            
            return {
                "access_token": access_token,
                "organization_id": integration.external_id,
                "integration_id": str(integration.id)
            }
        
        try:
            return await get_credentials()
        except Exception as e:
            logger.error(f"Failed to get Zoho credentials for {self.organization.name}: {e}")
            raise
    
    async def initialize(self):
        """
        Initialize connection to MCP server
        """
        try:
            await self._refresh_credentials()
            logger.info(f"Initialized MCP client for organization {self.organization.name}")
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            raise

    async def _refresh_credentials(self):
        """Fetch latest Zoho credentials and rebuild transport factory"""
        credentials = await self.get_zoho_credentials()

        logger.info(
            "Refreshing MCP transport for org %s (token length=%s)",
            self.organization.name,
            len(credentials.get('access_token') or '')
        )

        self.transport_factory = lambda: streamablehttp_client(
            url=f"{self.server_url}/mcp",
            headers={
                "Authorization": f"Bearer {credentials['access_token']}",
                "X-Zoho-Organization-ID": credentials['organization_id'],
            },
        )
        self.credentials = credentials

    async def __aenter__(self):
        """Async context manager entry"""
        if not hasattr(self, 'transport_factory'):
            await self.initialize()
        else:
            # Ensure we always use the freshest Zoho access token
            await self._refresh_credentials()
            
        try:
            # Create transport instance
            self.transport = self.transport_factory()
            
            # The streamablehttp_client returns a context manager
            transport_result = await self.transport.__aenter__()
            
            # Log what we received for debugging
            logger.info(f"Transport __aenter__ returned: {type(transport_result)}")
            
            # Try to handle it properly based on what was returned
            if isinstance(transport_result, tuple):
                if len(transport_result) == 2:
                    read_stream, write_stream = transport_result
                elif len(transport_result) == 3:
                    # StreamableHTTP returns (read_stream, write_stream, get_session_id)
                    read_stream, write_stream, _ = transport_result
                else:
                    raise ValueError(f"Expected 2 or 3-tuple from transport, got {len(transport_result)} items")
            else:
                # Maybe the transport returns a single object that we need to use for both read/write
                read_stream = write_stream = transport_result
                
            # Create and initialize MCP session
            self.mcp_session = ClientSession(read_stream, write_stream)
            await self.mcp_session.__aenter__()
            await self.mcp_session.initialize()
            
            # Store the transport result for cleanup
            self.transport_conn = transport_result
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP session: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            raise
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        try:
            if self.mcp_session:
                await self.mcp_session.__aexit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            logger.error(f"Error closing MCP session: {e}")
        
        try:
            if hasattr(self, 'transport'):
                await self.transport.__aexit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            logger.error(f"Error closing transport: {e}")
    
    async def load_tools(self) -> List[Dict[str, Any]]:
        """
        Load available tools from MCP server in OpenAI format
        """
        if not self.mcp_session:
            raise RuntimeError("MCP session not initialized. Use as async context manager.")
        
        if self.tools_cache is None:
            try:
                self.tools_cache = await experimental_mcp_client.load_mcp_tools(
                    session=self.mcp_session,
                    format="openai",
                )
                logger.info(f"Loaded {len(self.tools_cache)} tools from MCP server")
                
            except Exception as e:
                logger.error(f"Failed to load tools from MCP server: {e}")
                raise
        
        return self.tools_cache
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a specific tool on the MCP server
        """
        if not self.mcp_session:
            raise RuntimeError("MCP session not initialized. Use as async context manager.")
        
        try:
            # Create a mock tool call object that matches OpenAI's structure
            from litellm.types.utils import ChatCompletionMessageToolCall
            from litellm.types.utils import Function
            
            # Create function object
            function = Function(
                name=tool_name,
                arguments=json.dumps(arguments)
            )
            
            # Create tool call object
            tool_call = ChatCompletionMessageToolCall(
                id=f"call_{tool_name}_{hash(json.dumps(arguments))}",
                type="function",
                function=function
            )
            
            logger.info(f"Calling MCP tool: {tool_name}")
            logger.info(f"Tool call object: {tool_call}")
            
            result = await experimental_mcp_client.call_openai_tool(
                session=self.mcp_session,
                openai_tool=tool_call
            )
            
            logger.info(f"Raw MCP result type: {type(result)}")
            logger.info(f"Raw MCP result: {result}")
            
            # Convert MCP result to dict if needed
            if result is None:
                logger.warning(f"Tool {tool_name} returned None")
                return {"result": f"Tool {tool_name} returned no data. This might indicate an authentication issue or no data available."}
            
            if hasattr(result, 'content'):
                # If result has content attribute, extract it
                if isinstance(result.content, list) and len(result.content) > 0:
                    # Handle list of content items
                    content_item = result.content[0]
                    if hasattr(content_item, 'text'):
                        return {"result": content_item.text}
                    else:
                        return {"result": str(content_item)}
                else:
                    return {"result": str(result.content)}
            else:
                # Return as-is if already a dict
                return result if isinstance(result, dict) else {"result": str(result)}
            
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}")
            raise
    
    async def list_available_tools(self) -> List[str]:
        """
        Get list of available tool names
        """
        tools = await self.load_tools()
        return [tool.get('function', {}).get('name', 'unknown') for tool in tools]
    
    async def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific tool
        """
        tools = await self.load_tools()
        for tool in tools:
            if tool.get('function', {}).get('name') == tool_name:
                return tool
        return None


class MCPClientManager:
    """
    Manages MCP client instances for different organizations
    """
    
    _instances: Dict[int, FinSyncMCPClient] = {}
    
    @classmethod
    async def get_client(cls, organization) -> FinSyncMCPClient:
        """
        Get or create MCP client for organization
        """
        org_id = organization.id
        
        if org_id not in cls._instances:
            cls._instances[org_id] = FinSyncMCPClient(organization)
        
        return cls._instances[org_id]
    
    @classmethod
    async def cleanup_client(cls, organization):
        """
        Clean up MCP client for organization
        """
        org_id = organization.id
        if org_id in cls._instances:
            # Client will be cleaned up when context manager exits
            del cls._instances[org_id]
    
    @classmethod
    async def health_check(cls, organization) -> bool:
        """
        Check if MCP server is accessible for organization
        """
        try:
            async with cls.get_client(organization) as client:
                tools = await client.load_tools()
                return len(tools) > 0
        except Exception as e:
            logger.warning(f"MCP health check failed for {organization.name}: {e}")
            return False


# Utility functions for integration with existing codebase
async def get_mcp_client_for_organization(organization) -> FinSyncMCPClient:
    """
    Convenience function to get MCP client for organization
    """
    return await MCPClientManager.get_client(organization)


async def test_mcp_connection(organization) -> Dict[str, Any]:
    """
    Test MCP connection and return status info
    """
    try:
        client = await get_mcp_client_for_organization(organization)
        async with client:
            tools = await client.list_available_tools()
            
            return {
                "status": "connected",
                "tools_available": len(tools),
                "tool_names": tools,
                "server_url": client.server_url,
                "organization_id": client.credentials.get('organization_id'),
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "tools_available": 0,
            "tool_names": [],
        }
