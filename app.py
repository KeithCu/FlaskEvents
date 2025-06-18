from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from sqlalchemy import PrimaryKeyConstraint, create_engine, Column, String, Float, DateTime, Integer, Float, Date, ForeignKey, Text, Index, Sequence, text, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.types import PickleType
from datetime import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY
import os

# Get the directory where app.py is located
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'events.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

Base = declarative_base()
engine = create_engine(f'sqlite:///{db_path}', connect_args={"check_same_thread": False})
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

def verify_fts_setup():
    """Verify that FTS table and triggers are properly set up"""
    with engine.connect() as conn:
        try:
            # Check if FTS table exists
            fts_exists = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='event_fts'
            """)).scalar()
            print(f"FTS table exists: {fts_exists is not None}")
            
            # Check trigger count
            trigger_count = conn.execute(text("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='trigger' AND name LIKE 'event_a%'
            """)).scalar()
            print(f"Number of triggers: {trigger_count}")
            
            # Check FTS table content
            fts_count = conn.execute(text("SELECT COUNT(*) FROM event_fts")).scalar()
            event_count = conn.execute(text("SELECT COUNT(*) FROM event")).scalar()
            print(f"FTS table rows: {fts_count}")
            print(f"Event table rows: {event_count}")
            
            if fts_count != event_count:
                print("WARNING: FTS table count doesn't match event table count!")
            
            # Check sample content
            sample = conn.execute(text("""
                SELECT e.id, e.title, f.title as fts_title 
                FROM event e 
                LEFT JOIN event_fts f ON e.id = f.id 
                LIMIT 1
            """)).fetchone()
            if sample:
                print(f"Sample content - Event ID: {sample[0]}")
                print(f"Event title: {sample[1]}")
                print(f"FTS title: {sample[2]}")
            
            # Test FTS search
            test_query = "test"
            test_results = conn.execute(text("""
                SELECT * FROM event_fts 
                WHERE event_fts MATCH :query 
                LIMIT 1
            """), {"query": test_query}).fetchall()
            print(f"Test search returned {len(test_results)} results")
            
        except Exception as e:
            print(f"Error verifying FTS setup: {e}")
            raise

def setup_fts_triggers():
    """Set up triggers to keep FTS table in sync with main table"""
    with engine.begin() as conn:  # Use begin() for transaction
        try:
            # First, check if we can access the event table
            event_count = conn.execute(text("SELECT COUNT(*) FROM event")).scalar()
            print(f"Found {event_count} events in main table")
            
            # Drop existing FTS table and triggers if they exist
            conn.execute(text('DROP TABLE IF EXISTS event_fts'))
            conn.execute(text('DROP TRIGGER IF EXISTS event_ai'))
            conn.execute(text('DROP TRIGGER IF EXISTS event_au'))
            conn.execute(text('DROP TRIGGER IF EXISTS event_ad'))
            
            # Create FTS5 table with default tokenizer
            conn.execute(text('''
                CREATE VIRTUAL TABLE event_fts USING fts5(
                    id, title, description,
                    content='event',
                    content_rowid='id'
                )
            '''))
            
            # Create triggers for insert
            conn.execute(text('''
                CREATE TRIGGER event_ai AFTER INSERT ON event BEGIN
                    INSERT INTO event_fts(id, title, description)
                    VALUES (new.id, new.title, new.description);
                END
            '''))
            
            # Create triggers for update
            conn.execute(text('''
                CREATE TRIGGER event_au AFTER UPDATE ON event BEGIN
                    UPDATE event_fts SET
                        title = new.title,
                        description = new.description
                    WHERE id = old.id;
                END
            '''))
            
            # Create triggers for delete
            conn.execute(text('''
                CREATE TRIGGER event_ad AFTER DELETE ON event BEGIN
                    DELETE FROM event_fts WHERE id = old.id;
                END
            '''))
            
            # Populate FTS table with existing data in batches
            batch_size = 1000
            offset = 0
            while True:
                # Get a batch of events
                events = conn.execute(text("""
                    SELECT id, title, description 
                    FROM event 
                    LIMIT :limit OFFSET :offset
                """), {"limit": batch_size, "offset": offset}).fetchall()
                
                if not events:
                    break
                
                # Insert batch into FTS
                for event in events:
                    conn.execute(text("""
                        INSERT INTO event_fts(id, title, description)
                        VALUES (:id, :title, :description)
                    """), {
                        "id": event[0],
                        "title": event[1] or "",
                        "description": event[2] or ""
                    })
                
                offset += batch_size
                print(f"Processed {offset} events for FTS")
            
            # Verify setup
            verify_fts_setup()
            
            # Optimize FTS table
            conn.execute(text('INSERT INTO event_fts(event_fts) VALUES("optimize")'))
            
        except Exception as e:
            print(f"Error setting up FTS: {e}")
            raise

# Configure and initialize database
configure_database()
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
    
    venue = relationship("Venue", back_populates="events")
    
    # Define composite primary key and indexes
    __table_args__ = (
        PrimaryKeyConstraint('start_date', 'id'),
        Index('idx_title', 'title'),
        Index('idx_recurring', 'is_recurring', 'recurring_until'),  # Index for recurring queries
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

# JSON feed for events
@app.route('/events')
def get_events():
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
            
            # Get non-recurring events for this specific day
            day_events = session.query(Event).filter(
                Event.is_recurring == False,
                Event.start_date == target_date
            ).order_by(Event.start).all()
            
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
                    'venue': event.venue.name if event.venue else None
                }
                event_list.append(event_data)
            
            return jsonify(event_list)
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
    
    session = SessionLocal()
    try:
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
                'venue': event.venue.name if event.venue else None
            }
            event_list.append(event_data)
        
        print(f"Returning {len(event_list)} events (including {len(expanded_events)} expanded recurring instances)")
        return jsonify(event_list)
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
                                bg=bg)
        
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
            recurring_until=recurring_until
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
                                bg=bg)
        
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
        
        session.commit()
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
    session.close()
    return redirect(url_for('python_view'))

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

def initialize_fts():
    """Initialize FTS after tables are created"""
    setup_fts_triggers()
    check_database_stats()

# Only initialize FTS if this file is run directly
if __name__ == '__main__':
    initialize_fts()
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
            bg=event.bg
        )
        expanded_events.append(instance_event)
    
    return expanded_events 

def get_events_with_recurring():
    # Get all events (including old ones that might recur)
    all_events = session.query(Event).all()
    
    # Expand recurring events for the requested date range
    expanded_events = []
    for event in all_events:
        if event.rrule:
            # Expand this recurring event
            instances = expand_recurring_events(event, start_date, end_date)
            expanded_events.extend(instances)
        else:
            # Non-recurring event - only include if in range
            if start_date.date() <= event.start_date <= end_date.date():
                expanded_events.append(event)
    
    return expanded_events 