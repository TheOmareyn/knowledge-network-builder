import sqlite3
import csv

# Connect to database
conn = sqlite3.connect('knowledge_network.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Query all knowledge entries
cursor.execute('''
    SELECT 
        ke.id,
        ke.document_id,
        d.filename as document_filename,
        d.title as document_title,
        d.author as document_author,
        d.category as document_category,
        ke.keyword,
        ke.question,
        ke.answer,
        ke.proof,
        ke.page_number
    FROM KnowledgeEntry ke
    LEFT JOIN Document d ON ke.document_id = d.id
    ORDER BY ke.id
''')

# Fetch all rows
rows = cursor.fetchall()

# Write to CSV
with open('knowledge_entries_export.csv', 'w', newline='', encoding='utf-8') as csvfile:
    if rows:
        # Get column names
        column_names = rows[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=column_names)
        
        # Write header
        writer.writeheader()
        
        # Write data rows
        for row in rows:
            writer.writerow(dict(row))

conn.close()

print(f"Exported {len(rows)} knowledge entries to 'knowledge_entries_export.csv'")