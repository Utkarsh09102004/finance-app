#!/usr/bin/env python3
"""
Zoho Books MCP Server - Main Entry Point
"""

from src.mcp.server import mcp

if __name__ == "__main__":
    print("Starting Zoho Books MCP Server...")
    print("Server will be available at http://localhost:8002")
    print("Press Ctrl+C to stop the server")
    
    try:
        mcp.run(transport="streamable-http", port=8002)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")