# Milkbasket Order Fetcher

A Python tool to fetch your Milkbasket order history, categorize items (Fruits, Vegetables, Dairy, etc.), and export them to a CSV summary with a category-wise spending breakdown.

## Features
- **Automated OTP Login Flow**: Handles mobile verification directly inside the terminal.
- **Fetch Last 3 Months**: Automatically defaults to fetching the last 90 days of orders.
- **Rule-Based Categorization**: Uses keywords to automatically guess categories.
- **Interactive Training**: Asks for confirmation on new items and learns from your input.
- **Dynamic Categories**: Create and save new categories on the fly.
- **Spending Summary**: Displays a formatted table of your total spending per category.

---

## 🛠 Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/Oshin159/summarize-milkbasket.git
cd summarize-milkbasket
```

### 2. Set up a Virtual Environment (Recommended)
```bash
python3 -m venv .venv
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
---

## 🚀 Detailed Usage & Workflow

### Running the Script
```bash
source .venv/bin/activate
python3 milkbasket_fetch.py
```
1. **Login Flow**: On startup, the script handles your session automatically:
   - **First Run**: Enter your **10-digit registered mobile number** and the **OTP** sent to your phone to log in. Your session token will be automatically saved to a `.env` file so you don't have to log in again.
   - **Changing Accounts**: If you ever want to change the logged-in user or sign in with a different phone number, simply delete the `.env` file from the root folder.
2.  **Date Selection**: On startup, it will ask for a Start/End date. 
    - **Press Enter** to automatically fetch the last 3 months.
    - Or enter dates in `YYYY-MM-DD` format.
3.  **Fetching**: The script will fetch your order list and then download details for each order sequentially.
4.  **Interactive Categorization**: For every item, the script follows this logic:
    - **Check Cache**: Has this item been seen before? If yes, use the saved category.
    - **Keyword Guess**: Does the item name contain any keywords from `categories_config.json`? (e.g., "Tomato" contains "tomato" -> Vegetables).
    - **User Prompt**: If it's a new item or the guess is "others", it will ask you to confirm.

### 🧠 How Categorization Works

The system is designed to get "smarter" the more you use it. It relies on two main files:

#### 1. `categories_config.json` (The Brain)
This file defines your high-level categories and the keywords used to guess them.
- You can manually add keywords here to improve auto-guessing.
- Example: Adding `"soda"` to the `others` category keywords will ensure all soft drinks are categorized correctly without asking you.

#### 2. `item_categories.csv` (The Memory)
This file stores a 1:1 mapping of specific item names to categories.
- Once you confirm an item like "Amul Taaza 1L" is "Dairy", it is saved here.
- The next time you buy "Amul Taaza 1L", the script will categorize it instantly without prompting you.

### ➕ Adding New Categories
If you encounter an item that doesn't fit (e.g., "Pet Food"), you can:
1.  Type `n` when prompted for a suggestion.
2.  Type your new category name (e.g., `pets`).
3.  Confirm with `y` to create it.
4.  The script will automatically update `categories_config.json` and include "Pets" in your final spending summary.

> [!IMPORTANT]
> **Maintenance Note**: If you manually rename or delete categories in `categories_config.json`, you should also delete or update `item_categories.csv`. Since the CSV stores historical mappings, it may still contain references to old category names that no longer exist in your config, which could lead to inconsistencies in your spending summary.

---

## 📊 Post-Run Analysis

After the script finishes:
1.  **Terminal Summary**: You will see a table showing exactly how much you spent on Milk, Veggies, etc.
2.  **CSV File**: A detailed CSV is created in the `summary/` folder. This file is perfect for:
    - Importing into **Google Sheets** or **Excel**.
    - Creating pivot tables to see spending trends over time.
    - Auditing your monthly grocery expenses.


## 🛠 Troubleshooting

If the script stops working, fails to fetch data, or throws authentication errors, try the following steps:

1. **Clear the Session**: Delete the `.env` file from the root directory to wipe the cached token and force a fresh OTP handshake:
   ```bash
   rm .env
2. **Update Device Identifier**: If logins consistently fail, open `milkbasket_fetch.py`, find the `UDID` configuration defined right at the top of the file, and change its value to a fresh, random alphanumeric string.
