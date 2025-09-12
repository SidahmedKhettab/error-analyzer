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


def generate_topics_analysis(project_name, wrong_text, corrected_text, language='en', lang='en'):
    api_key = get_google_api_key()
    if not api_key:
        return {
            'summary': get_translation('API key not configured. Cannot perform AI-based topics analysis.', lang),
            'findings': [],
            'interpretation': get_translation('Please configure the GOOGLE_API_KEY in your application settings.', lang)
        }

    client = genai.Client(api_key=api_key)

    prompt = f"""{get_translation('You are an expert in topic modeling, discourse analysis, and semantics, with a strong interdisciplinary background in human and social sciences.', lang)}

{(_lang_reply_instruction(lang) or '')}

{get_translation('Your task is to perform a "Qualitative Topics Analysis" by comparing two texts: an "Original Text" and a "Corrected Text". The Corrected Text should be treated as the norm or baseline for topic structure and focus.', lang)}

{get_translation('**IMPORTANT**: Your analysis must focus *exclusively* on topics and themes. Do NOT include any analysis of grammar, syntax, or other linguistic features unless they directly impact the identification, development, or distortion of a topic. For example, a grammatical error that changes the meaning of a sentence and thus alters the topic is relevant, but a simple spelling error is not.', lang)}

{get_translation('Do NOT make any assumptions about the author of the Original Text.', lang)}

{get_translation('Your analysis must be returned as a JSON object with the following structure:', lang)}
{{
  "summary": "A brief, one-sentence summary of the main topic divergences.",
  "findings": [
    {{
      "label": "A specific topic or theme",
      "explanation": "A detailed explanation of how this topic is represented, developed, or distorted in the Original Text compared to the Corrected Text. Use Markdown for formatting and provide examples."
    }}
  ],
  "interpretation": "A brief, insightful interdisciplinary interpretation of the observed topic divergences. Synthesize concepts from multiple human and social sciences (e.g., communication studies, sociology of knowledge, media studies, political science) to explain the potential implications of the topic shifts. Use Markdown for formatting."
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
        sys_instr = get_translation('You are an expert in topic modeling, discourse analysis, and semantics, with a strong interdisciplinary background in human and social sciences.', lang)
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
            'interpretation': get_translation("The model's response was not valid JSON, which is required for this feature. The error was:", lang) + f" {e}"
        }
    except Exception as e:
        return {
            'summary': get_translation('An error occurred during AI analysis.', lang),
            'findings': [],
            'interpretation': str(e)
        }
