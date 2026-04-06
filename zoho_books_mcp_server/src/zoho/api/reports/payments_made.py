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

def extract_payments_made_data(payments_json_data):
    """
    Extracts relevant Payments Made information from the provided JSON structure.
    
    Args:
        payments_json_data (dict): A dictionary containing the payments made report JSON data.
        
    Returns:
        dict: A dictionary structured for potential AI analysis, containing:
              - report_metadata: Context about the report (dates, pagination info).
              - summary: Aggregate statistics across all payments.
              - payments: Detailed data for each payment made.
    """
    if payments_json_data.get("code") != 0 or not payments_json_data.get("payment_details"):
        print("Error or no payment data found in JSON.")
        return None

    payment_data = payments_json_data["payment_details"]
    page_context = payments_json_data.get("page_context", {})

    # Calculate summary statistics
    total_amount = sum(payment.get("amount", 0.0) for payment in payment_data)
    
    # Group by payment mode
    payment_mode_totals = {}
    vendor_totals = {}
    
    for payment in payment_data:
        mode = payment.get("payment_mode", "Unknown")
        payment_mode_totals[mode] = payment_mode_totals.get(mode, 0.0) + payment.get("amount", 0.0)
        
        vendor = payment.get("vendor_name", "Unknown")
        vendor_totals[vendor] = vendor_totals.get(vendor, 0.0) + payment.get("amount", 0.0)
    
    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "payments_made"),
            "from_date": page_context.get("from_date"),
            "to_date": page_context.get("to_date"),
            "page": page_context.get("page", 1),
            "per_page": page_context.get("per_page", 200),
            "has_more_pages": page_context.get("has_more_page", False),
            "currency": "INR"  # Default currency
        },
        "summary": {
            "total_payments": len(payment_data),
            "total_amount": total_amount,
            "average_payment_amount": total_amount / len(payment_data) if payment_data else 0,
            "unique_vendors": len(vendor_totals),
            "payment_mode_breakdown": [
                {"mode": mode, "total": amt, "percentage": (amt / total_amount * 100) if total_amount > 0 else 0}
                for mode, amt in sorted(payment_mode_totals.items(), key=lambda x: x[1], reverse=True)
            ],
            "top_vendors": [
                {"vendor": vendor, "total": amt, "percentage": (amt / total_amount * 100) if total_amount > 0 else 0}
                for vendor, amt in sorted(vendor_totals.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
        },
        "payments": []
    }

    # Process individual payment data
    for payment in payment_data:
        payment_info = {
            "payment_id": payment.get("payment_id"),
            "payment_number": payment.get("payment_number"),
            "payment_date": payment.get("payment_date"),
            "vendor_name": payment.get("vendor_name"),
            "vendor_id": payment.get("vendor_id"),
            "payment_mode": payment.get("payment_mode"),
            "reference_number": payment.get("reference_number"),
            "description": payment.get("description"),
            "amount": payment.get("amount", 0.0),
            "currency_code": payment.get("currency_code", "INR"),
            "exchange_rate": payment.get("exchange_rate", 1.0),
            "paid_through_account_name": payment.get("paid_through_account_name"),
            "paid_through_account_id": payment.get("paid_through_account_id"),
            "bill_numbers": payment.get("bill_numbers", ""),
            "status": payment.get("status", "paid")
        }
        
        extracted_data["payments"].append(payment_info)

    # Sort payments by date in descending order (most recent first)
    extracted_data["payments"].sort(key=lambda x: x["payment_date"], reverse=True)

    return extracted_data

def fetch_payments_made(organization_id=None, from_date=None, to_date=None, access_token=None):
    """
    Fetches payments made data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        from_date (str): Start date in YYYY-MM-DD format
        to_date (str): End date in YYYY-MM-DD format
        
    Returns:
        dict: Formatted payments made data
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
    
    # Define API endpoint for payments made report
    url = "https://www.zohoapis.in/books/v3/reports/vendorpayments"
    
    # Set parameters - only essential ones
    params = {
        "organization_id": organization_id,
        "sort_order": "D",
        "sort_column": "date",
        "filter_by": "PaymentDate.CustomDate",
        "from_date": from_date,
        "to_date": to_date
    }
    
    try:    
        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        # Check response status
        if response.status_code == 200:
            payments_data = response.json()
            
            # Extract relevant fields using the extraction logic
            relevant_data = extract_payments_made_data(payments_data)
            
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
    
    result = fetch_payments_made(
        from_date=start_date,
        to_date=end_date
    )
    
    if result:
        print("\nExtracted payments made data:")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to retrieve payments made data")