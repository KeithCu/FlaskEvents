from database import engine, SessionLocal, Base, Venue, migrate_database
import re
from fts import setup_fts_triggers

# List of venues extracted from the provided text
venues = [
    "Collected Detroit",
    "TV Lounge",
    "Hart Plaza",
    "Gregory Marina",
    "Leland City Club",
    "Marble Bar",
    "McShane's Pub",
    "Foxglove",
    "SPKR BOX",
    "Batch Brewing Company",
    "Level Two Bar",
    "Moondog Café",
    "Society Detroit",
    "Two James",
    "The Diamond Queen River Boat",
    "Common Pub",
    "MotorCity Wine",
    "225 Speakeasy",
    "Spot Lite",
    "UFO Bar",
    "Johnny Noodle King",
    "The Shadow Gallery",
    "Mudgie's",
    "Third Street Bar",
    "Corktown Tavern",
    "The Old Miami",
    "Temple Bar",
    "Menjo's",
    "Red Door Digital",
    "Tangent Gallery",
    "Bert's Warehouse Theatre",
    "Lincoln Factory",
    "Magic Stick",
    "7824 Mount Elliot Street",
    "The Russell Industrial Center",
    "Trumbullplex",
    "Well Done Goods",
    "Good Life"
]

def populate_venues():
    # Create tables first, before any model relationships are accessed
    print("Creating database tables...")
    Base.metadata.create_all(engine)
    
    # Run migration to ensure categories are set up
    print("Running database migration...")
    migrate_database()
    
    # Create a session
    session = SessionLocal()
    
    try:
        # Add each venue
        print("Setting up venues...")
        for venue_name in venues:
            # Check if venue already exists
            existing_venue = session.query(Venue).filter_by(name=venue_name).first()
            if not existing_venue:
                venue = Venue(name=venue_name)
                session.add(venue)
                print(f"Added venue: {venue_name}")
        
        # Commit the changes
        session.commit()
        print("All venues have been added successfully!")
        
        # Set up FTS triggers
        setup_fts_triggers()
        
    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    populate_venues() 