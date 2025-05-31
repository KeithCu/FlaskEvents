from app import Base, engine, SessionLocal, Event, Venue
from datetime import datetime, timedelta
import time
import random
from sqlalchemy import create_engine, text, Index, Column, Integer, Date, DateTime, String, Text, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import statistics
import os

# Create a new base for the conventional table
ConventionalBase = declarative_base()

# Create Venue model for conventional approach
class ConventionalVenue(ConventionalBase):
    __tablename__ = 'conventional_venue'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(Text)
    
    conventional_events = relationship("ConventionalEvent", back_populates="venue")

class ConventionalEvent(ConventionalBase):
    __tablename__ = 'conventional_event'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(Date, nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=False)
    rrule = Column(String(255))
    venue_id = Column(Integer, ForeignKey('conventional_venue.id'))
    color = Column(String(20))
    bg = Column(String(20))
    
    venue = relationship("ConventionalVenue", back_populates="conventional_events")
    
    __table_args__ = (
        Index('idx_start_date', 'start_date'),
    )

def create_test_data(session, num_days=3334, events_per_day=30):
    """Create test data for both approaches"""
    print(f"Creating test data: {num_days} days with {events_per_day} events per day")
    print(f"Total events to create: {num_days * events_per_day}")
    
    # Create test venues for both approaches
    venue = Venue(name="Test Venue", address="Test Address")
    session.add(venue)
    
    conventional_venue = ConventionalVenue(name="Test Venue", address="Test Address")
    session.add(conventional_venue)
    session.commit()
    
    # Generate events
    base_date = datetime(2025, 1, 1)
    events = []
    conventional_events = []
    
    # Create all events first with random date variations
    for day in range(num_days):
        current_date = base_date + timedelta(days=day)
        for i in range(events_per_day):
            # Add random variation to the date (-2 to +2 days)
            date_variation = random.randint(-2, 2)
            event_date = current_date + timedelta(days=date_variation)
            
            # Random time between 8 AM and 10 PM
            start_time = event_date.replace(
                hour=random.randint(8, 22),
                minute=random.choice([0, 15, 30, 45]),
                second=0,
                microsecond=0
            )
            end_time = start_time + timedelta(hours=random.randint(1, 3))
            
            # Create both types of events
            event = Event(
                title=f"Test Event {day}-{i}",
                description="Test Description",
                start=start_time,
                end=end_time,
                venue_id=venue.id,
                color="#3788d8",
                bg="#3788d8"
            )
            events.append(event)
            
            conventional_event = ConventionalEvent(
                title=f"Test Event {day}-{i}",
                description="Test Description",
                start=start_time,
                end=end_time,
                start_date=start_time.date(),
                venue_id=conventional_venue.id,
                color="#3788d8",
                bg="#3788d8"
            )
            conventional_events.append(conventional_event)
            
            # Print progress every 10,000 events
            if len(events) % 10000 == 0:
                print(f"Created {len(events)} events so far...")
    
    print("Shuffling events for random insertion order...")
    # Shuffle events to ensure they're not inserted in chronological order
    random.shuffle(events)
    random.shuffle(conventional_events)
    
    # Insert in batches of 1000
    batch_size = 1000
    total_batches = (len(events) + batch_size - 1) // batch_size
    
    print("\nInserting clustered events...")
    for i in range(0, len(events), batch_size):
        batch = events[i:i + batch_size]
        session.bulk_save_objects(batch)
        session.commit()
        print(f"Inserted batch {i//batch_size + 1} of {total_batches}")
    
    print("\nInserting conventional events...")
    for i in range(0, len(conventional_events), batch_size):
        batch = conventional_events[i:i + batch_size]
        session.bulk_save_objects(batch)
        session.commit()
        print(f"Inserted batch {i//batch_size + 1} of {total_batches}")

