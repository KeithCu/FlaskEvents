from app import Base, engine, SessionLocal, Event, initialize_fts
from datetime import datetime
import os
from sqlalchemy import text

def migrate_database():
    """Migrate existing database to add recurring event columns"""
    print("Starting database migration...")
    
    with engine.connect() as conn:
        # Check if the new columns already exist
        result = conn.execute(text("""
            SELECT name FROM pragma_table_info('event') 
            WHERE name IN ('is_recurring', 'recurring_until', 'is_virtual', 'is_hybrid', 'url')
        """)).fetchall()
        
        existing_columns = [row[0] for row in result]
        print(f"Existing columns: {existing_columns}")
        
        # Add is_recurring column if it doesn't exist
        if 'is_recurring' not in existing_columns:
            print("Adding is_recurring column...")
            conn.execute(text("ALTER TABLE event ADD COLUMN is_recurring BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Added is_recurring column")
        
        # Add recurring_until column if it doesn't exist
        if 'recurring_until' not in existing_columns:
            print("Adding recurring_until column...")
            conn.execute(text("ALTER TABLE event ADD COLUMN recurring_until DATE"))
            conn.commit()
            print("Added recurring_until column")
        
        # Add virtual event columns if they don't exist
        if 'is_virtual' not in existing_columns:
            print("Adding is_virtual column...")
            conn.execute(text("ALTER TABLE event ADD COLUMN is_virtual BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Added is_virtual column")
        
        if 'is_hybrid' not in existing_columns:
            print("Adding is_hybrid column...")
            conn.execute(text("ALTER TABLE event ADD COLUMN is_hybrid BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Added is_hybrid column")
        
        # Handle URL field migration
        if 'url' not in existing_columns:
            print("Adding url column...")
            conn.execute(text("ALTER TABLE event ADD COLUMN url VARCHAR(500)"))
            conn.commit()
            print("Added url column")
        
        # Create indexes if they don't exist
        indexes = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name IN ('idx_recurring', 'idx_virtual')
        """)).fetchall()
        
        existing_indexes = [row[0] for row in indexes]
        
        if 'idx_recurring' not in existing_indexes:
            print("Creating recurring events index...")
            conn.execute(text("""
                CREATE INDEX idx_recurring ON event (is_recurring, recurring_until)
            """))
            conn.commit()
            print("Created recurring events index")
        
        if 'idx_virtual' not in existing_indexes:
            print("Creating virtual events index...")
            conn.execute(text("""
                CREATE INDEX idx_virtual ON event (is_virtual, is_hybrid)
            """))
            conn.commit()
            print("Created virtual events index")
        
        # Update existing events to set is_recurring flag
        print("Updating existing events...")
        session = SessionLocal()
        try:
            # Find events with rrule and set is_recurring flag
            events_with_rrule = session.query(Event).filter(
                Event.rrule.isnot(None),
                Event.rrule != ''
            ).all()
            
            for event in events_with_rrule:
                event.is_recurring = True
                # Set recurring_until to 2 years from start if not set
                if not event.recurring_until:
                    event.recurring_until = event.start_date.replace(year=event.start_date.year + 2)
                print(f"Updated event '{event.title}' to recurring")
            
            session.commit()
            print(f"Updated {len(events_with_rrule)} events to recurring")
        finally:
            session.close()
    
    print("Database migration completed successfully!")

if __name__ == '__main__':
    migrate_database() 