from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_compress import Compress
from sqlalchemy import PrimaryKeyConstraint, Column, String, Float, DateTime, Integer, Float, Date, ForeignKey, Text, Index, text, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
from dateutil.rrule import rrule
from cacheout import Cache
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fts import setup_fts_triggers, verify_fts_setup
from database import engine, db_path

# Global cache configuration - can be adjusted
CACHE_TTL_HOURS = 1
CACHE_TTL_SECONDS = CACHE_TTL_HOURS * 3600

# Initialize cache for expanded recurring events (day-based)
# Key format: f"{date_str}" (e.g., "2025-01-15")
# Value: list of expanded event objects for that day
expanded_events_cache = Cache(maxsize=1000, ttl=CACHE_TTL_SECONDS)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable response compression
Compress(app)

Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

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

# Home route (widget test page)
@app.route('/')
def home():
    return render_template('widget_test.html')

# Python route (original home page)
@app.route('/python')
def python_view():
    now = datetime.now()
    session = SessionLocal()
    try:
        # Get today's events using start_date for better performance
        today = now.date()
        today_events = session.query(Event).filter(
            Event.start_date == today
        ).order_by(Event.start).all()
        
        return render_template('home.html', 
                             year=now.year, 
                             month=now.month, 
                             day=now.day,
                             events=today_events)
    finally:
        session.close()

# Monthly view
@app.route('/month/<int:year>/<int:month>')
def month_view(year, month):
    return render_template('month.html', year=year, month=month)

# Daily view
@app.route('/day/<date>')
def day_view(date):
    print("="*50)
    print(f"DAY VIEW ENDPOINT CALLED for date: {date}")
    print("="*50)
    
    try:
        # Parse the date string into a datetime object
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        session = SessionLocal()
        try:
            # Get events for the specified day using start_date
            day_events = session.query(Event).filter(
                Event.start_date == date_obj.date()
            ).order_by(Event.start).all()
            
            print(f"Found {len(day_events)} events for {date}")
            for event in day_events:
                print(f"Event: {event.title} on {event.start_date} with ID {event.id}")
            
            return render_template('widget_test.html', 
                                 year=date_obj.year, 
                                 month=date_obj.month, 
                                 day=date_obj.day,
                                 events=day_events)
        finally:
            session.close()
    except ValueError:
        print(f"Invalid date format: {date}")
        # If date parsing fails, redirect to home
        return redirect(url_for('home'))

def get_events_in_batches(session, start_date, end_date, batch_size=1000):
    """Get events in batches to avoid memory issues with large datasets"""
    events = []
    offset = 0
    
    while True:
        batch = session.query(Event).filter(
            Event.start_date >= start_date,
            Event.start_date <= end_date
        ).order_by(Event.start_date, Event.start).offset(offset).limit(batch_size).all()
        
        if not batch:
            break
            
        events.extend(batch)
        offset += batch_size
        
        # Safety check to prevent infinite loops
        if len(batch) < batch_size:
            break
    
    return events

