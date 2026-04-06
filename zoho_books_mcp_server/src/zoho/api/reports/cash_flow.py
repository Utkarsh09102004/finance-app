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

def extract_cash_flow_data(cash_flow_json_data):
    """
    Extracts relevant Cash Flow information from the provided JSON structure.
    
    Args:
        cash_flow_json_data (dict): A dictionary containing the cash flow report JSON data.
        
    Returns:
        dict: A dictionary structured for potential AI analysis, containing:
              - report_metadata: Context about the report (dates, basis).
              - summary: Key cash flow figures.
              - operating_activities: Breakdown of operating cash flows.
              - investing_activities: Breakdown of investing cash flows.
              - financing_activities: Breakdown of financing cash flows.
    """
    if cash_flow_json_data.get("code") != 0 or not cash_flow_json_data.get("cash_flow"):
        print("Error or no cash flow data found in JSON.")
        return None

    cash_flow_sections = cash_flow_json_data["cash_flow"]
    page_context = cash_flow_json_data.get("page_context", {})

    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "cash_flow"),
            "from_date": page_context.get("from_date"),
            "to_date": page_context.get("to_date"),
            "report_basis": page_context.get("report_basis", "Unknown"),
            "currency": "Implicit (assumed from values, not specified)"
        },
        "summary": {
            "beginning_cash_balance": 0.0,
            "net_change_in_cash": 0.0,
            "ending_cash_balance": 0.0
        },
        "operating_activities": {
            "net_income": 0.0,
            "adjustments": [],
            "total": 0.0
        },
        "investing_activities": {
            "activities": [],
            "total": 0.0
        },
        "financing_activities": {
            "activities": [],
            "total": 0.0
        }
    }

    def process_activity_accounts(accounts):
        """Helper function to extract individual activity details."""
        activities_list = []
        for acc in accounts:
            if acc.get("name") and acc.get("total") is not None:
                activities_list.append({
                    "activity_name": acc.get("name"),
                    "amount": acc.get("total", 0.0),
                    "account_id": acc.get("account_id", "")
                })
        return activities_list

    # Process main sections
    for section in cash_flow_sections:
        section_name = section.get("name")
        section_total = section.get("total", 0.0)

        if section_name == "Beginning Cash Balance":
            extracted_data["summary"]["beginning_cash_balance"] = section_total
        elif section_name == "Ending Cash Balance":
            extracted_data["summary"]["ending_cash_balance"] = section_total
        elif section_name == "Net Change in cash":
            extracted_data["summary"]["net_change_in_cash"] = section_total
            
            # Process sub-activities
            for activity_group in section.get("account_transactions", []):
                group_name = activity_group.get("name")
                group_total = activity_group.get("total", 0.0)
                
                if group_name == "Cash Flow from Operating Activities":
                    extracted_data["operating_activities"]["total"] = group_total
                    
                    # Extract Net Income and other operating activities
                    for item in activity_group.get("account_transactions", []):
                        if item.get("name") == "Net Income":
                            extracted_data["operating_activities"]["net_income"] = item.get("total", 0.0)
                        else:
                            extracted_data["operating_activities"]["adjustments"].append({
                                "adjustment_name": item.get("name"),
                                "amount": item.get("total", 0.0)
                            })
                            
                elif group_name == "Cash Flow from Investing Activities":
                    extracted_data["investing_activities"]["total"] = group_total
                    extracted_data["investing_activities"]["activities"] = process_activity_accounts(
                        activity_group.get("account_transactions", [])
                    )
                    
                elif group_name == "Cash Flow from Financing Activities":
                    extracted_data["financing_activities"]["total"] = group_total
                    extracted_data["financing_activities"]["activities"] = process_activity_accounts(
                        activity_group.get("account_transactions", [])
                    )

    return extracted_data

def fetch_cash_flow(organization_id=None, from_date=None, to_date=None, access_token=None):
    """
    Fetches cash flow data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        from_date (str): Start date in YYYY-MM-DD format
        to_date (str): End date in YYYY-MM-DD format
        access_token (str, optional): Zoho access token. If None, attempts to get from token manager.
        
    Returns:
        dict: Formatted cash flow data
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
    
    # Define API endpoint for cash flow report
    url = "https://www.zohoapis.in/books/v3/reports/cashflow"
    
    # Set parameters - only essential ones
    params = {
        "organization_id": organization_id,
        "cash_based": "false",
        "filter_by": "TransactionDate.CustomDate",
        "from_date": from_date,
        "to_date": to_date,
        "sort_column": "name",
        "sort_order": "A"
    }
    
    try:    
        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        # Check response status
        if response.status_code == 200:
            cash_flow_data = response.json()
            
            # Extract relevant fields using the extraction logic
            relevant_data = extract_cash_flow_data(cash_flow_data)
            
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
    # Test the cash flow fetch to see the raw response
    from datetime import datetime, timedelta
    
    # Test with fiscal year 2024-2025
    start_date = "2024-04-01"
    end_date = "2025-03-31"
    
    result = fetch_cash_flow(
        from_date=start_date,
        to_date=end_date
    )
    
    if result:
        print("\nExtracted cash flow data:")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to retrieve cash flow data")