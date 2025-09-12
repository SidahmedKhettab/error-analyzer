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


def generate_coherence_analysis(project_name, wrong_text, corrected_text, language='en', lang='en'):
    api_key = get_google_api_key()
    if not api_key:
        return {
            'summary': get_translation('API key not configured. Cannot perform AI-based coherence analysis.', lang),
            'findings': [],
            'interpretation': get_translation('Please configure the GOOGLE_API_KEY in your application settings.', lang)
        }

    client = genai.Client(api_key=api_key)

    prompt = f"""{get_translation('Your task is to perform a "Qualitative Coherence Analysis" by comparing two texts: an "Original Text" and a "Corrected Text". The Corrected Text should be treated as the norm or baseline for coherence and cohesion.', lang)}

{(_lang_reply_instruction(lang) or '')}

{get_translation('Do NOT make any assumptions about the author of the Original Text. It could be a human learner, a machine translation output, or any other source. Frame your analysis neutrally.', lang)}

{get_translation('Your analysis must be returned as a JSON object with the following structure:', lang)}
{{
  "summary": "A brief, one-sentence summary of the main coherence and cohesion issues.",
  "findings": [
    {{
      "label": "A specific linguistic feature (e.g., Reference, Conjunction, Lexical Cohesion)",
      "explanation": "A detailed explanation of the divergence, with specific examples from both texts. Use Markdown for formatting."
    }}
  ],
  "interpretation": "A brief, insightful interdisciplinary interpretation of the observed divergences, synthesizing concepts from multiple human and social sciences (e.g., cognitive science, sociolinguistics, psychology). Use Markdown for formatting."
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
        sys_instr = get_translation('You are an expert in discourse analysis, linguistics, and communication studies, with a strong interdisciplinary background in human and social sciences (including cognitive science, sociology, and psychology).', lang)
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
