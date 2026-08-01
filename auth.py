from functools import wraps
from urllib.parse import urlparse

import os
import tempfile
import yaml
from flask import (
    session, redirect, url_for, request, render_template,
    flash, jsonify,
)
from werkzeug.security import check_password_hash, generate_password_hash


ADMIN_USERNAME = 'admin'
_users = []
_config_path = None


def _config_path_default():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')


def _normalize_users(config):
    """Build users list from config, including legacy admin: block."""
    users = config.get('users')
    if users:
        normalized = []
        for entry in users:
            if not isinstance(entry, dict):
                continue
            username = (entry.get('username') or '').strip()
            password_hash = entry.get('password_hash') or ''
            if username:
                normalized.append({
                    'username': username,
                    'password_hash': password_hash,
                })
        return normalized

    admin = config.get('admin') or {}
    username = (admin.get('username') or '').strip()
    password_hash = admin.get('password_hash') or ''
    if username:
        return [{'username': username, 'password_hash': password_hash}]
    return []


def init_auth(config, config_path=None):
    """Store users from loaded config (supports legacy admin:)."""
    global _users, _config_path
    _config_path = config_path or _config_path_default()
    _users = _normalize_users(config or {})


def reload_users():
    """Refresh in-memory users from config.yaml on disk."""
    global _users
    path = _config_path or _config_path_default()
    try:
        with open(path, 'r') as file:
            config = yaml.safe_load(file) or {}
    except FileNotFoundError:
        _users = []
        return
    _users = _normalize_users(config)


def get_users():
    """Return a copy of the in-memory users list."""
    return [dict(u) for u in _users]


def _find_user(username):
    for user in _users:
        if user['username'] == username:
            return user
    return None


def has_any_password_configured():
    return any(u.get('password_hash') for u in _users)


def save_users(users):
    """Persist users to config.yaml atomically and refresh in-memory list."""
    global _users
    path = _config_path or _config_path_default()
    with open(path, 'r') as file:
        config = yaml.safe_load(file) or {}

    config['users'] = [
        {
            'username': u['username'],
            'password_hash': u['password_hash'],
        }
        for u in users
    ]
    config.pop('admin', None)

    directory = os.path.dirname(path) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='config.', suffix='.yaml.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w') as file:
            yaml.safe_dump(
                config,
                file,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    _users = [dict(u) for u in config['users']]


def verify_login(username, password):
    """Check username/password against configured users."""
    reload_users()
    user = _find_user(username)
    if not user or not user.get('password_hash'):
        return False
    return check_password_hash(user['password_hash'], password)


def is_admin():
    return session.get('logged_in') and session.get('username') == ADMIN_USERNAME


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


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not is_admin():
            if _is_api_request():
                return jsonify({'error': 'Admin access required'}), 403
            flash('Only the admin account can manage users.', 'error')
            return redirect(url_for('home'))
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


def _validate_username(username, *, exclude_username=None):
    username = (username or '').strip()
    if not username:
        return None, 'Username is required.'
    if ' ' in username:
        return None, 'Username cannot contain spaces.'
    for user in _users:
        if user['username'] == username and user['username'] != exclude_username:
            return None, 'That username is already taken.'
    return username, None


def register_auth_routes(app):
    @app.context_processor
    def inject_auth():
        return {
            'logged_in': session.get('logged_in', False),
            'current_username': session.get('username'),
            'is_admin': is_admin(),
        }

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if session.get('logged_in'):
            return redirect(url_for('home'))

        if request.method == 'POST':
            reload_users()
            if not has_any_password_configured():
                flash(
                    'No user passwords configured. Run: python hash_password.py \'your-password\'',
                    'error',
                )
                return render_template('login.html')

            username = request.form.get('username', '')
            password = request.form.get('password', '')

            if verify_login(username, password):
                session['logged_in'] = True
                session['username'] = username
                next_url = _safe_redirect_target(request.args.get('next'))
                return redirect(next_url or '/admin/')
            flash('Invalid username or password', 'error')

        return render_template('login.html')

    @app.route('/logout', methods=['POST', 'GET'])
    def logout():
        session.pop('logged_in', None)
        session.pop('username', None)
        return redirect(url_for('home'))

    @app.route('/users')
    @admin_required
    def list_users():
        reload_users()
        return render_template('users.html', users=get_users(), admin_username=ADMIN_USERNAME)

    @app.route('/users/new', methods=['GET', 'POST'])
    @admin_required
    def add_user():
        reload_users()
        if request.method == 'POST':
            username, error = _validate_username(request.form.get('username', ''))
            password = request.form.get('password', '')
            if error:
                flash(error, 'error')
                return render_template('user_form.html', user=None, form_username=request.form.get('username', ''))
            if not password:
                flash('Password is required.', 'error')
                return render_template('user_form.html', user=None, form_username=username)

            users = get_users()
            users.append({
                'username': username,
                'password_hash': generate_password_hash(password),
            })
            save_users(users)
            flash(f'User "{username}" created.', 'success')
            return redirect(url_for('list_users'))

        return render_template('user_form.html', user=None, form_username='')

    @app.route('/users/<username>/edit', methods=['GET', 'POST'])
    @admin_required
    def edit_user(username):
        reload_users()
        user = _find_user(username)
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('list_users'))

        is_admin_user = username == ADMIN_USERNAME

        if request.method == 'POST':
            if is_admin_user:
                new_username = ADMIN_USERNAME
            else:
                new_username, error = _validate_username(
                    request.form.get('username', ''),
                    exclude_username=username,
                )
                if error:
                    flash(error, 'error')
                    return render_template(
                        'user_form.html',
                        user=user,
                        form_username=request.form.get('username', ''),
                        is_admin_user=False,
                    )
                if new_username == ADMIN_USERNAME and _find_user(ADMIN_USERNAME):
                    flash('Cannot rename a user to the reserved admin username.', 'error')
                    return render_template(
                        'user_form.html',
                        user=user,
                        form_username=request.form.get('username', ''),
                        is_admin_user=False,
                    )

            password = request.form.get('password', '')
            users = get_users()
            for entry in users:
                if entry['username'] == username:
                    entry['username'] = new_username
                    if password:
                        entry['password_hash'] = generate_password_hash(password)
                    break
            save_users(users)
            flash(f'User "{new_username}" updated.', 'success')
            return redirect(url_for('list_users'))

        return render_template(
            'user_form.html',
            user=user,
            form_username=user['username'],
            is_admin_user=is_admin_user,
        )

    @app.route('/users/<username>/delete', methods=['POST'])
    @admin_required
    def delete_user(username):
        reload_users()
        if username == ADMIN_USERNAME:
            flash('The admin account cannot be deleted.', 'error')
            return redirect(url_for('list_users'))
        if not _find_user(username):
            flash('User not found.', 'error')
            return redirect(url_for('list_users'))
        if len(_users) <= 1:
            flash('Cannot delete the last remaining user.', 'error')
            return redirect(url_for('list_users'))

        users = [u for u in get_users() if u['username'] != username]
        save_users(users)
        flash(f'User "{username}" deleted.', 'success')
        return redirect(url_for('list_users'))
