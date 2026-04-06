from typing import Dict, Any, Optional, List
import asyncio
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_request
from starlette.requests import Request

# Import all report functions
try:
    from ..zoho.api.reports.profit_and_loss import fetch_profit_and_loss
    from ..zoho.api.reports.balance_sheet import fetch_balance_sheet
    from ..zoho.api.reports.cash_flow import fetch_cash_flow
    from ..zoho.api.reports.sales_by_customer import fetch_sales_by_customer
    from ..zoho.api.reports.sales_by_item import fetch_sales_by_item
    from ..zoho.api.reports.ar_aging_summary import fetch_ar_aging_summary
    from ..zoho.api.reports.ap_aging_summary import fetch_ap_aging_summary
    from ..zoho.api.reports.expenses_by_category import fetch_expenses_by_category
    from ..zoho.api.reports.expense_details import fetch_expense_details
    from ..zoho.api.reports.invoice_details import fetch_invoice_details
    from ..zoho.api.reports.payments_made import fetch_payments_made
    from ..zoho.api.reports.payments_received import fetch_payments_received
except ImportError:
    import sys
    import os
    # Get path to FinSync directory
    current_file = os.path.abspath(__file__)
    mcp_dir = os.path.dirname(current_file)
    src_dir = os.path.dirname(mcp_dir)
    server_root = os.path.dirname(src_dir)
    finsync_dir = os.path.dirname(server_root)
    
    sys.path.insert(0, finsync_dir)
    from zoho_books_mcp_server.src.zoho.api.reports.profit_and_loss import fetch_profit_and_loss
    from zoho_books_mcp_server.src.zoho.api.reports.balance_sheet import fetch_balance_sheet
    from zoho_books_mcp_server.src.zoho.api.reports.cash_flow import fetch_cash_flow
    from zoho_books_mcp_server.src.zoho.api.reports.sales_by_customer import fetch_sales_by_customer
    from zoho_books_mcp_server.src.zoho.api.reports.sales_by_item import fetch_sales_by_item
    from zoho_books_mcp_server.src.zoho.api.reports.ar_aging_summary import fetch_ar_aging_summary
    from zoho_books_mcp_server.src.zoho.api.reports.ap_aging_summary import fetch_ap_aging_summary
    from zoho_books_mcp_server.src.zoho.api.reports.expenses_by_category import fetch_expenses_by_category
    from zoho_books_mcp_server.src.zoho.api.reports.expense_details import fetch_expense_details
    from zoho_books_mcp_server.src.zoho.api.reports.invoice_details import fetch_invoice_details
    from zoho_books_mcp_server.src.zoho.api.reports.payments_made import fetch_payments_made
    from zoho_books_mcp_server.src.zoho.api.reports.payments_received import fetch_payments_received

mcp = FastMCP("finsync-tools")

# --- Helper function to make this logic reusable ---
def get_zoho_credentials() -> tuple[str, str]:
    """
    Extracts Zoho credentials from the current HTTP request headers.
    This is a reusable helper to avoid repeating logic in every tool.
    """
    try:
        request: Request = get_http_request()
    except RuntimeError:
        # This will happen if the tool is called outside an HTTP request context
        raise ToolError("This tool can only be used via an HTTP server.")

    # 1. Get the Access Token from the 'Authorization' header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ToolError("Authorization header with Bearer token is missing or invalid.")
    access_token = auth_header.split("Bearer ")[1]

    # 2. Get the Organization ID from a custom header (e.g., 'X-Zoho-Organization-ID')
    organization_id = request.headers.get("X-Zoho-Organization-ID")
    if not organization_id:
        raise ToolError("X-Zoho-Organization-ID header is missing.")

    return access_token, organization_id


