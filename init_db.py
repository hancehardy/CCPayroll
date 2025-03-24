#!/usr/bin/env python
"""
Simple initialization script to create the database tables on Heroku
"""

from ccpayroll.database import init_db
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('init_db')

logger.info("Initializing database tables...")
init_db()
logger.info("Database initialization complete!") 