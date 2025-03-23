# SQLite to PostgreSQL Migration Script

This script migrates the Creative Closets Payroll database from SQLite to PostgreSQL. It's designed specifically for deploying on Heroku, but can also be run locally with the correct configuration.

## Features

- Complete schema extraction from SQLite
- Data type mapping from SQLite to PostgreSQL 
- Automatic table creation with proper constraints
- Batch migration of all data
- Error handling and detailed logging
- Migration validation to verify data integrity

## Prerequisites

- Python 3.6+
- Access to both SQLite database and target PostgreSQL database
- Required Python packages (see requirements.txt)

## Installation

1. Make sure the SQLite database exists at `data/payroll.db`
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Local Development

1. Create a `.env` file in the project root with the following content:

```
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
LOG_LEVEL=INFO
```

2. Run the migration script:

```bash
python migrate_db.py
```

### Heroku Deployment

1. Make sure your Heroku app has the PostgreSQL addon installed:

```bash
heroku addons:create heroku-postgresql:mini
```

2. Push your code to Heroku:

```bash
git push heroku main
```

3. Copy your SQLite database to Heroku (if needed):

```bash
heroku run bash
mkdir -p data
# Use sftp or other means to transfer your SQLite database to Heroku's data/ folder
```

4. Run the migration script on Heroku:

```bash
heroku run python migrate_db.py
```

Alternatively, you can run the migration locally against your Heroku PostgreSQL database:

```bash
# Get your Heroku database URL
heroku config:get DATABASE_URL

# Set it as an environment variable or in your .env file
export DATABASE_URL=postgres://user:password@host:port/dbname

# Run the migration script
python migrate_db.py
```

## Monitoring and Troubleshooting

- The script creates a timestamped log file `migration_YYYYMMDD_HHMMSS.log`
- All log messages are also printed to the console
- Set `LOG_LEVEL=DEBUG` for more detailed logging
- Check Heroku logs with `heroku logs --tail`

## After Migration

After successfully migrating to PostgreSQL, you'll need to update your application to use the PostgreSQL database instead of SQLite:

1. Update your database connection code to use the `DATABASE_URL` environment variable
2. Make sure your application includes the proper PostgreSQL driver (`psycopg2`)
3. Test your application with the new database

## Common Issues

- **Connection Issues**: Ensure your DATABASE_URL is correctly formatted and the database is accessible
- **Permission Errors**: Make sure your PostgreSQL user has proper permissions
- **Data Type Mismatches**: Check the log for any type conversion errors and adjust the mapping if needed

## Notes for Heroku Deployment

- Heroku uses dynamically assigned DATABASE_URL, so hard-coded connection strings will not work
- Heroku's filesystem is ephemeral, so any SQLite database in the app will be lost on dyno restart
- Consider transferring your data to a temporary PostgreSQL database locally, then using pg_dump/pg_restore to move it to Heroku 