#!/usr/bin/env python3
"""
Script to add the missing reimbursement column to timesheet_entries table
"""

import os
from flask import Flask
from ccpayroll.database import get_db

def add_reimbursement_column():
    print("Starting migration to add reimbursement column...")
    app = Flask(__name__)
    app.config.from_mapping(
        PG_HOST=os.environ.get('PG_HOST', 'localhost'),
        PG_PORT=os.environ.get('PG_PORT', '5432'),
        PG_USER=os.environ.get('PG_USER', 'postgres'),
        PG_PASSWORD=os.environ.get('PG_PASSWORD', 'postgres'),
        PG_DB=os.environ.get('PG_DB', 'ccpayroll'),
    )
    
    # Load .env file if it exists
    if os.path.exists('.env'):
        from dotenv import load_dotenv
        load_dotenv()
    
    with app.app_context():
        try:
            print("Connecting to database...")
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Check if column exists
                try:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='timesheet_entries' AND column_name='reimbursement'
                    """)
                    column_exists = cursor.fetchone() is not None
                    
                    if column_exists:
                        print("Reimbursement column already exists.")
                    else:
                        print("Adding reimbursement column to timesheet_entries table...")
                        cursor.execute("""
                            ALTER TABLE timesheet_entries
                            ADD COLUMN reimbursement TEXT
                        """)
                        conn.commit()
                        print("Successfully added reimbursement column!")
                except Exception as e:
                    print(f"Error checking/adding column: {str(e)}")
                    conn.rollback()
                    raise
                
                # Verify column exists
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='timesheet_entries' AND column_name='reimbursement'
                """)
                if cursor.fetchone():
                    print("Verified: Reimbursement column exists in the database schema.")
                else:
                    print("ERROR: Failed to add reimbursement column!")
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            return False
    
    print("Migration completed successfully.")
    return True

if __name__ == "__main__":
    add_reimbursement_column() 