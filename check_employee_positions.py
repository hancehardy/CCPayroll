#!/usr/bin/env python3
"""
Simple script to check employees in the database
"""

import os
from flask import Flask
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

def get_db_connection():
    """Get database connection"""
    # Check for Heroku DATABASE_URL first
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Handle Heroku's postgres:// vs postgresql:// in the connection URL
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Connect using the DATABASE_URL
        return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    else:
        # Use local configuration
        host = os.environ.get('PG_HOST', 'localhost')
        port = os.environ.get('PG_PORT', '5432')
        user = os.environ.get('PG_USER', 'postgres')
        password = os.environ.get('PG_PASSWORD', 'postgres')
        db_name = os.environ.get('PG_DB', 'ccpayroll')
        
        # Connect to PostgreSQL
        return psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=db_name,
            cursor_factory=RealDictCursor
        )

def main():
    """Main function"""
    with app.app_context():
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, position, pay_type FROM employees ORDER BY name")
                rows = cursor.fetchall()
                
                print(f"Found {len(rows)} employees:")
                for row in rows:
                    print(f"Name: {row['name']}, Position: {row['position']}, Pay Type: {row['pay_type']}")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 