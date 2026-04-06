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

def extract_balance_sheet_data(balance_sheet_json_data):
    """
    Extracts relevant Balance Sheet information from the provided JSON structure.

    Args:
        balance_sheet_json_data (dict): A dictionary containing the balance sheet report JSON data.

    Returns:
        dict: A dictionary structured for potential AI analysis, containing:
              - report_metadata: Context about the report (date, basis).
              - summary: Key balance sheet figures (Total Assets, Total Liabilities, Total Equity).
              - assets: Breakdown of assets (Current, Fixed, Other).
              - liabilities: Breakdown of liabilities (Current, Long Term, Other).
              - equity: Breakdown of equity accounts.
    """
    try:
        if balance_sheet_json_data.get("code") != 0 or not balance_sheet_json_data.get("balance_sheet"):
            print("Error or no balance sheet data found in JSON.")
            return None

        balance_sheet_list = balance_sheet_json_data["balance_sheet"]
        page_context = balance_sheet_json_data.get("page_context", {})
    except Exception as e:
        print(f"Error accessing balance sheet data: {e}")
        print(f"Data type: {type(balance_sheet_json_data)}")
        if isinstance(balance_sheet_json_data, dict):
            print(f"Keys: {balance_sheet_json_data.keys()}")
        return None

    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "balance_sheet"),
            "as_of_date": page_context.get("as_of_date"),
            "report_basis": page_context.get("report_basis", "Unknown"),
            "currency": "Implicit (assumed from values, not specified)"
        },
        "summary": {
            "total_assets": 0.0,
            "total_liabilities": 0.0,
            "total_equity": 0.0
        },
        "assets": {
            "current_assets": {
                "total": 0.0,
                "cash": {"total": 0.0, "accounts": []},
                "bank": {"total": 0.0, "accounts": []},
                "accounts_receivable": {"total": 0.0, "accounts": []},
                "other_current_assets": {"total": 0.0, "accounts": []}
            },
            "fixed_assets": {"total": 0.0, "accounts": []},
            "other_assets": {"total": 0.0, "accounts": []}
        },
        "liabilities": {
            "current_liabilities": {"total": 0.0, "accounts": []},
            "long_term_liabilities": {"total": 0.0, "accounts": []},
            "other_liabilities": {"total": 0.0, "accounts": []}
        },
        "equity": {
            "total": 0.0,
            "accounts": []
        }
    }

    def extract_nested_accounts(node):
        """Recursively extract accounts from nested structure."""
        accounts = []
        for child_node in node.get("account_transactions", []):
            if not child_node.get("account_transactions"):
                accounts.append({
                    "account_name": child_node.get("name"),
                    "account_code": child_node.get("account_code", ""),
                    "total": child_node.get("total", 0.0),
                    "account_id": child_node.get("account_id", "")
                })
            else:
                accounts.extend(extract_nested_accounts(child_node))
        return accounts

    # Process main sections
    try:
        print(f"Processing {len(balance_sheet_list)} main sections")
        
        for section in balance_sheet_list:
            section_name = section.get("name", "")
            section_total = section.get("total", 0.0)
            print(f"Processing section: {section_name}, total: {section_total}")
            
            if section_name == "Assets":
                extracted_data["summary"]["total_assets"] = section_total
                
                for asset_category in section.get("account_transactions", []):
                    category_name = asset_category.get("name", "")
                    category_total = asset_category.get("total", 0.0)
                    
                    if category_name == "Current Assets":
                        extracted_data["assets"]["current_assets"]["total"] = category_total
                        
                        for current_asset in asset_category.get("account_transactions", []):
                            asset_type_name = current_asset.get("name", "")
                            asset_total = current_asset.get("total", 0.0)
                            
                            # Normalize names to match keys in `extracted_data`
                            normalized_name = asset_type_name.lower().replace(" ", "_")
                            
                            if normalized_name in extracted_data["assets"]["current_assets"]:
                                extracted_data["assets"]["current_assets"][normalized_name]["total"] = asset_total
                                extracted_data["assets"]["current_assets"][normalized_name]["accounts"] = extract_nested_accounts(current_asset)

                    elif category_name == "Fixed Assets":
                        extracted_data["assets"]["fixed_assets"]["total"] = category_total
                        extracted_data["assets"]["fixed_assets"]["accounts"] = extract_nested_accounts(asset_category)
                    
                    elif category_name == "Other Assets":
                        extracted_data["assets"]["other_assets"]["total"] = category_total
                        extracted_data["assets"]["other_assets"]["accounts"] = extract_nested_accounts(asset_category)
            
            elif section_name == "Liabilities & Equities":
                
                for le_category in section.get("account_transactions", []):
                    category_name = le_category.get("name", "")
                    category_total = le_category.get("total", 0.0)
                    
                    if category_name == "Liabilities":
                        extracted_data["summary"]["total_liabilities"] = category_total
                        
                        for liability_type in le_category.get("account_transactions", []):
                            liability_name = liability_type.get("name", "")
                            liability_total = liability_type.get("total", 0.0)
                            
                            normalized_name = liability_name.lower().replace(" ", "_")

                            if normalized_name in extracted_data["liabilities"]:
                                extracted_data["liabilities"][normalized_name]["total"] = liability_total
                                extracted_data["liabilities"][normalized_name]["accounts"] = extract_nested_accounts(liability_type)

                    elif category_name == "Equities":
                        extracted_data["summary"]["total_equity"] = category_total
                        extracted_data["equity"]["total"] = category_total
                        extracted_data["equity"]["accounts"] = extract_nested_accounts(le_category)
    
    except Exception as e:
        print(f"Error in extraction process: {e}")
        import traceback
        traceback.print_exc()
        return None

    return extracted_data