# JSON feed for events
@app.route('/events')
def get_events():
    start_time = time.time()
    
    print("="*50)
    print("EVENTS ENDPOINT CALLED")
    print("="*50)
    
    # Check if this is a single-day request (from events list widget)
    date = request.args.get('date')
    if date:
        print(f"Single day request for date: {date}")
        session = SessionLocal()
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()
            
            # Check cache first for expanded events
            cached_expanded = get_cached_expanded_events(date)
            
            # Get non-recurring events for this specific day
            day_events = session.query(Event).filter(
                Event.is_recurring == False,
                Event.start_date == target_date
            ).order_by(Event.start).all()
            
            if cached_expanded is not None:
                # Use cached expanded events
                print(f"Using cached expanded events for {date}")
                expanded_events = cached_expanded
            else:
                # Get recurring events that might occur on this day
                recurring_events = session.query(Event).filter(
                    Event.is_recurring == True,
                    Event.start_date <= target_date,  # Started before or on this day
                    (Event.recurring_until == None) | (Event.recurring_until >= target_date)  # Ends after or on this day
                ).all()
                
                # Expand recurring events for this specific day
                expanded_events = []
                for event in recurring_events:
                    instances = expand_recurring_events(event, 
                                                      datetime.combine(target_date, datetime.min.time()),
                                                      datetime.combine(target_date, datetime.max.time()))
                    # Filter to only include instances that fall on the target date
                    for instance in instances:
                        if instance.start.date() == target_date:
                            expanded_events.append(instance)
                
                # Cache the expanded events
                set_cached_expanded_events(date, expanded_events)
            
            # Combine and sort all events
            all_events = day_events + expanded_events
            all_events.sort(key=lambda x: x.start)
            
            print(f"Found {len(day_events)} non-recurring events and {len(expanded_events)} recurring instances for {date}")
            
            event_list = []
            for event in all_events:
                event_data = {
                    'id': event.id,
                    'title': event.title,
                    'start': event.start.isoformat(),
                    'end': event.end.isoformat(),
                    'description': event.description,
                    'venue': event.venue.name if event.venue else None,
                    'is_virtual': event.is_virtual,
                    'is_hybrid': event.is_hybrid,
                    'url': event.url,
                }
                event_list.append(event_data)
            
            elapsed_time = time.time() - start_time
            print(f"Single day request completed in {elapsed_time:.3f}s")
            
            response = jsonify(event_list)
            return set_cache_headers(response, max_age=300)  # Cache for 5 minutes
        finally:
            session.close()
    
    # Calendar widget request (date range)
    start = request.args.get('start')
    end = request.args.get('end')
    
    print(f"Calendar request for events between {start} and {end}")
    
    # Convert string dates to datetime objects
    start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
    
    print(f"Converted dates - start: {start_date.date()}, end: {end_date.date()}")
    
    # Check cache first for calendar range
    start_str = start_date.date().isoformat()
    end_str = end_date.date().isoformat()
    cached_calendar = get_cached_calendar_events(start_str, end_str)
    
    session = SessionLocal()
    try:
        if cached_calendar is not None:
            # Use cached calendar events
            print(f"Using cached calendar events for {start_str} to {end_str}")
            event_list = cached_calendar
        else:
            # Get non-recurring events in range
            non_recurring = session.query(Event).filter(
                Event.is_recurring == False,
                Event.start_date >= start_date.date(),
                Event.start_date <= end_date.date()
            ).all()

            # Get recurring events that might affect this range
            recurring = session.query(Event).filter(
                Event.is_recurring == True,
                Event.start_date <= end_date.date(),  # Started before or during range
                (Event.recurring_until == None) | (Event.recurring_until >= start_date.date())  # Ends after or during range
            ).all()
            
            print(f"Found {len(non_recurring)} non-recurring events and {len(recurring)} recurring events")
            
            # Expand recurring events for the date range
            expanded_events = []
            for event in recurring:
                instances = expand_recurring_events(event, start_date, end_date)
                expanded_events.extend(instances)
            
            # Combine all events
            all_events = non_recurring + expanded_events
            all_events.sort(key=lambda x: x.start)
            
            event_list = []
            for event in all_events:
                event_data = {
                    'id': event.id,
                    'title': event.title,
                    'start': event.start.isoformat(),
                    'end': event.end.isoformat(),
                    'rrule': event.rrule,
                    'color': event.color,
                    'backgroundColor': event.bg,
                    'description': event.description,
                    'venue': event.venue.name if event.venue else None,
                    'is_virtual': event.is_virtual,
                    'is_hybrid': event.is_hybrid,
                    'url': event.url,
                }
                event_list.append(event_data)
            
            # Cache the calendar events
            set_cached_calendar_events(start_str, end_str, event_list)
        
        elapsed_time = time.time() - start_time
        print(f"Calendar request completed in {elapsed_time:.3f}s")
        print(f"Returning {len(event_list)} events")
        response = jsonify(event_list)
        return set_cache_headers(response, max_age=300)  # Cache for 5 minutes
    finally:
        session.close()

