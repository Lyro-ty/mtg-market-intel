# Querying PostgreSQL Database for Users

This guide shows you how to query your PostgreSQL database for users once the containers are running.

## Database Connection Details

- **Container Name**: `mtg-db`
- **Host**: `localhost` (from host machine) or `db` (from within Docker network)
- **Port**: `5432`
- **Database**: `mtg_market_intel` (default) or check your `.env` file
- **Username**: `mtg_user` (default) or check your `.env` file
- **Password**: `mtg_password` (default) or check your `.env` file

## Method 1: Using Docker Exec (Easiest)

Run psql directly inside the container:

```bash
# Interactive psql session
docker exec -it mtg-db psql -U mtg_user -d mtg_market_intel

# Then run SQL queries:
SELECT * FROM users;
SELECT id, email, username, display_name, is_active, is_verified, is_admin, created_at FROM users;
SELECT COUNT(*) FROM users;
```

Or run a single query:

```bash
docker exec -it mtg-db psql -U mtg_user -d mtg_market_intel -c "SELECT id, email, username, display_name, is_active, is_verified, is_admin, created_at FROM users;"
```

## Method 2: Using psql from Host Machine

If you have PostgreSQL client tools installed on your host machine:

```bash
# Connect to the database
psql -h localhost -p 5432 -U mtg_user -d mtg_market_intel

# When prompted, enter password: mtg_password
```

Then run your queries:
```sql
SELECT * FROM users;
SELECT id, email, username, display_name, is_active, is_verified, is_admin, created_at FROM users;
```

## Method 3: Using Python Script

Create a Python script to query users:

```python
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def query_users():
    # Get connection details from environment or use defaults
    user = os.getenv('POSTGRES_USER', 'mtg_user')
    password = os.getenv('POSTGRES_PASSWORD', 'mtg_password')
    database = os.getenv('POSTGRES_DB', 'mtg_market_intel')
    host = 'localhost'  # Use 'db' if running from within Docker network
    
    conn = await asyncpg.connect(
        host=host,
        port=5432,
        user=user,
        password=password,
        database=database
    )
    
    try:
        # Query all users
        rows = await conn.fetch('''
            SELECT id, email, username, display_name, is_active, 
                   is_verified, is_admin, created_at, last_login
            FROM users
            ORDER BY created_at DESC
        ''')
        
        print(f"\nFound {len(rows)} users:\n")
        for row in rows:
            print(f"ID: {row['id']}")
            print(f"  Email: {row['email']}")
            print(f"  Username: {row['username']}")
            print(f"  Display Name: {row['display_name']}")
            print(f"  Active: {row['is_active']}")
            print(f"  Verified: {row['is_verified']}")
            print(f"  Admin: {row['is_admin']}")
            print(f"  Created: {row['created_at']}")
            print(f"  Last Login: {row['last_login']}")
            print()
            
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(query_users())
```

## Method 4: Using Database GUI Tools

You can connect using any PostgreSQL client tool:

### pgAdmin
- Host: `localhost`
- Port: `5432`
- Database: `mtg_market_intel`
- Username: `mtg_user`
- Password: `mtg_password`

### DBeaver
- Database Type: PostgreSQL
- Host: `localhost`
- Port: `5432`
- Database: `mtg_market_intel`
- Username: `mtg_user`
- Password: `mtg_password`

### TablePlus / DataGrip / Other Tools
Use the same connection details as above.

## Common SQL Queries

### List all users
```sql
SELECT * FROM users;
```

### List users with specific fields
```sql
SELECT id, email, username, display_name, is_active, is_verified, is_admin, created_at 
FROM users;
```

### Count total users
```sql
SELECT COUNT(*) FROM users;
```

### Find active users
```sql
SELECT id, email, username, is_active 
FROM users 
WHERE is_active = true;
```

### Find admin users
```sql
SELECT id, email, username, is_admin 
FROM users 
WHERE is_admin = true;
```

### Find users by email
```sql
SELECT * FROM users WHERE email = 'user@example.com';
```

### Find users created in the last 7 days
```sql
SELECT id, email, username, created_at 
FROM users 
WHERE created_at >= NOW() - INTERVAL '7 days';
```

### Get user with their inventory count
```sql
SELECT u.id, u.email, u.username, COUNT(i.id) as inventory_count
FROM users u
LEFT JOIN inventory_items i ON u.id = i.user_id
GROUP BY u.id, u.email, u.username;
```

## Troubleshooting

### Container not running
```bash
docker ps
# If mtg-db is not listed, start containers:
docker-compose up -d
```

### Connection refused
- Make sure the container is running: `docker ps`
- Check if port 5432 is already in use
- Verify the container is healthy: `docker ps` should show "healthy" status

### Authentication failed
- Check your `.env` file for `POSTGRES_USER` and `POSTGRES_PASSWORD`
- Default values are `mtg_user` and `mtg_password` if not set in `.env`

### Database doesn't exist
- The database should be created automatically when the container starts
- Check logs: `docker logs mtg-db`

