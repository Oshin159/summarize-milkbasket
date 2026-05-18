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
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# ─────────────────────────────────────────────
# CONFIG & AUTH
# ─────────────────────────────────────────────
AUTH_TOKEN = os.getenv("MILKBASKET_BEARER_TOKEN")

API_URL = "https://consumerbff.milkbasket.com/graphql"
CONFIG_FILE = "categories_config.json"
CACHE_FILE = "item_categories.csv"
SUMMARY_DIR = "summary"

# ─────────────────────────────────────────────
# CONFIG LOAD/SAVE
# ─────────────────────────────────────────────

def load_categories_config():
    """Loads categories and keywords from JSON."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Default fallback
    return {
        "categories": ["fruits", "vegetables", "bakery", "dairy", "others"],
        "keywords": {
            "fruits": ["apple", "banana"],
            "vegetables": ["potato", "onion"],
            "bakery": ["bread"],
            "dairy": ["milk"]
        }
    }

def save_categories_config(config):
    """Saves categories and keywords to JSON."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

# Load global config
CAT_CONFIG = load_categories_config()
VALID_CATEGORIES = CAT_CONFIG["categories"]
KEYWORDS = CAT_CONFIG["keywords"]

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
    "role": "1",
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
                if len(row) >= 2:
                    # Store normalized keys
                    cache[row[0].strip().lower()] = row[1].strip().lower()
    return cache


