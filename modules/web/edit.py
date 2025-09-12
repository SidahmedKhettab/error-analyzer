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

from flask import Blueprint, request, jsonify, current_app

from modules.webutils import project_access_required
from modules.db import update_tags_or_highlights, load_json_data, save_highlights
from modules.translations import get_translation


edit_bp = Blueprint('edit', __name__, url_prefix='')


@edit_bp.route('/update_tags', methods=['POST'])
@project_access_required
def update_tags():
    data = request.json
    project_name = data.get('project_name')
    if not project_name:
        return get_translation('Project name is required'), 400
    result = update_tags_or_highlights(project_name, data, is_highlight_update=False, db_path=current_app.config['DATABASE_PATH'])
    return jsonify({"status": "success", **result}), 200


@edit_bp.route('/update_highlight', methods=['POST'])
@project_access_required
def update_highlight():
    data = request.json
    project_name = data.get('project_name')
    if not project_name:
        return get_translation('Project name is required'), 400
    result = update_tags_or_highlights(project_name, data, is_highlight_update=True, db_path=current_app.config['DATABASE_PATH'])
    return jsonify({"status": "success", **result}), 200


@edit_bp.route('/save_highlight', methods=['POST'])
@project_access_required
def update_highlight_route():
    data = request.get_json()
    project_name = data['project_name']
    data_type = data['data_type']
    original_name = data['original_name']
    new_name = data.get('new_name')
    new_description = data.get('new_description')
    save_highlights(project_name, data_type, original_name, current_app.config['DATABASE_PATH'], new_name, new_description)
    return jsonify({"message": get_translation('Highlight updated successfully!')})


@edit_bp.route('/delete_highlight', methods=['POST'])
@project_access_required
def delete_highlight_route():
    data = request.get_json()
    project_name = data.get('project_name')
    data_type = "wrong"
    name = data['name']
    html_wrong = load_json_data(project_name, 'wrong', current_app.config['DATABASE_PATH'])
    html_correct = load_json_data(project_name, 'correct', current_app.config['DATABASE_PATH'])
    html_diff = load_json_data(project_name, 'diff', current_app.config['DATABASE_PATH'])
    from modules.db import delete_highlight as _delete
    highlights, element, pos_wrong, pos_correct, pos_diff, pair_id = _delete(html_wrong, project_name, 'wrong', name, current_app.config['DATABASE_PATH'])
    highlights, element, pos_wrong, pos_correct, pos_diff, pair_id = _delete(html_correct, project_name, 'correct', name, current_app.config['DATABASE_PATH'])
    highlights, element, pos_wrong, pos_correct, pos_diff, pair_id = _delete(html_diff, project_name, 'diff', name, current_app.config['DATABASE_PATH'])
    return jsonify({"message": get_translation('Highlight deleted successfully!'), "highlights": highlights})

