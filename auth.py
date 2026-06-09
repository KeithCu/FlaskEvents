from functools import wraps
from urllib.parse import urlparse

from flask import (
    session, redirect, url_for, request, render_template,
    flash, jsonify,
)
from werkzeug.security import check_password_hash

_admin_config = None


def init_auth(config):
    """Store admin credentials from loaded config."""
    global _admin_config
    _admin_config = config.get('admin', {})


def load_admin_credentials():
    """Return (username, password_hash) from config."""
    if _admin_config is None:
        return None, None
    return _admin_config.get('username'), _admin_config.get('password_hash')


def verify_login(username, password):
    """Check username/password against config credentials."""
    config_username, password_hash = load_admin_credentials()
    if not config_username or not password_hash:
        return False
    if username != config_username:
        return False
    return check_password_hash(password_hash, password)


def _is_api_request():
    return request.path.startswith('/api/') or request.is_json


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            if _is_api_request():
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated


def _safe_redirect_target(next_url):
    """Reject open redirects; allow only same-host relative paths."""
    if not next_url:
        return None
    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc:
        return None
    if not next_url.startswith('/'):
        return None
    return next_url


def register_auth_routes(app):
    @app.context_processor
    def inject_auth():
        return {'logged_in': session.get('logged_in', False)}

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if session.get('logged_in'):
            return redirect(url_for('home'))

        if request.method == 'POST':
            _, password_hash = load_admin_credentials()
            if not password_hash:
                flash(
                    'Admin password not configured. Run: python hash_password.py \'your-password\'',
                    'error',
                )
                return render_template('login.html')

            username = request.form.get('username', '')
            password = request.form.get('password', '')

            if verify_login(username, password):
                session['logged_in'] = True
                next_url = _safe_redirect_target(request.args.get('next'))
                return redirect(next_url or '/admin/')
            flash('Invalid username or password', 'error')

        return render_template('login.html')

    @app.route('/logout', methods=['POST', 'GET'])
    def logout():
        session.pop('logged_in', None)
        return redirect(url_for('home'))
