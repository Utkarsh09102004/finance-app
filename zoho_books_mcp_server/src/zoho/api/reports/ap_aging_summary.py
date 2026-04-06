import os
import requests
import json
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from datetime import datetime

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

def extract_ap_aging_data(ap_json_data):
    """
    Extracts relevant AP Aging Summary information from the provided JSON structure.
    
    Args:
        ap_json_data (dict): A dictionary containing the AP aging report JSON data.
        
    Returns:
        dict: A dictionary structured for potential AI analysis
    """
    if ap_json_data.get("code") != 0 or not ap_json_data.get("bill"):
        print("Error or no bill data found in JSON.")
        return None

    bill_data = ap_json_data["bill"]
    page_context = ap_json_data.get("page_context", {})

    # Extract interval details
    intervals = []
    for interval in bill_data.get("intervals", []):
        intervals.append({
            "interval": interval.get("interval"),
            "interval_formatted": interval.get("interval_formatted"),
            "amount": interval.get("amount", 0.0)
        })

    # Extract vendor-wise aging details
    vendors = []
    for group in bill_data.get("group_list", []):
        for vendor in group.get("group_list", []):
            vendor_intervals = []
            for interval in vendor.get("intervals", []):
                vendor_intervals.append({
                    "interval": interval.get("interval"),
                    "interval_formatted": interval.get("interval_formatted"),
                    "amount": interval.get("amount", 0.0)
                })
            
            vendors.append({
                "vendor_name": vendor.get("name"),
                "vendor_id": vendor.get("id"),
                "total": vendor.get("total", 0.0),
                "overdue": vendor.get("overdue", 0.0),
                "intervals": vendor_intervals,
                "foreign_currency_total": vendor.get("fcy_total", 0.0)
            })

    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "ap_aging_summary"),
            "report_name": page_context.get("report_name", "Bill Aging Summary"),
            "as_of_date": page_context.get("as_of_date"),
            "aging_by": page_context.get("aging_by_formatted", "Bill Due Date"),
            "show_by": page_context.get("show_by_formatted", "Outstanding Bill Amount"),
            "page": page_context.get("page", 1),
            "per_page": page_context.get("per_page", 500),
            "has_more_pages": page_context.get("has_more_page", False),
            "interval_type": page_context.get("interval_type", "days"),
            "interval_range": page_context.get("interval_range", "30"),
            "currency": "INR"  # Default currency
        },
        "summary": {
            "total_outstanding": bill_data.get("total", 0.0),
            "total_overdue": bill_data.get("overdue", 0.0),
            "intervals": intervals,
            "total_vendors": len(vendors)
        },
        "vendors": vendors
    }

    # Sort vendors by total outstanding in descending order
    extracted_data["vendors"].sort(key=lambda x: x["total"], reverse=True)

    return extracted_data

def fetch_ap_aging_summary(organization_id=None, as_of_date=None, access_token=None):
    """
    Fetches AP aging summary data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        as_of_date (str, optional): As of date in YYYY-MM-DD format (defaults to today)
        
    Returns:
        dict: Formatted AP aging summary data
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
    
    # Define API endpoint for AP aging summary report
    url = "https://www.zohoapis.in/books/v3/reports/apagingsummary"
    
    # Set parameters - only essential ones
    params = {
        "organization_id": organization_id,
        "sort_order": "A",
        "sort_column": "vendor_name",
        "show_by": "overdueamount",
        "group_by": "none",
        "interval_type": "days",
        "number_of_columns": 4,
        "interval_range": 30,  # 30-day intervals
        "entity_list": "bill"
    }
    
    # Add date filter
    if as_of_date:
        params["filter_by"] = "BillDueDate.CustomDate"
        params["to_date"] = as_of_date
    else:
        params["filter_by"] = "BillDueDate.Today"
    
    try:    
        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        # Check response status
        if response.status_code == 200:
            ap_data = response.json()
            
            # Extract relevant fields using the extraction logic
            relevant_data = extract_ap_aging_data(ap_data)
            
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
    result = fetch_ap_aging_summary()
    
    if result:
        print("\nExtracted AP aging summary data:")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to retrieve AP aging summary data")