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

import zipfile
import os
import sqlite3
from modules.db import create_project_db, get_project_details

def import_project_from_zip(zip_path, new_project_name, db_path, owner_id):
    extract_path = os.path.join(os.path.dirname(zip_path), new_project_name)
    if not os.path.exists(extract_path):
        os.makedirs(extract_path)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

    db_files = [f for f in os.listdir(extract_path) if f.endswith('.db')]
    if not db_files:
        raise Exception("No .db file found in the zip archive.")

    old_db_path = os.path.join(extract_path, db_files[0])
    old_project_name = os.path.splitext(db_files[0])[0]

    # Get project details from the main database
    project_details = get_project_details(old_project_name, db_path, owner_id)

    if not project_details:
        # Fallback for older exports that might not have metadata in maindb.db
        # This part remains as a fallback, but the primary logic is to use maindb.
        try:
            conn = sqlite3.connect(old_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT description, language FROM projects")
            project_details_fallback = cursor.fetchone()
            conn.close()
            if not project_details_fallback:
                 raise Exception("Could not read project details from the database.")
            description, language = project_details_fallback
        except sqlite3.OperationalError:
            raise Exception("Could not read project details from the database.")
    else:
        _, description, language = project_details

    # Create a new project
    create_project_db(new_project_name, description, language, db_path, owner_id)

    # Copy data from the old db to the new db
    new_db_path = os.path.join(db_path, f"{new_project_name}.db")
    
    old_conn = sqlite3.connect(old_db_path)
    new_conn = sqlite3.connect(new_db_path)
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    # Get all tables from the old database
    old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = old_cursor.fetchall()
    
    for table_name in tables:
        table_name = table_name[0]
        if table_name == 'sqlite_sequence':
            continue
            
        old_cursor.execute(f"SELECT * FROM {table_name}")
        rows = old_cursor.fetchall()
        
        if rows:
            # Get column names
            column_names = [description[0] for description in old_cursor.description]
            placeholders = ','.join(['?'] * len(column_names))
            
            # Check if table exists in new db and has same columns
            new_cursor.execute(f"PRAGMA table_info({table_name})")
            new_table_cols = [row[1] for row in new_cursor.fetchall()]

            if set(column_names).issubset(set(new_table_cols)):
                query = f"INSERT INTO {table_name} ({','.join(column_names)}) VALUES ({placeholders})"
                new_cursor.executemany(query, rows)

    new_conn.commit()
    
    old_conn.close()
    new_conn.close()
    
    # Clean up extracted files
    for root, dirs, files in os.walk(extract_path, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(extract_path)