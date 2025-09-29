#!/usr/bin/env python3
"""Test PostgreSQL database connection using credentials from 1.env file"""

import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from the 1.env file
load_dotenv('/home/mohammed/Desktop/tech_projects/growbal/envs/1.env')

# Get database credentials from environment
postgres_host = os.getenv('POSTGRES_HOST').strip("'")
postgres_port = os.getenv('POSTGRES_PORT').strip("'")
postgres_user = os.getenv('POSTGRES_DB_USERNAME').strip("'")
postgres_password = os.getenv('POSTGRES_DB_PASSWORD').strip("'")
postgres_db = os.getenv('POSTGRES_DB_NAME').strip("'")

print("Connecting to PostgreSQL with:")
print(f"Host: {postgres_host}")
print(f"Port: {postgres_port}")
print(f"Database: {postgres_db}")
print(f"User: {postgres_user}")
print(f"Password: {postgres_password}")

try:
    conn = psycopg2.connect(
        host=postgres_host,
        database=postgres_db,
        user=postgres_user,
        password=postgres_password,
        port=postgres_port
    )
    print("\n✅ Successfully connected to PostgreSQL!")
    
    # Create cursor for executing queries
    cursor = conn.cursor()
    
    # Test basic database access with schema query
    print("\n📋 Testing database schema access...")
    
    # Query to list all tables in the database
    cursor.execute("""
        SELECT table_name, table_schema 
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name;
    """)
    
    tables = cursor.fetchall()
    
    if tables:
        print(f"\n📊 Found {len(tables)} tables:")
        for table_name, schema_name in tables:
            print(f"  - {schema_name}.{table_name}")
    else:
        print("\n⚠️  No user tables found in the database")
    
    # Get database version
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"\n🐘 PostgreSQL Version: {version}")
    
    # Get current database name
    cursor.execute("SELECT current_database();")
    current_db = cursor.fetchone()[0]
    print(f"📂 Current Database: {current_db}")
    
    cursor.close()
    
except psycopg2.Error as e:
    print(f"\n❌ Database connection failed: {e}")
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
finally:
    if 'conn' in locals() and conn:
        conn.close()
        print("\n🔌 Database connection closed")