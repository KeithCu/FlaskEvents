from flask import Flask, render_template, request, jsonify, redirect, url_for
from sqlalchemy import PrimaryKeyConstraint, create_engine, Column, String, Float, DateTime, Integer, Float, Date, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.types import PickleType
from datetime import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

Base = declarative_base()
engine = create_engine('sqlite:///events.db', connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# Event model
class Event(Base):
    __tablename__ = 'event'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=False)
    rrule = Column(String(255))
    venue_id = Column(Integer, ForeignKey('venue.id'))
    color = Column(String(20))
    bg = Column(String(20))
    
    venue = relationship("Venue", back_populates="events")

# Venue model
class Venue(Base):
    __tablename__ = 'venue'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(Text)
    
    events = relationship("Event", back_populates="venue")

# Home route (redirect to current month)
@app.route('/')
def home():
    now = datetime.now()
    session = SessionLocal()
    try:
        # Get today's events
        today_start = datetime(now.year, now.month, now.day)
        today_end = datetime(now.year, now.month, now.day, 23, 59, 59)
        today_events = session.query(Event).filter(
            Event.start >= today_start,
            Event.start <= today_end
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
    try:
        # Parse the date string into a datetime object
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        session = SessionLocal()
        try:
            # Get events for the specified day
            day_start = datetime(date_obj.year, date_obj.month, date_obj.day)
            day_end = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)
            day_events = session.query(Event).filter(
                Event.start >= day_start,
                Event.start <= day_end
            ).order_by(Event.start).all()
            
            return render_template('home.html', 
                                 year=date_obj.year, 
                                 month=date_obj.month, 
                                 day=date_obj.day,
                                 events=day_events)
        finally:
            session.close()
    except ValueError:
        # If date parsing fails, redirect to home
        return redirect(url_for('home'))

# JSON feed for events
@app.route('/events')
def get_events():
    start = request.args.get('start')
    end = request.args.get('end')
    
    print(f"Received request for events between {start} and {end}")
    
    # Convert string dates to datetime objects
    start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
    
    print(f"Converted dates - start: {start_date}, end: {end_date}")
    
    session = SessionLocal()
    try:
        events = session.query(Event).filter(
            Event.start >= start_date,
            Event.end <= end_date
        ).all()
        
        print(f"Found {len(events)} events in the database")
        
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
    session = SessionLocal()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        start = datetime.fromisoformat(request.form['start'])
        end = datetime.fromisoformat(request.form['end'])
        rrule_str = request.form.get('rrule')
        venue_id = request.form.get('venue_id')
        color = request.form.get('color', '#3788d8')
        bg = request.form.get('bg', '#3788d8')
        event = Event(title=title, description=description, start=start, end=end,
                      rrule=rrule_str, venue_id=venue_id, color=color, bg=bg)
        session.add(event)
        session.commit()
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
        event.title = request.form['title']
        event.description = request.form['description']
        event.start = datetime.fromisoformat(request.form['start'])
        event.end = datetime.fromisoformat(request.form['end'])
        event.rrule = request.form.get('rrule')
        event.venue_id = request.form.get('venue_id')
        event.color = request.form.get('color', '#3788d8')
        event.bg = request.form.get('bg', '#3788d8')
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