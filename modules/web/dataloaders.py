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

from flask import current_app
from modules.db import load_json_data, retrieve_all_genre_main_idea_and_category, load_text_data, migrate_project_db

class ProjectDataLoader:
    def __init__(self, project_name):
        self.project_name = project_name
        self.db_path = current_app.config['DATABASE_PATH']
        self._migrate_db()

    def _migrate_db(self):
        migrate_project_db(self.project_name, self.db_path)

    def _load_json(self, data_type):
        return load_json_data(self.project_name, data_type, self.db_path)

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
                    'pair_id': int(entry.get('pair_id')),
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