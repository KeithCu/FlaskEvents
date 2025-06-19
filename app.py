from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_compress import Compress
from sqlalchemy import text
from datetime import datetime
from sqlalchemy.orm import joinedload

import os
import sys
import time
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fts import setup_fts_triggers, ensure_fts_setup, search_events
from database import engine, db_path, Base, SessionLocal, Event, Venue, EventFTS, migrate_database, get_next_event_id


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set timezone to local timezone instead of UTC
# You can change this to your specific timezone if needed
# Common options: 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles'
LOCAL_TIMEZONE = pytz.timezone('America/New_York')  # Adjust this to your timezone

def get_local_now():
    """Get current datetime in local timezone"""
    utc_now = datetime.now(pytz.UTC)
    return utc_now.astimezone(LOCAL_TIMEZONE)

# Enable response compression
Compress(app)

# Home route (widget test page)
@app.route('/')
def home():
    now = get_local_now()
    today_str = now.strftime('%Y-%m-%d')
    return render_template('widget_test.html', date=today_str)

# Python route (original home page)
@app.route('/python')
def python_view():
    now = get_local_now()
    session = SessionLocal()
    try:
        # Get today's events using start_date for better performance
        today = now.date()
        today_events = session.query(Event).options(joinedload(Event.venue)).filter(
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
    print(f"DAY VIEW ENDPOINT CALLED for date: {date}")
    
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
            
            return render_template('widget_test.html', 
                                 year=date_obj.year, 
                                 month=date_obj.month, 
                                 day=date_obj.day,
                                 date=date,  # Pass the original date string
                                 events=day_events)
        finally:
            session.close()
    except ValueError:
        print(f"Invalid date format: {date}")
        # If date parsing fails, redirect to home
        return redirect(url_for('home'))

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

# Run migration automatically after models are defined
try:
    migrate_database()
except Exception as e:
    print(f"Migration failed: {e}")
    print("Continuing with app startup...")

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

@app.route('/pool-stats')
def pool_stats():
    """Endpoint to check connection pool statistics"""
    pool = engine.pool
    stats = {
        'pool_size': pool.size(),
        'checked_out': pool.checkedout(),
        'overflow': pool.overflow(),
        'checked_in': pool.checkedin(),
        'total_connections': pool.size() + pool.overflow()
    }
    return jsonify(stats) 

# Register routes from other modules
from events import register_events
from venue import register_venues
register_events(app)
register_venues(app)

@app.route('/cache-management')
def cache_management():
    """Cache management and testing page"""
    return render_template('cache_management.html')

@app.route('/api/cache/stats')
def cache_stats():
    """Get cache statistics"""
    try:
        from events import day_events_cache, calendar_events_cache
        
        day_stats = {
            'maxsize': day_events_cache.maxsize,
            'ttl': day_events_cache.ttl,
            'size': len(day_events_cache),
            'keys': list(day_events_cache.keys())[:20]  # Show first 20 keys
        }
        
        calendar_stats = {
            'maxsize': calendar_events_cache.maxsize,
            'ttl': calendar_events_cache.ttl,
            'size': len(calendar_events_cache),
            'keys': list(calendar_events_cache.keys())[:20]  # Show first 20 keys
        }
        
        return jsonify({
            'day_events_cache': day_stats,
            'calendar_events_cache': calendar_stats,
            'total_cached_items': len(day_events_cache) + len(calendar_events_cache)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/test', methods=['POST'])
def test_cache():
    """Test cache functionality"""
    try:
        from events import day_events_cache, calendar_events_cache
        
        data = request.get_json()
        test_key = data.get('key', 'test_key')
        test_value = data.get('value', ['test_value'])
        
        # Test setting and getting from day events cache
        day_events_cache.set(test_key, test_value)
        retrieved_value = day_events_cache.get(test_key)
        
        return jsonify({
            'success': True,
            'test_key': test_key,
            'test_value': test_value,
            'retrieved_value': retrieved_value,
            'cache_hit': retrieved_value is not None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear all caches"""
    try:
        from events import day_events_cache, calendar_events_cache
        
        # Clear both caches directly
        day_events_cache.clear()
        calendar_events_cache.clear()
        
        return jsonify({
            'success': True,
            'message': 'All caches cleared successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/get/<key>')
def get_cache_value(key):
    """Get a specific cache value"""
    try:
        from events import day_events_cache, calendar_events_cache
        
        # Try both caches
        day_value = day_events_cache.get(key)
        calendar_value = calendar_events_cache.get(key)
        
        return jsonify({
            'key': key,
            'day_events_cache': day_value,
            'calendar_events_cache': calendar_value,
            'found_in_day': day_value is not None,
            'found_in_calendar': calendar_value is not None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/set', methods=['POST'])
def set_cache_value():
    """Set a cache value"""
    try:
        from events import day_events_cache, calendar_events_cache
        
        data = request.get_json()
        key = data.get('key')
        value = data.get('value')
        cache_type = data.get('cache_type', 'day')  # 'day' or 'calendar'
        
        if not key or value is None:
            return jsonify({'error': 'Key and value are required'}), 400
        
        if cache_type == 'day':
            day_events_cache.set(key, value)
        elif cache_type == 'calendar':
            calendar_events_cache.set(key, value)
        else:
            return jsonify({'error': 'Invalid cache type'}), 400
        
        return jsonify({
            'success': True,
            'message': f'Value set in {cache_type} cache',
            'key': key,
            'value': value
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500 