import os
from sqlalchemy import create_engine, text, PrimaryKeyConstraint, Column, String, Float, DateTime, Integer, Date, ForeignKey, Text, Index, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# Get the directory where the files are located
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'events.db')

# Add connection pooling for better performance
engine = create_engine(
    f'sqlite:///{db_path}', 
    connect_args={"check_same_thread": False},
    pool_size=10,  # Number of connections to maintain
    max_overflow=20,  # Additional connections that can be created
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300  # Recycle connections after 5 minutes (300 seconds)
) 


def configure_database():
    # Check if database exists and is empty
    db_exists = os.path.exists(db_path)
    if db_exists:
        with engine.connect() as conn:
            # Check if any tables exist
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            if result:
                print("Database already has tables, cannot change page size")
                return
    
    # Set page size to 16KB (16384 bytes)
    with engine.connect() as conn:
        conn.execute(text('PRAGMA page_size = 16384'))
        print("Database page size set to 16KB")

def optimize_database():
    """Set SQLite optimizations for read-heavy workloads with large database but recent event access"""
    with engine.connect() as conn:
        # For read-heavy workloads, DELETE mode is often faster than WAL
        # WAL adds overhead for infrequent writes and small databases
        conn.execute(text('PRAGMA journal_mode = DELETE'))
        
        # Smaller cache size appropriate for 300MB database
        # 8MB cache (8192 pages) is sufficient for this size
        conn.execute(text('PRAGMA cache_size = -8192'))  # 8MB in pages
        
        # Enable memory-mapped I/O for better performance
        # Even with 300MB database, most queries are for recent events
        conn.execute(text('PRAGMA mmap_size = 67108864'))  # 64MB
        
        # Use memory for temp store (faster for small operations)
        conn.execute(text('PRAGMA temp_store = 2'))
        
        # Enable foreign key constraints
        conn.execute(text('PRAGMA foreign_keys = ON'))
        
        # Optimize for read performance
        conn.execute(text('PRAGMA synchronous = NORMAL'))  # Faster than FULL, still safe
        
        # Disable WAL mode features that add overhead for small DBs
        conn.execute(text('PRAGMA wal_autocheckpoint = 0'))
        
        print("Database optimized for read-heavy workload with large database but recent event access")

def migrate_database():
    """Migrate existing database to add recurring event columns"""
    print("Starting database migration...")
    
    with engine.connect() as conn:
        # Check if the event table exists
        table_exists = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='event'
        """)).fetchone()
        
        if not table_exists:
            print("Event table doesn't exist yet, skipping migration")
            return
        
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

def check_database_stats():
    with engine.connect() as conn:
        # Get page count and free pages
        page_count = conn.execute(text('PRAGMA page_count')).scalar()
        free_pages = conn.execute(text('PRAGMA freelist_count')).scalar()
        page_size = conn.execute(text('PRAGMA page_size')).scalar()
        
        # Calculate fragmentation
        total_size = page_count * page_size
        free_size = free_pages * page_size
        fragmentation = (free_pages / page_count * 100) if page_count > 0 else 0
        
        print(f"Database stats:")
        print(f"Total pages: {page_count}")
        print(f"Free pages: {free_pages}")
        print(f"Page size: {page_size} bytes")
        print(f"Total size: {total_size/1024:.1f} KB")
        print(f"Free space: {free_size/1024:.1f} KB")
        print(f"Fragmentation: {fragmentation:.1f}%")
        
        # Only vacuum if fragmentation is significant
        if fragmentation > 10:  # More than 10% fragmented
            print("Fragmentation is high, running VACUUM...")
            with engine.begin() as conn:
                conn.execute(text('VACUUM'))
            print("Database vacuum completed")
        else:
            print("Database is well-optimized, skipping VACUUM")

Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

# Configure and initialize database
configure_database()
optimize_database()

Base.metadata.create_all(engine)  # Create all tables first

# Event model
class Event(Base):
    __tablename__ = 'event'
    
    # Composite primary key for clustering by date
    start_date = Column(Date, nullable=False)
    id = Column(Integer, nullable=True)  # Nullable to allow ID generation after object creation
    
    title = Column(String(100), nullable=False)
    description = Column(Text)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=False)
    rrule = Column(String(255))
    venue_id = Column(Integer, ForeignKey('venue.id'))
    color = Column(String(20))
    bg = Column(String(20))
    
    # Add fields for recurring events
    is_recurring = Column(Boolean, default=False)
    recurring_until = Column(Date)  # When does the series end?
    
    # Add fields for virtual and hybrid events
    is_virtual = Column(Boolean, default=False)
    is_hybrid = Column(Boolean, default=False)
    url = Column(String(500))  # General URL for any event (website, Facebook page, virtual meeting, etc.)
    
    venue = relationship("Venue", back_populates="events")
    
    # Define composite primary key and indexes
    __table_args__ = (
        PrimaryKeyConstraint('start_date', 'id'),
        Index('idx_title', 'title'),
        Index('idx_recurring', 'is_recurring', 'recurring_until'),  # Index for recurring queries
        Index('idx_virtual', 'is_virtual', 'is_hybrid'),  # Index for virtual/hybrid queries
    )
    
    def __init__(self, **kwargs):
        super(Event, self).__init__(**kwargs)
        # Automatically set start_date from start
        if self.start:
            self.start_date = self.start.date()

# FTS5 virtual table for full-text search
class EventFTS(Base):
    __tablename__ = 'event_fts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text)
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

# Venue model
class Venue(Base):
    __tablename__ = 'venue'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(Text)
    
    events = relationship("Event", back_populates="venue")

# Add this after the SessionLocal definition
def get_next_event_id(session, start_date):
    print(f"Getting next ID for date: {start_date}")
    # Get the max ID for the specific date
    query = text("SELECT MAX(id) FROM event WHERE start_date = :start_date")
    print(f"Executing query with params: {{'start_date': {start_date}}}")
    result = session.execute(query, {"start_date": start_date}).scalar()
    print(f"Query result: {result}")
    next_id = (result or 0) + 1
    print(f"Generated next ID: {next_id}")
    return next_id

def get_next_event_ids(session, events):
    print("Getting next IDs for multiple events")
    # Group events by date
    date_to_events = {}
    for event in events:
        if event.start_date not in date_to_events:
            date_to_events[event.start_date] = []
        date_to_events[event.start_date].append(event)
    
    print(f"Grouped events by date: {date_to_events.keys()}")
    
    # Assign IDs for each date
    for start_date, date_events in date_to_events.items():
        next_id = get_next_event_id(session, start_date)
        for event in date_events:
            event.id = next_id
            next_id += 1
            print(f"Assigned ID {event.id} to event '{event.title}' on {start_date}")