# Add new event
@app.route('/event/new', methods=['GET', 'POST'])
def add_event():
    print("="*50)
    print("ADD EVENT ENDPOINT CALLED")
    print("="*50)
    
    session = SessionLocal()
    if request.method == 'POST':
        print("Processing POST request")
        title = request.form['title']
        description = request.form['description']
        start = datetime.fromisoformat(request.form['start'])
        end = datetime.fromisoformat(request.form['end'])
        rrule_str = request.form.get('rrule')
        venue_id = request.form.get('venue_id')
        color = request.form.get('color', '#3788d8')
        bg = request.form.get('bg', '#3788d8')
        
        # Get virtual event fields
        is_virtual = request.form.get('is_virtual') == 'on'
        is_hybrid = request.form.get('is_hybrid') == 'on'
        url = request.form.get('url', '').strip()
        
        # Validate venue_id
        if not venue_id:
            flash('Please select a venue', 'error')
            venues = session.query(Venue).all()
            session.close()
            return render_template('event_form.html', 
                                venues=venues,
                                title=title,
                                description=description,
                                start=start,
                                end=end,
                                rrule=rrule_str,
                                color=color,
                                bg=bg,
                                is_virtual=is_virtual,
                                is_hybrid=is_hybrid,
                                url=url)
        
        print(f"Creating event: {title} on {start.date()}")
        
        # Determine if this is a recurring event
        is_recurring = bool(rrule_str and rrule_str.strip())
        recurring_until = None
        
        # If recurring, calculate when the series should end (default: 2 years from start)
        if is_recurring:
            recurring_until = start.date().replace(year=start.date().year + 2)
        
        event = Event(
            title=title, 
            description=description, 
            start=start, 
            end=end,
            rrule=rrule_str, 
            venue_id=venue_id, 
            color=color, 
            bg=bg,
            is_recurring=is_recurring,
            recurring_until=recurring_until,
            is_virtual=is_virtual,
            is_hybrid=is_hybrid,
            url=url if url else None
        )
        
        # Generate ID for the new event based on its date
        event.id = get_next_event_id(session, event.start_date)
        print(f"Generated ID {event.id} for event on {event.start_date}")
        print(f"Event is recurring: {is_recurring}, until: {recurring_until}")
        
        session.add(event)
        session.commit()
        
        # Verify the event was stored
        stored_event = session.query(Event).filter(
            Event.start_date == event.start_date,
            Event.id == event.id
        ).first()
        print(f"Stored event: {stored_event.title if stored_event else 'Not found'}")
        
        # Clear cache since we added a new event
        clear_expanded_events_cache()
        
        # Ensure FTS is set up and updated
        ensure_fts_setup()
        
        session.close()
        return redirect(url_for('python_view'))
    venues = session.query(Venue).all()
    session.close()
    return render_template('event_form.html', venues=venues)

# Edit event
@app.route('/event/<int:id>/edit', methods=['GET', 'POST'])
def edit_event(id):
    session = SessionLocal()
    event = session.query(Event).get_or_404(id)
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        start = datetime.fromisoformat(request.form['start'])
        end = datetime.fromisoformat(request.form['end'])
        rrule_str = request.form.get('rrule')
        venue_id = request.form.get('venue_id')
        color = request.form.get('color', '#3788d8')
        bg = request.form.get('bg', '#3788d8')
        
        # Get virtual event fields
        is_virtual = request.form.get('is_virtual') == 'on'
        is_hybrid = request.form.get('is_hybrid') == 'on'
        url = request.form.get('url', '').strip()
        
        # Validate venue_id
        if not venue_id:
            flash('Please select a venue', 'error')
            venues = session.query(Venue).all()
            session.close()
            return render_template('event_form.html', 
                                event=event,
                                venues=venues,
                                title=title,
                                description=description,
                                start=start,
                                end=end,
                                rrule=rrule_str,
                                color=color,
                                bg=bg,
                                is_virtual=is_virtual,
                                is_hybrid=is_hybrid,
                                url=url)
        
        # Determine if this is a recurring event
        is_recurring = bool(rrule_str and rrule_str.strip())
        recurring_until = None
        
        # If recurring, calculate when the series should end (default: 2 years from start)
        if is_recurring:
            recurring_until = start.date().replace(year=start.date().year + 2)
        
        event.title = title
        event.description = description
        event.start = start
        event.end = end
        event.rrule = rrule_str
        event.venue_id = venue_id
        event.color = color
        event.bg = bg
        event.is_recurring = is_recurring
        event.recurring_until = recurring_until
        event.is_virtual = is_virtual
        event.is_hybrid = is_hybrid
        event.url = url if url else None
        
        session.commit()
        
        # Clear cache since we modified an event
        clear_expanded_events_cache()
        
        # Ensure FTS is set up and updated
        ensure_fts_setup()
        
        session.close()
        return redirect(url_for('home'))
    venues = session.query(Venue).all()
    session.close()
    return render_template('event_form.html', event=event, venues=venues)

