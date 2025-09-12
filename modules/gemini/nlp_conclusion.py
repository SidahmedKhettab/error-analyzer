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
from flask import current_app
from ..utils import get_google_api_key

from ..db import get_project_file, load_nlp_dataframe, load_text_data
from ..translations import get_translation
from ..models import get_gemini_model
from ._common import _lang_reply_instruction
from ._summaries import summarize_tokens, summarize_entities


def generate_nlp_conclusion(project_name, pair_id, lang='en'):
    google_api_key = get_google_api_key()
    if not google_api_key:
        return None

    client = genai.Client(api_key=google_api_key)

    try:
        _, _, language, _ = get_project_file(project_name, current_app.config['DATABASE_PATH'])
    except Exception:
        language = 'en'

    try:
        pairs = load_text_data(project_name, current_app.config['DATABASE_PATH'])
        pair = next((p for p in pairs if int(p['id']) == int(pair_id)), None)
        wrong_text = pair.get('error_text') if pair else ''
        corrected_text = pair.get('corrected_text') if pair else ''
    except Exception:
        wrong_text, corrected_text = '', ''

    cond = f"pair_id = {int(pair_id)}"
    tokens_df = load_nlp_dataframe(project_name, 'tokens', current_app.config['DATABASE_PATH'], condition=cond)
    entities_df = load_nlp_dataframe(project_name, 'entities', current_app.config['DATABASE_PATH'], condition=cond)
    try:
        tokens_wrong = tokens_df[tokens_df['text_type'] == 'error_text'] if not tokens_df.empty else tokens_df
        tokens_correct = tokens_df[tokens_df['text_type'] == 'corrected_text'] if not tokens_df.empty else tokens_df
    except Exception:
        tokens_wrong = tokens_df
        tokens_correct = tokens_df

    try:
        entities_wrong = entities_df[entities_df['text_type'] == 'error_text'] if not entities_df.empty else entities_df
        entities_correct = entities_df[entities_df['text_type'] == 'corrected_text'] if not entities_df.empty else entities_df
    except Exception:
        entities_wrong = entities_df
        entities_correct = entities_df

    summary_wrong = {
        'tokens': summarize_tokens(tokens_wrong),
        'entities': summarize_entities(entities_wrong),
    }
    summary_correct = {
        'tokens': summarize_tokens(tokens_correct),
        'entities': summarize_entities(entities_correct),
    }

    prompt = (
        get_translation('You are a helpful and insightful linguistic analyst. Your goal is to provide a clear and detailed explanation of the grammatical and usage errors in a given text.', lang) + "\n\n"
        + get_translation('You will be provided with a "wrong" text, a "corrected" text, and NLP analysis summaries for both.', lang) + "\n"
        + get_translation('Your analysis should be presented in a narrative format, as if you were explaining the errors to a student or colleague.', lang) + "\n\n"
        + get_translation('Here is the data:', lang) + "\n"
        + get_translation('- Project Language:', lang) + f" {language}\n"
        + get_translation('- Wrong Text:', lang) + f"\n{wrong_text}\n\n"
        + get_translation('- Corrected Text:', lang) + f"\n{corrected_text}\n\n"
        + get_translation('- NLP Analysis (Wrong Text):', lang) + f"\n{str(summary_wrong)}\n\n"
        + get_translation('- NLP Analysis (Corrected Text):', lang) + f"\n{str(summary_correct)}\n\n"
        + get_translation('Based on this data, please provide the following in your response:', lang) + "\n"
        + get_translation('1.  **Detailed Analysis:** A comprehensive explanation of the errors in the "wrong" text. Use the NLP data to support your analysis. Explain *why* the corrections were made.', lang) + "\n"
        + get_translation('2.  **Interpretation:** Interpret the patterns of errors. Are there recurring issues? What do these errors suggest about the writer\'s proficiency?', lang) + "\n"
        + get_translation('3.  **Clarity and Tone:** Write in a clear, encouraging, and human-like tone. Avoid overly technical jargon.', lang) + "\n\n"
        + get_translation('Please format your response as a JSON object with the following keys:', lang) + "\n"
        + '{\n  "response": {\n    "conclusion": string, // Your detailed analysis and interpretation\n    "inconsistencies": [string] // A list of the main error categories identified\n  }\n}'
    )

    generation_config = types.GenerateContentConfig(
        temperature=0.6,
        top_p=0.9,
        top_k=40,
        max_output_tokens=2048,
        response_schema=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "response": types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "conclusion": types.Schema(type=types.Type.STRING),
                        "inconsistencies": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                    },
                ),
            },
        ),
        response_mime_type="application/json",
    )

    sys_instr = (
        get_translation('You are a linguistic expert providing a detailed and easy-to-understand analysis of text errors.', lang)
    )
    li = _lang_reply_instruction(lang)
    if li:
        sys_instr = sys_instr + ' ' + li

    try:
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
            config=generation_config
        )
    except Exception:
        return None

    raw_text = ''
    try:
        raw_text = getattr(response, 'text', '')
    except Exception:
        raw_text = ''
    if not raw_text:
        try:
            raw_text = str(response)
        except Exception:
            raw_text = ''

    if raw_text:
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                resp = parsed.get('response', parsed)
                return {
                    'conclusion': resp.get('conclusion', ''),
                    'inconsistencies': resp.get('inconsistencies', []),
                }
        except Exception:
            import re
            m = re.search(r'(\{\s*"response"[\s\S]*\})', raw_text)
            if m:
                try:
                    sub = json.loads(m.group(1))
                    resp = sub.get('response', sub)
                    return {
                        'conclusion': resp.get('conclusion', ''),
                        'inconsistencies': resp.get('inconsistencies', []),
                    }
                except Exception:
                    pass

    try:
        data = response.to_dict()
        if isinstance(data, dict) and 'response' in data:
            resp = data['response']
            return {
                'conclusion': resp.get('conclusion', ''),
                'inconsistencies': resp.get('inconsistencies', []),
            }
    except Exception:
        pass

    return {'conclusion': raw_text or '', 'inconsistencies': []}
