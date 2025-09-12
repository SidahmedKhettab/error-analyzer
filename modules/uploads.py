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
import pandas as pd
import sqlite3
from flask import request, redirect, url_for, current_app, flash, g
from werkzeug.utils import secure_filename
from .db import save_csv_data_if_not_exists, update_project_file_name, get_project_file
from .diff_handler import process_and_save_text_pairs

def handle_upload():
    project_name = request.form['project_name']
    file = request.files['csvFile']

    if file and file.filename.endswith('.csv'):
        try:
            # Attempt to read the CSV file with UTF-8 encoding
            # Save the uploaded file temporarily
            temp_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], "temp_" + secure_filename(file.filename))
            file.save(temp_filepath)

            # Read the CSV file from the temporary path
            try:
                df = pd.read_csv(temp_filepath, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(temp_filepath, encoding='latin1')

            if df.empty:
                flash('The uploaded CSV file is empty. Please upload a valid CSV file.', 'error')
                return redirect(url_for('upload_csv', project_name=project_name))

            if 'ErrorText' in df.columns and 'CorrectedText' in df.columns:
                # Use the temporary filepath for further processing
                filepath = temp_filepath

                csv_data = df.to_dict(orient='records')
                save_csv_data_if_not_exists(project_name, csv_data, current_app.config['DATABASE_PATH'])
                owner_id = g.current_user['id'] if getattr(g, 'current_user', None) else None
                update_project_file_name(project_name, secure_filename(file.filename), current_app.config['DATABASE_PATH'], owner_id=owner_id)
                os.remove(temp_filepath) # Clean up the temporary file

                flash('File uploaded and processed successfully!', 'success')
                return redirect(url_for('projects.project', project_name=project_name))

            else:
                flash('Invalid CSV format. The file must contain ErrorText and CorrectedText columns. Download a sample CSV file <a href="/download_sample">here</a>.', 'error')
                return redirect(url_for('upload_csv', project_name=project_name))
        except pd.errors.EmptyDataError:
            flash('The uploaded CSV file is empty. Please upload a valid CSV file.', 'error')
            return redirect(url_for('upload_csv', project_name=project_name))
        except pd.errors.ParserError:
            flash('Error parsing the CSV file. Please ensure it is properly formatted.', 'error')
            return redirect(url_for('upload_csv', project_name=project_name))
    else:
        flash('Invalid file format. Please upload a CSV file.', 'error')
        return redirect(url_for('upload_csv', project_name=project_name))
