import sqlite3
from datetime import datetime

conn = sqlite3.connect('knowledge_network.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("CONSISTENCY CHECK RECORDS")
print("=" * 80)

cursor.execute("""
    SELECT 
        cc.*,
        d1.title as book1_title,
        d2.title as book2_title
    FROM ConsistencyCheck cc
    LEFT JOIN Document d1 ON cc.book1_id = d1.id
    LEFT JOIN Document d2 ON cc.book2_id = d2.id
    ORDER BY cc.checked_timestamp DESC
""")

records = cursor.fetchall()

if not records:
    print("\n❌ No consistency check records found yet.")
    print("\nRun a consistency check from the global network page to create records.")
else:
    print(f"\n✓ Found {len(records)} consistency check record(s)\n")
    
    for i, row in enumerate(records, 1):
        print(f"{'─' * 80}")
        print(f"Record #{i}")
        print(f"{'─' * 80}")
        print(f"ID: {row['id']}")
        print(f"Question: {row['question']}")
        print(f"\nBook 1 (ID: {row['book1_id']}): {row['book1_title'] or 'Unknown'}")
        print(f"Answer: {row['book1_answer'][:100]}...")
        print(f"\nBook 2 (ID: {row['book2_id']}): {row['book2_title'] or 'Unknown'}")
        print(f"Answer: {row['book2_answer'][:100]}...")
        print(f"\n🎯 Contradiction Percentage: {row['contradiction_percentage']}%")
        print(f"📅 Checked: {row['checked_timestamp']}")
        print()

print("=" * 80)

# Show statistics
if records:
    percentages = [row['contradiction_percentage'] for row in records]
    avg = sum(percentages) / len(percentages)
    print(f"\n📊 Statistics:")
    print(f"   Total questions analyzed: {len(records)}")
    print(f"   Average contradiction: {avg:.1f}%")
    print(f"   Min contradiction: {min(percentages)}%")
    print(f"   Max contradiction: {max(percentages)}%")
    
    # Count by contradiction level
    low = sum(1 for p in percentages if p <= 30)
    medium = sum(1 for p in percentages if 30 < p <= 60)
    high = sum(1 for p in percentages if p > 60)
    
    print(f"\n   Low contradiction (0-30%): {low}")
    print(f"   Medium contradiction (31-60%): {medium}")
    print(f"   High contradiction (61-100%): {high}")

conn.close()
