from flask import render_template, request, jsonify, redirect, url_for, flash
from sqlalchemy import text
from datetime import datetime
import time
from cacheout import Cache
from dateutil.rrule import rrule

from database import SessionLocal, Event, Venue, get_next_event_id
from fts import ensure_fts_setup

# Global cache configuration - can be adjusted
CACHE_TTL_HOURS = 1
CACHE_TTL_SECONDS = CACHE_TTL_HOURS * 3600

# Initialize cache for expanded recurring events (day-based)
# Key format: f"{date_str}" (e.g., "2025-01-15")
# Value: list of expanded event objects for that day
expanded_events_cache = Cache(maxsize=1000, ttl=CACHE_TTL_SECONDS)

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
            return redirect(url_for('main.python_view'))
        venues = session.query(Venue).all()
        session.close()
        return render_template('event_form.html', venues=venues)

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
            return redirect(url_for('main.home'))
        venues = session.query(Venue).all()
        session.close()
        return render_template('event_form.html', event=event, venues=venues)

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

    def clear_expanded_events_cache():
        """Clear the expanded events cache - call this when events are modified"""
        if expanded_events_cache:
            expanded_events_cache.clear()
            print("Cleared expanded events cache")

    def get_cached_expanded_events(date_str):
        """Get expanded events for a specific date from cache"""
        if expanded_events_cache:
            return expanded_events_cache.get(date_str)
        return None

    def set_cached_expanded_events(date_str, events):
        """Cache expanded events for a specific date"""
        if expanded_events_cache:
            expanded_events_cache.set(date_str, events)
            print(f"Cached {len(events)} expanded events for {date_str}")

    def get_cached_calendar_events(start_str, end_str):
        """Get calendar events for a date range from cache"""
        if expanded_events_cache:
            cache_key = f"calendar_{start_str}_{end_str}"
            return expanded_events_cache.get(cache_key)
        return None

    def set_cached_calendar_events(start_str, end_str, events):
        """Cache calendar events for a date range"""
        if expanded_events_cache:
            cache_key = f"calendar_{start_str}_{end_str}"
            expanded_events_cache.set(cache_key, events)
            print(f"Cached {len(events)} calendar events for {start_str} to {end_str}")

    def set_cache_headers(response, max_age=3600):
        """Set cache headers for better performance"""
        response.headers['Cache-Control'] = f'public, max-age={max_age}'
        response.headers['Vary'] = 'Accept-Encoding'
        return response

