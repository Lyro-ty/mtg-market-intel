#!/usr/bin/env python3
"""
Simple script to query users from the PostgreSQL database.
Run this from the project root after containers are up.
"""
import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path('.') / '.env'
if env_path.exists():
    load_dotenv(env_path)

async def query_users():
    """Query and display all users from the database."""
    # Get connection details from environment or use defaults
    user = os.getenv('POSTGRES_USER', 'mtg_user')
    password = os.getenv('POSTGRES_PASSWORD', 'mtg_password')
    database = os.getenv('POSTGRES_DB', 'mtg_market_intel')
    host = 'localhost'  # Use 'db' if running from within Docker network
    
    print(f"Connecting to database: {database} on {host}...")
    
    try:
        conn = await asyncpg.connect(
            host=host,
            port=5432,
            user=user,
            password=password,
            database=database
        )
        
        print("Connected successfully!\n")
        
        # Query all users
        rows = await conn.fetch('''
            SELECT id, email, username, display_name, is_active, 
                   is_verified, is_admin, created_at, last_login
            FROM users
            ORDER BY created_at DESC
        ''')
        
        if not rows:
            print("No users found in the database.")
            return
        
        print(f"Found {len(rows)} user(s):\n")
        print("-" * 80)
        
        for row in rows:
            print(f"ID: {row['id']}")
            print(f"  Email: {row['email']}")
            print(f"  Username: {row['username']}")
            if row['display_name']:
                print(f"  Display Name: {row['display_name']}")
            print(f"  Active: {row['is_active']}")
            print(f"  Verified: {row['is_verified']}")
            print(f"  Admin: {row['is_admin']}")
            print(f"  Created: {row['created_at']}")
            if row['last_login']:
                print(f"  Last Login: {row['last_login']}")
            print("-" * 80)
            
    except asyncpg.exceptions.InvalidPasswordError:
        print("Error: Invalid password. Check your POSTGRES_PASSWORD in .env file.")
    except asyncpg.exceptions.InvalidCatalogNameError:
        print(f"Error: Database '{database}' does not exist.")
    except asyncpg.exceptions.ConnectionRefusedError:
        print(f"Error: Could not connect to database at {host}:5432")
        print("Make sure the containers are running: docker-compose up -d")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()
            print("\nConnection closed.")

if __name__ == '__main__':
    asyncio.run(query_users())

