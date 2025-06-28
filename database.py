import os
from sqlalchemy import create_engine, text, PrimaryKeyConstraint, Column, String, Float, DateTime, Integer, Date, ForeignKey, Text, Index, Boolean, Table
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
    """Migrate database to add categories support"""
    with engine.connect() as conn:
        # Check if category table exists
        category_table_exists = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='category'
        """)).fetchone()
        
        if not category_table_exists:
            print("Creating category table...")
            conn.execute(text("""
                CREATE TABLE category (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    usage_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """))
            conn.commit()
            print("Created category table")
        
        # Check if event table exists before trying to add columns
        event_table_exists = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='event'
        """)).fetchone()
        
        if event_table_exists:
            # Check if categories column exists in event table
            columns = conn.execute(text("""
                PRAGMA table_info(event)
            """)).fetchall()
            
            column_names = [col[1] for col in columns]
            
            if 'categories' not in column_names:
                print("Adding categories column to event table...")
                conn.execute(text("""
                    ALTER TABLE event ADD COLUMN categories TEXT DEFAULT ''
                """))
                conn.commit()
                print("Added categories column to event table")
            else:
                print("Categories column already exists in event table")
        else:
            print("Event table doesn't exist yet, skipping column addition")
        
        # Insert default categories if they don't exist
        default_categories = [
            "Art/Fashion", "Broadcast", "Comedy", "Community", "Concert", 
            "Conferences", "Drag/Burlesque", "Education/Lecture", "Festival/Fair", 
            "Film/TV", "Food/Drink", "Fundraisers", "Going Late", "Literature/Poetry", 
            "Music : DJ", "Music : Live", "Other", "Record Store", "Record Store Day", 
            "Theatre/Dance", "Tours"
        ]
        
        for category_name in default_categories:
            conn.execute(text("""
                INSERT OR IGNORE INTO category (name, usage_count) 
                VALUES (:name, 0)
            """), {"name": category_name})
        
        conn.commit()
        print(f"Inserted {len(default_categories)} default categories")
    
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

# Simple Category model for managing available categories
class Category(Base):
    __tablename__ = 'category'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    def __init__(self, **kwargs):
        super(Category, self).__init__(**kwargs)
        if self.usage_count is None:
            self.usage_count = 0
        if self.is_active is None:
            self.is_active = True

# Event model (updated)
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
    
    # Add categories as a comma-separated list
    categories = Column(Text, default='')
    
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
