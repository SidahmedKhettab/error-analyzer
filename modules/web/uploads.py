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

from flask import Blueprint, render_template, request, send_from_directory, current_app

from modules.webutils import login_required, project_access_required
from modules.uploads import handle_upload


uploads_bp = Blueprint('uploads', __name__, url_prefix='')


@uploads_bp.route('/upload_csv')
@project_access_required
def upload_csv():
    project_name = request.args.get('project_name')
    return render_template('upload_csv.html', project_name=project_name)


@uploads_bp.route('/upload_csv', methods=['POST'])
@login_required
def upload_csv_post():
    return handle_upload()


@uploads_bp.route('/download_sample')
def download_sample():
    return send_from_directory(current_app.config['SAMPLE_FOLDER'], 'sample_model.csv')

