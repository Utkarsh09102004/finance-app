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

def extract_expenses_by_category_data(expenses_json_data):
    """
    Extracts relevant Expenses by Category information from the provided JSON structure.
    
    Args:
        expenses_json_data (dict): A dictionary containing the expenses by category report JSON data.
        
    Returns:
        dict: A dictionary structured for potential AI analysis, containing:
              - report_metadata: Context about the report (dates, pagination info).
              - summary: Aggregate statistics across all categories.
              - categories: Detailed expense data for each category.
    """
    if expenses_json_data.get("code") != 0 or not expenses_json_data.get("expense_details"):
        print("Error or no expense data found in JSON.")
        return None

    expense_data = expenses_json_data["expense_details"]
    page_context = expenses_json_data.get("page_context", {})

    # Calculate summary statistics
    total_expenses = sum(category.get("total", 0.0) for category in expense_data)
    
    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "expenses_by_category"),
            "from_date": page_context.get("from_date"),
            "to_date": page_context.get("to_date"),
            "page": page_context.get("page", 1),
            "per_page": page_context.get("per_page", 200),
            "has_more_pages": page_context.get("has_more_page", False),
            "currency": "INR"  # Default currency
        },
        "summary": {
            "total_categories": len(expense_data),
            "total_expenses": total_expenses,
            "average_expense_per_category": total_expenses / len(expense_data) if expense_data else 0
        },
        "categories": []
    }

    # Process individual category data
    for category in expense_data:
        category_info = {
            "category_name": category.get("account_name"),
            "category_id": category.get("account_id"),
            "total_amount": category.get("total", 0.0),
            "expense_percentage": (category.get("total", 0.0) / total_expenses * 100) if total_expenses > 0 else 0
        }
        
        extracted_data["categories"].append(category_info)

    # Sort categories by total amount in descending order for better analysis
    extracted_data["categories"].sort(key=lambda x: x["total_amount"], reverse=True)

    return extracted_data

def fetch_expenses_by_category(organization_id=None, from_date=None, to_date=None, access_token=None):
    """
    Fetches expenses by category data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        from_date (str): Start date in YYYY-MM-DD format
        to_date (str): End date in YYYY-MM-DD format
        
    Returns:
        dict: Formatted expenses by category data
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
    
    # Define API endpoint for expenses by category report
    url = "https://www.zohoapis.in/books/v3/reports/expensesbycategory"
    
    # Set parameters - only essential ones
    params = {
        "organization_id": organization_id,
        "sort_order": "D",
        "sort_column": "total",
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
            relevant_data = extract_expenses_by_category_data(expenses_data)
            
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
    
    result = fetch_expenses_by_category(
        from_date=start_date,
        to_date=end_date
    )
    
    if result:
        print("\nExtracted expenses by category data:")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to retrieve expenses by category data")