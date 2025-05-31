from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from sqlalchemy import PrimaryKeyConstraint, create_engine, Column, String, Float, DateTime, Integer, Float, Date, ForeignKey, Text, Index, Sequence, text
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

# Event model
class Event(Base):
    __tablename__ = 'event'
    
    # Composite primary key for clustering by date
    start_date = Column(Date, nullable=False)
    id = Column(Integer, nullable=True)  # Make id nullable since it's part of composite key
    title = Column(String(100), nullable=False)
    description = Column(Text)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=False)
    rrule = Column(String(255))
    venue_id = Column(Integer, ForeignKey('venue.id'))
    color = Column(String(20))
    bg = Column(String(20))
    
    venue = relationship("Venue", back_populates="events")
    
    # Define composite primary key and indexes
    __table_args__ = (
        PrimaryKeyConstraint('start_date', 'id'),
        Index('idx_start_end', 'start', 'end'),
    )
    
    def __init__(self, **kwargs):
        super(Event, self).__init__(**kwargs)
        # Automatically set start_date from start
        if self.start:
            self.start_date = self.start.date()

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

# Home route (redirect to current month)
@app.route('/')
def home():
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
            
            return render_template('home.html', 
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
    
    start = request.args.get('start')
    end = request.args.get('end')
    
    print(f"Received request for events between {start} and {end}")
    
    # Convert string dates to datetime objects
    start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
    
    print(f"Converted dates - start: {start_date.date()}, end: {end_date.date()}")
    
    session = SessionLocal()
    try:
        # Use start_date for filtering to take advantage of clustering
        events = session.query(Event).filter(
            Event.start_date >= start_date.date(),
            Event.start_date <= end_date.date()
        ).order_by(Event.start).all()
        
        print(f"Found {len(events)} events in the database")
        for event in events:
            print(f"Event: {event.title} on {event.start_date} with ID {event.id}")
        
        event_list = []
        for event in events:
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
            print(f"Event data: {event_data}")
        
        print(f"Returning {len(event_list)} events")
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
        
        event = Event(
            title=title, 
            description=description, 
            start=start, 
            end=end,
            rrule=rrule_str, 
            venue_id=venue_id, 
            color=color, 
            bg=bg
        )
        
        # Generate ID for the new event based on its date
        event.id = get_next_event_id(session, event.start_date)
        print(f"Generated ID {event.id} for event on {event.start_date}")
        
        session.add(event)
        session.commit()
        
        # Verify the event was stored
        stored_event = session.query(Event).filter(
            Event.start_date == event.start_date,
            Event.id == event.id
        ).first()
        print(f"Stored event: {stored_event.title if stored_event else 'Not found'}")
        
        session.close()
        return redirect(url_for('home'))
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
        
        event.title = title
        event.description = description
        event.start = start
        event.end = end
        event.rrule = rrule_str
        event.venue_id = venue_id
        event.color = color
        event.bg = bg
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
    return redirect(url_for('home'))

if __name__ == '__main__':
    Base.metadata.create_all(engine)
    app.run(debug=True) 

# WSGI application
application = app 