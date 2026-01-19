#!/usr/bin/env python3
"""
Migration script to add hunger_before and fullness_after columns to food_entries table
Run this on the server: python3 migrate_hunger_fullness.py
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
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(food_entries)")
        columns = [row[1] for row in cursor.fetchall()]

        needs_migration = False

        if 'hunger_before' not in columns:
            print("Adding hunger_before column to food_entries...")
            cursor.execute("""
                ALTER TABLE food_entries
                ADD COLUMN hunger_before INTEGER
            """)
            needs_migration = True

        if 'fullness_after' not in columns:
            print("Adding fullness_after column to food_entries...")
            cursor.execute("""
                ALTER TABLE food_entries
                ADD COLUMN fullness_after INTEGER
            """)
            needs_migration = True

        if needs_migration:
            conn.commit()
            print("✓ Migration completed successfully!")
        else:
            print("✓ Columns already exist, no migration needed")

        # Verify the columns were added
        cursor.execute("PRAGMA table_info(food_entries)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'hunger_before' in columns and 'fullness_after' in columns:
            print("✓ Verified: hunger_before and fullness_after columns exist")

            # Show current food entries count
            cursor.execute("SELECT COUNT(*) FROM food_entries")
            count = cursor.fetchone()[0]
            print(f"✓ {count} existing food entries (can be updated with hunger/fullness ratings)")
        else:
            print("✗ ERROR: Columns were not added")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
