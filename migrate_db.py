from app import Base, engine, SessionLocal, Event
from datetime import datetime

def migrate_database():
    # Drop all tables
    Base.metadata.drop_all(engine)
    
    # Create tables with new schema
    Base.metadata.create_all(engine)
    
    print("Database schema has been updated successfully!")

if __name__ == "__main__":
    migrate_database() 