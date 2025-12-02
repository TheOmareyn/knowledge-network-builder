"""Check current API usage for all users"""

import sqlite3
from datetime import date

conn = sqlite3.connect('knowledge_network.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

users = cursor.execute("SELECT id, username, is_premium, is_admin, api_calls_today, api_calls_reset_date FROM User").fetchall()

print("\n" + "="*80)
print("Current API Usage Status")
print("="*80)
print(f"Today's date: {date.today()}")
print("-"*80)

for user in users:
    account_type = "ADMIN" if user['is_admin'] else ("PREMIUM" if user['is_premium'] else "FREE")
    limit = "Unlimited" if user['is_admin'] else ("100" if user['is_premium'] else "20")
    
    needs_reset = user['api_calls_reset_date'] != str(date.today())
    reset_status = "⚠️ NEEDS RESET" if needs_reset else "✓ Current"
    
    print(f"\nUser: {user['username']} (ID: {user['id']})")
    print(f"  Account: {account_type}")
    print(f"  API Calls Today: {user['api_calls_today']}/{limit}")
    print(f"  Last Reset: {user['api_calls_reset_date']} {reset_status}")

print("\n" + "="*80)
print("\nNote: The counter will automatically reset when the user loads the dashboard")
print("      or attempts to use an API call after the date changes.")
print("="*80 + "\n")

conn.close()
