from datetime import datetime, timedelta
import random
from faker import Faker
import argparse

from fts import setup_fts_triggers
from app import Base, engine, SessionLocal, Event, Venue
from database import get_next_event_ids, migrate_database

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

def generate_recurring_pattern(indefinite_count, max_indefinite=10):
    """Generate recurring pattern with various expiration dates"""
    patterns = [
        # Indefinite events (limited to max_indefinite total)
        {"recurrence": "weekly", "expires": None, "weight": 1 if indefinite_count < max_indefinite else 0},
        # Short-term recurring events (few days to few weeks)
        {"recurrence": "daily", "expires": random.randint(3, 7), "weight": 2},
        {"recurrence": "weekly", "expires": random.randint(1, 4), "weight": 2},
        # Medium-term recurring events (few weeks to few months)
        {"recurrence": "weekly", "expires": random.randint(4, 12), "weight": 2},
        {"recurrence": "monthly", "expires": random.randint(1, 3), "weight": 1},
        # Non-recurring events (90% of events)
        {"recurrence": None, "expires": None, "weight": 90}
    ]
    
    # Weighted selection
    total_weight = sum(p["weight"] for p in patterns)
    if total_weight == 0:
        # If no patterns available (e.g., all indefinite slots filled), default to non-recurring
        return {"recurrence": None, "expires": None, "weight": 90}
    
    rand = random.uniform(0, total_weight)
    current_weight = 0
    
    for pattern in patterns:
        current_weight += pattern["weight"]
        if rand <= current_weight:
            return pattern
    
    return patterns[-1]  # Default to non-recurring

def populate_events(total_events=50000):
    # Create tables
    Base.metadata.create_all(engine)
    
    # Run migration to ensure categories are set up
    print("Running database migration...")
    migrate_database()
    
    # Create a session
    session = SessionLocal()
    
    try:
        # Get all venues
        venues = session.query(Venue).all()
        if not venues:
            print("No venues found. Please run populate_venues.py first.")
            return

        print(f"Found {len(venues)} venues:")
        for venue in venues:
            print(f"ID: {venue.id}, Name: {venue.name}")

        # Calculate number of days needed with 30 events per day
        events_per_day = 30
        total_days = total_events // events_per_day
        
        # Start date
        start_date = datetime(2025, 1, 1)
        
        # Generate events
        events = []
        venue_counts = {venue.id: 0 for venue in venues}  # Track venue usage
        indefinite_events_total = 0  # Track total indefinite events
        ongoing_events_today = 0  # Track ongoing events for current day
        
        for day in range(total_days):
            current_date = start_date + timedelta(days=day)
            
            # Reset ongoing events counter for each day
            ongoing_events_today = 0
            
            # Generate events for this day
            for _ in range(events_per_day):
                # Specific start hours between 8 AM and 11 PM
                start_hour = random.choice([8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23])
                
                # Determine if this should be an ongoing event (stretching to next day)
                should_be_ongoing = False
                if ongoing_events_today < 3 and random.random() < 0.1:  # 10% chance, max 3 per day
                    should_be_ongoing = True
                    ongoing_events_today += 1
                
                # Random duration - shorter for most events, longer for ongoing events
                if should_be_ongoing:
                    # Ongoing events: 8-18 hours (to stretch to next day)
                    duration_hours = random.randint(8, 18)
                else:
                    # Regular events: 1-6 hours
                    duration_hours = random.randint(1, 6)
                
                start_time = current_date.replace(
                    hour=start_hour,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                
                end_time = start_time + timedelta(hours=duration_hours)
                
                # For ongoing events, ensure they stretch to next day but not past noon
                if should_be_ongoing and end_time.day > start_time.day:
                    if end_time.hour > 12:
                        end_time = end_time.replace(hour=12, minute=0)
                elif not should_be_ongoing and end_time.day > start_time.day:
                    # Regular events shouldn't cross midnight
                    end_time = start_time.replace(hour=23, minute=59)
                
                color, bg = generate_event_colors()
                
                # Select venue with least events
                venue = min(venues, key=lambda v: venue_counts[v.id])
                venue_counts[venue.id] += 1
                
                # Generate recurring pattern
                pattern = generate_recurring_pattern(indefinite_events_total, max_indefinite=10)
                
                # Track indefinite events
                if pattern["recurrence"] == "weekly" and pattern["expires"] is None:
                    indefinite_events_total += 1
                    print(f"Created indefinite event #{indefinite_events_total}/10")
                
                # Calculate expiration date if needed
                recurring_until = None
                rrule = None
                is_recurring = False
                
                if pattern["recurrence"] is not None:
                    is_recurring = True
                    
                    # Generate RRULE based on recurrence pattern
                    if pattern["recurrence"] == "daily":
                        rrule = "FREQ=DAILY"
                        if pattern["expires"] is not None:
                            recurring_until = current_date + timedelta(days=pattern["expires"])
                    elif pattern["recurrence"] == "weekly":
                        rrule = "FREQ=WEEKLY"
                        if pattern["expires"] is not None:
                            recurring_until = current_date + timedelta(weeks=pattern["expires"])
                    elif pattern["recurrence"] == "monthly":
                        rrule = "FREQ=MONTHLY"
                        if pattern["expires"] is not None:
                            recurring_until = current_date + timedelta(days=pattern["expires"] * 30)
                
                event = Event(
                    title=generate_event_title(),
                    description=generate_event_description(),
                    start=start_time,
                    end=end_time,
                    venue_id=venue.id,
                    color=color,
                    bg=bg,
                    is_recurring=is_recurring,
                    recurring_until=recurring_until,
                    rrule=rrule
                )
                events.append(event)
                
                # Commit in batches of 1000 to avoid memory issues
                if len(events) >= 1000:
                    # Generate IDs for this batch
                    get_next_event_ids(session, events)
                    session.bulk_save_objects(events)
                    session.commit()
                    print(f"Added {len(events)} events... (Indefinite events: {indefinite_events_total}/10, Ongoing events today: {ongoing_events_today})")
                    print("Current venue distribution:")
                    for v in venues:
                        print(f"Venue {v.name}: {venue_counts[v.id]} events")
                    events = []
        
        # Commit any remaining events
        if events:
            # Generate IDs for the final batch
            get_next_event_ids(session, events)
            session.bulk_save_objects(events)
            session.commit()
            print(f"Added final {len(events)} events...")
            print("Final venue distribution:")
            for v in venues:
                print(f"Venue {v.name}: {venue_counts[v.id]} events")
        
        print(f"All events have been added successfully! Total indefinite events: {indefinite_events_total}/10")
        
        # Set up FTS after populating events
        print("Setting up FTS for search functionality...")
        setup_fts_triggers()
        print("FTS setup completed!")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Populate events in the database')
    parser.add_argument('--total-events', type=int, default=50000,
                      help='Total number of events to create (default: 50000)')
    args = parser.parse_args()
    populate_events(args.total_events) 