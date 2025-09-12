# Copyright © 2025 Sid Ahmed KHETTAB
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/agpl-3.0.html>.

from functools import wraps
from flask import session, flash, url_for, request, redirect, jsonify, g, current_app
from modules.translations import get_translation
from modules.db import user_owns_project, get_user_by_id


def _extract_project_name(**kwargs):
    if 'project_name' in kwargs and kwargs['project_name']:
        return kwargs['project_name']
    pn = request.args.get('project_name')
    if pn:
        return pn
    if request.method in ('POST', 'PUT', 'PATCH'):
        if request.form.get('project_name'):
            return request.form.get('project_name')
        try:
            data = request.get_json(silent=True) or {}
            if isinstance(data, dict):
                return data.get('project_name')
        except Exception:
            pass
    return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash(get_translation('Please log in to continue.'), 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper


def project_access_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash(get_translation('Please log in to continue.'), 'warning')
            return redirect(url_for('auth.login', next=request.url))
        project_name = _extract_project_name(**kwargs)
        if not project_name:
            return f(*args, **kwargs)
        if not user_owns_project(session['user_id'], project_name, current_app.config.get('DATABASE_PATH', 'databases')):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': get_translation('Forbidden')}), 403
            flash(get_translation('You do not have access to this project.'), 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return wrapper


def load_current_user():
    user_id = session.get('user_id')
    g.current_user = get_user_by_id(current_app.config.get('DATABASE_PATH', 'databases'), user_id) if user_id else None

