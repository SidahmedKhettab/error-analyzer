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

import sqlite3
import json
import os
import pandas as pd
from .utils import sanitize_input

def init_db(db_path):
    """
    Initialize the main database by creating the necessary tables if they do not exist.
    """
    if not os.path.exists(db_path):
        os.makedirs(db_path)

    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    # Create table for storing project metadata including file name and Google NLP JSON file
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            file_name TEXT,
            
            nlp_active INTEGER NOT NULL DEFAULT 0,
            genre_active INTEGER NOT NULL DEFAULT 0,
            language TEXT NOT NULL DEFAULT 'en'
        )
    ''')

    # Ensure owner_id column exists for user scoping of projects
    try:
        c.execute("PRAGMA table_info(projects)")
        cols = [row[1] for row in c.fetchall()]
        if 'owner_id' not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN owner_id INTEGER")
    except Exception as e:
        print(f"[WARN] Could not ensure owner_id column on projects: {e}")

    # Users table for authentication & profile management (lives in main DB)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            bio TEXT,
            avatar_url TEXT,
            google_api_key TEXT,
            google_nlp_key_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add columns to users table if they don't exist
    try:
        c.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in c.fetchall()]
        if 'google_api_key' not in cols:
            c.execute("ALTER TABLE users ADD COLUMN google_api_key TEXT")
        if 'google_nlp_key_path' not in cols:
            c.execute("ALTER TABLE users ADD COLUMN google_nlp_key_path TEXT")
    except Exception as e:
        print(f"[WARN] Could not alter users table: {e}")

    conn.commit()
    conn.close()

    # Ensure the databases directory exists
    if not os.path.exists(db_path):
        os.makedirs(db_path)

def create_project_db(project_name, project_description, project_language, db_path, owner_id=None):
    """
    Create a new database for a specific project and add project metadata to the main database.
    """
    # Sanitize project_language
    ALLOWED_LANGUAGES = ['en', 'fr']

    # Sanitize project_language
    if project_language not in ALLOWED_LANGUAGES:
        project_language = 'en'

    project_name = sanitize_input(project_name) # Sanitize project_name
    project_description = sanitize_input(project_description) # Sanitize project_description

    # Ensure the databases directory exists
    if not os.path.exists(db_path):
        os.makedirs(db_path)

    # Get the first project's Google key file, if any
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    

    # Save project metadata in the main database
    if owner_id is not None:
        c.execute('INSERT INTO projects (name, description, language, owner_id) VALUES (?, ?, ?, ?)',
                  (project_name, project_description, project_language, owner_id))
    else:
        c.execute('INSERT INTO projects (name, description, language) VALUES (?, ?, ?)',
                  (project_name, project_description, project_language))
    conn.commit()
    conn.close()

    # Create a new database for the project in the databases folder
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    # Create table for storing CSV data
    c.execute('''
        CREATE TABLE IF NOT EXISTS csv_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            error_text TEXT NOT NULL,
            corrected_text TEXT NOT NULL,
            meaning TEXT,
            genre TEXT,
            title TEXT
        )
    ''')

    # Create table for storing JSON data with data_type column
    c.execute('''
        CREATE TABLE IF NOT EXISTS json_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id TEXT NOT NULL,
            data_type TEXT NOT NULL,
            json_content JSON NOT NULL
        )
    ''')

    # Create classifications table
    c.execute('''
        CREATE TABLE IF NOT EXISTS classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER,
            text_type TEXT,
            category_name TEXT,
            confidence REAL,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create tokens table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER,
            text_type TEXT,
            token TEXT,
            "position" INTEGER,
            tag TEXT,
            "number" TEXT,
            proper TEXT,
            aspect TEXT,
            "case" TEXT,
            form TEXT,
            gender TEXT,
            mood TEXT,
            person TEXT,
            reciprocity TEXT,
            tense TEXT,
            voice TEXT,
            head_token INTEGER,
            label TEXT,
            lemma TEXT,
            -- Enum codes for robust re-labeling across languages
            tag_code INTEGER,
            number_code INTEGER,
            proper_code INTEGER,
            aspect_code INTEGER,
            case_code INTEGER,
            form_code INTEGER,
            gender_code INTEGER,
            mood_code INTEGER,
            person_code INTEGER,
            reciprocity_code INTEGER,
            tense_code INTEGER,
            voice_code INTEGER,
            dep_label_code INTEGER,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create entities table
    c.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER,
            text_type TEXT,
            name TEXT,
            type TEXT,
            content TEXT,
            position INTEGER,
            common_or_proper TEXT,
            -- Enum codes to support re-labeling
            entity_type_code INTEGER,
            mention_type_code INTEGER,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create tags table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            parent_tag_id INTEGER,
            color TEXT NOT NULL DEFAULT '#000000',
            FOREIGN KEY(parent_tag_id) REFERENCES tags(id)
        )
    ''')

    # Create annotations table
    c.execute('''
        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            pair_id INTEGER NOT NULL,
            data_type TEXT NOT NULL,
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            text TEXT,
            FOREIGN KEY(tag_id) REFERENCES tags(id)
        )
    ''')

    conn.commit()
    
    # Create nlp_conclusions table (cache for AI-generated NLP analysis)
    c.execute('''
        CREATE TABLE IF NOT EXISTS nlp_conclusions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL UNIQUE,
            conclusion TEXT,
            inconsistencies TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    conn.commit()
    
    # Create nlp_linguistic_analyses table (cache for AI-driven linguistic categorization)
    c.execute('''
        CREATE TABLE IF NOT EXISTS nlp_linguistic_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL UNIQUE,
            analysis_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create auto_tagging_jobs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS auto_tagging_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL,
            instruction TEXT NOT NULL,
            plan TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    conn.commit()
    conn.close()


def save_google_nlp_to_database(project_name, table, content, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    # Prevent duplicate rows if NLP is re-run: clear prior rows for the same pair_id and text_type
    try:
        if content and table in ('tokens', 'entities', 'classifications'):
            # Support both dict and tuple inputs to extract pair_id and text_type
            first = content[0]
            if isinstance(first, dict):
                pair_id = first.get('pair_id')
                text_type = first.get('text_type')
            else:
                pair_id = first[0]
                text_type = first[1]
            if pair_id is not None and text_type is not None:
                c.execute(f"DELETE FROM {table} WHERE pair_id = ? AND text_type = ?", (pair_id, text_type))
                conn.commit()
    except Exception:
        pass

    def _existing_columns(tbl):
        c.execute(f"PRAGMA table_info({tbl})")
        return [row[1] for row in c.fetchall()]

    if table in ('tokens', 'entities', 'classifications'):
        cols_in_db = _existing_columns(table)

        # Canonical ordered columns for each table
        canonical = {
            'tokens': [
                'pair_id','text_type','token','position','tag','number','proper','aspect','case','form','gender',
                'mood','person','reciprocity','tense','voice','head_token','label','lemma',
                'tag_code','number_code','proper_code','aspect_code','case_code','form_code','gender_code','mood_code',
                'person_code','reciprocity_code','tense_code','voice_code','dep_label_code'
            ],
            'entities': [
                'pair_id','text_type','name','type','content','position','common_or_proper','entity_type_code','mention_type_code'
            ],
            'classifications': [
                'pair_id','text_type','category_name','confidence'
            ],
        }

        insert_cols = [col for col in canonical[table] if col in cols_in_db]
        if not insert_cols:
            conn.close()
            return

        placeholders = ', '.join(['?'] * len(insert_cols))
        quoted_cols = ', '.join([f'"{col}"' for col in insert_cols])
        sql = f"INSERT INTO {table} ({quoted_cols}) VALUES ({placeholders})"

        rows = []
        for item in content:
            if isinstance(item, dict):
                rows.append(tuple(item.get(col) for col in insert_cols))
            else:
                # Backward compatibility for legacy tuples
                if table == 'tokens':
                    # Legacy order had 19 fields up to lemma
                    legacy_cols = [
                        'pair_id','text_type','token','position','tag','number','proper','aspect','case','form','gender',
                        'mood','person','reciprocity','tense','voice','head_token','label','lemma'
                    ]
                    legacy_map = dict(zip(legacy_cols, item))
                    rows.append(tuple(legacy_map.get(col) for col in insert_cols))
                elif table == 'entities':
                    legacy_cols = ['pair_id','text_type','name','type','content','position','common_or_proper']
                    legacy_map = dict(zip(legacy_cols, item))
                    rows.append(tuple(legacy_map.get(col) for col in insert_cols))
                else:  # classifications
                    rows.append(tuple(item[i] for i in range(len(insert_cols))))

        c.executemany(sql, rows)
        conn.commit()

    conn.close()


def get_projects(db_path, owner_id=None):
    """
    Retrieve all projects from the main database.
    """
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    if owner_id is None:
        c.execute('SELECT name, description, file_name FROM projects')
    else:
        c.execute('SELECT name, description, file_name FROM projects WHERE owner_id = ?', (owner_id,))
    projects = c.fetchall()
    conn.close()
    return projects

# ========== Users: Authentication & Profile Management (main DB) ==========

def _main_conn(db_path):
    return sqlite3.connect(os.path.join(db_path, 'maindb.db'))

def create_user(db_path, username, password_hash, email=None, full_name=None):
    conn = _main_conn(db_path)
    c = conn.cursor()
    c.execute(
        'INSERT INTO users (username, email, password_hash, full_name) VALUES (?, ?, ?, ?)',
        (username, email, password_hash, full_name)
    )
    conn.commit()
    user_id = c.lastrowid
    conn.close()
    return get_user_by_id(db_path, user_id)

def get_user_by_username(db_path, username):
    conn = _main_conn(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(db_path, user_id):
    conn = _main_conn(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_profile(db_path, user_id, full_name=None, bio=None, avatar_url=None, email=None, google_api_key=None, google_nlp_key_path=None):
    conn = _main_conn(db_path)
    c = conn.cursor()
    fields = []
    params = []
    if full_name is not None:
        fields.append('full_name = ?')
        params.append(full_name)
    if bio is not None:
        fields.append('bio = ?')
        params.append(bio)
    if avatar_url is not None:
        fields.append('avatar_url = ?')
        params.append(avatar_url)
    if email is not None:
        fields.append('email = ?')
        params.append(email)
    if google_api_key is not None:
        fields.append('google_api_key = ?')
        params.append(google_api_key)
    if google_nlp_key_path is not None:
        fields.append('google_nlp_key_path = ?')
        params.append(google_nlp_key_path)
    if not fields:
        conn.close()
        return get_user_by_id(db_path, user_id)
    fields.append('updated_at = CURRENT_TIMESTAMP')
    params.append(user_id)
    c.execute(f'UPDATE users SET {", ".join(fields)} WHERE id = ?', tuple(params))
    conn.commit()
    conn.close()
    return get_user_by_id(db_path, user_id)

def get_project_file(project_name, db_path, owner_id=None):
    """
    Retrieve the file name for a given project from the main database.
    """
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    if owner_id is None:
        c.execute('SELECT file_name, nlp_active, language, genre_active FROM projects WHERE name = ?', (project_name,))
    else:
        c.execute('SELECT file_name, nlp_active, language, genre_active FROM projects WHERE name = ? AND owner_id = ?', (project_name, owner_id))
    result = c.fetchone()
    conn.close()
    return result if result else (None, None)

def update_project_file_name(project_name, file_name, db_path, owner_id=None):
    """
    Update the file name for a project in the main database.
    """
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    if owner_id is None:
        c.execute('UPDATE projects SET file_name = ? WHERE name = ?', (file_name, project_name))
    else:
        c.execute('UPDATE projects SET file_name = ? WHERE name = ? AND owner_id = ?', (file_name, project_name, owner_id))
    conn.commit()
    conn.close()

def update_nlp_state(project_name, db_path, owner_id=None):
    """
    Update the nlp_active state to true for a project in the main database.
    """
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    if owner_id is None:
        c.execute('UPDATE projects SET nlp_active = ? WHERE name = ?', (1, project_name))
    else:
        c.execute('UPDATE projects SET nlp_active = ? WHERE name = ? AND owner_id = ?', (1, project_name, owner_id))
    conn.commit()
    conn.close()

def update_genre_state(project_name, db_path, owner_id=None):
    """
    Update the genre_active state to true for a project in the main database.
    """
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    if owner_id is None:
        c.execute('UPDATE projects SET genre_active = ? WHERE name = ?', (1, project_name))
    else:
        c.execute('UPDATE projects SET genre_active = ? WHERE name = ? AND owner_id = ?', (1, project_name, owner_id))
    conn.commit()
    conn.close()


def get_project_details(project_name, db_path, owner_id=None):
    """
    Retrieve details of a specific project from the main database.
    """
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    if owner_id is None:
        c.execute('SELECT name, description, language FROM projects WHERE name = ?', (project_name,))
    else:
        c.execute('SELECT name, description, language FROM projects WHERE name = ? AND owner_id = ?', (project_name, owner_id))
    project_details = c.fetchone()
    conn.close()
    return project_details

def update_project_db(old_project_name, new_project_name, new_project_description, new_project_language, db_path, owner_id=None):
    """
    Update project details in the main database and rename the project's database file.
    """
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    if owner_id is None:
        c.execute('UPDATE projects SET name = ?, description = ?, language = ? WHERE name = ?',
                  (new_project_name, new_project_description, new_project_language, old_project_name))
    else:
        c.execute('UPDATE projects SET name = ?, description = ?, language = ? WHERE name = ? AND owner_id = ?',
                  (new_project_name, new_project_description, new_project_language, old_project_name, owner_id))
    conn.commit()
    conn.close()

    # Prepare paths
    old_db_path = os.path.join(db_path, f'{old_project_name}.db')
    new_db_path = os.path.join(db_path, f'{new_project_name}.db')

    # If the project database exists, update embedded references before rename
    if os.path.exists(old_db_path):
        try:
            pconn = sqlite3.connect(old_db_path)
            pc = pconn.cursor()
            # Best-effort: update annotations.project_name to the new project name
            try:
                pc.execute("UPDATE annotations SET project_name = ? WHERE project_name = ?", (new_project_name, old_project_name))
                pconn.commit()
            except Exception:
                # Table may not exist in very old DBs; ignore
                pass
        finally:
            try:
                pconn.close()
            except Exception:
                pass

        # Finally rename the project's database file
        os.rename(old_db_path, new_db_path)

def delete_project_db(project_name, db_path, owner_id=None):
    """
    Delete a project from the main database and remove its associated database file.
    """
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    if owner_id is None:
        c.execute('DELETE FROM projects WHERE name = ?', (project_name,))
    else:
        c.execute('DELETE FROM projects WHERE name = ? AND owner_id = ?', (project_name, owner_id))
    conn.commit()
    conn.close()

    # Delete the project's database file
    project_db_path = os.path.join(db_path, f'{project_name}.db')
    if os.path.exists(project_db_path):
        # Attempt to close any lingering connections and ensure the database is not busy
        try:
            # Connect to the project database to ensure it's not busy and close it
            project_conn = sqlite3.connect(project_db_path)
            project_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            project_conn.execute("VACUUM;")
            project_conn.close()
        except sqlite3.Error as e:
            print(f"Error closing project database connection: {e}")
            # Log the error but continue to try and remove the file
        
        try:
            os.remove(project_db_path)
        except OSError as e:
            print(f"Error deleting project database file: {e}")
            # Re-raise the exception if it's still a permission error
            raise

def user_owns_project(user_id, project_name, db_path):
    conn = sqlite3.connect(os.path.join(db_path, 'maindb.db'))
    c = conn.cursor()
    c.execute('SELECT 1 FROM projects WHERE name = ? AND owner_id = ?', (project_name, user_id))
    row = c.fetchone()
    conn.close()
    return bool(row)

def migrate_project_db(project_name, db_path):
    """
    Apply migrations to a project's database.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    # Check if 'title' column exists in 'csv_data'
    c.execute("PRAGMA table_info(csv_data)")
    columns = [column[1] for column in c.fetchall()]
    if 'title' not in columns:
        print(f"Adding 'title' column to csv_data table for project {project_name}")
        c.execute("ALTER TABLE csv_data ADD COLUMN title TEXT")
    if 'scratchpad_content' not in columns:
        print(f"Adding 'scratchpad_content' column to csv_data table for project {project_name}")
        c.execute("ALTER TABLE csv_data ADD COLUMN scratchpad_content TEXT")

    # Check if 'color' column exists in 'tags'
    c.execute("PRAGMA table_info(tags)")
    columns = [column[1] for column in c.fetchall()]
    if 'color' not in columns:
        print(f"Adding 'color' column to tags table for project {project_name}")
        c.execute("ALTER TABLE tags ADD COLUMN color TEXT NOT NULL DEFAULT '#000000'")

    # Create tags table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            parent_tag_id INTEGER,
            color TEXT NOT NULL DEFAULT '#000000',
            FOREIGN KEY(parent_tag_id) REFERENCES tags(id)
        )
    ''')

    # Create diff_data table
    c.execute('''
        CREATE TABLE IF NOT EXISTS diff_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL UNIQUE,
            diff_text TEXT NOT NULL,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create annotations table
    c.execute('''
        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            pair_id INTEGER NOT NULL,
            data_type TEXT NOT NULL,
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            text TEXT,
            FOREIGN KEY(tag_id) REFERENCES tags(id)
        )
    ''')

    # Check if 'text' column exists in 'annotations'
    c.execute("PRAGMA table_info(annotations)")
    columns = [column[1] for column in c.fetchall()]
    if 'text' not in columns:
        print(f"Adding 'text' column to annotations table for project {project_name}")
        c.execute("ALTER TABLE annotations ADD COLUMN text TEXT")

    # Create chat_history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create tag_report_chat_history table (project-level chat for Tag Report Insights)
    c.execute('''
        CREATE TABLE IF NOT EXISTS tr_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sender TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')

    # Create notes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create nlp_conclusions table if missing
    c.execute('''
        CREATE TABLE IF NOT EXISTS nlp_conclusions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL UNIQUE,
            conclusion TEXT,
            inconsistencies TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create nlp_linguistic_analyses table if missing
    c.execute('''
        CREATE TABLE IF NOT EXISTS nlp_linguistic_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL UNIQUE,
            analysis_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    # Create auto_tagging_jobs table if missing
    c.execute('''
        CREATE TABLE IF NOT EXISTS auto_tagging_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL,
            instruction TEXT NOT NULL,
            plan TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(pair_id) REFERENCES csv_data(id)
        )
    ''')

    conn.commit()

    # Add enum code columns to tokens if missing
    c.execute("PRAGMA table_info(tokens)")
    token_cols = [column[1] for column in c.fetchall()]
    def _add_token_col(name):
        print(f"Adding '{name}' column to tokens table for project {project_name}")
        c.execute(f"ALTER TABLE tokens ADD COLUMN {name} INTEGER")

    for col in (
        'tag_code','number_code','proper_code','aspect_code','case_code','form_code','gender_code',
        'mood_code','person_code','reciprocity_code','tense_code','voice_code','dep_label_code'
    ):
        if col not in token_cols:
            _add_token_col(col)

    # Add enum code columns to entities if missing
    c.execute("PRAGMA table_info(entities)")
    ent_cols = [column[1] for column in c.fetchall()]
    def _add_entity_col(name):
        print(f"Adding '{name}' column to entities table for project {project_name}")
        c.execute(f"ALTER TABLE entities ADD COLUMN {name} INTEGER")

    for col in ('entity_type_code','mention_type_code'):
        if col not in ent_cols:
            _add_entity_col(col)

    conn.commit()

    # Deduplicate previously inserted NLP rows to avoid duplicated tokens/entities
    try:
        c.execute('''
            DELETE FROM tokens
            WHERE id NOT IN (
                SELECT MIN(id) FROM tokens
                GROUP BY pair_id, text_type, position, token, tag, head_token, label, lemma
            )
        ''')
        c.execute('''
            DELETE FROM entities
            WHERE id NOT IN (
                SELECT MIN(id) FROM entities
                GROUP BY pair_id, text_type, position, name, type, content
            )
        ''')
        c.execute('''
            DELETE FROM classifications
            WHERE id NOT IN (
                SELECT MIN(id) FROM classifications
                GROUP BY pair_id, text_type, category_name, confidence
            )
        ''')
        conn.commit()
    except Exception as e:
        print(f"[WARN] Deduplication during migration failed for project {project_name}: {e}")

    # Cleanup orphan annotations: remove any annotations referencing tags that no longer exist
    try:
        c.execute("DELETE FROM annotations WHERE tag_id NOT IN (SELECT id FROM tags)")
        conn.commit()
    except Exception as e:
        print(f"[WARN] Cleanup of orphan annotations failed for project {project_name}: {e}")

    conn.close()

def get_nlp_conclusion(project_name, pair_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT pair_id, conclusion, inconsistencies FROM nlp_conclusions WHERE pair_id = ?', (pair_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    try:
        import json as _json
        inconsistencies = _json.loads(row['inconsistencies']) if row['inconsistencies'] else []
    except Exception:
        inconsistencies = []
    return {'pair_id': row['pair_id'], 'conclusion': row['conclusion'] or '', 'inconsistencies': inconsistencies}

def save_nlp_conclusion(project_name, pair_id, conclusion, inconsistencies, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    import json as _json
    inconsistencies_json = _json.dumps(inconsistencies or [])
    # Upsert by pair_id
    c.execute('''
        INSERT INTO nlp_conclusions (pair_id, conclusion, inconsistencies)
        VALUES (?, ?, ?)
        ON CONFLICT(pair_id) DO UPDATE SET
            conclusion=excluded.conclusion,
            inconsistencies=excluded.inconsistencies,
            updated_at=CURRENT_TIMESTAMP
    ''', (pair_id, conclusion or '', inconsistencies_json))
    conn.commit()
    conn.close()

def get_linguistic_analysis(project_name, pair_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    if not os.path.exists(project_db_name):
        raise FileNotFoundError(f"Database file not found at {project_db_name}")
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT analysis_json FROM nlp_linguistic_analyses WHERE pair_id = ?', (pair_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    try:
        import json as _json
        return _json.loads(row['analysis_json'])
    except Exception:
        return None

def save_linguistic_analysis(project_name, pair_id, analysis_obj, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    import json as _json
    payload = _json.dumps(analysis_obj or {})
    c.execute('''
        INSERT INTO nlp_linguistic_analyses (pair_id, analysis_json)
        VALUES (?, ?)
        ON CONFLICT(pair_id) DO UPDATE SET
            analysis_json=excluded.analysis_json,
            updated_at=CURRENT_TIMESTAMP
    ''', (pair_id, payload))
    conn.commit()
    conn.close()

def get_all_notes(project_name, db_path):
    """
    Return all notes for a project as a list of dicts: {id, pair_id, title, content}.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute('SELECT id, pair_id, title, content FROM notes ORDER BY pair_id, id')
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_notes_count(project_name, db_path):
    """
    Return the total number of notes for a project.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    try:
        c.execute('SELECT COUNT(*) FROM notes')
        count = c.fetchone()[0]
        return count
    finally:
        conn.close()

def load_json_data(project_name, data_type, db_path):
    """
    Load JSON data from the project's database for a given data type.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        SELECT id, pair_id, json_content
        FROM json_items
        WHERE data_type = ?
    ''', (data_type,))
    results = c.fetchall()
    conn.close()
    loaded_data = []
    for result in results:
        content = json.loads(result[2]) # json_content is at index 2
        if isinstance(content, dict):
            content['id'] = result[0] # Add the row ID as 'id'
            # Prioritize pair_id from content, else use from table
            content['pair_id'] = content.get('pair_id', result[1])
            loaded_data.append(content)
    return loaded_data

def load_text_data(project_name, db_path):
    """
    Load error_text and corrected_text data from the project's database.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        SELECT id, error_text, corrected_text, title, scratchpad_content
        FROM csv_data
    ''')
    results = c.fetchall()
    conn.close()
    loaded_data = [{'id': result[0], 'error_text': result[1], 'corrected_text': result[2], 'title': result[3], 'scratchpad_content': result[4]} for result in results]
    return loaded_data


def load_nlp_dataframe(project_name, table_name, db_path, condition=None):
    """
    Load data from a specified table in the project's database into a pandas DataFrame.

    Args:
        project_name (str): The name of the project.
        table_name (str): The name of the table to load data from.
        condition (str, optional): An optional condition to filter the data.

    Returns:
        pd.DataFrame: A DataFrame containing the table data.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)

    query = f'SELECT * FROM {table_name}'
    if condition:
        query += f' WHERE {condition}'

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df

def load_csv_data(project_name, db_path):
    """
    Load data from the csv_data table of the project's database.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        SELECT id, error_text, corrected_text, title
        FROM csv_data
    ''')
    results = c.fetchall()
    conn.close()
    return [{'id': result[0], 'error_text': result[1], 'corrected_text': result[2], 'title': result[3]} for result in results]

def save_title_to_db(project_name, pair_id, title, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        UPDATE csv_data
        SET title = ?
        WHERE id = ?
    ''', (title, pair_id))
    conn.commit()
    conn.close()


# Function to save genre and main idea to the database
def save_genre_and_main_idea(project_name, genre, main_idea, record_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        UPDATE csv_data
        SET genre = ?, meaning = ?
        WHERE id = ?
    ''', (genre, main_idea, record_id))
    conn.commit()
    conn.close()


def retrieve_all_genre_main_idea_and_category(project_name, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    with sqlite3.connect(project_db_name) as conn:
        c = conn.cursor()

        # Retrieve data from csv_data table
        c.execute('''
            SELECT id, genre, meaning
            FROM csv_data
        ''')
        csv_data_results = c.fetchall()

        # Retrieve data from classifications table
        c.execute('''
            SELECT pair_id, category_name
            FROM classifications
        ''')
        classifications_results = c.fetchall()

    return {
        "Genre": csv_data_results,
        "Classifications": classifications_results
    }

def save_json_data_if_not_exists(project_name, pair_id, data_type, json_content, db_path):
    """
    Save JSON data to the project's database, replacing existing entries for the same pair_id and data_type.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    # Delete existing data for this pair_id and data_type to prevent duplication
    c.execute('DELETE FROM json_items WHERE pair_id = ? AND data_type = ?', (pair_id, data_type))

    try:
        # Ensure json_content is a valid JSON string
        if isinstance(json_content, str):
            json_content = json.loads(json_content)  # Convert JSON string to a list of dictionaries
        else:
            json_content = json_content  # Already a list of dictionaries

        for item in json_content:
            operation_type = item.get('operation')
            if operation_type:
                item['pair_id'] = pair_id # Add pair_id to the item
                json_item = json.dumps(item)
                c.execute('''
                    INSERT INTO json_items (pair_id, data_type, json_content)
                    VALUES (?, ?, ?)
                ''', (pair_id, data_type, json_item))
                item_id = c.lastrowid

    except json.JSONDecodeError as jde:
        print(f"JSON decode error: {jde}, json_content: {json_content[:50]}...")  # Debugging print
    except Exception as e:
        print(f"Error inserting item: {e}, json_content: {json_content[:50]}...")  # Debugging print

    conn.commit()
    conn.close()


def save_csv_data_if_not_exists(project_name, csv_data, db_path):
    """
    Save CSV data to the project's database if it does not already exist.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM csv_data')
    if c.fetchone()[0] == 0:
        for item in csv_data:
            c.execute('''
                INSERT INTO csv_data (error_text, corrected_text)
                VALUES (?, ?)
            ''', (item['ErrorText'], item['CorrectedText']))
            item['id'] = c.lastrowid
        conn.commit()
    conn.close()

def update_json_item(project_name, data_type, item_id, json_content, db_path):
    """
    Update a JSON item in the project's database with new content.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('UPDATE json_items SET json_content = ? WHERE data_type = ? AND id = ?', (json.dumps(json_content), data_type, item_id))
    conn.commit()
    conn.close()


def save_highlights(project_name, data_type, original_name, db_path, new_name=None, new_description=None):
    """
    Update the highlights in the JSON content stored in the json_items table.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    # Select the json_content from the json_items table
    c.execute('SELECT id, json_content FROM json_items WHERE data_type = ?', (data_type,))
    rows = c.fetchall()

    for row in rows:
        item_id, json_content = row
        content = json.loads(json_content)

        # Update the Highlights in the json_content
        updated = False
        for highlight in content.get('Highlights', []):
            if highlight['name'] == original_name:
                if new_name:
                    highlight['name'] = new_name
                if new_description:
                    highlight['description'] = new_description
                updated = True

        # Save the updated json_content back to the database
        if updated:
            new_json_content = json.dumps(content)
            c.execute('UPDATE json_items SET json_content = ? WHERE id = ?', (new_json_content, item_id))

    conn.commit()
    conn.close()

def update_tags_or_highlights(project_name, data, is_highlight_update, db_path):
    """
    Update tags or highlights in the JSON data based on the provided data.
    """
    elementText = data['elementText']
    elementPosWrong = data.get('elementPosWrong', '')
    elementPosCorrect = data.get('elementPosCorrect', '')
    elementPosDiff = data.get('elementPosDiff', '')
    elementDataPairId = data.get('elementDataPairId', '')

    tagName = data['name']

    tagDescription = None
    isActive = None

    if is_highlight_update:
        isActive = data['active']
    else:
        tagDescription = data.get('description', '')

    html_wrong = load_json_data(project_name, 'wrong', db_path)
    html_correct = load_json_data(project_name, 'correct', db_path)
    html_diff = load_json_data(project_name, 'diff', db_path)

    updated_highlights, updated_element, updated_pos_wrong, updated_pos_correct, updated_pos_diff, updated_pair_id = (
        update_highlights(html_wrong, project_name, 'wrong', elementText, elementPosWrong, elementPosCorrect, elementPosDiff, elementDataPairId, tagName, db_path, tagDescription, isActive) or
        update_highlights(html_correct, project_name, 'correct', elementText, elementPosWrong, elementPosCorrect, elementPosDiff, elementDataPairId, tagName, db_path, tagDescription, isActive) or
        update_highlights(html_diff, project_name, 'diff', elementText, elementPosWrong, elementPosCorrect, elementPosDiff, tagName, elementDataPairId, db_path, tagDescription, isActive)
    )

    return {
        "updated_highlights": updated_highlights,
        "updated_element": updated_element,
        "updated_pos_wrong": updated_pos_wrong,
        "updated_pos_correct": updated_pos_correct,
        "updated_pos_diff": updated_pos_diff,
        "updated_pair_id": updated_pair_id
    }

def update_highlights(dataset, project_name, data_type, elementText, elementPosWrong, elementPosCorrect, elementPosDiff, elementDataPairId, tagName, db_path, tagDescription=None, isActive=None):
    """
    Helper function to update highlights in the JSON dataset.
    """
    updated = False
    for item in dataset:
        # Ensure item is a dictionary and has the necessary keys
        if not isinstance(item, dict):
            continue

        # Access position data directly from the item dictionary
        item_pos_wrong = item.get('position_in_wrong')
        item_pos_correct = item.get('position_in_correct')
        item_pos_diff = item.get('position_in_diff')
        item_pair_id = item.get('pair_id')

        match_found = (item.get('element') == elementText and
                       (elementPosWrong in [None, '', "undefined"] or item_pos_wrong == elementPosWrong) and
                       (elementPosCorrect in ['', "undefined"] or item_pos_correct == elementPosCorrect) and
                       (elementPosDiff in ['', "undefined"] or item_pos_diff == elementPosDiff) and
                       (elementDataPairId in ['', "undefined"] or item_pair_id == elementDataPairId))

        if tagDescription is not None:
            tag_exists = False
            for highlight in item.get('Highlights', []):
                if highlight['name'] == tagName:
                    if highlight['active'] != match_found:
                        highlight['active'] = match_found
                        updated = True
                    tag_exists = True
                    break

            if not tag_exists:
                item.setdefault('Highlights', []).append({
                    'name': tagName,
                    'description': tagDescription,
                    'active': match_found
                })
                updated = True
        else:
            highlight_found = False
            for highlight in item.get('Highlights', []):
                if highlight['name'] == tagName:
                    highlight['active'] = isActive
                    highlight_found = True
                    updated = True
                    break

            if not highlight_found:
                item.setdefault('Highlights', []).append({
                    'name': tagName,
                    'active': isActive
                })
                updated = True

        if match_found:
            if updated:
                update_json_item(project_name, data_type, item['id'], item, db_path)
            return (item.get('Highlights', []),
                    item.get('element'),
                    item.get('position_in_wrong'),
                    item.get('position_in_correct'),
                    item.get('position_in_diff'),
                    item.get('pair_id'))

    return [], None, None, None, None


# Save highlight function
def save_highlight(dataset, project_name, data_type, original_name, new_name, new_description, db_path):
    updated = False
    for item in dataset:
        for highlight in item.get('Highlights', []):
            if highlight['name'] == original_name:
                highlight['name'] = new_name
                highlight['description'] = new_description
                updated = True
                break

        if updated:
            update_json_item(project_name, data_type, item['id'], item, db_path)
            return (item.get('Highlights', []),
                    item.get('element', None),
                    item.get('position_in_wrong', None),
                    item.get('position_in_correct', None),
                    item.get('position_in_diff', None),
                    item.get('pair_id', None))

    return [], None, None, None, None

def get_tags(project_name, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM tags')
    tags = [dict(row) for row in c.fetchall()]
    conn.close()
    return tags

def create_tag(project_name, name, description, parent_tag_id, color, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('INSERT INTO tags (name, description, parent_tag_id, color) VALUES (?, ?, ?, ?)', (name, description, parent_tag_id, color))
    conn.commit()
    new_tag_id = c.lastrowid
    conn.close()
    return get_tag(project_name, new_tag_id, db_path)

def get_tag(project_name, tag_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM tags WHERE id = ?', (tag_id,))
    tag = dict(c.fetchone())
    conn.close()
    return tag

def update_tag(project_name, tag_id, db_path, **kwargs):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    fields_to_update = []
    params = []

    for key, value in kwargs.items():
        fields_to_update.append(f"{key} = ?")
        params.append(value)

    if not fields_to_update:
        return get_tag(project_name, tag_id, db_path)

    params.append(tag_id)
    c.execute(f'UPDATE tags SET {", ".join(fields_to_update)} WHERE id = ?', tuple(params))
    
    conn.commit()
    conn.close()
    return get_tag(project_name, tag_id, db_path)

def delete_tag(project_name, tag_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    # Get all descendant tags (including the tag itself)
    c.execute('''
        WITH RECURSIVE Subtags AS (
            SELECT id FROM tags WHERE id = ?
            UNION ALL
            SELECT t.id FROM tags t JOIN Subtags s ON t.parent_tag_id = s.id
        )
        SELECT id FROM Subtags;
    ''', (tag_id,))
    tags_to_delete = [row[0] for row in c.fetchall()]

    if tags_to_delete:
        # Also remove any manual highlights (JSON) whose name matches the tag(s)
        try:
            # Fetch names before deleting tags
            placeholders = ','.join('?' * len(tags_to_delete))
            c.execute(f'SELECT name FROM tags WHERE id IN ({placeholders})', tags_to_delete)
            tag_names = [row[0] for row in c.fetchall()]
        except Exception:
            tag_names = []

        try:
            if tag_names:
                html_wrong = load_json_data(project_name, 'wrong', db_path)
                html_correct = load_json_data(project_name, 'correct', db_path)
                html_diff = load_json_data(project_name, 'diff', db_path)
                for nm in tag_names:
                    try:
                        delete_highlight(html_wrong, project_name, 'wrong', nm, db_path)
                    except Exception:
                        pass
                    try:
                        delete_highlight(html_correct, project_name, 'correct', nm, db_path)
                    except Exception:
                        pass
                    try:
                        delete_highlight(html_diff, project_name, 'diff', nm, db_path)
                    except Exception:
                        pass
        except Exception:
            pass

        # Delete annotations associated with these tags
        placeholders = ','.join('?' * len(tags_to_delete))
        c.execute(f'DELETE FROM annotations WHERE tag_id IN ({placeholders})', tags_to_delete)

        # Delete the tags themselves
        c.execute(f'DELETE FROM tags WHERE id IN ({placeholders})', tags_to_delete)

    conn.commit()
    conn.close()

def delete_tags(project_name, tag_ids, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    if not tag_ids:
        conn.close()
        return

    placeholders = ','.join('?' for _ in tag_ids)

    # Get all descendant tags (including the tags themselves)
    c.execute(f'''
        WITH RECURSIVE Subtags AS (
            SELECT id FROM tags WHERE id IN ({placeholders})
            UNION ALL
            SELECT t.id FROM tags t JOIN Subtags s ON t.parent_tag_id = s.id
        )
        SELECT id FROM Subtags;
    ''', tag_ids)
    tags_to_delete = [row[0] for row in c.fetchall()]

    if tags_to_delete:
        # Also remove any manual highlights (JSON) whose name matches the tag(s)
        try:
            placeholders = ','.join('?' * len(tags_to_delete))
            c.execute(f'SELECT name FROM tags WHERE id IN ({placeholders})', tags_to_delete)
            tag_names = [row[0] for row in c.fetchall()]
        except Exception:
            tag_names = []

        try:
            if tag_names:
                html_wrong = load_json_data(project_name, 'wrong', db_path)
                html_correct = load_json_data(project_name, 'correct', db_path)
                html_diff = load_json_data(project_name, 'diff', db_path)
                for nm in tag_names:
                    try:
                        delete_highlight(html_wrong, project_name, 'wrong', nm, db_path)
                    except Exception:
                        pass
                    try:
                        delete_highlight(html_correct, project_name, 'correct', nm, db_path)
                    except Exception:
                        pass
                    try:
                        delete_highlight(html_diff, project_name, 'diff', nm, db_path)
                    except Exception:
                        pass
        except Exception:
            pass

        # Delete annotations associated with these tags
        placeholders = ','.join('?' * len(tags_to_delete))
        c.execute(f'DELETE FROM annotations WHERE tag_id IN ({placeholders})', tags_to_delete)

        # Delete the tags themselves
        c.execute(f'DELETE FROM tags WHERE id IN ({placeholders})', tags_to_delete)

    conn.commit()
    conn.close()

def save_annotation(project_name, pair_id, data_type, start_offset, end_offset, tag_id, text, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()

    # Check for an existing annotation with the same attributes
    c.execute('''
        SELECT id FROM annotations 
        WHERE project_name = ? AND pair_id = ? AND data_type = ? AND start_offset = ? AND end_offset = ? AND tag_id = ?
    ''', (project_name, pair_id, data_type, start_offset, end_offset, tag_id))
    existing_annotation = c.fetchone()

    if existing_annotation:
        # If it exists, return the existing annotation
        conn.close()
        return get_annotation(project_name, existing_annotation[0], db_path)

    # Delete any existing annotations with the same tag that overlap with the new one.
    # Overlap condition: (StartA <= EndB) and (EndA >= StartB)
    c.execute('''
        DELETE FROM annotations
        WHERE project_name = ? AND pair_id = ? AND data_type = ? AND tag_id = ? AND
              start_offset <= ? AND end_offset >= ?
    ''', (project_name, pair_id, data_type, tag_id, end_offset, start_offset))

    # If it doesn't exist, insert the new annotation
    c.execute('INSERT INTO annotations (project_name, pair_id, data_type, start_offset, end_offset, tag_id, text) VALUES (?, ?, ?, ?, ?, ?, ?)', (project_name, pair_id, data_type, start_offset, end_offset, tag_id, text))
    conn.commit()
    new_annotation_id = c.lastrowid
    conn.close()
    return get_annotation(project_name, new_annotation_id, db_path)

def save_diff_text(project_name, pair_id, diff_text, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO diff_data (pair_id, diff_text) VALUES (?, ?)', (pair_id, diff_text))
    conn.commit()
    conn.close()

def get_annotation(project_name, annotation_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM annotations WHERE id = ?', (annotation_id,))
    annotation = dict(c.fetchone())
    conn.close()
    return annotation

# Delete highlight function
def delete_highlight(dataset, project_name, data_type, name, db_path):
    updated = False
    for item in dataset:
        highlights = item.get('Highlights', [])
        new_highlights = [highlight for highlight in highlights if highlight['name'] != name]

        if len(highlights) != len(new_highlights):
            item['Highlights'] = new_highlights
            updated = True

        if updated:
            update_json_item(project_name, data_type, item['id'], item, db_path)
            return (item.get('Highlights', []),
                    item.get('element', None),
                    item.get('position_in_wrong', None),
                    item.get('position_in_correct', None),
                    item.get('position_in_diff', None),
                    item.get('pair_id', None))

    return [], None, None, None, None

def delete_annotation(project_name, annotation_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('DELETE FROM annotations WHERE id = ?', (annotation_id,))
    conn.commit()
    conn.close()

def save_chat_message(project_name, pair_id, sender, message, db_path):
    """
    Save a chat message to the project's database.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        INSERT INTO chat_history (pair_id, sender, message)
        VALUES (?, ?, ?)
    ''', (pair_id, sender, message))
    conn.commit()
    conn.close()

def get_chat_history(project_name, pair_id, db_path):
    """
    Retrieve the chat history for a given pair_id from the project's database.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT id, sender, message, timestamp
        FROM chat_history
        WHERE pair_id = ?
        ORDER BY timestamp ASC
    ''', (pair_id,))
    history = [dict(row) for row in c.fetchall()]
    conn.close()
    return history

def save_tr_chat_message(project_name, sender, message, db_path):
    """
    Save a Tag Report Insights chat message for the project (project-level, not tied to a pair).
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        INSERT INTO tr_chat_history (sender, message)
        VALUES (?, ?)
    ''', (sender, message))
    conn.commit()
    conn.close()

def get_tr_chat_history(project_name, limit, db_path):
    """
    Retrieve the last N Tag Report Insights chat messages for the project, ordered oldest->newest.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Get last 'limit' by id DESC, then reverse to chronological order
    c.execute('''
        SELECT id, sender, message, timestamp
        FROM tr_chat_history
        ORDER BY id DESC
        LIMIT ?
    ''', (int(limit or 10),))
    rows = c.fetchall()
    conn.close()
    messages = [dict(r) for r in rows][::-1]
    return messages

def save_scratchpad_content(project_name, pair_id, content, db_path):
    """
    Save the scratchpad content for a specific pair_id.
    """
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        UPDATE csv_data
        SET scratchpad_content = ?
        WHERE id = ?
    ''', (content, pair_id))
    conn.commit()
    conn.close()

def create_note(project_name, pair_id, title, content, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('INSERT INTO notes (pair_id, title, content) VALUES (?, ?, ?)', (pair_id, title, content))
    conn.commit()
    note_id = c.lastrowid
    conn.close()
    return get_note(project_name, note_id, db_path)

def get_note(project_name, note_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM notes WHERE id = ?', (note_id,))
    note = dict(c.fetchone())
    conn.close()
    return note

def get_notes_for_pair(project_name, pair_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM notes WHERE pair_id = ? ORDER BY updated_at DESC', (pair_id,))
    notes = [dict(row) for row in c.fetchall()]
    conn.close()
    return notes

def update_note(project_name, note_id, title, content, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (title, content, note_id))
    conn.commit()
    conn.close()
    return get_note(project_name, note_id, db_path)

def delete_note(project_name, note_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()


def create_auto_tagging_job(project_name, pair_id, instruction, plan, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        INSERT INTO auto_tagging_jobs (pair_id, instruction, plan)
        VALUES (?, ?, ?)
    ''', (pair_id, instruction, json.dumps(plan)))
    conn.commit()
    job_id = c.lastrowid
    conn.close()
    return job_id


def update_auto_tagging_job_status(project_name, job_id, status, result, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    c = conn.cursor()
    c.execute('''
        UPDATE auto_tagging_jobs
        SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status, json.dumps(result), job_id))
    conn.commit()
    conn.close()


def get_auto_tagging_job(project_name, job_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM auto_tagging_jobs WHERE id = ?', (job_id,))
    job = dict(c.fetchone())
    conn.close()
    return job


def get_auto_tagging_jobs_for_pair(project_name, pair_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM auto_tagging_jobs WHERE pair_id = ? ORDER BY created_at DESC', (pair_id,))
    jobs = [dict(row) for row in c.fetchall()]
    conn.close()
    return jobs


def load_text_pair(project_name, pair_id, db_path):
    project_db_name = os.path.join(db_path, f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM csv_data WHERE id = ?', (pair_id,))
    pair = dict(c.fetchone())
    conn.close()
    return pair
