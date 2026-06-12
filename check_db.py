import sqlite3

conn = sqlite3.connect('dev.db')
try:
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    print("Tables:", tables)
    for table_name in tables:
        name = table_name[0]
        rows = conn.execute(f"SELECT * FROM {name} LIMIT 5;").fetchall()
        print(f"Table {name} rows:", rows)
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
