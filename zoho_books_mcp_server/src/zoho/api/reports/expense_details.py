import os
import requests
import json
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional

# Handle both package import and direct execution
try:
    from ...auth.token_manager import get_valid_access_token
except ImportError:
    import sys
    import os
    # Get the path to the zoho_books_mcp_server directory
    current_file = os.path.abspath(__file__)
    reports_dir = os.path.dirname(current_file)
    api_dir = os.path.dirname(reports_dir)
    zoho_dir = os.path.dirname(api_dir)
    src_dir = os.path.dirname(zoho_dir)
    server_root = os.path.dirname(src_dir)
    
    # Add parent of zoho_books_mcp_server to path
    sys.path.insert(0, os.path.dirname(server_root))
    
    # Now import using the full path from FinSync directory
    from zoho_books_mcp_server.src.zoho.auth.token_manager import get_valid_access_token

def extract_expense_details_data(expense_json_data):
    """
    Extracts relevant Expense Details information from the provided JSON structure.
    
    Args:
        expense_json_data (dict): A dictionary containing the expense details report JSON data.
        
    Returns:
        dict: A dictionary structured for potential AI analysis, containing:
              - report_metadata: Context about the report (dates, pagination info).
              - summary: Aggregate statistics across all expenses.
              - expenses: Detailed data for each expense transaction.
    """
    if expense_json_data.get("code") != 0 or not expense_json_data.get("expense_details"):
        print("Error or no expense data found in JSON.")
        return None

    expense_data = expense_json_data["expense_details"]
    page_context = expense_json_data.get("page_context", {})

    # Calculate summary statistics
    total_amount = sum(expense.get("total", 0.0) for expense in expense_data)
    
    # Group expenses by category for summary
    category_totals = {}
    for expense in expense_data:
        category = expense.get("account_name", "Uncategorized")
        category_totals[category] = category_totals.get(category, 0.0) + expense.get("total", 0.0)
    
    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "expense_details"),
            "from_date": page_context.get("from_date"),
            "to_date": page_context.get("to_date"),
            "page": page_context.get("page", 1),
            "per_page": page_context.get("per_page", 200),
            "has_more_pages": page_context.get("has_more_page", False),
            "currency": "INR"  # Default currency
        },
        "summary": {
            "total_expenses": len(expense_data),
            "total_amount": total_amount,
            "average_expense_amount": total_amount / len(expense_data) if expense_data else 0,
            "categories_count": len(category_totals),
            "category_breakdown": [
                {"category": cat, "total": amt, "percentage": (amt / total_amount * 100) if total_amount > 0 else 0}
                for cat, amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
            ]
        },
        "expenses": []
    }

    # Process individual expense data
    for expense in expense_data:
        expense_info = {
            "expense_id": expense.get("expense_id"),
            "expense_date": expense.get("expense_date"),
            "expense_number": expense.get("expense_number"),
            "vendor_name": expense.get("vendor_name"),
            "vendor_id": expense.get("vendor_id"),
            "category_name": expense.get("account_name"),
            "category_id": expense.get("account_id"),
            "description": expense.get("description"),
            "reference_number": expense.get("reference_number"),
            "payment_mode": expense.get("payment_mode"),
            "status": expense.get("status"),
            "total_amount": expense.get("total", 0.0),
            "currency_code": expense.get("currency_code", "INR"),
            "expense_type": expense.get("expense_type", "expense")  # Could be expense or bill
        }
        
        extracted_data["expenses"].append(expense_info)

    # Sort expenses by date in descending order (most recent first)
    extracted_data["expenses"].sort(key=lambda x: x["expense_date"], reverse=True)

    return extracted_data

def fetch_expense_details(organization_id=None, from_date=None, to_date=None, access_token=None):
    """
    Fetches expense details data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        from_date (str): Start date in YYYY-MM-DD format
        to_date (str): End date in YYYY-MM-DD format
        
    Returns:
        dict: Formatted expense details data
    """
    load_dotenv()
    
    # Get organization ID from environment variables if not provided
    if not organization_id:
        organization_id = os.getenv("ZOHO_ORGANIZATION_ID")
    
    if not organization_id:
        print("Error: ZOHO_ORGANIZATION_ID not found in environment variables")
        return None
    
    # Get valid access token if not provided
    if not access_token:
        access_token = get_valid_access_token()
        if not access_token:
            print("Error: Failed to obtain a valid access token")
            return None
    
    # Prepare request headers
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }
    
    # Define API endpoint for expense details report
    url = "https://www.zohoapis.in/books/v3/reports/expensedetails"
    
    # Set parameters - only essential ones
    params = {
        "organization_id": organization_id,
        "sort_order": "D",
        "sort_column": "date",
        "filter_by": "ExpenseDate.CustomDate",
        "from_date": from_date,
        "to_date": to_date,
        "entity_list": "expense,bill"  # Include both expenses and bills
    }
    
    try:    
        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        # Check response status
        if response.status_code == 200:
            expenses_data = response.json()
            
            # Extract relevant fields using the extraction logic
            relevant_data = extract_expense_details_data(expenses_data)
            
            return relevant_data
        else:
            print(f"API request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    
    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {str(e)}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None


if __name__ == "__main__":
    # Test with fiscal year 2024-2025
    start_date = "2024-04-01"
    end_date = "2025-03-31"
    
    result = fetch_expense_details(
        from_date=start_date,
        to_date=end_date
    )
    
    if result:
        print("\nExtracted expense details data:")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to retrieve expense details data")