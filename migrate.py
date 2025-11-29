#!/usr/bin/env python3
"""Database migration script to add format_id and quality columns"""

import sys
from sqlalchemy import create_engine, text
from config import settings

def migrate():
    """Add format_id and quality columns to download_tasks table"""
    print("Starting database migration...")
    
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Check if columns already exist
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='download_tasks' 
                AND column_name IN ('format_id', 'quality')
            """))
            
            existing_columns = [row[0] for row in result]
            
            # Add format_id column if it doesn't exist
            if 'format_id' not in existing_columns:
                print("Adding format_id column...")
                conn.execute(text("""
                    ALTER TABLE download_tasks 
                    ADD COLUMN format_id VARCHAR(255) DEFAULT NULL
                """))
                conn.commit()
                print("✅ format_id column added successfully")
            else:
                print("ℹ️  format_id column already exists")
            
            # Add quality column if it doesn't exist
            if 'quality' not in existing_columns:
                print("Adding quality column...")
                conn.execute(text("""
                    ALTER TABLE download_tasks 
                    ADD COLUMN quality VARCHAR(50) DEFAULT NULL
                """))
                conn.commit()
                print("✅ quality column added successfully")
            else:
                print("ℹ️  quality column already exists")
            
            print("\n✅ Migration completed successfully!")
            return True
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False
    finally:
        engine.dispose()

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)