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
import json
from flask import session

TRANSLATIONS = {}
locales_dir = os.path.join(os.path.dirname(__file__), 'locales')

for filename in os.listdir(locales_dir):
    if filename.endswith('.json'):
        lang = filename[:-5]
        with open(os.path.join(locales_dir, filename), 'r', encoding='utf-8') as f:
            TRANSLATIONS[lang] = json.load(f)

def get_translation(key, lang=None, **kwargs):
    if lang is None:
        lang = session.get('language', 'en')
    translation = TRANSLATIONS.get(lang, {}).get(key, key)
    if kwargs:
        return translation.format(**kwargs)
    return translation