# Delete event
@app.route('/event/<int:id>/delete', methods=['POST'])
def delete_event(id):
    session = SessionLocal()
    event = session.query(Event).get_or_404(id)
    session.delete(event)
    session.commit()
    
    # Clear cache since we deleted an event
    clear_expanded_events_cache()
    
    # Ensure FTS is set up and updated
    ensure_fts_setup()
    
    session.close()
    return redirect(url_for('python_view'))

# Venue management routes
@app.route('/venues')
def list_venues():
    session = SessionLocal()
    try:
        venues = session.query(Venue).order_by(Venue.name).all()
        return render_template('venues.html', venues=venues)
    finally:
        session.close()

@app.route('/venue/new', methods=['GET', 'POST'])
def add_venue():
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        
        if not name:
            flash('Venue name is required', 'error')
            return render_template('venue_form.html', name=name, address=address)
        
        session = SessionLocal()
        try:
            venue = Venue(name=name, address=address)
            session.add(venue)
            session.commit()
            flash('Venue added successfully', 'success')
            return redirect(url_for('list_venues'))
        finally:
            session.close()
    
    return render_template('venue_form.html')

@app.route('/venue/<int:id>/edit', methods=['GET', 'POST'])
def edit_venue(id):
    session = SessionLocal()
    venue = session.query(Venue).get_or_404(id)
    
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        
        if not name:
            flash('Venue name is required', 'error')
            session.close()
            return render_template('venue_form.html', venue=venue, name=name, address=address)
        
        venue.name = name
        venue.address = address
        session.commit()
        flash('Venue updated successfully', 'success')
        session.close()
        return redirect(url_for('list_venues'))
    
    session.close()
    return render_template('venue_form.html', venue=venue)

@app.route('/venue/<int:id>/delete', methods=['POST'])
def delete_venue(id):
    session = SessionLocal()
    venue = session.query(Venue).get_or_404(id)
    
    # Check if venue has associated events
    event_count = session.query(Event).filter(Event.venue_id == id).count()
    if event_count > 0:
        flash(f'Cannot delete venue "{venue.name}" because it has {event_count} associated event(s). Please reassign or delete those events first.', 'error')
        session.close()
        return redirect(url_for('list_venues'))
    
    session.delete(venue)
    session.commit()
    flash('Venue deleted successfully', 'success')
    session.close()
    return redirect(url_for('list_venues'))

@app.route('/widget-test')
def widget_test():
    return render_template('widget_test.html')

@app.route('/search')
def search():
    query = request.args.get('q', '')
    print(f"Search query received: {query}")
    
    if not query:
        return jsonify([])
    
    session = SessionLocal()
    try:
        # Debug: Check FTS table contents
        with engine.connect() as conn:
            try:
                fts_count = conn.execute(text("SELECT COUNT(*) FROM event_fts")).scalar()
                print(f"Total rows in FTS table: {fts_count}")
                
                # Debug: Check if the search query works directly
                test_results = conn.execute(
                    text("SELECT * FROM event_fts WHERE event_fts MATCH :query"), 
                    {"query": query}
                ).fetchall()
                print(f"Direct FTS query results count: {len(test_results)}")
                if test_results:
                    print("Sample result:", test_results[0])
            except Exception as e:
                print(f"Error querying FTS table: {e}")
                return jsonify([])
        
        results = search_events(query, session)
        print(f"Search results count: {len(results)}")
        
        event_list = []
        for event in results:
            event_data = {
                'id': event.id,
                'title': event.title,
                'start': event.start.isoformat(),
                'end': event.end.isoformat(),
                'description': event.description,
                'venue': event.venue.name if event.venue else None,
                'color': event.color,
                'backgroundColor': event.bg
            }
            event_list.append(event_data)
        return jsonify(event_list)
    except Exception as e:
        print(f"Error in search: {e}")
        return jsonify([])
    finally:
        session.close()

