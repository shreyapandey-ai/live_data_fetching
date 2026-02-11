import sqlite3
import json
import os

def migrate():
    # Load your current JSON data 
    with open("research_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # Create and connect to the SQLite database
    conn = sqlite3.connect("research_library.db")
    cursor = conn.cursor()

    # Create the tables
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER,
            source TEXT,
            url TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities (id)
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER,
            content TEXT,
            FOREIGN KEY (doc_id) REFERENCES documents (id)
        );
    ''')

    # Insert the data
    for entry in data:
        entity_name = entry.get("entity")
        cursor.execute("INSERT OR IGNORE INTO entities (name) VALUES (?)", (entity_name,))
        cursor.execute("SELECT id FROM entities WHERE name = ?", (entity_name,))
        entity_id = cursor.fetchone()[0]

        for doc in entry.get("documents", []):
            cursor.execute("INSERT INTO documents (entity_id, source, url) VALUES (?, ?, ?)", 
                           (entity_id, doc.get("source"), doc.get("url")))
            doc_id = cursor.lastrowid
            
            for chunk in doc.get("chunks", []):
                cursor.execute("INSERT INTO chunks (doc_id, content) VALUES (?, ?)", 
                               (doc_id, chunk.get("text")))

    conn.commit()
    conn.close()
    print("✅ Migration complete! You can now open 'research_library.db' in SQLite Browser.")

if __name__ == "__main__":
    migrate()