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

def extract_invoice_details_data(invoice_json_data):
    """
    Extracts relevant Invoice Details information from the provided JSON structure.
    
    Args:
        invoice_json_data (dict): A dictionary containing the invoice details report JSON data.
        
    Returns:
        dict: A dictionary structured for potential AI analysis, containing:
              - report_metadata: Context about the report (dates, pagination info).
              - summary: Aggregate statistics across all invoices.
              - invoices: Detailed data for each invoice.
    """
    if invoice_json_data.get("code") != 0 or not invoice_json_data.get("invoice_details"):
        print("Error or no invoice data found in JSON.")
        return None

    invoice_data = invoice_json_data["invoice_details"]
    page_context = invoice_json_data.get("page_context", {})

    # Calculate summary statistics
    total_amount = sum(invoice.get("total", 0.0) for invoice in invoice_data)
    total_balance = sum(invoice.get("balance", 0.0) for invoice in invoice_data)
    total_paid = total_amount - total_balance
    
    # Group by status
    status_counts = {}
    for invoice in invoice_data:
        status = invoice.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "invoice_details"),
            "from_date": page_context.get("from_date"),
            "to_date": page_context.get("to_date"),
            "page": page_context.get("page", 1),
            "per_page": page_context.get("per_page", 200),
            "has_more_pages": page_context.get("has_more_page", False),
            "currency": "INR"  # Default currency
        },
        "summary": {
            "total_invoices": len(invoice_data),
            "total_invoice_amount": total_amount,
            "total_paid_amount": total_paid,
            "total_outstanding_amount": total_balance,
            "average_invoice_amount": total_amount / len(invoice_data) if invoice_data else 0,
            "collection_rate": (total_paid / total_amount * 100) if total_amount > 0 else 0,
            "status_breakdown": status_counts
        },
        "invoices": []
    }

    # Process individual invoice data
    for invoice in invoice_data:
        invoice_info = {
            "invoice_id": invoice.get("invoice_id"),
            "invoice_number": invoice.get("invoice_number"),
            "invoice_date": invoice.get("invoice_date"),
            "due_date": invoice.get("due_date"),
            "customer_name": invoice.get("customer_name"),
            "customer_id": invoice.get("customer_id"),
            "status": invoice.get("status"),
            "reference_number": invoice.get("reference_number"),
            "salesperson_name": invoice.get("salesperson_name"),
            "subtotal": invoice.get("sub_total", 0.0),
            "tax_total": invoice.get("tax_total", 0.0),
            "total": invoice.get("total", 0.0),
            "balance": invoice.get("balance", 0.0),
            "paid_amount": invoice.get("total", 0.0) - invoice.get("balance", 0.0),
            "currency_code": invoice.get("currency_code", "INR"),
            "overdue_days": invoice.get("overdue_days", 0),
            "payment_terms": invoice.get("payment_terms"),
            "payment_expected_date": invoice.get("payment_expected_date"),
            "last_payment_date": invoice.get("last_payment_date")
        }
        
        extracted_data["invoices"].append(invoice_info)

    # Sort invoices by date in descending order (most recent first)
    extracted_data["invoices"].sort(key=lambda x: x["invoice_date"], reverse=True)

    return extracted_data

def fetch_invoice_details(organization_id=None, from_date=None, to_date=None, access_token=None):
    """
    Fetches invoice details data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        from_date (str): Start date in YYYY-MM-DD format
        to_date (str): End date in YYYY-MM-DD format
        
    Returns:
        dict: Formatted invoice details data
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
    
    # Define API endpoint for invoice details report
    url = "https://www.zohoapis.in/books/v3/reports/invoicedetails"
    
    # Set parameters - only essential ones
    params = {
        "organization_id": organization_id,
        "sort_order": "D",
        "sort_column": "date",
        "filter_by": "InvoiceDate.CustomDate",
        "from_date": from_date,
        "to_date": to_date,
        "entity_list": "invoice,creditnote"  # Include invoices and credit notes
    }
    
    try:    
        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        # Check response status
        if response.status_code == 200:
            invoice_data = response.json()
            
            # Extract relevant fields using the extraction logic
            relevant_data = extract_invoice_details_data(invoice_data)
            
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
    
    result = fetch_invoice_details(
        from_date=start_date,
        to_date=end_date
    )
    
    if result:
        print("\nExtracted invoice details data:")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to retrieve invoice details data")