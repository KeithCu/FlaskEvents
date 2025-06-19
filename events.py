from flask import render_template, request, jsonify, redirect, url_for, flash
from sqlalchemy import text
from datetime import datetime
import time
from cacheout import Cache
from dateutil.rrule import rrule
from contextlib import contextmanager
from sqlalchemy.orm import joinedload
import os

from database import SessionLocal, Event, Venue, get_next_event_id
from fts import ensure_fts_setup

# Global cache configuration - can be adjusted
CACHE_TTL_HOURS = 1
CACHE_TTL_SECONDS = CACHE_TTL_HOURS * 3600

# Initialize cache for complete day events
# Key format: f"{date_str}" (e.g., "2025-01-15")
# Value: complete list of events (non-recurring + expanded recurring) for that day
day_events_cache = Cache(maxsize=1000, ttl=CACHE_TTL_SECONDS)

# Initialize cache for calendar range events
# Key format: f"calendar_{start_str}_{end_str}"
# Value: list of events for the calendar range
calendar_events_cache = Cache(maxsize=100, ttl=CACHE_TTL_SECONDS)

@contextmanager
def get_db_session():
    """Context manager for database sessions"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def register_events(app):

    def get_events_in_batches(session, start_date, end_date, batch_size=1000):
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
            if len(batch) < batch_size:
                break
        return events

    @app.route('/events')
    def get_events():
        start_time = time.time()
        
        print("="*50)
        print("EVENTS ENDPOINT CALLED")
        print("="*50)
        print(f"Day events cache initialized: {day_events_cache is not None}")
        print(f"Calendar events cache initialized: {calendar_events_cache is not None}")
        
        # Check if this is a single-day request (from events list widget)
        date = request.args.get('date')
        if date:
            print(f"Single day request for date: {date}")
            
            target_date = datetime.strptime(date, '%Y-%m-%d').date()
            
            # Check cache first for complete day events
            cached_day_events = get_cached_day_events(date)
            
            if cached_day_events is not None:
                # Use cached complete day events
                print(f"Using cached complete day events for {date}")
                event_list = cached_day_events
            else:
                with get_db_session() as session:
                    # Get non-recurring events for this specific day
                    day_events = session.query(Event).options(joinedload(Event.venue)).filter(
                        Event.is_recurring == False,
                        Event.start_date == target_date
                    ).order_by(Event.start).all()
                    
                    # Get recurring events that might occur on this day
                    recurring_events = session.query(Event).options(joinedload(Event.venue)).filter(
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
                        'venue': event.venue.name if event.venue else None,
                        'is_virtual': event.is_virtual,
                        'is_hybrid': event.is_hybrid,
                        'url': event.url,
                    }
                    event_list.append(event_data)
                
                print(f"About to cache {len(event_list)} events for date {date}")
                try:
                    # Cache the complete day events
                    set_cached_day_events(date, event_list)
                    print(f"Successfully cached events for {date}")
                except Exception as e:
                    print(f"Error caching events for {date}: {e}")
            
            elapsed_time = time.time() - start_time
            print(f"Single day request completed in {elapsed_time:.3f}s")
            
            response = jsonify(event_list)
            return set_cache_headers(response, max_age=300)  # Cache for 5 minutes
        
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
        
        if cached_calendar is not None:
            # Use cached calendar events
            print(f"Using cached calendar events for {start_str} to {end_str}")
            event_list = cached_calendar
        else:
            with get_db_session() as session:
                # Get non-recurring events in range
                non_recurring = session.query(Event).filter(
                    Event.is_recurring == False,
                    Event.start_date >= start_date.date(),
                    Event.start_date <= end_date.date()
                ).options(joinedload(Event.venue)).all()

                # Get recurring events that might affect this range
                recurring = session.query(Event).filter(
                    Event.is_recurring == True,
                    Event.start_date <= end_date.date(),  # Started before or during range
                    (Event.recurring_until == None) | (Event.recurring_until >= start_date.date())  # Ends after or during range
                ).options(joinedload(Event.venue)).all()
                
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

    @app.route('/event/new', methods=['GET', 'POST'])
    def add_event():
        print("="*50)
        print("ADD EVENT ENDPOINT CALLED")
        print("="*50)
        
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
            
            # Get recurring event fields
            recurring_until_str = request.form.get('recurring_until', '').strip()
            recurring_until = None
            if recurring_until_str:
                try:
                    recurring_until = datetime.strptime(recurring_until_str, '%Y-%m-%d').date()
                except ValueError:
                    # If invalid date, use default
                    pass
            
            with get_db_session() as session:
                # Validate venue_id
                if not venue_id:
                    flash('Please select a venue', 'error')
                    venues = session.query(Venue).all()
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
                                        url=url,
                                        recurring_until=recurring_until_str)
                
                print(f"Creating event: {title} on {start.date()}")
                
                # Determine if this is a recurring event
                is_recurring = bool(rrule_str and rrule_str.strip())
                
                # If recurring and no end date specified, use default (2 years from start)
                if is_recurring and not recurring_until:
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
            clear_day_events_cache()
            clear_calendar_events_cache()
            
            # Ensure FTS is set up and updated
            ensure_fts_setup()
            
            return redirect(url_for('main.python_view'))
        
        with get_db_session() as session:
            venues = session.query(Venue).all()
            return render_template('event_form.html', venues=venues)

    @app.route('/event/<int:id>/edit', methods=['GET', 'POST'])
    def edit_event(id):
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
            
            # Get recurring event fields
            recurring_until_str = request.form.get('recurring_until', '').strip()
            recurring_until = None
            if recurring_until_str:
                try:
                    recurring_until = datetime.strptime(recurring_until_str, '%Y-%m-%d').date()
                except ValueError:
                    # If invalid date, use default
                    pass
            
            with get_db_session() as session:
                event = session.query(Event).get_or_404(id)
                
                # Validate venue_id
                if not venue_id:
                    flash('Please select a venue', 'error')
                    venues = session.query(Venue).all()
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
                                        url=url,
                                        recurring_until=recurring_until_str)
                
                # Determine if this is a recurring event
                is_recurring = bool(rrule_str and rrule_str.strip())
                
                # If recurring and no end date specified, use default (2 years from start)
                if is_recurring and not recurring_until:
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
            clear_day_events_cache()
            clear_calendar_events_cache()
            
            # Ensure FTS is set up and updated
            ensure_fts_setup()
            
            return redirect(url_for('main.home'))
        
        with get_db_session() as session:
            event = session.query(Event).get_or_404(id)
            venues = session.query(Venue).all()
            return render_template('event_form.html', event=event, venues=venues)

    @app.route('/event/<int:id>/delete', methods=['POST'])
    def delete_event(id):
        with get_db_session() as session:
            event = session.query(Event).get_or_404(id)
            session.delete(event)
            session.commit()
        
        # Clear cache since we deleted an event
        clear_day_events_cache()
        clear_calendar_events_cache()
        
        # Ensure FTS is set up and updated
        ensure_fts_setup()
        
        return redirect(url_for('main.python_view'))

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

    def clear_day_events_cache():
        """Clear the complete day events cache - call this when events are modified"""
        if day_events_cache:
            day_events_cache.clear()
            print("Cleared complete day events cache")
        else:
            print("Attempted to clear cache but cache not initialized")

    def clear_calendar_events_cache():
        """Clear the calendar events cache - call this when events are modified"""
        if calendar_events_cache:
            calendar_events_cache.clear()
            print("Cleared calendar events cache")
        else:
            print("Attempted to clear calendar cache but cache not initialized")

    def get_cached_day_events(date_str):
        """Get complete day events for a specific date from cache"""
        if day_events_cache:
            cached = day_events_cache.get(date_str)
            print(f"Cache lookup for {date_str}: {'HIT' if cached is not None else 'MISS'}")
            return cached
        print(f"Cache lookup for {date_str}: NO CACHE (cache not initialized)")
        return None

    def set_cached_day_events(date_str, events):
        """Cache complete day events for a specific date"""
        print(f"set_cached_day_events called with date_str={date_str}, events_count={len(events)}")
        if day_events_cache:
            day_events_cache.set(date_str, events)
            print(f"Cached {len(events)} complete day events for {date_str}")
        else:
            print(f"Failed to cache events for {date_str}: cache not initialized")

    def get_cached_calendar_events(start_str, end_str):
        """Get calendar events for a date range from cache"""
        if calendar_events_cache:
            cache_key = f"calendar_{start_str}_{end_str}"
            return calendar_events_cache.get(cache_key)
        return None

    def set_cached_calendar_events(start_str, end_str, events):
        """Cache calendar events for a date range"""
        if calendar_events_cache:
            cache_key = f"calendar_{start_str}_{end_str}"
            calendar_events_cache.set(cache_key, events)
            print(f"Cached {len(events)} calendar events for {start_str} to {end_str}")

    def set_cache_headers(response, max_age=3600):
        """Set cache headers for better performance"""
        response.headers['Cache-Control'] = f'public, max-age={max_age}'
        response.headers['Vary'] = 'Accept-Encoding'
        return response