def test_clustered_index(session, num_queries=200):
    """Test performance of our clustered index approach"""
    print("\nTesting clustered index approach...")
    results = {
        'single_day': [],
        'date_range_3': [],
        'date_range_7': []
    }
    
    for _ in range(num_queries):
        # Random date in our test range
        test_date = datetime(2025, 1, 1) + timedelta(days=random.randint(0, 29))
        
        # Test 1: Single day query
        start_time = time.time()
        events = session.query(Event).filter(
            Event.start_date == test_date.date()
        ).all()
        end_time = time.time()
        results['single_day'].append(end_time - start_time)
        
        # Test 2: 3-day range query
        start_time = time.time()
        events = session.query(Event).filter(
            Event.start_date >= test_date.date(),
            Event.start_date < test_date.date() + timedelta(days=3)
        ).all()
        end_time = time.time()
        results['date_range_3'].append(end_time - start_time)
        
        # Test 3: 7-day range query
        start_time = time.time()
        events = session.query(Event).filter(
            Event.start_date >= test_date.date(),
            Event.start_date < test_date.date() + timedelta(days=7)
        ).all()
        end_time = time.time()
        results['date_range_7'].append(end_time - start_time)
        
        # Print progress every 50 queries
        if (_ + 1) % 50 == 0:
            print(f"Completed {_ + 1} queries...")
    
    return {query_type: {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'min': min(times),
        'max': max(times),
        'std_dev': statistics.stdev(times) if len(times) > 1 else 0
    } for query_type, times in results.items()}

def test_conventional_index(session, num_queries=200):
    """Test performance of conventional index approach"""
    print("\nTesting conventional index approach...")
    
    results = {
        'single_day': [],
        'date_range_3': [],
        'date_range_7': []
    }
    
    for _ in range(num_queries):
        # Random date in our test range
        test_date = datetime(2025, 1, 1) + timedelta(days=random.randint(0, 29))
        
        # Test 1: Single day query
        start_time = time.time()
        events = session.query(ConventionalEvent).filter(
            ConventionalEvent.start_date == test_date.date()
        ).all()
        end_time = time.time()
        results['single_day'].append(end_time - start_time)
        
        # Test 2: 3-day range query
        start_time = time.time()
        events = session.query(ConventionalEvent).filter(
            ConventionalEvent.start_date >= test_date.date(),
            ConventionalEvent.start_date < test_date.date() + timedelta(days=3)
        ).all()
        end_time = time.time()
        results['date_range_3'].append(end_time - start_time)
        
        # Test 3: 7-day range query
        start_time = time.time()
        events = session.query(ConventionalEvent).filter(
            ConventionalEvent.start_date >= test_date.date(),
            ConventionalEvent.start_date < test_date.date() + timedelta(days=7)
        ).all()
        end_time = time.time()
        results['date_range_7'].append(end_time - start_time)
        
        # Print progress every 50 queries
        if (_ + 1) % 50 == 0:
            print(f"Completed {_ + 1} queries...")
    
    return {query_type: {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'min': min(times),
        'max': max(times),
        'std_dev': statistics.stdev(times) if len(times) > 1 else 0
    } for query_type, times in results.items()}

def run_performance_test():
    """Run the complete performance test"""
    # Drop existing database and create a new one
    db_path = 'test_events.db'
    if os.path.exists(db_path):
        print(f"Removing existing database: {db_path}")
        os.remove(db_path)
    
    # Create a new test database
    engine = create_engine('sqlite:///test_events.db')
    Base.metadata.create_all(engine)
    ConventionalBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    session = SessionLocal()
    try:
        # Create test data
        create_test_data(session)
        
        # Run tests
        clustered_results = test_clustered_index(session)
        conventional_results = test_conventional_index(session)
        
        # Print results
        print("\nPerformance Test Results:")
        
        for query_type in ['single_day', 'date_range_3', 'date_range_7']:
            print(f"\n{query_type.replace('_', ' ').title()} Queries:")
            print("\nClustered Index Approach:")
            for metric, value in clustered_results[query_type].items():
                print(f"{metric}: {value:.6f} seconds")
            
            print("\nConventional Index Approach:")
            for metric, value in conventional_results[query_type].items():
                print(f"{metric}: {value:.6f} seconds")
            
            # Calculate improvement
            improvement = (conventional_results[query_type]['mean'] - clustered_results[query_type]['mean']) / conventional_results[query_type]['mean'] * 100
            print(f"\nClustered index is {improvement:.2f}% faster on average for {query_type} queries")
        
    finally:
        session.close()

if __name__ == "__main__":
    run_performance_test()