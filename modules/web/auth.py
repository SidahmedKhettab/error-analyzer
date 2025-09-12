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

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from modules.db import create_user, get_user_by_username, update_user_profile
from modules.translations import get_translation
from modules.webutils import login_required


auth_bp = Blueprint('auth', __name__, url_prefix='')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        email = request.form.get('email', '').strip() or None
        full_name = request.form.get('full_name', '').strip() or None
        if not username or not password:
            flash(get_translation('Username and password are required.'), 'error')
            return redirect(url_for('auth.register'))
        existing = get_user_by_username(current_app.config.get('DATABASE_PATH', 'databases'), username)
        if existing:
            flash(get_translation('Username already exists. Please choose another.'), 'error')
            return redirect(url_for('auth.register'))
        pw_hash = generate_password_hash(password)
        user = create_user(current_app.config.get('DATABASE_PATH', 'databases'), username, pw_hash, email=email, full_name=full_name)
        session['user_id'] = user['id']
        flash(get_translation('Welcome! Your account has been created.'), 'success')
        return redirect(url_for('site.home'))
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        next_url = request.args.get('next') or url_for('site.home')
        user = get_user_by_username(current_app.config.get('DATABASE_PATH', 'databases'), username)
        if not user or not user.get('password_hash') or not check_password_hash(user['password_hash'], password):
            flash(get_translation('Invalid username or password.'), 'error')
            return redirect(url_for('auth.login'))
        session['user_id'] = user['id']
        flash(get_translation('Logged in successfully.'), 'success')
        return redirect(next_url)
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    flash(get_translation('You have been logged out.'), 'success')
    return redirect(url_for('site.home'))


@auth_bp.route('/profile/<username>')
def profile(username):
    user = get_user_by_username(current_app.config.get('DATABASE_PATH', 'databases'), username)
    if not user:
        flash(get_translation('User not found.'), 'error')
        return redirect(url_for('site.home'))
    return render_template('profile.html', profile_user=user)


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = g.current_user
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        bio = request.form.get('bio', '').strip()
        avatar_url = request.form.get('avatar_url', '').strip()
        email = request.form.get('email', '').strip()
        updated = update_user_profile(current_app.config.get('DATABASE_PATH', 'databases'), user['id'], full_name=full_name or None, bio=bio or None, avatar_url=avatar_url or None, email=email or None)
        flash(get_translation('Profile updated.'), 'success')
        return redirect(url_for('auth.profile', username=updated['username']))
    return render_template('edit_profile.html', profile_user=user)