def fetch_balance_sheet(organization_id=None, as_of_date=None, access_token=None):
    """
    Fetches balance sheet data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        as_of_date (str, optional): Date for the balance sheet in YYYY-MM-DD format. If None, uses today.
        access_token (str, optional): Access token if provided by MCP server.
        
    Returns:
        dict: Formatted balance sheet data
    """
    # Load environment variables
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
    
    # Define API endpoint for balance sheet report
    url = "https://www.zohoapis.in/books/v3/reports/balancesheet"
    
    # Set parameters
    params = {
        "organization_id": organization_id,
        "cash_based": "false",
        "show_rows": "non_zero",
        "sort_column": "account",
        "sort_order": "A"
    }
    
    # Add date filter
    if as_of_date:
        params["filter_by"] = "TransactionDate.CustomDate"
        params["to_date"] = as_of_date
    else:
        params["filter_by"] = "TransactionDate.Today"
    
    try:    
        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        # Check response status
        if response.status_code == 200:
            balance_sheet_data = response.json()
            
            # Extract relevant fields using the extraction logic
            relevant_data = extract_balance_sheet_data(balance_sheet_data)
            

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
    
    # Test with today's date
    result = fetch_balance_sheet()
    
    # Print the result as formatted JSON
    if result:
        print(json.dumps(result, indent=2))
        
        # Print summary
        if "summary" in result:
            as_of_date = result["report_metadata"]["as_of_date"]
            total_assets = result["summary"]["total_assets"]
            total_liabilities = result["summary"]["total_liabilities"]
            total_equity = result["summary"]["total_equity"]
            print(f"\nBalance Sheet Summary (as of {as_of_date}):")
            print(f"Total Assets: {total_assets}")
            print(f"Total Liabilities: {total_liabilities}")
            print(f"Total Equity: {total_equity}")
            print(f"Balance Check (Assets = Liabilities + Equity): {total_assets} = {total_liabilities + total_equity}")
        
    else:
        print("Failed to retrieve balance sheet data")