def save_to_category_cache(item, category):
    """Appends a single item-category mapping to the local CSV file."""
    file_exists = os.path.exists(CACHE_FILE)
    with open(CACHE_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([item, category])


def categorize_item_interactive(name, cache):
    """Categorize a single item using cache, keywords, and user interaction."""
    global VALID_CATEGORIES, KEYWORDS
    name_lower = name.strip().lower()
    
    # 1. Check cache
    if name_lower in cache:
        return cache[name_lower]
    
    # 2. Try keyword guessing
    guess_cat = "others"
    for cat, keywords in KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            guess_cat = cat
            break
            
    # 3. Interactive confirmation/input
    print(f"\n🔍  New Item: \"{name}\"")
    choice = input(f"    Suggest category: {guess_cat}. Is this correct? (y/n): ").strip().lower()
    
    final_cat = guess_cat
    if choice != 'y':
        print(f"    Existing categories: {', '.join(VALID_CATEGORIES)}")
        while True:
            manual_cat = input(f"    Enter category (or type a NEW one to create it): ").strip().lower()
            if not manual_cat:
                continue
                
            if manual_cat not in VALID_CATEGORIES:
                confirm_new = input(f"    \" {manual_cat} \" is new. Create it? (y/n): ").strip().lower()
                if confirm_new == 'y':
                    VALID_CATEGORIES.append(manual_cat)
                    if manual_cat not in KEYWORDS:
                        KEYWORDS[manual_cat] = []
                    # Save updated config
                    save_categories_config({"categories": VALID_CATEGORIES, "keywords": KEYWORDS})
                    final_cat = manual_cat
                    break
                else:
                    print(f"    Available: {', '.join(VALID_CATEGORIES)}")
                    continue
            else:
                final_cat = manual_cat
                break
            
    # Save to cache
    save_to_category_cache(name, final_cat)
    cache[name_lower] = final_cat
    return final_cat


# ─────────────────────────────────────────────
# API CALLS
# ─────────────────────────────────────────────

def send_otp(phone_number):
    """Sends OTP to the provided phone number."""
    payload = {
        "operationName": "verifyNumber",
        "variables": {
            "phone": phone_number,
            "retry": False,
            "retryType": "",
            "appHash": "#iymUES6mGJt",
            "udid": "hesH0PXrK0vSqzFK"
        },
        "query": """
            mutation verifyNumber($phone: String!, $retry: Boolean!, $retryType: String!, $appHash: String!, $udid: String!) {
              verifyPhoneNumber(
                phone: $phone
                retry: $retry
                retryType: $retryType
                appHash: $appHash
                udid: $udid
              ) {
                status
                error
                errorMsg
                otpBlockTime
                __typename
              }
            }
        """
    }
    # For login, we don't have the auth token yet
    login_headers = HEADERS.copy()
    if "authorization" in login_headers:
        del login_headers["authorization"]
    
    resp = requests.post(API_URL, headers=login_headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]["verifyPhoneNumber"]


def verify_otp(phone_number, otp):
    """Verifies the OTP and returns the auth token."""
    payload = {
        "operationName": "login",
        "variables": {
            "phone": phone_number,
            "otp": otp,
            "appVersion": "8.0.9.0",
            "binaryVersion": "8.0.9",
            "source": "web",
            "deviceDetail": {
                "udid": "hesH0PXrK0vSqzFK",
                "deviceModel": "unknown",
                "isVirtual": False,
                "manufacturer": "unknown",
                "platform": "web",
                "androidVersion": 0,
                "advertisingId": "",
                "tracking": False,
                "trackierId": ""
            }
        },
        "query": """
            mutation login($phone: String!, $otp: String!, $appVersion: String!, $binaryVersion: String!, $source: String!, $inviteCode: String, $deviceDetail: DeviceDetailInput) {
              login(
                phone: $phone
                otp: $otp
                appVersion: $appVersion
                binaryVersion: $binaryVersion
                source: $source
                inviteCode: $inviteCode
                deviceDetail: $deviceDetail
              ) {
                status
                authExpiry
                authKey
                errorMsg
                refreshKey
                __typename
              }
            }
        """
    }
    login_headers = HEADERS.copy()
    if "authorization" in login_headers:
        del login_headers["authorization"]

    resp = requests.post(API_URL, headers=login_headers, json=payload, timeout=15)
    print(resp.status_code)
    print(resp.text)
    resp.raise_for_status()
    return resp.json()["data"]["login"]


def perform_login():
    """Handles the full login flow."""
    print("\n🔑  Milkbasket Login")
    phone = input("  Enter your 10-digit phone number: ").strip()
    if not phone:
        return None

    print(f"  Sending OTP to {phone}...")
    try:
        res = send_otp(phone)
        if not res.get("status"):
            print(f"  ❌ Failed to send OTP: {res.get('errorMsg')}")
            return None
            
        otp = input("  Enter the OTP received: ").strip()
        if not otp:
            return None
            
        print("  Verifying OTP...")
        login_res = verify_otp(phone, otp)
        
        if login_res.get("status") and login_res.get("authKey"):
            token = login_res["authKey"]
            print("  ✅ Login successful!")
            
            # Save to .env
            with open(".env", "a") as f:
                f.write(f"\nMILKBASKET_BEARER_TOKEN={token}\n")
            print("  💾 Token saved to .env for future use.")
            return token
        else:
            print(f"  ❌ Login failed: {login_res.get('errorMsg')}")
            return None
    except Exception as e:
        print(f"  ❌ Login error: {e}")
        return None


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
    print(f"  Sub-total : ₹{bill_info['subTotal']}")
    print(f"  Savings   : ₹{bill_info['subSavings']}")
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
        AUTH_TOKEN = perform_login()

    if not AUTH_TOKEN:
        print("❌  No token available. Exiting.")
        exit(1)

    print("\n📅  Filter by Date (Enter for last 3 months)")
    start_date_str = input("  Start Date (YYYY-MM-DD): ").strip()
    end_date_str = input("  End Date   (YYYY-MM-DD): ").strip()

    start_date = None
    end_date = None
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        else:
            start_date = datetime.now() - timedelta(days=90)
            print(f"    Using default start date: {start_date.strftime('%Y-%m-%d')}")
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        print("❌  Invalid date format. Please use YYYY-MM-DD. Exiting.")
        exit(1)

    # Update headers with the provided token
    HEADERS["authorization"] = f"Bearer {AUTH_TOKEN}"
    print()

    # Load cache once
    cache = load_category_cache()

    # Step 1: get all orders
    print("📦  Fetching order list...")
    orders = fetch_orders()
    
    # Filter orders by date
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

    # Step 2: fetch detail for each order and categorize
    all_rows = []
    for i, order in enumerate(orders, 1):
        order_id = int(order["id"])
        order_date = order["date"].strip()
        print(f"[{i}/{len(orders)}] Order {order_id} — {order_date} — ₹{order['amount']}")

        try:
            detail = fetch_order_detail(order_id)
            print_order(detail)
            
            # Collect data for CSV and categorize on the fly
            for section in detail["data"]:
                for item in section["data"]:
                    item_name = item["name"]
                    category = categorize_item_interactive(item_name, cache)
                    
                    all_rows.append({
                        "order date": order_date,
                        "item name": item_name,
                        "quantity": item["order"]["quantity"],
                        "mrp": item["price"]["mrp"]["value"],
                        "price": item["price"]["price"]["value"],
                        "category": category
                    })
        except Exception as e:
            print(f"    ⚠️  Failed: {e}")

        time.sleep(0.3)  # be polite

    # Step 3: Organized Export
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

        # Step 4: Summary Table
        print(f"\n📊  Spending Summary ({date_range_str})")
        print(f"{'─'*40}")
        print(f"  {'Category':<20} {'Total Amount':>15}")
        print(f"{'─'*40}")
        
        category_totals = {cat: 0.0 for cat in VALID_CATEGORIES}
        grand_total = 0.0
        
        for row in all_rows:
            cat = row["category"]
            price = float(row["price"])
            category_totals[cat] += price
            grand_total += price
            
        for cat, total in category_totals.items():
            if total > 0:
                print(f"  {cat.capitalize():<20} ₹{total:>14.2f}")
                
        print(f"{'─'*40}")
        print(f"  {'Grand Total':<20} ₹{grand_total:>14.2f}")
        print(f"{'─'*40}")

    print("\n✅  Done!\n")

