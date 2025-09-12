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

import json
from google import genai
from google.genai import types
from flask import current_app, g

from ..db import get_project_file
from ..utils import get_google_api_key
from ..translations import get_translation
from ..models import get_gemini_model
from ._common import _lang_reply_instruction


def get_genre_and_main_idea(project_name, corrected_text, lang='en'):
    google_api_key = get_google_api_key()
    if not google_api_key:
        return None, None

    client = genai.Client(api_key=google_api_key)

    try:
        _, _, language, _ = get_project_file(project_name, current_app.config['DATABASE_PATH'])
        _ = language  # reserved for future use
        prompt = get_translation(
            'You are a helpful assistant. Please determine the genre and main idea of the following text.',
            lang,
        ) + f'\n\n{corrected_text}'
    except Exception:
        return None, None

    try:
        generation_config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_schema=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "response": types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "genre": types.Schema(type=types.Type.STRING),
                            "main_idea": types.Schema(type=types.Type.STRING),
                        },
                    ),
                },
            ),
            response_mime_type="application/json",
        )
        sys_instr = get_translation(
            'You are a helpful assistant. Please determine the genre and main idea of the following text.',
            lang,
        )
        li = _lang_reply_instruction(lang)
        if li:
            sys_instr = sys_instr + ' ' + li
    except Exception:
        return None, None

    try:
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
            config=generation_config
        )
    except Exception:
        return None, None

    genre = None
    main_idea = None
    try:
        response_data = response.to_dict()  # SDK dependent
        genre = response_data["response"].get("genre")
        main_idea = response_data["response"].get("main_idea")
    except Exception:
        pass
    return genre, main_idea
