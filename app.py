from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_compress import Compress
from flask_cors import CORS
from flask_assets import Environment, Bundle
from sqlalchemy import text
from datetime import datetime
from sqlalchemy.orm import joinedload
import yaml
import os
import sys
import time
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fts import setup_fts_triggers, ensure_fts_setup, search_events
from database import engine, db_path, Base, SessionLocal, Event, Venue, EventFTS, migrate_database, get_next_event_id
from admin import init_admin


def load_config():
    """Load configuration from config.yaml file"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            if not config:
                raise ValueError("config.yaml is empty")
            return config
    except FileNotFoundError:
        print(f"ERROR: config.yaml not found at {config_path}")
        print("Please create a config.yaml file with the required settings.")
        print("See README.md for configuration details.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML in config.yaml: {e}")
        print("Please fix the YAML syntax in your config.yaml file.")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Please ensure config.yaml contains valid configuration.")
        sys.exit(1)


# Load configuration
config = load_config()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{config["database"]["path"]}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable CORS for WordPress integration using config
if config['cors']['enabled']:
    CORS(app, 
         origins=config['cors']['origins'],
         methods=config['cors'].get('methods', ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']),
         allow_headers=config['cors'].get('allow_headers', ['Content-Type', 'Authorization']))

# Set timezone to local timezone instead of UTC
# You can change this to your specific timezone if needed
# Common options: 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles'
LOCAL_TIMEZONE = pytz.timezone(config['timezone']['local'])  # Adjust this to your timezone

def get_local_now():
    """Get current datetime in local timezone"""
    utc_now = datetime.now(pytz.UTC)
    return utc_now.astimezone(LOCAL_TIMEZONE)

# Enable response compression
Compress(app)

# Initialize Flask-Assets
assets = Environment(app)

# Configure asset bundles
css_bundle = Bundle(
    'css/base.css',
    'css/calendar.css',
    'css/forms.css',
    'css/widgets.css',
    filters='cssmin',
    output='gen/packed.css'
)
assets.register('css_all', css_bundle)

# Future JavaScript bundle (for when you add JS files)
# js_bundle = Bundle(
#     'js/calendar.js',
#     'js/forms.js',
#     filters='jsmin',
#     output='gen/packed.js'
# )
# assets.register('js_all', js_bundle)

# Home route (widget test page)
@app.route('/')
def home():
    now = get_local_now()
    today_str = now.strftime('%Y-%m-%d')
    return render_template('widget_test.html', date=today_str)


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

# Initialize Flask-Admin
init_admin(app)

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
from cache import register_cache_routes
register_events(app)
register_venues(app)
register_cache_routes(app)

