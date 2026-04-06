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

# --- New Recursive Extraction Logic ---
def extract_pnl_data(pnl_json_data):
    """
    Extracts relevant Profit and Loss information from the provided JSON structure.

    Args:
        pnl_json_data (dict): A dictionary containing the P&L report JSON data.

    Returns:
        dict: A dictionary structured for potential AI analysis, containing:
              - report_metadata: Context about the report (dates, basis).
              - summary: Key P&L figures (Gross Profit, Operating Profit, Net Profit).
              - income_details: Breakdown of Operating Income.
              - cogs_details: Breakdown of Cost of Goods Sold.
              - expense_details: Breakdown of Operating Expenses.
              - non_operating_details: Breakdown of Non-Operating Income/Expense.
              - raw_sections: The main sections with their totals for reference.
    """
    if pnl_json_data.get("code") != 0 or not pnl_json_data.get("profit_and_loss"):
        print("Error or no P&L data found in JSON.")
        return None

    pnl_sections = pnl_json_data["profit_and_loss"]
    page_context = pnl_json_data.get("page_context", {})

    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "profit_and_loss"),
            "from_date": page_context.get("from_date"),
            "to_date": page_context.get("to_date"),
            "report_basis": page_context.get("report_basis", "Unknown"),
            "currency": "Implicit (assumed from values, not specified)" # Assuming USD or similar, add if available
        },
        "summary": {},
        "income_details": {
            "total_operating_income": 0.0,
            "accounts": []
        },
        "cogs_details": {
            "total_cogs": 0.0,
            "accounts": []
        },
        "expense_details": {
            "total_operating_expense": 0.0,
            "accounts": []
        },
        "non_operating_details": {
            "total_non_operating_income": 0.0,
            "income_accounts": [],
            "total_non_operating_expense": 0.0,
            "expense_accounts": []
        },
        "raw_sections": [] # Store raw section totals if needed
    }

    def process_account_transactions(transactions):
        """Helper function to extract individual account details."""
        accounts_list = []
        for acc in transactions:
            accounts_list.append({
                "account_name": acc.get("name"),
                "account_code": acc.get("account_code", ""), # Handle missing code
                "total": acc.get("total", 0.0),
                "account_id": acc.get("account_id") # Keep ID if useful later
            })
        return accounts_list

    # --- Main Processing Logic ---
    for section in pnl_sections:
        section_name = section.get("name")
        section_total = section.get("total", 0.0)

        # Store raw section totals
        extracted_data["raw_sections"].append({
            "section_name": section_name,
            "total": section_total
        })

        # Extract Summary Figures
        if section_name == "Gross Profit":
            extracted_data["summary"]["gross_profit"] = section_total
        elif section_name == "Operating Profit":
            extracted_data["summary"]["operating_profit"] = section_total
        elif section_name == "Net Profit/Loss":
            extracted_data["summary"]["net_profit_loss"] = section_total

        # Extract Detailed Breakdowns
        for category in section.get("account_transactions", []):
            category_name = category.get("name")
            category_total = category.get("total", 0.0)
            category_accounts = category.get("account_transactions", [])

            if category_name == "Operating Income":
                extracted_data["income_details"]["total_operating_income"] = category_total
                extracted_data["income_details"]["accounts"] = process_account_transactions(category_accounts)
            elif category_name == "Cost of Goods Sold":
                 extracted_data["cogs_details"]["total_cogs"] = category_total
                 extracted_data["cogs_details"]["accounts"] = process_account_transactions(category_accounts)
            elif category_name == "Operating Expense":
                 extracted_data["expense_details"]["total_operating_expense"] = category_total
                 extracted_data["expense_details"]["accounts"] = process_account_transactions(category_accounts)
            elif category_name == "Non Operating Income":
                 extracted_data["non_operating_details"]["total_non_operating_income"] = category_total
                 extracted_data["non_operating_details"]["income_accounts"] = process_account_transactions(category_accounts)
            elif category_name == "Non Operating Expense":
                 extracted_data["non_operating_details"]["total_non_operating_expense"] = category_total
                 extracted_data["non_operating_details"]["expense_accounts"] = process_account_transactions(category_accounts)

    # --- Data Validation/Consistency Check (Optional but Recommended) ---
    # Check if calculated totals match summary figures (within a small tolerance for float math)
    calculated_gross_profit = extracted_data["income_details"]["total_operating_income"] - extracted_data["cogs_details"]["total_cogs"]
    calculated_operating_profit = calculated_gross_profit - extracted_data["expense_details"]["total_operating_expense"]
    calculated_net_profit = (calculated_operating_profit +
                             extracted_data["non_operating_details"]["total_non_operating_income"] -
                             extracted_data["non_operating_details"]["total_non_operating_expense"])

    tolerance = 0.01 # Allow for tiny floating point differences

    if abs(calculated_gross_profit - extracted_data["summary"].get("gross_profit", 0.0)) > tolerance:
        print(f"Warning: Calculated Gross Profit ({calculated_gross_profit}) does not match summary ({extracted_data['summary'].get('gross_profit')})")
    if abs(calculated_operating_profit - extracted_data["summary"].get("operating_profit", 0.0)) > tolerance:
         print(f"Warning: Calculated Operating Profit ({calculated_operating_profit}) does not match summary ({extracted_data['summary'].get('operating_profit')})")
    if abs(calculated_net_profit - extracted_data["summary"].get("net_profit_loss", 0.0)) > tolerance:
         print(f"Warning: Calculated Net Profit/Loss ({calculated_net_profit}) does not match summary ({extracted_data['summary'].get('net_profit_loss')})")

    return extracted_data


def fetch_profit_and_loss(organization_id=None, from_date="2024-04-01", to_date="2025-02-03", access_token=None):
    """
    Fetches profit and loss data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        from_date (str): Start date in YYYY-MM-DD format. Default: 2024-04-01
        to_date (str): End date in YYYY-MM-DD format. Default: 2025-02-03
        access_token (str, optional): Zoho access token. If None, attempts to get from token manager.
        
    Returns:
        dict: Formatted profit and loss data
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
    
    # Define API endpoint for P&L report
    url = "https://www.zohoapis.in/books/v3/reports/profitandloss"
    
    # Set parameters
    params = {
        "organization_id": organization_id,
        "cash_based": "false",
        "filter_by": "TransactionDate.CustomDate",
        "from_date": from_date,
        "to_date": to_date,
        "show_rows": "non_zero",
        "sort_column": "total",
        "sort_order": "A"
    }
    
    try:    
        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        # Check response status
        if response.status_code == 200:
            p_and_l_data = response.json()
            
            # Extract relevant fields using the extraction logic
            relevant_data = extract_pnl_data(p_and_l_data)
            
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
    
    result = fetch_profit_and_loss()
    
    # Print the result as formatted JSON
    if result:
        print(json.dumps(result, indent=2))
        
        # Print summary
        if "summary" in result and "net_profit_loss" in result["summary"]:
            from_date = result["report_metadata"]["from_date"]
            to_date = result["report_metadata"]["to_date"]
            net_profit = result["summary"]["net_profit_loss"]
            print(f"\nOverall Net Profit/Loss ({from_date} to {to_date}): {net_profit}")
        
    else:
        print("Failed to retrieve profit and loss data")