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
import csv
import io
import openpyxl
import yaml
import json
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import sqlite3
from dicttoxml import dicttoxml
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, g, session, send_from_directory, Response

from modules.db import load_json_data, retrieve_all_genre_main_idea_and_category, load_text_data, migrate_project_db
from modules.translations import get_translation
from modules.webutils import project_access_required


site_bp = Blueprint('site', __name__, url_prefix='')


class ProjectDataLoader:
    def __init__(self, project_name):
        self.project_name = project_name
        self.db_path = current_app.config.get('DATABASE_PATH', 'databases')
        self._migrate_db()

    def _migrate_db(self):
        migrate_project_db(self.project_name, self.db_path)

    def _load_json(self, data_type):
        return load_json_data(self.project_name, data_type, self.db_path)

    def _safe_int(self, value, default=None):
        try:
            if value is None:
                return default
            return int(value)
        except Exception:
            return default

    def _extract_highlights(self, html_wrong, html_correct, html_diff):
        all_html_data = html_wrong + html_correct + html_diff
        highlights_data = []
        for entry in all_html_data:
            highlights = entry.get('Highlights', [])
            for highlight in highlights:
                highlight_data = {
                    'name': highlight.get('name'),
                    'active': highlight.get('active'),
                    'position_in_diff': entry.get('position_in_diff'),
                    'position_in_wrong': entry.get('position_in_wrong'),
                    'position_in_correct': entry.get('position_in_correct'),
                    'operation': entry.get('operation'),
                    'pair_id': self._safe_int(entry.get('pair_id')),
                    'description': highlight.get('description')
                }
                highlights_data.append(highlight_data)
        return highlights_data

    def get_data(self):
        html_wrong = self._load_json('wrong')
        html_correct = self._load_json('correct')
        html_diff = self._load_json('diff')
        highlights = self._extract_highlights(html_wrong, html_correct, html_diff)
        genre_and_main_idea_data = retrieve_all_genre_main_idea_and_category(self.project_name, self.db_path)
        text_pairs = load_text_data(self.project_name, self.db_path)
        return {
            'html_wrong': html_wrong,
            'html_correct': html_correct,
            'html_diff': html_diff,
            'highlights': highlights,
            'genre_and_main_idea': genre_and_main_idea_data,
            'text_pairs': text_pairs
        }


@site_bp.route('/api/project_data/<project_name>')
@project_access_required
def get_project_data_api(project_name):
    project_data = ProjectDataLoader(project_name).get_data()
    return jsonify(project_data)


# download_project_data moved to API blueprint


@site_bp.route('/set_language', methods=['POST'])
def set_language():
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
    lang = (data.get('language') or '').strip().lower()
    if lang not in {'en', 'fr'}:
        return jsonify({'status': 'error', 'message': get_translation('Invalid language')}), 400
    session['language'] = lang
    return jsonify({'status': 'success', 'language': lang})


@site_bp.route('/')
def home():
    if g.get('current_user'):
        user_id = g.current_user['id']
        from modules.db import get_projects
        projects = get_projects(current_app.config.get('DATABASE_PATH', 'databases'), owner_id=user_id)
        return render_template('index.html', projects=projects)
    return render_template('index_public.html')


@site_bp.route('/about')
def about():
    return render_template('about.html')





@site_bp.route('/nlp_selection')
@project_access_required
def nlp_selection():
    project_name = request.args.get('project_name')
    texts = load_text_data(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
    return render_template('nlp_selection.html', project_name=project_name, texts=texts)


@site_bp.route('/erroranalyzer')
@project_access_required
def error_analyzer():
    project_name = request.args.get('project_name')
    if not project_name:
        return get_translation('Project name is required'), 400
    project_data = ProjectDataLoader(project_name).get_data()
    return render_template('erroranalyzer.html', project_name=project_name, **project_data)


@site_bp.route('/comparison/<project_name>')
@site_bp.route('/comparison/<project_name>/<int:pair_id>')
@project_access_required
def comparison(project_name, pair_id=None):
    if not project_name:
        return get_translation('Project name is required'), 400
    project_data = ProjectDataLoader(project_name).get_data()
    return render_template('comparison.html', project_name=project_name, initial_pair_id=pair_id, **project_data)


@site_bp.route('/tag_report')
@project_access_required
def tag_report():
    project_name = request.args.get('project_name')
    if not project_name:
        return get_translation('Project name is required'), 400
    return render_template('tag_report.html', project_name=project_name)
