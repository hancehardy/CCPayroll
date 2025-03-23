import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('init_db')

# Ensure DATABASE_URL is set to Postgres URL format
if 'DATABASE_URL' in os.environ and os.environ['DATABASE_URL'].startswith('postgres://'):
    os.environ['DATABASE_URL'] = os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://', 1)
    logger.info("Fixed DATABASE_URL format")

from ccpayroll.database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    try:
        init_db()
        print("Database initialization complete!")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        import traceback
        traceback.print_exc() 