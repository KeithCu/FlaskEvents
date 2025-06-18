from app import Base, engine, SessionLocal, Event, initialize_fts
from datetime import datetime
import os

def migrate_database():
    # Get the database path
    db_path = os.path.join(os.path.dirname(__file__), 'events.db')
    
    # Close any existing connections
    engine.dispose()
    
    # Remove the existing database file if it exists
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print("Removed existing database file")
        except Exception as e:
            print(f"Error removing database file: {e}")
            return
    
    try:
        # Create tables with new schema
        Base.metadata.create_all(engine)
        print("Created new database schema")
        
        # Initialize FTS
        initialize_fts()
        print("Initialized FTS")
        
        print("Database schema has been updated successfully!")
    except Exception as e:
        print(f"Error during migration: {e}")
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                print("Removed corrupted database file")
            except:
                pass
        raise

if __name__ == "__main__":
    migrate_database() 