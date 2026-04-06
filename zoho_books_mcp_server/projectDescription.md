# Zoho Books MCP Server Project Description

## Overview

The Zoho Books MCP Server is a Model Context Protocol (MCP) server implementation that provides programmatic access to Zoho Books financial data. Built using FastMCP, it exposes Zoho Books API functionality through standardized MCP tools that can be consumed by AI assistants and other MCP clients.

## Architecture

### Core Components

1. **MCP Server (`src/mcp/server.py`)**
   - Built on FastMCP framework
   - Runs as a streamable HTTP server on port 8002
   - Implements authentication via HTTP headers
   - Exposes comprehensive financial reporting tools:
     - `get_profit_and_loss`: Fetches P&L reports for multiple date ranges
     - `get_balance_sheet`: Fetches balance sheet reports for multiple dates
     - `get_cash_flow`: Fetches cash flow statements showing operating, investing, and financing activities
     - `get_sales_by_customer`: Retrieves sales data grouped by customer
     - `get_sales_by_item`: Retrieves sales data grouped by product/item
     - `get_ar_aging_summary`: Shows outstanding customer invoices by age
     - `get_ap_aging_summary`: Shows outstanding vendor bills by age
     - `get_expenses_by_category`: Retrieves expenses grouped by category
     - `get_expense_details`: Fetches detailed expense transactions
     - `get_invoice_details`: Retrieves detailed invoice information
     - `get_payments_made`: Shows vendor payment details
     - `get_payments_received`: Shows customer payment details

2. **Entry Point (`main.py`)**
   - Simple launcher script
   - Starts the MCP server with streamable-http transport
   - Handles graceful shutdown on interrupt

3. **Authentication System (`src/zoho/auth/token_manager.py`)**
   - Implements OAuth 2.0 flow for Zoho Books
   - Features:
     - Browser-based authorization flow
     - Local callback server for OAuth redirect
     - Token persistence in `zoho_tokens.json`
     - Automatic token refresh when expired
     - Support for multiple Zoho data centers

4. **Zoho API Integration (`src/zoho/api/reports/`)**
   
   **Financial Statements:**
   - **Profit & Loss Report** - Operating income, COGS, expenses, net profit with account-level details
   - **Balance Sheet** - Assets, liabilities, equity with nested account structures
   - **Cash Flow Statement** - Operating, investing, and financing activities
   
   **Sales Analytics:**
   - **Sales by Customer** - Revenue breakdown by customer with transaction counts
   - **Sales by Item** - Product performance metrics including quantity and average price
   
   **Receivables & Payables:**
   - **AR Aging Summary** - Customer invoice aging in 30-day intervals
   - **AP Aging Summary** - Vendor bill aging in 30-day intervals
   
   **Expense Management:**
   - **Expenses by Category** - Category-wise expense breakdown
   - **Expense Details** - Individual expense transactions with vendor details
   
   **Transaction Details:**
   - **Invoice Details** - Comprehensive invoice data with status tracking
   - **Payments Made** - Vendor payment records with payment modes
   - **Payments Received** - Customer payment records with invoice references
   
   Each report implementation includes:
   - Data extraction and structuring for AI analysis
   - Summary statistics and calculations
   - Proper error handling and validation

## Authentication Flow

### Initial Setup
1. OAuth flow initiated via `token_manager.py`
2. Opens browser for user authorization
3. Local server captures callback with authorization code
4. Exchanges code for access/refresh tokens
5. Stores tokens in `zoho_tokens.json`

### Runtime Authentication
- MCP server expects credentials in HTTP headers:
  - `Authorization: Bearer <access_token>`
  - `X-Zoho-Organization-ID: <org_id>`
- Helper function `get_zoho_credentials()` extracts these from requests
- Note: Current implementation doesn't pass access token to API functions (commented out)

## Data Flow

1. **Client Request** → MCP Server receives tool invocation via HTTP
2. **Authentication** → Server extracts credentials from headers
3. **API Call** → Server calls appropriate Zoho API function
4. **Data Processing** → Raw JSON response is extracted and structured
5. **Response** → Structured data returned to MCP client

## Dependencies

- `fastmcp>=0.1.0` - MCP server framework
- `starlette>=0.27.0` - ASGI framework (FastMCP dependency)
- `requests>=2.31.0` - HTTP client for Zoho API calls
- `python-dotenv>=1.0.0` - Environment variable management

## Configuration

Environment variables required (in `.env`):
- `ZOHO_CLIENT_ID` - OAuth client ID
- `ZOHO_CLIENT_SECRET` - OAuth client secret
- `ZOHO_REDIRECT_URL` - OAuth callback URL (typically `http://localhost:8000/callback`)
- `ZOHO_ORGANIZATION_ID` - Default organization ID

## Current Limitations

1. **Authentication Gap**: Access token from MCP headers not passed to API functions (uses stored tokens instead)
2. **Fixed API Region**: Hardcoded to Indian data center (`zohoapis.in`)
3. **No Write Operations**: Only read operations are implemented
4. **Limited Error Recovery**: Basic error handling in MCP tools
5. **No Real-time Updates**: Reports are fetched on-demand without caching

## Extension Points

The structure is designed for easy extension:
- Add new report types in `src/zoho/api/reports/`
- Implement transaction APIs in `src/zoho/api/transactions/` (create, update, delete operations)
- Add new MCP tools in `src/mcp/server.py`
- Extend authentication to support multiple regions dynamically
- Add caching layer for frequently accessed reports
- Implement webhook support for real-time updates

## Usage

1. Ensure environment variables are configured
2. Run initial authentication: `python src/zoho/auth/token_manager.py`
3. Start MCP server: `python main.py`
4. Server available at `http://localhost:8002`
5. Send requests with required headers for authentication