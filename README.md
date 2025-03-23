# Creative Closets Payroll

A payroll management application for Creative Closets, designed to handle employee data, pay periods, timesheet entries, and generate payroll reports.

## Features

- Employee management (add, edit, delete)
- Pay period management
- Timesheet entry and tracking
- Payroll reports (PDF and CSV formats)
- Support for different pay types (hourly, salary, commission, salary+hourly)

## Requirements

- Python 3.8+
- Flask
- SQLite
- wkhtmltopdf (for PDF generation)
- Other dependencies listed in requirements.txt

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/CCPayroll.git
   cd CCPayroll
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install wkhtmltopdf (system dependency for PDF generation):
   - On Ubuntu/Debian: `sudo apt-get install wkhtmltopdf`
   - On macOS: `brew install wkhtmltopdf`
   - On Windows: Download and install from https://wkhtmltopdf.org/downloads.html

## Usage

1. Run the application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Project Structure

- `ccpayroll/` - Main application package
  - `__init__.py` - Application factory
  - `database/` - Database management
  - `models/` - Data models
  - `routes/` - Route blueprints
  - `static/` - Static assets (CSS, JS, images)
  - `templates/` - Jinja2 templates
  - `utils/` - Utility functions
  - `reports/` - Report generation

## Development

To run the application in development mode:

```bash
python app.py
```

## Testing

To run tests:

```bash
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Directory Structure

- `app.py`: Main application file
- `templates/`: HTML templates for the web interface
- `static/`: Static files (CSS, JavaScript, images)
- `data/`: JSON files for storing application data
- `uploads/`: Temporary storage for uploaded and exported files
- `requirements.txt`: List of required Python packages

## Technologies Used

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Data Processing**: Pandas, NumPy
- **Visualization**: Matplotlib
- **Data Storage**: JSON files

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Database System

The application now uses SQLite for data storage, which provides the following benefits:

1. **Data Integrity**: Prevents data corruption issues that were occurring with JSON files
2. **Transactional Support**: Each update is atomic, preventing partial writes
3. **Concurrency**: Properly handles multiple simultaneous updates
4. **Better Performance**: More efficient for larger datasets

### Migration Process

When you first run the application after this update, it will automatically:

1. Initialize the SQLite database (stored in `data/payroll.db`)
2. Migrate all existing data from JSON files to the database
3. Keep the original JSON files as backup

No manual migration steps are required. Your existing data will be preserved.

### Troubleshooting

If you experience any issues after migration:

1. Check the `data/payroll.log` file for error messages
2. Use the `/fix-timesheet/<period_id>` route to reset a specific timesheet if needed

## Heroku Deployment

To deploy this application to Heroku, follow these steps:

1. Make sure you have the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed
2. Login to Heroku:
   ```
   heroku login
   ```

3. Create a new Heroku app:
   ```
   heroku create your-app-name
   ```

4. Add the PostgreSQL add-on:
   ```
   heroku addons:create heroku-postgresql:mini
   ```

5. Set environment variables:
   ```
   heroku config:set SECRET_KEY=your_secure_secret_key
   ```

6. Deploy the application:
   ```
   git add .
   git commit -m "Prepare for Heroku deployment"
   git push heroku main
   ```

7. Initialize the database:
   ```
   heroku run python -c "from ccpayroll.database import init_db; init_db()"
   ```

8. Open the application:
   ```
   heroku open
   ```

### Important Notes

- The app uses PostgreSQL on Heroku instead of SQLite
- Local file uploads are not persistent on Heroku due to its ephemeral filesystem. For production use, consider using a service like AWS S3 for file storage.
- You might need to scale your dyno:
  ```
  heroku ps:scale web=1
  ``` 