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
import json
import re
from typing import Iterable

from ..translations import get_translation
from ..models import get_gemini_model
from ._common import _lang_reply_instruction


def _strip_html_preserve_breaks(text: str) -> str:
    """Remove HTML tags while preserving reasonable line breaks.

    - Convert <br> and <p> to newlines before stripping other tags
    - Unescape HTML entities at the end
    """
    if not text:
        return ''
    s = str(text)
    # Normalize common block/line-break tags to newlines to keep readable layout
    s = re.sub(r'<\s*(br|br\s*/?)\s*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<\s*/?p\s*>', '\n', s, flags=re.IGNORECASE)
    # Strip all remaining tags
    s = re.sub(r'<[^>]+>', '', s)
    # Collapse excessive blank lines
    s = re.sub(r'\n{3,}', '\n\n', s)
    # Unescape entities
    try:
        import html as _html
        s = _html.unescape(s)
    except Exception:
        pass
    return s.strip()


def _format_json_report_to_markdown(report_json_str: str) -> str:
    """Formats a JSON report object into a Markdown string if applicable."""
    try:
        data = json.loads(report_json_str)
        if not isinstance(data, dict) or "summary" not in data or "findings" not in data:
            return report_json_str
    except json.JSONDecodeError:
        return report_json_str

    parts = []
    if data.get("summary"):
        parts.append(data["summary"])
        parts.append("")

    for finding in data.get("findings", []):
        if isinstance(finding, dict) and "label" in finding and "explanation" in finding:
            parts.append(f"### {finding['label']}")
            parts.append("")
            parts.append(finding['explanation'])
            parts.append("")

    return "\n".join(parts)


def generate_notes_report(project_name, notes, lang='en'):
    if not notes or not any((n.get('content') or '').strip() for n in notes):
        return ''
    api_key = None
    try:
        api_key = get_google_api_key()
    except Exception:
        api_key = None
    if not api_key:
        current_app.logger.warning("GOOGLE_API_KEY not configured for notes report. Skipping heuristic and returning empty report as requested.")
        return ''

    items = []
    for n in notes:
        pid = n.get('pair_id')
        title = _strip_html_preserve_breaks((n.get('title') or '').strip())
        content = _strip_html_preserve_breaks((n.get('content') or '').strip())
        if not (title or content):
            continue
        items.append(f"- Pair {pid} — {title}\n{content}")
    if not items:
        current_app.logger.warning("No contentful notes found for notes report.")
        return ''
    corpus = '\n\n'.join(items)

    try:
        client = genai.Client(api_key=api_key)
        current_app.logger.info("Gemini API configured for notes report.")
    except Exception as e:
        current_app.logger.error(f"Failed to configure Gemini API for notes report: {e}")
        return ''

    # System instruction: keep it simple, narrative, and explicitly non-JSON
    sys_instr = get_translation(
        'You are an expert report generator. Your task is to objectively summarize the provided project notes. Focus solely on synthesizing the content of the notes into a concise narrative report in plain Markdown. Do not offer interpretations, suggestions, or pedagogical advice. Your entire response must be in Markdown format. Do not use any HTML tags. For example, instead of `<h3>Title</h3>`, use `### Title`. Instead of `<ul><li>Item</li></ul>`, use `- Item.`',
        lang
    )
    li = _lang_reply_instruction(lang)
    if li:
        sys_instr = sys_instr + ' ' + li

    from google.genai.types import HarmCategory, HarmBlockThreshold, SafetySetting

    safety_settings = [
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
    ]

    generation_config = genai.types.GenerateContentConfig(
        temperature=0.2, # Lower temperature for more factual, less creative output
        top_p=0.9,
        top_k=32,
        max_output_tokens=8192,
        safety_settings=safety_settings,
    )

    user_prompt = (
        sys_instr + '\n\n' +
        get_translation(
            "Please read the following project notes (titles and contents) and produce a concise, objective report in pure Markdown (headings and bullet points are allowed). Do not return JSON, code blocks, or HTML. Do not add external links, citations, or a references section.",
            lang
        )
        + '\n\n' + corpus
    )
    current_app.logger.info(f"Sending prompt to Gemini for notes report: {user_prompt[:500]}...")
    try:
        resp = client.models.generate_content(
            model=get_gemini_model(),
            contents=user_prompt,
            config=generation_config,
        )
        current_app.logger.info(f"Raw Gemini response for notes report: {resp}")
        text = getattr(resp, 'text', '')
        current_app.logger.info(f"Extracted text from Gemini response for notes report: {text[:500]}...")

        # Attempt to format if it's a JSON report (fallback only)
        formatted_text = _format_json_report_to_markdown(text.strip())

        # Clean up the text, whether it was JSON-formatted or not
        # Remove references and grounding sections
        cleaned_text = re.sub(r'###\s*References[\s\S]*', '', formatted_text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r'Grounded via Google Search[\s\S]*', '', cleaned_text, flags=re.IGNORECASE)
        # Strip HTML (preserving reasonable breaks) and numbered references like [1]
        cleaned_text = _strip_html_preserve_breaks(cleaned_text)
        cleaned_text = re.sub(r'\s*\[\d+\]', '', cleaned_text)
        return cleaned_text.strip()

    except Exception as e:
        current_app.logger.error(f"Error generating notes report with Gemini: {e}", exc_info=True)
        return ''
