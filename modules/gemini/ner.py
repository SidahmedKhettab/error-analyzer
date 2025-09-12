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
from flask import current_app

from ..utils import get_google_api_key
from ..translations import get_translation
from ..models import get_gemini_model
from ._common import _lang_reply_instruction
from ..db import load_text_data, get_project_file, load_nlp_dataframe


def generate_qualitative_ner_analysis(project_name, wrong_text, corrected_text, language='en', lang='en'):
    api_key = get_google_api_key()
    if not api_key:
        return {
            'summary': get_translation('API key not configured. Cannot perform AI-based coherence analysis.', lang),
            'findings': [],
            'interpretation': get_translation('Please configure the GOOGLE_API_KEY in your application settings.', lang)
        }

    client = genai.Client(api_key=api_key)

    prompt = f"""{(_lang_reply_instruction(lang) or '')}

{get_translation('Your task is to perform a "Qualitative NER Analysis" by comparing two texts: an "Original Text" and a "Corrected Text". The Corrected Text should be treated as the norm or baseline for NER structure and focus.', lang)}

{get_translation('Do NOT make any assumptions about the author of the Original Text. It could be a human learner, a machine translation output, or any other source. Frame your analysis neutrally.', lang)}

{get_translation('Your analysis must be returned as a JSON object with the following structure:', lang)}
{{
  "summary": "A brief, one-sentence summary of the main NER divergences.",
  "findings": [
    {{
      "label": "A specific entity type (e.g., Person, Location, Organization)",
      "explanation": "A detailed explanation of how this entity type is represented, developed, or distorted in the Original Text compared to the Corrected Text. Use Markdown for formatting and provide examples."
    }}
  ],
  "interpretation": "A brief, insightful interdisciplinary interpretation of the observed NER divergences. Synthesize concepts from multiple human and social sciences (e.g., cognitive linguistics, psycholinguistics, sociolinguistics) to explain the potential implications of the NER shifts. Use Markdown for formatting."
}}

{get_translation('**Original Text**:', lang)}
---
{wrong_text}
---

{get_translation('**Corrected Text**:', lang)}
---
{corrected_text}
---
"""

    try:
        sys_instr = get_translation('You are an expert linguistic analyst and a helpful assistant for qualitative research.', lang)
        li = _lang_reply_instruction(lang)
        if li:
            sys_instr = sys_instr + ' ' + li
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        analysis_text = getattr(response, 'text', '') or str(response)
        if not analysis_text.strip():
            return {
                'summary': get_translation('AI analysis returned an empty response.', lang),
                'findings': [],
                'interpretation': get_translation('The model returned an empty response. This could be due to a content filter or an API issue.', lang)
            }
        return json.loads(analysis_text)
    except json.JSONDecodeError as e:
        return {
            'summary': get_translation('An error occurred during AI analysis: Invalid JSON response.', lang),
            'findings': [{'label': get_translation('Raw Model Output', lang), 'explanation': analysis_text}],
            'interpretation': get_translation("The model's response was not valid JSON, which is required for this feature. The error was: {e}", lang).format(e=e)
        }
    except Exception as e:
        return {
            'summary': get_translation('An error occurred during AI analysis.', lang),
            'findings': [],
            'interpretation': str(e)
        }


def generate_ner_analysis(project_name, pair_id, lang='en'):
    try:
        pairs = load_text_data(project_name, current_app.config['DATABASE_PATH'])
        pair = next((p for p in pairs if int(p['id']) == int(pair_id)), None)
        wrong_text = pair.get('error_text') if pair else ''
        corrected_text = pair.get('corrected_text') if pair else ''
    except Exception:
        wrong_text = corrected_text = ''

    try:
        _, _, language, _ = get_project_file(project_name, current_app.config['DATABASE_PATH'])
    except Exception:
        language = 'en'

    cond = f"pair_id = {int(pair_id)}"
    entities_df = load_nlp_dataframe(project_name, 'entities', current_app.config['DATABASE_PATH'], condition=cond)

    try:
        e_wrong = entities_df[entities_df['text_type'] == 'error_text'] if entities_df is not None and not entities_df.empty else entities_df
        e_corr = entities_df[entities_df['text_type'] == 'corrected_text'] if entities_df is not None and not entities_df.empty else entities_df
    except Exception:
        e_wrong = entities_df
        e_corr = entities_df

    qualitative_ner = generate_qualitative_ner_analysis(project_name, wrong_text, corrected_text, language, lang)

    return {
        'ner_analysis': {
            'wrong': e_wrong.to_dict(orient='records') if (e_wrong is not None and not e_wrong.empty) else [],
            'correct': e_corr.to_dict(orient='records') if (e_corr is not None and not e_corr.empty) else [],
            'qualitative_analysis': qualitative_ner,
        }
    }

