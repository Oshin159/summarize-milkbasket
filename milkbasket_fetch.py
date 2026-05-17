#!/usr/bin/env python3
"""
Milkbasket Order Fetcher
------------------------
Fetches all orders and prints a parsed summary per order.

Usage:
    pip install requests
    python3 milkbasket_fetch.py

Steps:
    1. Go to milkbasket.com, login
    2. Open DevTools → Network → any GraphQL request
    3. Copy the Bearer token from the Authorization header
    4. Paste it below
"""

import requests
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────
# Auth token — prompted at runtime
# ─────────────────────────────────────────────
AUTH_TOKEN = None  # set at runtime

API_URL = "https://consumerbff.milkbasket.com/graphql"

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "appplatform": "web",
    "appversion": "8.0.9.0",
    "authorization": f"Bearer {AUTH_TOKEN}",
    "binaryversion": "8.0.9",
    "cache-control": "no-cache",
    "cityid": "1",
    "content-type": "application/json",
    "hubid": "1",
    "mbexpress": "0",
    "mblitetype": "0",
    "origin": "https://milkbasket.com",
    "pragma": "no-cache",
    "referer": "https://milkbasket.com/",
    "role": "0",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def parse_mb_date(mb_date_str, year=None):
    """
    Parses Milkbasket date formats:
    - " 18 May,Monday" (no year)
    - "31 Mar 2026" (with year)
    Returns a datetime object.
    """
    clean_str = mb_date_str.strip()
    
    # Format 1: "31 Mar 2026"
    try:
        return datetime.strptime(clean_str, "%d %b %Y")
    except ValueError:
        pass

    # Format 2: "18 May,Monday"
    if not year:
        year = datetime.now().year
    
    clean_date = clean_str.split(",")[0].strip()
    try:
        return datetime.strptime(f"{clean_date} {year}", "%d %b %Y")
    except ValueError:
        return None


# ─────────────────────────────────────────────
# API CALLS
# ─────────────────────────────────────────────

def fetch_orders():
    """Fetch all order IDs and basic info."""
    payload = {
        "operationName": "fetchOrders",
        "variables": {},
        "query": """
            query fetchOrders {
              getAccountHistory {
                orders {
                  id
                  details
                  amount
                  date
                  day
                }
              }
            }
        """
    }
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]["getAccountHistory"]["orders"]


def fetch_order_detail(order_id: int):
    """Fetch full item breakdown for a single order."""
    payload = {
        "operationName": "getOrderDetail",
        "variables": {"orderId": order_id},
        "query": """
            query getOrderDetail($orderId: Float!) {
              getOrderDetail(orderId: $orderId) {
                data {
                  title
                  type
                  data {
                    id
                    name
                    weight { text }
                    order { quantity }
                    price {
                      currency
                      mrp { value }
                      price { value }
                      discount { value }
                    }
                  }
                }
                billDetails {
                  date
                  id
                  billDetails {
                    total
                    subTotal
                    subSavings
                    deliveryFee
                    payableAmount
                  }
                }
              }
            }
        """
    }
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]["getOrderDetail"]


# ─────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────

def print_order(detail):
    bill = detail["billDetails"]
    bill_info = bill["billDetails"]

    print(f"\n{'═'*50}")
    print(f"  Order ID  : {bill['id']}")
    print(f"  Date      : {bill['date'].strip()}")
    print(f"  Sub-total : {bill_info['subTotal']}")
    print(f"  Savings   : {bill_info['subSavings']}")
    print(f"  Delivery  : ₹{bill_info['deliveryFee']}")
    print(f"  Payable   : ₹{bill_info['payableAmount']}")
    print(f"{'─'*50}")
    print(f"  {'Item':<28} {'Qty':>4}  {'MRP':>6}  {'Price':>6}")
    print(f"{'─'*50}")

    for section in detail["data"]:
        for item in section["data"]:
            name  = item["name"]
            qty   = item["order"]["quantity"]
            mrp   = item["price"]["mrp"]["value"]
            price = item["price"]["price"]["value"]
            print(f"  {name:<28} {qty:>4}  ₹{mrp:>5}  ₹{price:>5}")

    print(f"{'═'*50}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🛒  Milkbasket Order Fetcher\n")
    print("How to get your token:")
    print("  1. Open milkbasket.com and log in")
    print("  2. Open DevTools → Network tab")
    print("  3. Click any request to consumerbff.milkbasket.com")
    print("  4. Copy the Authorization header value (after 'Bearer ')\n")

    AUTH_TOKEN = input("Paste your Bearer token: ").strip()
    if not AUTH_TOKEN:
        print("❌  No token provided. Exiting.")
        exit(1)

    print("\n📅  Filter by Date (Optional, press Enter to skip)")
    start_date_str = input("  Start Date (YYYY-MM-DD): ").strip()
    end_date_str = input("  End Date   (YYYY-MM-DD): ").strip()

    start_date = None
    end_date = None
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        print("❌  Invalid date format. Please use YYYY-MM-DD. Exiting.")
        exit(1)

    # Update headers with the provided token
    HEADERS["authorization"] = f"Bearer {AUTH_TOKEN}"
    print()

    # Step 1: get all orders
    print("📦  Fetching order list...")
    orders = fetch_orders()
    
    # Filter orders by date if requested
    if start_date or end_date:
        filtered_orders = []
        for order in orders:
            order_dt = parse_mb_date(order["date"])
            if not order_dt:
                continue
            
            is_after_start = True if not start_date else order_dt >= start_date
            is_before_end = True if not end_date else order_dt <= end_date
            
            if is_after_start and is_before_end:
                filtered_orders.append(order)
        orders = filtered_orders

    print(f"    Found {len(orders)} orders in range\n")

    # Step 2: fetch detail for each order
    for i, order in enumerate(orders, 1):
        order_id = int(order["id"])
        print(f"[{i}/{len(orders)}] Order {order_id} — {order['date']} — ₹{order['amount']}")

        try:
            detail = fetch_order_detail(order_id)
            print_order(detail)
        except Exception as e:
            print(f"    ⚠️  Failed: {e}")

        time.sleep(0.5)  # be polite to their servers

    print("\n✅  Done!\n")
