#!/usr/bin/env python3
"""
Migration script to add timezone_offset column to user_profiles table
Run this on the server: python3 migrate_timezone.py
"""

import sqlite3
import os
import sys

# Database path
DB_PATH = os.getenv("DB_PATH", "/opt/yourbody-pro/bot.db")

def migrate():
    print(f"Connecting to database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if timezone_offset column already exists
        cursor.execute("PRAGMA table_info(user_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'timezone_offset' in columns:
            print("✓ timezone_offset column already exists, no migration needed")
            return

        print("Adding timezone_offset column to user_profiles...")

        # Add timezone_offset column with default value 180 (MSK)
        cursor.execute("""
            ALTER TABLE user_profiles
            ADD COLUMN timezone_offset INTEGER DEFAULT 180
        """)

        conn.commit()
        print("✓ Migration completed successfully!")

        # Verify the column was added
        cursor.execute("PRAGMA table_info(user_profiles)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'timezone_offset' in columns:
            print("✓ Verified: timezone_offset column exists")

            # Show current user count
            cursor.execute("SELECT COUNT(*) FROM user_profiles")
            count = cursor.fetchone()[0]
            print(f"✓ {count} existing user profiles will use default timezone (MSK +3)")
        else:
            print("✗ ERROR: Column was not added")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