def ensure_fts_setup():
    """Ensure FTS is set up, initialize if needed"""
    try:
        with engine.connect() as conn:
            # Check if FTS table exists and has data
            fts_count = conn.execute(text("SELECT COUNT(*) FROM event_fts")).scalar()
            event_count = conn.execute(text("SELECT COUNT(*) FROM event")).scalar()
            
            if fts_count == 0 and event_count > 0:
                print("FTS table is empty but events exist, setting up FTS...")
                setup_fts_triggers()
                print("FTS setup completed")
            elif fts_count != event_count:
                print(f"FTS count ({fts_count}) doesn't match event count ({event_count}), reinitializing FTS...")
                setup_fts_triggers()
                print("FTS reinitialization completed")
    except Exception as e:
        print(f"Error checking FTS setup: {e}")
        # If FTS table doesn't exist, set it up
        try:
            print("Setting up FTS table...")
            setup_fts_triggers()
            print("FTS setup completed")
        except Exception as setup_error:
            print(f"FTS setup failed: {setup_error}")

# Initialize FTS automatically when the app starts
try:
    ensure_fts_setup()
except Exception as e:
    print(f"FTS setup failed: {e}")
    print("Starting app without FTS...")

# Only initialize FTS if this file is run directly
if __name__ == '__main__':
    app.run(debug=True)

# WSGI application
application = app 

def expand_recurring_events(event, start_date, end_date):
    if not event.rrule:
        return [event]
    
    # Parse RRULE and generate all instances
    rule = rrule.rrulestr(event.rrule, dtstart=event.start)
    instances = rule.between(start_date, end_date)
    
    # Create event objects for each instance
    expanded_events = []
    for instance_start in instances:
        # Calculate instance end time
        duration = event.end - event.start
        instance_end = instance_start + duration
        
        # Create new event object for this instance
        instance_event = Event(
            title=event.title,
            description=event.description,
            start=instance_start,
            end=instance_end,
            venue_id=event.venue_id,
            color=event.color,
            bg=event.bg,
            is_virtual=event.is_virtual,
            is_hybrid=event.is_hybrid,
            url=event.url,
        )
        expanded_events.append(instance_event)
    
    return expanded_events

def clear_expanded_events_cache():
    """Clear the expanded events cache - call this when events are modified"""
    expanded_events_cache.clear()
    print("Cleared expanded events cache")

def get_cached_expanded_events(date_str):
    """Get expanded events for a specific date from cache"""
    return expanded_events_cache.get(date_str)

def set_cached_expanded_events(date_str, events):
    """Cache expanded events for a specific date"""
    expanded_events_cache.set(date_str, events)
    print(f"Cached {len(events)} expanded events for {date_str}")

def get_cached_calendar_events(start_str, end_str):
    """Get calendar events for a date range from cache"""
    cache_key = f"calendar_{start_str}_{end_str}"
    return expanded_events_cache.get(cache_key)

def set_cached_calendar_events(start_str, end_str, events):
    """Cache calendar events for a date range"""
    cache_key = f"calendar_{start_str}_{end_str}"
    expanded_events_cache.set(cache_key, events)
    print(f"Cached {len(events)} calendar events for {start_str} to {end_str}")

def search_events(query, session):
    """Search for events using FTS"""
    try:
        # Use FTS for full-text search
        with engine.connect() as conn:
            # Search in FTS table
            fts_results = conn.execute(text("""
                SELECT id FROM event_fts 
                WHERE event_fts MATCH :query 
                ORDER BY rank
                LIMIT 50
            """), {"query": query}).fetchall()
            
            if not fts_results:
                return []
            
            # Get the actual event objects
            event_ids = [row[0] for row in fts_results]
            events = session.query(Event).filter(Event.id.in_(event_ids)).all()
            
            return events
    except Exception as e:
        print(f"Error in search_events: {e}")
        # Fallback to simple LIKE search
        return session.query(Event).filter(
            Event.title.ilike(f'%{query}%') | 
            Event.description.ilike(f'%{query}%')
        ).limit(50).all()

def set_cache_headers(response, max_age=3600):
    """Set cache headers for better performance"""
    response.headers['Cache-Control'] = f'public, max-age={max_age}'
    response.headers['Vary'] = 'Accept-Encoding'
    return response 

def monitor_connection_pool():
    """Monitor connection pool usage"""
    pool = engine.pool
    print(f"Connection pool stats:")
    print(f"  Size: {pool.size()}")
    print(f"  Checked out: {pool.checkedout()}")
    print(f"  Overflow: {pool.overflow()}")
    print(f"  Checked in: {pool.checkedin()}")

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors gracefully"""
    print(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404 