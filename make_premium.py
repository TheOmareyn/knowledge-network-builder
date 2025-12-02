"""
Helper script to make a user premium.
Usage: python make_premium.py <username>
"""

import sqlite3
import sys

def make_user_premium(username):
    """Make a user premium."""
    conn = sqlite3.connect('knowledge_network.db')
    cursor = conn.cursor()
    
    # Check if user exists
    user = cursor.execute("SELECT id, username, is_premium FROM User WHERE username = ?", (username,)).fetchone()
    
    if not user:
        print(f"❌ User '{username}' not found!")
        conn.close()
        return
    
    user_id, username, is_premium = user
    
    if is_premium:
        print(f"ℹ️  User '{username}' is already premium!")
    else:
        cursor.execute("UPDATE User SET is_premium = 1 WHERE id = ?", (user_id,))
        conn.commit()
        print(f"✅ User '{username}' is now premium!")
        print(f"   Benefits: 100 API calls/day • Private networks • Priority support")
    
    conn.close()

def list_users():
    """List all users and their premium status."""
    conn = sqlite3.connect('knowledge_network.db')
    cursor = conn.cursor()
    
    users = cursor.execute("SELECT username, is_premium, api_calls_today FROM User").fetchall()
    
    if not users:
        print("No users found in database.")
    else:
        print("\nUsers:")
        print("-" * 60)
        for username, is_premium, api_calls in users:
            status = "⭐ PREMIUM" if is_premium else "FREE"
            print(f"{username:<20} {status:<15} API calls today: {api_calls}")
        print("-" * 60)
    
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python make_premium.py <username>")
        print("   or: python make_premium.py --list")
        list_users()
    elif sys.argv[1] == '--list' or sys.argv[1] == '-l':
        list_users()
    else:
        username = sys.argv[1]
        make_user_premium(username)
