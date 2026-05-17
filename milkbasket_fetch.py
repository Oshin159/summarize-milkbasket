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
import csv
import os
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# ─────────────────────────────────────────────
# CONFIG & AUTH
# ─────────────────────────────────────────────
AUTH_TOKEN = os.getenv("MILKBASKET_BEARER_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

API_URL = "https://consumerbff.milkbasket.com/graphql"
CACHE_FILE = "item_categories.csv"
SUMMARY_DIR = "summary"

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
    """Parses various Milkbasket date formats."""
    clean_str = mb_date_str.strip()
    try:
        return datetime.strptime(clean_str, "%d %b %Y")
    except ValueError:
        pass

    if not year:
        year = datetime.now().year
    clean_date = clean_str.split(",")[0].strip()
    try:
        return datetime.strptime(f"{clean_date} {year}", "%d %b %Y")
    except ValueError:
        return None


def load_category_cache():
    """Loads item-category mappings from a local CSV file."""
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) == 2:
                    # Store normalized keys
                    cache[row[0].strip().lower()] = row[1]
    return cache


def save_to_category_cache(item_category_map):
    """Appends new item-category mappings to the local CSV file."""
    with open(CACHE_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for item, category in item_category_map.items():
            # item is already likely the original string from AI/unique_items
            writer.writerow([item, category])


def categorize_items_smart(item_names):
    """Categorize items using local cache first, then Gemini."""
    cache = load_category_cache()
    
    final_map = {}
    to_categorize = []
    
    for name in item_names:
        name_lower = name.strip().lower()
        if name_lower in cache:
            final_map[name] = cache[name_lower]
        else:
            to_categorize.append(name)
            
    if not to_categorize:
        return final_map

    # Call Gemini for unknowns
    if not GEMINI_API_KEY:
        print("    ⚠️  No Gemini API Key found in .env; skipping AI.")
        for name in to_categorize:
            final_map[name] = "others"
        return final_map

    print(f"🤖  AI: Categorizing {len(to_categorize)} new items...")
    # print(f"    Items: {to_categorize}") # Debug: see what's being sent

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    categories = ["fruits", "vegetables", "bakery", "dairy", "others"]
    
    prompt = f"""
    Act as an expert Indian grocery classifier. Categorize the list of items provided below into exactly one of these five categories:
    - 'fruits': All fresh fruits.
    - 'vegetables': All fresh vegetables and herbs.
    - 'bakery': Breads, buns, pav, cookies, biscuits, cakes, and rusks.
    - 'dairy': Milk, paneer, curd, yogurt, butter, cheese, and ghee.
    - 'others': Everything else, including staples (atta, rice), pulses, eggs, meat, spices, and household items.

    Input Items: {json.dumps(to_categorize)}

    Output Requirement:
    - Return a JSON object where the keys are EXACTLY the item names from the input.
    - The values must be one of: {', '.join(categories)}.
    """
    
    try:
        response = model.generate_content(
            prompt, 
            generation_config={"response_mime_type": "application/json"}
        )
        new_mappings = json.loads(response.text)
        
        # print(f"    AI Response: {new_mappings}") # Debug: see raw result

        # Save new findings to cache
        save_to_category_cache(new_mappings)
        
        # Merge with final map
        final_map.update(new_mappings)
    except Exception as e:
        print(f"    ⚠️  AI Error: {e}")
        for name in to_categorize:
            final_map[name] = "others"
            
    return final_map


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
    
    if not AUTH_TOKEN:
        print("How to get your token:")
        print("  1. Open milkbasket.com and log in")
        print("  2. Open DevTools → Network tab")
        print("  3. Click any request to consumerbff.milkbasket.com")
        print("  4. Copy the Authorization header value (after 'Bearer ')\n")
        print("  💡 Tip: Save this as MILKBASKET_BEARER_TOKEN in your .env file to skip this prompt.")
        AUTH_TOKEN = input("\nPaste your Bearer token: ").strip()

    if not AUTH_TOKEN:
        print("❌  No token provided. Exiting.")
        exit(1)

    if not GEMINI_API_KEY:
        GEMINI_API_KEY = input("Paste your Gemini API Key (optional, Enter to skip AI): ").strip()

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
    filtered_orders = []
    earliest_date = None
    latest_date = None

    for order in orders:
        order_dt = parse_mb_date(order["date"])
        if not order_dt:
            continue
        
        is_after_start = True if not start_date else order_dt >= start_date
        is_before_end = True if not end_date else order_dt <= end_date
        
        if is_after_start and is_before_end:
            filtered_orders.append(order)
            if not earliest_date or order_dt < earliest_date: earliest_date = order_dt
            if not latest_date or order_dt > latest_date: latest_date = order_dt
    
    orders = filtered_orders
    print(f"    Found {len(orders)} orders in range\n")

    # Step 2: fetch detail for each order
    all_rows = []
    unique_items = set()
    for i, order in enumerate(orders, 1):
        order_id = int(order["id"])
        order_date = order["date"].strip()
        print(f"[{i}/{len(orders)}] Order {order_id} — {order_date} — ₹{order['amount']}")

        try:
            detail = fetch_order_detail(order_id)
            print_order(detail)
            
            # Collect data for CSV
            for section in detail["data"]:
                for item in section["data"]:
                    unique_items.add(item["name"])
                    all_rows.append({
                        "order date": order_date,
                        "item name": item["name"],
                        "quantity": item["order"]["quantity"],
                        "mrp": item["price"]["mrp"]["value"],
                        "price": item["price"]["price"]["value"]
                    })
        except Exception as e:
            print(f"    ⚠️  Failed: {e}")

        time.sleep(0.5)  # be polite to their servers

    # Step 3: Smart Categorization
    if all_rows:
        category_map = categorize_items_smart(list(unique_items))
        # Normalize keys in category_map for robust lookup
        normalized_map = {str(k).strip().lower(): v for k, v in category_map.items()}
        
        for row in all_rows:
            item_key = str(row["item name"]).strip().lower()
            row["category"] = normalized_map.get(item_key, "others")

    # Step 4: Organized Export
    if all_rows:
        if not os.path.exists(SUMMARY_DIR):
            os.makedirs(SUMMARY_DIR)
        
        date_range_str = "all"
        if earliest_date and latest_date:
            date_range_str = f"{earliest_date.strftime('%Y-%m-%d')}-to-{latest_date.strftime('%Y-%m-%d')}"
            
        filename = os.path.join(SUMMARY_DIR, f"orders-{date_range_str}.csv")
        keys = all_rows[0].keys()
        with open(filename, "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(all_rows)
        print(f"\n📁  Exported {len(all_rows)} items to {filename}")

    print("\n✅  Done!\n")
