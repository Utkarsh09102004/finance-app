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

def extract_sales_by_item_data(sales_json_data):
    """
    Extracts relevant Sales by Item information from the provided JSON structure.
    
    Args:
        sales_json_data (dict): A dictionary containing the sales by item report JSON data.
        
    Returns:
        dict: A dictionary structured for potential AI analysis, containing:
              - report_metadata: Context about the report (dates, pagination info).
              - summary: Aggregate statistics across all items.
              - items: Detailed sales data for each item.
    """
    if sales_json_data.get("code") != 0 or not sales_json_data.get("sales"):
        print("Error or no sales data found in JSON.")
        return None

    sales_data = sales_json_data["sales"]
    page_context = sales_json_data.get("page_context", {})

    # Calculate summary statistics
    total_quantity = sum(item.get("quantity_sold", 0.0) for item in sales_data)
    total_amount = sum(item.get("amount", 0.0) for item in sales_data)
    
    extracted_data = {
        "report_metadata": {
            "report_type": page_context.get("report_type", "sales_by_item"),
            "from_date": page_context.get("from_date"),
            "to_date": page_context.get("to_date"),
            "page": page_context.get("page", 1),
            "per_page": page_context.get("per_page", 200),
            "has_more_pages": page_context.get("has_more_page", False),
            "entity_types": page_context.get("entity_list", "").split(","),
            "currency": "INR"  # Assuming INR based on other reports
        },
        "summary": {
            "total_items": len(sales_data),
            "total_quantity_sold": total_quantity,
            "total_sales_amount": total_amount,
            "average_sales_per_item": total_amount / len(sales_data) if sales_data else 0,
            "average_quantity_per_item": total_quantity / len(sales_data) if sales_data else 0,
            "weighted_average_price": total_amount / total_quantity if total_quantity > 0 else 0
        },
        "items": []
    }

    # Process individual item data
    for item in sales_data:
        item_info = {
            "item_id": item.get("item_id"),
            "item_name": item.get("item_name"),
            "unit": item.get("unit", ""),
            "is_combo_product": item.get("is_combo_product", False),
            "quantity_sold": item.get("quantity_sold", 0.0),
            "total_sales": item.get("amount", 0.0),
            "average_price": item.get("average_price", 0.0),
            "sales_percentage": (item.get("amount", 0.0) / total_amount * 100) if total_amount > 0 else 0,
            "quantity_percentage": (item.get("quantity_sold", 0.0) / total_quantity * 100) if total_quantity > 0 else 0
        }
        
        extracted_data["items"].append(item_info)

    # Sort items by sales amount in descending order for better analysis
    extracted_data["items"].sort(key=lambda x: x["total_sales"], reverse=True)

    # Add top performers summary
    if extracted_data["items"]:
        top_5_items = extracted_data["items"][:5]
        top_5_sales = sum(item["total_sales"] for item in top_5_items)
        extracted_data["summary"]["top_5_items_sales_percentage"] = (top_5_sales / total_amount * 100) if total_amount > 0 else 0

    return extracted_data

def fetch_sales_by_item(organization_id=None, from_date=None, to_date=None, access_token=None):
    """
    Fetches sales by item data from Zoho Books API.
    
    Args:
        organization_id (str, optional): Zoho organization ID. If None, gets from env vars.
        from_date (str): Start date in YYYY-MM-DD format
        to_date (str): End date in YYYY-MM-DD format
        
    Returns:
        dict: Formatted sales by item data
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
    
    # Define API endpoint for sales by item report
    url = "https://www.zohoapis.in/books/v3/reports/salesbyitem"
    
    # Set parameters - only essential ones
    params = {
        "organization_id": organization_id,
        "sort_order": "A",
        "sort_column": "item_name",
        "filter_by": "TransactionDate.CustomDate",
        "from_date": from_date,
        "to_date": to_date,
        "entity_list": "invoice,creditnote"  # Include invoices and credit notes
    }
    
    try:    
        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        # Check response status
        if response.status_code == 200:
            sales_data = response.json()
            
            # Extract relevant fields using the extraction logic
            relevant_data = extract_sales_by_item_data(sales_data)
            
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
    
    result = fetch_sales_by_item(
        from_date=start_date,
        to_date=end_date
    )
    
    if result:
        print("\nExtracted sales by item data:")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to retrieve sales by item data")