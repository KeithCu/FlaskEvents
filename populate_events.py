from app import Base, engine, SessionLocal, Event, Venue, get_next_event_ids
from datetime import datetime, timedelta
import random
from faker import Faker

fake = Faker()

def generate_event_title():
    event_types = [
        "Team Meeting", "Client Presentation", "Workshop", "Training Session",
        "Product Launch", "Strategy Session", "Review Meeting", "Brainstorming",
        "Quarterly Planning", "Team Building", "Conference Call", "Demo Day",
        "Hackathon", "Code Review", "Sprint Planning", "Retrospective",
        "All-Hands Meeting", "Town Hall", "Interview", "Onboarding"
    ]
    return f"{random.choice(event_types)} - {fake.word().capitalize()} {fake.word().capitalize()}"

def generate_event_description():
    return fake.paragraph(nb_sentences=3)

def generate_event_colors():
    colors = [
        "#3788d8", "#28a745", "#dc3545", "#ffc107", "#17a2b8",
        "#6610f2", "#fd7e14", "#20c997", "#e83e8c", "#6f42c1"
    ]
    color = random.choice(colors)
    return color, color

def populate_events():
    # Create tables
    Base.metadata.create_all(engine)
    
    # Create a session
    session = SessionLocal()
    
    try:
        # Get a venue for the events
        venue = session.query(Venue).first()
        if not venue:
            print("No venues found. Please run populate_venues.py first.")
            return

        # Calculate number of days needed for 100,000 events with 30 events per day
        total_events = 100000
        events_per_day = 30
        total_days = total_events // events_per_day
        
        # Start date
        start_date = datetime(2025, 1, 1)
        
        # Generate events
        events = []
        for day in range(total_days):
            current_date = start_date + timedelta(days=day)
            
            # Generate 30 events for this day
            for _ in range(events_per_day):
                # Random start time between 8 AM and 8 PM
                start_hour = random.randint(8, 20)
                start_minute = random.choice([0, 15, 30, 45])
                
                # Random duration between 30 minutes and 3 hours
                duration_hours = random.randint(0, 2)
                duration_minutes = random.choice([0, 15, 30, 45])
                
                start_time = current_date.replace(
                    hour=start_hour,
                    minute=start_minute,
                    second=0,
                    microsecond=0
                )
                
                end_time = start_time + timedelta(
                    hours=duration_hours,
                    minutes=duration_minutes
                )
                
                # Ensure end time doesn't go past midnight
                if end_time.day > start_time.day:
                    end_time = start_time.replace(hour=23, minute=59)
                
                color, bg = generate_event_colors()
                
                event = Event(
                    title=generate_event_title(),
                    description=generate_event_description(),
                    start=start_time,
                    end=end_time,
                    venue_id=venue.id,
                    color=color,
                    bg=bg
                )
                events.append(event)
                
                # Commit in batches of 1000 to avoid memory issues
                if len(events) >= 1000:
                    # Generate IDs for this batch
                    get_next_event_ids(session, events)
                    session.bulk_save_objects(events)
                    session.commit()
                    print(f"Added {len(events)} events...")
                    events = []
        
        # Commit any remaining events
        if events:
            # Generate IDs for the final batch
            get_next_event_ids(session, events)
            session.bulk_save_objects(events)
            session.commit()
            print(f"Added final {len(events)} events...")
        
        print("All events have been added successfully!")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    populate_events() 