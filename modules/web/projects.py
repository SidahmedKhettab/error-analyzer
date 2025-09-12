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

import os
import html
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, g, session

from modules.db import (
    create_project_db, get_project_file, load_text_data, get_project_details,
    update_project_db, delete_project_db, migrate_project_db
)
from modules.translations import get_translation
from modules.webutils import login_required, project_access_required
from modules.google_nlp import sample_annotate_text
from modules.diff_handler import process_and_save_text_pairs


projects_bp = Blueprint('projects', __name__, url_prefix='')


@projects_bp.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    if not g.current_user.get('google_api_key'):
        flash(get_translation('Please configure your Google API key before creating a project.'), 'warning')
        return redirect(url_for('projects.settings'))
    if request.method == 'POST':
        name = request.form.get('project_name')
        description = request.form.get('project_description')
        language = request.form.get('project_language')
        if not name:
            flash('Project name is required.', 'error')
            return redirect(url_for('projects.create_project'))
        create_project_db(
            project_name=name,
            project_description=description,
            project_language=language,
            db_path=current_app.config.get('DATABASE_PATH', 'databases'),
            owner_id=g.current_user['id']
        )
        flash('Project created successfully!', 'success')
        return redirect(url_for('site.home'))
    default_language = session.get('language', 'en')
    return render_template('create_project.html', default_language=default_language)


@projects_bp.route('/edit_project/<project_name>', methods=['GET', 'POST'])
@login_required
def edit_project(project_name):
    if request.method == 'POST':
        new_project_name = request.form['project_name']
        new_project_description = request.form['project_description']
        new_project_language = request.form['project_language']
        update_project_db(project_name, new_project_name, new_project_description, new_project_language, current_app.config.get('DATABASE_PATH', 'databases'), owner_id=g.current_user['id'])
        flash(get_translation('Project {} updated successfully!').format(project_name), 'success')
        return redirect(url_for('site.home'))
    else:
        project_details = get_project_details(project_name, current_app.config.get('DATABASE_PATH', 'databases'), owner_id=g.current_user['id'])
        if project_details:
            return render_template('create_project.html', project=project_details)
        else:
            flash(get_translation('Project not found.'), 'error')
            return redirect(url_for('site.home'))


@projects_bp.route('/delete_project/<project_name>', methods=['GET', 'POST'])
@login_required
def delete_project(project_name):
    delete_project_db(project_name, current_app.config.get('DATABASE_PATH', 'databases'), owner_id=g.current_user['id'])
    
    flash(get_translation('Project {} deleted successfully!').format(html.unescape(project_name)), 'success')
    return redirect(url_for('site.home'))


@projects_bp.route('/project/<project_name>')
@project_access_required
def project(project_name):
    migrate_project_db(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
    file_name, nlp_active, language, genre_active = get_project_file(project_name, current_app.config.get('DATABASE_PATH', 'databases'), owner_id=g.current_user['id'] if g.current_user else None)
    if file_name:
        if language:
            if nlp_active == 1:
                return redirect(url_for('site.error_analyzer', project_name=project_name))
            return redirect(url_for('site.nlp_selection', project_name=project_name))
        flash(get_translation('Project language is not set.'), 'error')
        return redirect(url_for('site.home'))
    return render_template('upload_csv.html', project_name=project_name)


@projects_bp.route('/perform_nlp', methods=['POST'])
@login_required
def perform_nlp():
    project_name = request.form.get('project_name')
    selected_text_ids = request.form.getlist('selected_texts')
    if not selected_text_ids:
        flash(get_translation('No texts selected for processing.'), 'error')
        return redirect(request.referrer)
    if not project_name:
        flash(get_translation('Project name is required.'), 'error')
        return redirect(url_for('site.home'))
    google_api_key = g.current_user.get('google_api_key')
    google_nlp_key_path = g.current_user.get('google_nlp_key_path')
    sample_annotate_text(project_name, selected_text_ids, current_app.config.get('DATABASE_PATH', 'databases'))
    process_and_save_text_pairs(project_name, current_app.config.get('DATABASE_PATH', 'databases'), google_api_key)
    return redirect(url_for('projects.project', project_name=project_name))


@projects_bp.route('/settings', methods=['GET'])
@login_required
def settings():
    return render_template('settings.html', config=g.current_user)


@projects_bp.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    from werkzeug.utils import secure_filename
    from modules.db import update_user_profile
    
    google_api_key = request.form.get('google_api_key', '')
    google_nlp_key_path = request.form.get('google_nlp_key_path', '')

    # Handle Google NLP Key file upload
    if 'google_nlp_key_file' in request.files:
        file = request.files['google_nlp_key_file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            google_nlp_key_path = file_path

    update_user_profile(
        db_path=current_app.config.get('DATABASE_PATH'),
        user_id=g.current_user['id'],
        google_api_key=google_api_key,
        google_nlp_key_path=google_nlp_key_path
    )

    flash(get_translation('Settings updated successfully!'), 'success')
    return redirect(url_for('projects.settings'))


@projects_bp.route('/import_project', methods=['POST'])
@login_required
def import_project():
    from werkzeug.utils import secure_filename
    if 'project_file' not in request.files:
        flash(get_translation('No file part'), 'error')
        return redirect(url_for('site.home'))
    file = request.files['project_file']
    if file.filename == '':
        flash(get_translation('No selected file'), 'error')
        return redirect(url_for('site.home'))
    if file and file.filename.endswith('.zip'):
        new_project_name = request.form.get('new_project_name')
        if not new_project_name:
            flash(get_translation('New project name is required'), 'error')
            return redirect(url_for('site.home'))
        filename = secure_filename(file.filename)
        zip_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(zip_path)
        try:
            from modules.project_importer import import_project_from_zip
            import_project_from_zip(zip_path, new_project_name, current_app.config.get('DATABASE_PATH', 'databases'), g.current_user['id'])
            flash(get_translation('Project imported successfully!'), 'success')
        except Exception as e:
            flash(str(e), 'error')
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)
        return redirect(url_for('site.home'))
    else:
        flash(get_translation('Invalid file type. Please upload a .zip file.'), 'error')
        return redirect(url_for('site.home'))


@projects_bp.route('/export_project/<project_name>')
@login_required
def export_project(project_name):
    try:
        from modules.project_exporter import export_project_to_zip
        zip_path = export_project_to_zip(project_name, current_app.config.get('DATABASE_PATH', 'databases'), current_app.config['UPLOAD_FOLDER'])
        return send_from_directory(directory=os.path.dirname(zip_path), path=os.path.basename(zip_path), as_attachment=True)
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('site.home'))


@projects_bp.route('/configure_google_key')
@login_required
def configure_google_key():
    return render_template('upload_google_key.html', config=g.current_user)



