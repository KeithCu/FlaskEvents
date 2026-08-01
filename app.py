from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory, session
from flask_compress import Compress
from flask_cors import CORS
from flask_assets import Environment, Bundle
from flask_wtf.csrf import CSRFProtect
from datetime import datetime
import logging
import yaml
import os
import sys
import traceback
import pytz
from markupsafe import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, db_path, SessionLocal, AdminSession, Event, migrate_database
from admin import init_admin
from auth import init_auth, register_auth_routes
from events import EVENT_LINK_ARROW, register_events
from cache import register_cache_routes


def configure_logging():
    """Only emit ERROR and above from the app and Werkzeug access logger."""
    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
        force=True,
    )
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('flask_wtf').setLevel(logging.ERROR)


configure_logging()
logger = logging.getLogger(__name__)


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
        logger.error("config.yaml not found at %s", config_path)
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error("Invalid YAML in config.yaml: %s", e)
        sys.exit(1)
    except ValueError as e:
        logger.error("%s", e)
        sys.exit(1)


# Load configuration
config = load_config()
init_auth(config)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = config.get('secret_key', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = None

# Set timezone to local timezone instead of UTC
LOCAL_TIMEZONE = pytz.timezone(config['timezone']['local'])
app.config['LOCAL_TIMEZONE'] = LOCAL_TIMEZONE

app.logger.setLevel(logging.ERROR)

csrf = CSRFProtect(app)

@app.context_processor
def inject_template_globals():
    return {'event_link_arrow': EVENT_LINK_ARROW}

# WordPress host site — hardcoded CORS for now
CORS_ORIGINS = [
    'https://thedetroitilove.com',
    'https://www.thedetroitilove.com',
]
CORS(app,
     origins=CORS_ORIGINS,
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization', 'X-CSRFToken', 'X-CSRF-Token'])

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
    'css/venue.css',
    filters='cssmin',
    output='gen/packed.css'
)
assets.register('css_all', css_bundle)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon',
    )

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
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        session = SessionLocal()
        try:
            day_events = session.query(Event).filter(
                Event.start_date == date_obj.date()
            ).order_by(Event.start).all()

            return render_template('widget_test.html',
                                 year=date_obj.year,
                                 month=date_obj.month,
                                 day=date_obj.day,
                                 date=date,
                                 events=day_events)
        finally:
            session.close()
    except ValueError:
        return redirect(url_for('home'))

@app.route('/widget-test')
def widget_test():
    return render_template('widget_test.html')

# Run migration automatically after models are defined
try:
    migrate_database()
except Exception as e:
    logger.error("Migration failed: %s", e, exc_info=True)

# Auth routes (login/logout) before admin
register_auth_routes(app)

# Initialize Flask-Admin
init_admin(app)

# Register routes from other modules
register_events(app)
register_cache_routes(app)

@app.teardown_appcontext
def shutdown_admin_session(exception=None):
    AdminSession.remove()

def set_cache_headers(response, max_age=3600):
    """Set cache headers for better performance"""
    response.headers['Cache-Control'] = f'public, max-age={max_age}'
    response.headers['Vary'] = 'Accept-Encoding'
    return response

def monitor_connection_pool():
    """Monitor connection pool usage"""
    pool = engine.pool
    return {
        'pool_size': pool.size(),
        'checked_out': pool.checkedout(),
        'overflow': pool.overflow(),
        'checked_in': pool.checkedin(),
    }

@app.errorhandler(500)
def internal_error(error):
    """Log full traceback; show details only to logged-in admins."""
    original = getattr(error, 'original_exception', None) or error
    tb = getattr(original, '__traceback__', None)
    exc_info = (type(original), original, tb)
    app.logger.error('Internal server error', exc_info=exc_info)

    if session.get('logged_in'):
        tb_text = ''.join(traceback.format_exception(*exc_info))
        html = (
            '<!DOCTYPE html><html><head><title>500 Internal Server Error</title></head>'
            '<body style="font-family: monospace; margin: 2rem;">'
            '<h1>500 Internal Server Error</h1>'
            f'<p><strong>{escape(type(original).__name__)}:</strong> {escape(str(original))}</p>'
            f'<pre style="white-space: pre-wrap; background: #f5f5f5; padding: 1rem; '
            f'border: 1px solid #ccc;">{escape(tb_text)}</pre>'
            '</body></html>'
        )
        return html, 500

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

# WSGI application
application = app

if __name__ == '__main__':
    app.config['SESSION_COOKIE_SECURE'] = False
    app.run(debug=True)
