"""
Creative Closets Payroll Application
====================================

A Flask application for managing payroll for Creative Closets.
"""

import os
import logging
from datetime import datetime
from flask import Flask, url_for

def create_app(test_config=None):
    """Create and configure the Flask application"""
    app = Flask(__name__, instance_relative_config=True)
    
    # Default configuration
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'payroll.sqlite'),
        UPLOAD_FOLDER=os.path.join(app.instance_path, 'uploads'),
        REPORT_FOLDER=os.path.join(app.instance_path, 'reports'),
        DATA_FOLDER=os.path.join(app.instance_path, 'data'),
    )
    
    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
        os.makedirs(app.config['DATA_FOLDER'], exist_ok=True)
    except OSError:
        pass
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(app.instance_path, 'payroll.log')),
            logging.StreamHandler()
        ]
    )
    
    # Initialize database
    from .database import init_app
    init_app(app)
    
    # Add context processor for templates
    @app.context_processor
    def utility_processor():
        def now():
            return datetime.now()
        return dict(now=now)
    
    # Register blueprints
    from .routes import main, employees, pay_periods, timesheet, reports
    
    app.register_blueprint(main)
    app.register_blueprint(employees)
    app.register_blueprint(pay_periods)
    app.register_blueprint(timesheet)
    app.register_blueprint(reports)
    
    # Add URL rule for the index page
    app.add_url_rule('/', endpoint='index')
    
    return app 