@mcp.tool
async def get_profit_and_loss(
    date_ranges: List[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves comprehensive profit and loss statements from for multiple date ranges.
    
    This tool fetches detailed P&L reports showing revenue, expenses, and profitability metrics.
    Each report includes hierarchical account breakdowns for operating income, cost of goods sold,
    operating expenses, and non-operating items.
    
    Args:
        date_ranges: List of date range dictionaries, each containing:
            - from_date (str): Start date in YYYY-MM-DD format
            - to_date (str): End date in YYYY-MM-DD format
            Example: [{"from_date": "2024-01-01", "to_date": "2024-03-31"}]
    
    Returns:
        List of structured P&L data for each date range, each containing:
            - report_metadata: Report context (dates, basis, currency)
            - summary: Key figures (gross_profit, operating_profit, net_profit_loss)
            - income_details: Operating income breakdown by account
            - cogs_details: Cost of goods sold breakdown
            - expense_details: Operating expense breakdown by category
            - non_operating_details: Other income/expense items
    
 
    
    Example Response Structure:
        {
            "report_metadata": {
                "from_date": "2024-01-01",
                "to_date": "2024-03-31",
                "report_basis": "Accrual"
            },
            "summary": {
                "gross_profit": 150000.0,
                "operating_profit": 100000.0,
                "net_profit_loss": 95000.0
            },
            "income_details": {...},
            "expense_details": {...}
        }
    """
    if not date_ranges:
        return []

    # Get credentials for this specific request
    access_token, organization_id = get_zoho_credentials()

    tasks = []
    for date_range in date_ranges:
        from_date, to_date = date_range.get("from_date"), date_range.get("to_date")
        if from_date and to_date:
            # Pass the retrieved credentials to your API-calling function
            task = asyncio.to_thread(
                fetch_profit_and_loss,
                organization_id,
                from_date,
                to_date,
                access_token=access_token 
            )
            tasks.append(task)
    
    if not tasks:
        return []

    all_results = await asyncio.gather(*tasks)
    return all_results

@mcp.tool
async def get_balance_sheet(
    as_of_dates: List[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves comprehensive balance sheet reports from Zoho Books API for multiple dates.
    
    This tool fetches detailed balance sheets showing the financial position at specific points in time.
    Reports include hierarchical breakdowns of assets, liabilities, and equity with account-level details.
    
    Args:
        as_of_dates: List of dates for balance sheets in YYYY-MM-DD format.
                     Each date represents the "as of" date for that balance sheet snapshot.
                     Example: ["2024-12-31", "2024-06-30", "2024-03-31"]
    
    Returns:
        List of structured balance sheet data for each date, each containing:
            - report_metadata: Report context (as_of_date, basis, currency)
            - summary: Total figures (total_assets, total_liabilities, total_equity)
            - assets: Detailed breakdown including:
                - current_assets: Cash, bank, accounts receivable, other current
                - fixed_assets: Property, equipment, accumulated depreciation
                - other_assets: Long-term investments, intangibles
            - liabilities: Detailed breakdown including:
                - current_liabilities: Accounts payable, short-term debt
                - long_term_liabilities: Long-term debt, deferred items
                - other_liabilities: Other payables
            - equity: Owner's equity, retained earnings, current year earnings
    
    Authentication:
        Requires HTTP headers:
        - Authorization: Bearer <access_token>
        - X-Zoho-Organization-ID: <organization_id>
    
    Example Response Structure:
        {
            "report_metadata": {
                "as_of_date": "2024-12-31",
                "report_basis": "Accrual"
            },
            "summary": {
                "total_assets": 500000.0,
                "total_liabilities": 200000.0,
                "total_equity": 300000.0
            },
            "assets": {
                "current_assets": {...},
                "fixed_assets": {...}
            },
            "liabilities": {...},
            "equity": {...}
        }
    
    Note: The balance sheet equation (Assets = Liabilities + Equity) is validated in the response.
    """
    if not as_of_dates:
        return []

    # Get credentials for this specific request
    access_token, organization_id = get_zoho_credentials()

    tasks = []
    for as_of_date in as_of_dates:
        if as_of_date:
            # Pass the retrieved credentials to your API-calling function
            task = asyncio.to_thread(
                fetch_balance_sheet,
                organization_id,
                as_of_date,
                # You'll likely need to modify fetch_balance_sheet to accept the token
                # access_token=access_token 
            )
            tasks.append(task)
    
    if not tasks:
        return []

    all_results = await asyncio.gather(*tasks)
    return all_results

@mcp.tool
async def get_cash_flow(
    date_ranges: List[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieves comprehensive cash flow statements from Zoho Books API for multiple date ranges.
    
    This tool fetches detailed cash flow reports showing how cash moves through the business
    via operating, investing, and financing activities. Essential for understanding liquidity
    and cash management.
    
    Args:
        date_ranges: List of date range dictionaries, each containing:
            - from_date (str): Start date in YYYY-MM-DD format
            - to_date (str): End date in YYYY-MM-DD format
            Example: [{"from_date": "2024-01-01", "to_date": "2024-03-31"}]
    
    Returns:
        List of structured cash flow data for each date range, each containing:
            - report_metadata: Report context (dates, basis, currency)
            - summary: Key figures including:
                - beginning_cash_balance: Cash at start of period
                - net_change_in_cash: Total cash flow for period
                - ending_cash_balance: Cash at end of period
            - operating_activities: Cash from business operations
                - net_income: Profit/loss for the period
                - adjustments: Non-cash items (depreciation, working capital changes)
                - total: Net cash from operations
            - investing_activities: Cash from investments
                - activities: Purchase/sale of assets, investments
                - total: Net cash from investing
            - financing_activities: Cash from financing
                - activities: Loans, equity, dividends
                - total: Net cash from financing
    
    Authentication:
        Requires HTTP headers:
        - Authorization: Bearer <access_token>
        - X-Zoho-Organization-ID: <organization_id>
    
    Example Response Structure:
        {
            "report_metadata": {
                "from_date": "2024-01-01",
                "to_date": "2024-03-31"
            },
            "summary": {
                "beginning_cash_balance": 100000.0,
                "net_change_in_cash": 25000.0,
                "ending_cash_balance": 125000.0
            },
            "operating_activities": {
                "net_income": 50000.0,
                "adjustments": [...],
                "total": 40000.0
            }
        }
    
    Note: Cash flow uses the indirect method, starting with net income and adjusting for non-cash items.
    """
    if not date_ranges:
        return []

    access_token, organization_id = get_zoho_credentials()

    tasks = []
    for date_range in date_ranges:
        from_date, to_date = date_range.get("from_date"), date_range.get("to_date")
        if from_date and to_date:
            task = asyncio.to_thread(
                fetch_cash_flow,
                organization_id,
                from_date,
                to_date,
                access_token=access_token
            )
            tasks.append(task)
    
    if not tasks:
        return []

    all_results = await asyncio.gather(*tasks)
    return all_results

# @mcp.tool
# async def get_sales_by_customer(
#     from_date: str,
#     to_date: str
# ) -> Dict[str, Any]:
#     """
#     Retrieves detailed sales analytics grouped by customer from Zoho Books API.
    
#     This tool provides comprehensive customer-wise sales analysis, helping identify
#     top customers, revenue concentration, and customer performance metrics. Includes
#     both invoices and credit notes for accurate net sales figures.
    
#     Args:
#         from_date (str): Start date in YYYY-MM-DD format
#         to_date (str): End date in YYYY-MM-DD format
    
#     Returns:
#         Structured sales data containing:
#             - report_metadata: Report context including:
#                 - Date range and pagination info
#                 - Currency and entity types included
#             - summary: Aggregate statistics:
#                 - total_customers: Number of customers with sales
#                 - total_sales: Total revenue amount
#                 - total_sales_with_tax: Total including taxes
#                 - total_transactions: Total number of invoices/credit notes
#                 - average_sales_per_customer: Mean revenue per customer
#                 - average_transactions_per_customer: Mean transaction count
#             - customers: List of customer records, each containing:
#                 - customer_name: Business/individual name
#                 - customer_id: Unique identifier
#                 - transaction_count: Number of sales transactions
#                 - sales: Net sales amount
#                 - sales_with_tax: Gross sales including tax
#                 - sales_percentage: Percentage of total sales
#                 - currency_code: Transaction currency
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_customers": 25,
#                 "total_sales": 500000.0,
#                 "average_sales_per_customer": 20000.0
#             },
#             "customers": [
#                 {
#                     "customer_name": "ABC Corp",
#                     "sales": 150000.0,
#                     "sales_percentage": 30.0,
#                     "transaction_count": 15
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Identify top revenue-generating customers
#         - Analyze customer concentration risk
#         - Track customer purchase patterns
#         - Support sales team performance analysis
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_sales_by_customer,
#         organization_id,
#         from_date,
#         to_date
#     )
    
#     return result

# @mcp.tool
# async def get_sales_by_item(
#     from_date: str,
#     to_date: str
# ) -> Dict[str, Any]:
#     """
#     Retrieves detailed sales analytics grouped by item/product from Zoho Books API.
    
#     This tool provides comprehensive product-wise sales analysis, helping identify
#     best-selling items, pricing trends, and inventory movement patterns. Essential
#     for product portfolio management and pricing strategy.
    
#     Args:
#         from_date (str): Start date in YYYY-MM-DD format
#         to_date (str): End date in YYYY-MM-DD format
    
#     Returns:
#         Structured sales data containing:
#             - report_metadata: Report context including:
#                 - Date range and pagination info
#                 - Currency and entity types included
#             - summary: Aggregate statistics:
#                 - total_items: Number of unique items sold
#                 - total_quantity_sold: Total units sold across all items
#                 - total_sales_amount: Total revenue from all items
#                 - average_sales_per_item: Mean revenue per item type
#                 - average_quantity_per_item: Mean units sold per item
#                 - weighted_average_price: Overall average selling price
#                 - top_5_items_sales_percentage: Revenue concentration in top 5 items
#             - items: List of item records sorted by revenue, each containing:
#                 - item_id: Unique product identifier
#                 - item_name: Product/service name
#                 - unit: Unit of measurement (if applicable)
#                 - is_combo_product: Boolean for bundled products
#                 - quantity_sold: Total units sold
#                 - total_sales: Revenue generated
#                 - average_price: Average selling price per unit
#                 - sales_percentage: Percentage of total sales
#                 - quantity_percentage: Percentage of total quantity
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_items": 15,
#                 "total_quantity_sold": 1000,
#                 "total_sales_amount": 250000.0,
#                 "top_5_items_sales_percentage": 75.5
#             },
#             "items": [
#                 {
#                     "item_name": "Premium Widget",
#                     "quantity_sold": 150,
#                     "total_sales": 75000.0,
#                     "average_price": 500.0,
#                     "sales_percentage": 30.0
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Identify best-selling products
#         - Analyze product profitability
#         - Track pricing effectiveness
#         - Optimize inventory management
#         - Support product discontinuation decisions
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_sales_by_item,
#         organization_id,
#         from_date,
#         to_date
#     )
    
#     return result

# @mcp.tool
# async def get_ar_aging_summary(
#     as_of_date: Optional[str] = None
# ) -> Dict[str, Any]:
#     """
#     Retrieves comprehensive accounts receivable aging analysis from Zoho Books API.
    
#     This tool provides detailed aging analysis of outstanding customer invoices,
#     categorized by age intervals. Critical for credit management, collection
#     prioritization, and cash flow forecasting.
    
#     Args:
#         as_of_date (str, optional): Reference date for aging calculation in YYYY-MM-DD format.
#                                    Defaults to today if not specified.
    
#     Returns:
#         Structured AR aging data containing:
#             - report_metadata: Report context including:
#                 - as_of_date: Date used for aging calculation
#                 - interval_type: Time unit (days)
#                 - currency and pagination info
#             - summary: Overall receivables statistics:
#                 - total_outstanding: Total receivables amount
#                 - total_overdue: Amount past due date
#                 - current_amount: Not yet due
#                 - aging_brackets: Amounts in each interval
#                 - customer_count: Number of customers with receivables
#                 - average_days_outstanding: Weighted average age
#             - customers: List of customers with outstanding invoices:
#                 - customer_name: Business/individual name
#                 - customer_id: Unique identifier
#                 - total_outstanding: Total owed by customer
#                 - current: Amount not yet due
#                 - overdue: Total past due amount
#                 - aging_intervals: Breakdown by age bracket:
#                     - 0-30 days overdue
#                     - 31-60 days overdue
#                     - 61-90 days overdue
#                     - 90+ days overdue
#                 - oldest_invoice_days: Age of oldest unpaid invoice
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_outstanding": 150000.0,
#                 "total_overdue": 45000.0,
#                 "aging_brackets": {
#                     "current": 105000.0,
#                     "1-30_days": 20000.0,
#                     "31-60_days": 15000.0,
#                     "61-90_days": 5000.0,
#                     "over_90_days": 5000.0
#                 }
#             },
#             "customers": [
#                 {
#                     "customer_name": "ABC Corp",
#                     "total_outstanding": 50000.0,
#                     "overdue": 15000.0,
#                     "aging_intervals": {...}
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Prioritize collection efforts
#         - Assess credit risk by customer
#         - Calculate bad debt provisions
#         - Monitor DSO (Days Sales Outstanding)
#         - Support credit limit decisions
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_ar_aging_summary,
#         organization_id,
#         as_of_date
#     )
    
#     return result

# @mcp.tool
# async def get_ap_aging_summary(
#     as_of_date: Optional[str] = None
# ) -> Dict[str, Any]:
#     """
#     Retrieves comprehensive accounts payable aging analysis from Zoho Books API.
    
#     This tool provides detailed aging analysis of outstanding vendor bills,
#     categorized by age intervals. Essential for cash flow management, payment
#     prioritization, and vendor relationship management.
    
#     Args:
#         as_of_date (str, optional): Reference date for aging calculation in YYYY-MM-DD format.
#                                    Defaults to today if not specified.
    
#     Returns:
#         Structured AP aging data containing:
#             - report_metadata: Report context including:
#                 - as_of_date: Date used for aging calculation
#                 - interval_type: Time unit (days)
#                 - currency and pagination info
#             - summary: Overall payables statistics:
#                 - total_outstanding: Total payables amount
#                 - total_overdue: Amount past due date
#                 - current_amount: Not yet due
#                 - aging_brackets: Amounts in each interval
#                 - vendor_count: Number of vendors with payables
#                 - average_days_outstanding: Weighted average age
#             - vendors: List of vendors with outstanding bills:
#                 - vendor_name: Business name
#                 - vendor_id: Unique identifier
#                 - total_outstanding: Total owed to vendor
#                 - current: Amount not yet due
#                 - overdue: Total past due amount
#                 - aging_intervals: Breakdown by age bracket:
#                     - 0-30 days overdue
#                     - 31-60 days overdue
#                     - 61-90 days overdue
#                     - 90+ days overdue
#                 - oldest_bill_days: Age of oldest unpaid bill
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_outstanding": 80000.0,
#                 "total_overdue": 20000.0,
#                 "aging_brackets": {
#                     "current": 60000.0,
#                     "1-30_days": 10000.0,
#                     "31-60_days": 5000.0,
#                     "61-90_days": 3000.0,
#                     "over_90_days": 2000.0
#                 }
#             },
#             "vendors": [
#                 {
#                     "vendor_name": "XYZ Supplies",
#                     "total_outstanding": 25000.0,
#                     "overdue": 5000.0,
#                     "aging_intervals": {...}
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Prioritize vendor payments
#         - Manage cash outflows
#         - Negotiate payment terms
#         - Maintain vendor relationships
#         - Plan working capital needs
#         - Identify early payment discount opportunities
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_ap_aging_summary,
#         organization_id,
#         as_of_date
#     )
    
#     return result

# @mcp.tool
# async def get_expenses_by_category(
#     from_date: str,
#     to_date: str
# ) -> Dict[str, Any]:
#     """
#     Retrieves comprehensive expense analytics grouped by category from Zoho Books API.
    
#     This tool provides detailed expense analysis by category, helping identify
#     spending patterns, cost reduction opportunities, and budget variance analysis.
#     Includes all expense types: bills, expenses, and other payments.
    
#     Args:
#         from_date (str): Start date in YYYY-MM-DD format
#         to_date (str): End date in YYYY-MM-DD format
    
#     Returns:
#         Structured expense data containing:
#             - report_metadata: Report context including:
#                 - Date range and pagination info
#                 - Currency and report type
#             - summary: Aggregate expense statistics:
#                 - total_expenses: Total expense amount
#                 - category_count: Number of expense categories
#                 - average_per_category: Mean expense per category
#                 - top_5_categories_percentage: Expense concentration
#             - categories: List of expense categories sorted by amount:
#                 - category_name: Expense category description
#                 - category_id: Unique identifier
#                 - total_amount: Total expenses in category
#                 - expense_percentage: Percentage of total expenses
#                 - transaction_count: Number of transactions
#                 - average_transaction_amount: Mean transaction size
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_expenses": 150000.0,
#                 "category_count": 12,
#                 "top_5_categories_percentage": 78.5
#             },
#             "categories": [
#                 {
#                     "category_name": "Office Supplies",
#                     "total_amount": 35000.0,
#                     "expense_percentage": 23.3,
#                     "transaction_count": 45
#                 },
#                 {
#                     "category_name": "Travel & Entertainment",
#                     "total_amount": 28000.0,
#                     "expense_percentage": 18.7,
#                     "transaction_count": 23
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Identify major expense drivers
#         - Find cost reduction opportunities
#         - Budget vs actual analysis
#         - Department/category spending trends
#         - Expense policy compliance monitoring
#         - Financial planning and forecasting
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_expenses_by_category,
#         organization_id,
#         from_date,
#         to_date
#     )
    
#     return result

# @mcp.tool
# async def get_expense_details(
#     from_date: str,
#     to_date: str
# ) -> Dict[str, Any]:
#     """
#     Retrieves granular expense transaction details from Zoho Books API.
    
#     This tool provides individual expense transaction records with complete details,
#     enabling transaction-level analysis, audit trails, and expense report generation.
#     Includes bills, expenses, and vendor payments.
    
#     Args:
#         from_date (str): Start date in YYYY-MM-DD format
#         to_date (str): End date in YYYY-MM-DD format
    
#     Returns:
#         Structured expense details containing:
#             - report_metadata: Report context including:
#                 - Date range and pagination info
#                 - Total record count
#             - summary: Aggregate transaction statistics:
#                 - total_expenses: Sum of all expenses
#                 - transaction_count: Number of transactions
#                 - vendor_count: Unique vendors
#                 - category_breakdown: Expenses by category
#                 - payment_mode_breakdown: By payment method
#                 - status_breakdown: By transaction status
#             - expenses: List of individual transactions:
#                 - expense_id: Unique transaction identifier
#                 - date: Transaction date
#                 - transaction_type: Bill, expense, payment
#                 - transaction_number: Reference number
#                 - vendor_name: Payee name
#                 - account_name: Expense account/category
#                 - description: Transaction description
#                 - amount: Base amount
#                 - amount_with_tax: Total including tax
#                 - payment_mode: Cash, check, card, etc.
#                 - status: Paid, unpaid, partially paid
#                 - customer_name: If billable to customer
#                 - reference_number: External reference
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_expenses": 85000.0,
#                 "transaction_count": 156,
#                 "category_breakdown": {
#                     "Office Supplies": 15000.0,
#                     "Travel": 25000.0
#                 }
#             },
#             "expenses": [
#                 {
#                     "date": "2024-03-15",
#                     "vendor_name": "ABC Supplies",
#                     "account_name": "Office Supplies",
#                     "amount": 1250.0,
#                     "status": "paid",
#                     "payment_mode": "Credit Card"
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Expense report generation
#         - Transaction audit trails
#         - Vendor payment history
#         - Employee expense tracking
#         - Tax preparation support
#         - Duplicate payment detection
#         - Budget variance analysis at transaction level
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_expense_details,
#         organization_id,
#         from_date,
#         to_date
#     )
    
#     return result

# @mcp.tool
# async def get_invoice_details(
#     from_date: str,
#     to_date: str
# ) -> Dict[str, Any]:
#     """
#     Retrieves comprehensive invoice transaction details from Zoho Books API.
    
#     This tool provides complete invoice records with payment status, customer details,
#     and aging information. Essential for revenue tracking, collection management,
#     and customer account reconciliation.
    
#     Args:
#         from_date (str): Start date in YYYY-MM-DD format (invoice date)
#         to_date (str): End date in YYYY-MM-DD format
    
#     Returns:
#         Structured invoice data containing:
#             - report_metadata: Report context including:
#                 - Date range and pagination info
#                 - Total invoice count
#             - summary: Aggregate invoice statistics:
#                 - total_invoiced: Sum of all invoice amounts
#                 - total_paid: Amount collected
#                 - total_outstanding: Unpaid balance
#                 - invoice_count: Number of invoices
#                 - collection_rate: Percentage collected
#                 - average_invoice_value: Mean invoice amount
#                 - average_days_to_payment: Collection period
#                 - status_breakdown: Count by status (paid, unpaid, partial)
#             - invoices: List of individual invoices:
#                 - invoice_id: Unique identifier
#                 - invoice_number: Document number
#                 - date: Invoice date
#                 - due_date: Payment due date
#                 - customer_name: Buyer name
#                 - customer_id: Customer identifier
#                 - status: sent, paid, unpaid, overdue, partial
#                 - total: Invoice amount
#                 - balance: Outstanding amount
#                 - payment_terms: Net terms (e.g., Net 30)
#                 - reference_number: PO or reference
#                 - currency_code: Transaction currency
#                 - days_overdue: If past due
#                 - last_payment_date: Most recent payment
#                 - payment_made: Amount paid to date
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_invoiced": 500000.0,
#                 "total_outstanding": 125000.0,
#                 "collection_rate": 75.0,
#                 "average_days_to_payment": 28
#             },
#             "invoices": [
#                 {
#                     "invoice_number": "INV-00123",
#                     "date": "2024-03-01",
#                     "customer_name": "ABC Corp",
#                     "total": 25000.0,
#                     "balance": 0.0,
#                     "status": "paid",
#                     "days_overdue": 0
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Revenue recognition reporting
#         - Collection priority lists
#         - Customer payment behavior analysis
#         - Cash flow forecasting
#         - Aging analysis by invoice
#         - Sales tax reporting
#         - Customer statement generation
#         - Bad debt identification
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_invoice_details,
#         organization_id,
#         from_date,
#         to_date
#     )
    
#     return result

# @mcp.tool
# async def get_payments_made(
#     from_date: str,
#     to_date: str
# ) -> Dict[str, Any]:
#     """
#     Retrieves comprehensive vendor payment transaction details from Zoho Books API.
    
#     This tool provides complete records of payments made to vendors, including
#     payment methods, bill references, and bank reconciliation details. Essential
#     for cash flow management, vendor reconciliation, and payment audit trails.
    
#     Args:
#         from_date (str): Start date in YYYY-MM-DD format (payment date)
#         to_date (str): End date in YYYY-MM-DD format
    
#     Returns:
#         Structured payment data containing:
#             - report_metadata: Report context including:
#                 - Date range and pagination info
#                 - Currency information
#             - summary: Aggregate payment statistics:
#                 - total_payments: Sum of all payments
#                 - payment_count: Number of payment transactions
#                 - vendor_count: Unique vendors paid
#                 - average_payment: Mean payment amount
#                 - payment_mode_breakdown: Amounts by payment method
#                 - top_vendors: Largest payment recipients
#             - payments: List of individual payment records:
#                 - payment_id: Unique transaction identifier
#                 - payment_number: Reference number
#                 - date: Payment date
#                 - vendor_name: Payee name
#                 - vendor_id: Vendor identifier
#                 - amount: Payment amount
#                 - payment_mode: Check, ACH, wire, card, cash
#                 - bill_numbers: Associated bill references
#                 - description: Payment description/memo
#                 - paid_through_account: Bank/cash account used
#                 - reference_number: Check number or transaction ID
#                 - status: cleared, uncleared, void
#                 - is_advance_payment: Prepayment indicator
#                 - unused_amount: If advance payment
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_payments": 250000.0,
#                 "payment_count": 85,
#                 "payment_mode_breakdown": {
#                     "Check": 150000.0,
#                     "ACH": 75000.0,
#                     "Credit Card": 25000.0
#                 }
#             },
#             "payments": [
#                 {
#                     "payment_number": "PAY-00456",
#                     "date": "2024-03-15",
#                     "vendor_name": "XYZ Supplies",
#                     "amount": 15000.0,
#                     "payment_mode": "Check",
#                     "reference_number": "1234",
#                     "bill_numbers": "BILL-123, BILL-124"
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Cash disbursement reporting
#         - Vendor payment history
#         - Bank reconciliation
#         - Payment approval audit
#         - Cash flow analysis
#         - Duplicate payment detection
#         - Vendor 1099 reporting
#         - Payment method optimization
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_payments_made,
#         organization_id,
#         from_date,
#         to_date
#     )
    
#     return result

# @mcp.tool
# async def get_payments_received(
#     from_date: str,
#     to_date: str
# ) -> Dict[str, Any]:
#     """
#     Retrieves comprehensive customer payment transaction details from Zoho Books API.
    
#     This tool provides complete records of payments received from customers, including
#     payment methods, invoice applications, and deposit details. Critical for cash
#     position tracking, revenue reconciliation, and collection performance analysis.
    
#     Args:
#         from_date (str): Start date in YYYY-MM-DD format (payment date)
#         to_date (str): End date in YYYY-MM-DD format
    
#     Returns:
#         Structured payment data containing:
#             - report_metadata: Report context including:
#                 - Date range and pagination info
#                 - Currency information
#             - summary: Aggregate receipt statistics:
#                 - total_received: Sum of all receipts
#                 - payment_count: Number of payment transactions
#                 - customer_count: Unique customers who paid
#                 - average_payment: Mean receipt amount
#                 - payment_mode_breakdown: Amounts by payment method
#                 - top_customers: Largest payment sources
#                 - unapplied_amount: Payments not yet applied to invoices
#             - payments: List of individual payment records:
#                 - payment_id: Unique transaction identifier
#                 - payment_number: Receipt number
#                 - date: Payment date
#                 - customer_name: Payer name
#                 - customer_id: Customer identifier
#                 - amount: Total payment amount
#                 - payment_mode: Check, ACH, wire, card, cash, online
#                 - invoice_numbers: Applied invoice references
#                 - description: Payment description/memo
#                 - account_name: Deposit account
#                 - reference_number: Check number or transaction ID
#                 - bank_charges: Processing fees if any
#                 - unused_amount: Unapplied credit balance
#                 - exchange_rate: For foreign currency
#                 - is_advance_payment: Prepayment indicator
    
#     Authentication:
#         Requires HTTP headers:
#         - Authorization: Bearer <access_token>
#         - X-Zoho-Organization-ID: <organization_id>
    
#     Example Response:
#         {
#             "summary": {
#                 "total_received": 450000.0,
#                 "payment_count": 125,
#                 "payment_mode_breakdown": {
#                     "ACH": 300000.0,
#                     "Check": 100000.0,
#                     "Credit Card": 50000.0
#                 },
#                 "unapplied_amount": 5000.0
#             },
#             "payments": [
#                 {
#                     "payment_number": "REC-00789",
#                     "date": "2024-03-20",
#                     "customer_name": "ABC Corp",
#                     "amount": 50000.0,
#                     "payment_mode": "ACH",
#                     "invoice_numbers": "INV-123, INV-124",
#                     "unused_amount": 0.0
#                 }
#             ]
#         }
    
#     Use Cases:
#         - Daily cash receipts reporting
#         - Bank deposit reconciliation
#         - Collection efficiency tracking
#         - Customer payment pattern analysis
#         - Cash application monitoring
#         - Revenue recognition support
#         - Payment processing cost analysis
#         - DSO (Days Sales Outstanding) calculation
#         - Customer credit management
#     """
#     access_token, organization_id = get_zoho_credentials()
    
#     result = await asyncio.to_thread(
#         fetch_payments_received,
#         organization_id,
#         from_date,
#         to_date
#     )
    
#     return result

if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8002)