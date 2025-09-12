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

"""
App bootstrap: configure Flask, load configuration, initialize DB, register blueprints, and
set common context processors and hooks. All routes are defined in blueprints under modules/web/.
"""

import json
import os
import secrets
import sys
from datetime import datetime

from flask import Flask, session, g, send_from_directory

from modules.db import init_db
from modules.translations import get_translation
from modules.webutils import load_current_user as _load_current_user


def get_base_path():
    # For PyInstaller executable
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # For running from script
    return os.path.dirname(os.path.abspath(__file__))

base_path = get_base_path()

app = Flask(__name__,
            static_folder=os.path.join(base_path, 'static'),
            template_folder=os.path.join(base_path, 'templates'))

def basename(path):
    if path:
        return os.path.basename(path)
    return ''

app.jinja_env.filters['basename'] = basename


config_path = os.path.join(base_path, 'config.json')
config_data = {}
if os.path.exists(config_path):
    try:
        with open(config_path, 'r') as config_file:
            if os.stat(config_path).st_size > 0:
                config_data = json.load(config_file)
    except json.JSONDecodeError:
        print("config.json is corrupted. A new one will be created.")
        config_data = {}

app.config.update(config_data)

# Allow environment variables to override config.json for API keys in container/cloud envs
_env_google = os.environ.get('GOOGLE_API_KEY')
if _env_google:
    app.config['GOOGLE_API_KEY'] = _env_google


# Ensure paths are absolute
upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
if not os.path.isabs(upload_folder):
    app.config['UPLOAD_FOLDER'] = os.path.join(base_path, upload_folder)

database_path = app.config.get('DATABASE_PATH', 'databases')
if not os.path.isabs(database_path):
    app.config['DATABASE_PATH'] = os.path.join(base_path, database_path)


if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] == 'supersecretkey':
    print("Generating new secret key...")
    app.config['SECRET_KEY'] = secrets.token_hex(32)

    # When creating a new config, write relative paths
    config_to_save = {
        'SECRET_KEY': app.config['SECRET_KEY'],
        'UPLOAD_FOLDER': 'uploads',
        'DATABASE_PATH': 'databases',
        'GOOGLE_API_KEY': '',
        'GOOGLE_NLP_KEY_PATH': ''
    }

    with open(config_path, 'w') as config_file:
        json.dump(config_to_save, config_file, indent=4)

init_db(app.config['DATABASE_PATH'])


# Register Blueprints
from modules.web.api import api_bp
from modules.web.auth import auth_bp
from modules.web.projects import projects_bp
from modules.web.uploads import uploads_bp
from modules.web.views import site_bp

from modules.web.edit import edit_bp
from modules.web.compat import compat_bp

app.register_blueprint(api_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(uploads_bp)
app.register_blueprint(site_bp)

app.register_blueprint(edit_bp)
app.register_blueprint(compat_bp)


# Harden session cookie defaults (can be overridden in config.json or env)
import os as _os
app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
# Only mark secure if explicitly requested via environment or config
if 'SESSION_COOKIE_SECURE' not in app.config:
    _secure_flag = str(_os.environ.get('FLASK_SECURE_COOKIES', '0')).lower() in ('1', 'true', 'yes')
    app.config['SESSION_COOKIE_SECURE'] = _secure_flag

@app.before_request
def load_current_user():
    _load_current_user()


@app.context_processor
def inject_user():
    return {'current_user': g.get('current_user')}


@app.context_processor
def inject_year():
    return {'year': datetime.utcnow().year}


@app.context_processor
def inject_translations():
    def _get_translation(key, **kwargs):
        lang = session.get('language', 'en')
        return get_translation(key, lang, **kwargs)
    return dict(get_translation=_get_translation)

@app.route('/download_sample_csv')
def download_sample_csv():
    return send_from_directory(os.path.join(base_path, 'samples'), 'ai_ethics_paragraph_corrections.csv', as_attachment=True)
