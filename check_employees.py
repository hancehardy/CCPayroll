from ccpayroll.database import get_db; with get_db() as conn: cursor = conn.cursor(); cursor.execute("SELECT * FROM employees"); rows = cursor.fetchall(); print(f"Found {len(rows)} employees:", rows)
