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
import re
import urllib.request
from google import genai
from google.genai import types
from flask import current_app

from modules.translations import get_translation
from modules.utils import get_google_api_key
from .models import get_gemini_model


def add_citations(response):
    """Insert inline citations and format references. Links open in a new tab."""
    try:
        text = response.text
    except Exception:
        return getattr(response, 'text', '') or ''

    def get_url_info(url):
        try:
            response = urllib.request.urlopen(url, timeout=10)
            resolved_url = response.geturl()
            html = response.read().decode('utf-8', errors='ignore')
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            title = title_match.group(1) if title_match else None
            return {'url': resolved_url, 'title': title}
        except Exception:
            return {'url': url, 'title': None}

    try:
        candidates = getattr(response, 'candidates', None)
        if not candidates:
            return text
        c0 = candidates[0]
        metadata = getattr(c0, 'grounding_metadata', None) or getattr(c0, 'groundingMetadata', None)
        if not metadata:
            return text
        supports = getattr(metadata, 'grounding_supports', None) or getattr(metadata, 'groundingSupports', None)
        chunks = getattr(metadata, 'grounding_chunks', None) or getattr(metadata, 'groundingChunks', None)
        if not supports or not chunks:
            return text

        def get_prop(obj, snake, camel, default=None):
            return getattr(obj, snake, None) if hasattr(obj, snake) else getattr(obj, camel, default)

        # Sort supports by end index desc to avoid shifting on insertion
        sorted_supports = sorted(supports, key=lambda s: get_prop(getattr(s, 'segment', s), 'end_index', 'endIndex', 0), reverse=True)
        for support in sorted_supports:
            segment = getattr(support, 'segment', None) or {}
            end_index = get_prop(segment, 'end_index', 'endIndex', 0)
            idxs = getattr(support, 'grounding_chunk_indices', None) or getattr(support, 'groundingChunkIndices', None) or []
            if idxs:
                links = []
                for i in idxs:
                    try:
                        chunk = chunks[i]
                        web = getattr(chunk, 'web', None) or {}
                        original_uri = getattr(web, 'uri', '')
                        url_info = get_url_info(original_uri)
                        url = url_info['url']
                        # Use HTML for target="_blank"
                        links.append(f' <a href="{url}" target="_blank">[{i+1}]</a>')
                    except Exception:
                        continue
                if links and isinstance(end_index, int) and 0 <= end_index <= len(text):
                    text = text[:end_index] + ''.join(links) + text[end_index:]

        # Build a more academic-looking references section
        queries = getattr(metadata, 'web_search_queries', None) or getattr(metadata, 'webSearchQueries', None) or []
        refs_lines = []
        refs_lines.append("\n\n---\n**Grounded via Google Search**")
        if queries:
            try:
                qlist = ", ".join([f'<i>{q}</i>' for q in queries if q])
                if qlist:
                    refs_lines.append(f"_Queries used: {qlist}_\n")
            except Exception:
                pass
        refs_lines.append("### References")
        for i, chunk in enumerate(chunks):
            web = getattr(chunk, 'web', None) or {}
            original_uri = (getattr(web, 'uri', '') or '').strip()
            if original_uri:
                url_info = get_url_info(original_uri)
                url = url_info['url']
                title = url_info['title'] or (getattr(web, 'title', '') or '').strip() or f"Source {i+1}"
                # Academic-style citation with clickable link opening in new tab
                refs_lines.append(f'{i+1}. <a href="{url}" target="_blank">{title}</a>')
            else:
                title = (getattr(web, 'title', '') or '').strip() or f"Source {i+1}"
                refs_lines.append(f"{i+1}. {title}.")
        text += "\n\n" + "\n".join(refs_lines)
        return text
    except Exception:
        return text


def get_gemini_chat_response(project_name, question, context, lang='en', use_web_search=False, model_name=None):
    """
    Gets a response from the Gemini API for the chat functionality.

    Args:
        project_name (str): The name of the project.
        question (str): The user's question.
        context (dict): A dictionary containing context like selected text, tags, etc.
        lang (str): The language for the prompt.
        use_web_search (bool): Whether to use web search grounding.

    Returns:
        str: The AI's response, or None if an error occurred.
    """
    google_api_key = get_google_api_key()
    if not google_api_key:
        print(f"[ERROR] No Google API key found for current user or app.")
        return None

    http_options = types.HttpOptions(client_args={"timeout": 60})
    client = genai.Client(api_key=google_api_key, http_options=http_options)

    # Construct a detailed prompt for the AI
    lines = []
    lines.append(get_translation('You are an expert linguistic analyst and a helpful assistant for qualitative research.', lang))
    lines.append(get_translation('Your user is analyzing errors in a text.', lang))
    lines.append(get_translation("Given the user's question and the following context, provide a clear, concise, and insightful answer.", lang))
    lines.append(get_translation('Explain linguistic concepts simply. If the user asks for suggestions, provide them.', lang))
    lines.append(get_translation('Please structure your answer using markdown for clarity and readability. Use headings, lists, and bold text where appropriate.', lang))

    if use_web_search:
        lines.append(get_translation('IMPORTANT: The user has activated the web search tool. You MUST use the search tool to answer the question, synthesizing the search results with the provided context. Cite your sources.', lang))

    lines.append(get_translation('--- CONTEXT ---', lang))
    lines.append(f"{get_translation('Project:', lang)} {project_name}")
    lines.append(f"{get_translation('Selected Text:', lang)} \"{context.get('selected_text', 'N/A')}\"")
    lines.append(f"{get_translation('Analysis:', lang)} {context.get('analysis', 'N/A')}")
    lines.append(f"{get_translation('Existing Tags/Annotations on this text:', lang)} {context.get('tags', 'N/A')}")
    lines.append(f"{get_translation('Full Incorrect Text:', lang)} \"{context.get('wrong_text', 'N/A')}\"")
    lines.append(f"{get_translation('Full Corrected Text:', lang)} \"{context.get('correct_text', 'N/A')}\"")
    lines.append(get_translation('--- END CONTEXT ---', lang))
    lines.append('')
    lines.append(get_translation("User's Question:", lang) + " " + str(question))
    lines.append('')
    lines.append(get_translation('Your Answer:', lang))
    prompt = "\n".join(lines)

    config = None
    if use_web_search:
        # Following the Google AI Studio example provided by the user.
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[grounding_tool])

    try:
        response = client.models.generate_content(
            model=get_gemini_model(model_name),
            contents=prompt,
            config=config
        )
        if use_web_search:
            return add_citations(response)
        return response.text.strip()
    except Exception as e:
        print(f"[ERROR] Failed to generate response from Gemini: {e}")
        return None


def generate_note_title(project_name, content, lang='en'):
    """
    Generates a title for a note using the Gemini API.

    Args:
        project_name (str): The name of the project.
        content (str): The content of the note.
        lang (str): The language for the prompt.

    Returns:
        str: The generated title, or a default title if an error occurred.
    """
    google_api_key = get_google_api_key()
    if not google_api_key:
        print(f"[ERROR] No Google API key found for current user or app.")
        return get_translation('AI-Generated Note', lang)

    http_options = types.HttpOptions(client_args={"timeout": 60})
    client = genai.Client(api_key=google_api_key, http_options=http_options)

    # Build prompt via concatenation to avoid nested f-strings
    lines = []
    lines.append(get_translation('You are a helpful assistant.', lang))
    lines.append(get_translation('Your task is to generate a concise and descriptive title for the following note content.', lang))
    lines.append(get_translation('The title should be no more than 5 words.', lang))
    lines.append('')
    lines.append(get_translation('--- NOTE CONTENT ---', lang))
    lines.append(content)
    lines.append(get_translation('--- END NOTE CONTENT ---', lang))
    lines.append('')
    lines.append(get_translation('Title:', lang))
    prompt = "\n".join(lines)

    try:
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"[ERROR] Failed to generate title from Gemini: {e}")
        return get_translation('AI-Generated Note', lang)


def get_gemini_tag_report_chat_response(project_name, question, context, lang='en', use_web_search=False, model_name=None, history=None):
    """
    Generate a response from Gemini tailored for Tag Report exploration.

    The context should include:
      - filters: dict with keys like tag_name, data_type, search_query
      - stats: dict summarising counts (total_annotations, unique_tags, counts_by_tag, counts_by_data_type)
      - samples: list of compact annotation rows with keys: pair_id, tag_name, data_type, annotated_text, wrong_text, corrected_text

    Returns a markdown string.
    """
    google_api_key = get_google_api_key()
    if not google_api_key:
        print("[ERROR] No Google API key found for current user or app.")
        return None

    http_options = types.HttpOptions(client_args={"timeout": 90})
    client = genai.Client(api_key=google_api_key, http_options=http_options)

    filters = context.get('filters', {}) or {}
    stats = context.get('stats', {}) or {}
    samples = context.get('samples', []) or []

    # Build a compact, LLM-friendly prompt
    lines = []
    lines.append(get_translation('You are an expert data analyst for a linguistic tagging report.', lang))
    lines.append(get_translation('Use the provided filters, summary statistics and sample rows to answer the user.', lang))
    lines.append(get_translation('Be concise, cite numbers from stats when relevant, and reason about patterns across tags/data types.', lang))
    lines.append(get_translation('Format your answer in markdown with short sections and bullet points when helpful.', lang))
    # Strict scope: Tag Report only
    lines.append(get_translation('Important: You are operating inside the Tag Report. ONLY use the Tag Report context provided below.', lang))
    lines.append(get_translation('Do NOT reference or rely on any NLP Analysis or Notes Report content. If the user asks about those, reply that you only have Tag Report data.', lang))
    if use_web_search:
        lines.append(get_translation('Web search is enabled. If needed, use it to ground general claims beyond the dataset and cite sources.', lang))
    lines.append('')
    lines.append(get_translation('--- TAG REPORT CONTEXT ---', lang))
    lines.append(f"{get_translation('Project:', lang)} {project_name}")
    # Filters
    pretty_filters = {
        'tag_name': filters.get('tag_name') or 'All',
        'data_type': filters.get('data_type') or 'All',
        'search_query': filters.get('search_query') or '—',
        'sort_by': filters.get('sort_by') or 'pair_id'
    }
    lines.append(get_translation('Filters:', lang) + f" {pretty_filters}")
    # Stats
    lines.append(get_translation('Summary:', lang))
    lines.append(f"- {get_translation('Total annotations:', lang)} {stats.get('total_annotations', 0)}")
    lines.append(f"- {get_translation('Unique tags:', lang)} {stats.get('unique_tags', 0)}")
    cbt = stats.get('counts_by_tag') or {}
    if cbt:
        # show top 8 tags
        top_tags = sorted(cbt.items(), key=lambda kv: kv[1], reverse=True)[:8]
        lines.append(get_translation('Top tags:', lang) + ' ' + ', '.join([f"{k}({v})" for k, v in top_tags]))
    cbdt = stats.get('counts_by_data_type') or {}
    if cbdt:
        lines.append(get_translation('Counts by data type:', lang) + ' ' + ', '.join([f"{k}={v}" for k, v in cbdt.items()]))
    lines.append('')
    # Samples
    if samples:
        lines.append(get_translation('Sample annotations (truncated):', lang))
        for s in samples[:25]:
            pid = s.get('pair_id')
            tag = s.get('tag_name')
            dtype = s.get('data_type')
            ann = s.get('annotated_text')
            wt = s.get('wrong_text')
            ct = s.get('corrected_text')
            lines.append(f"- #{pid} [{dtype}] {tag}: '{ann}' | w: '{wt}' | c: '{ct}'")
        lines.append('')
    # Explicitly communicate coverage so the model doesn't conflate sample vs totals
    try:
        total = int(stats.get('total_annotations', 0))
        sum_tags = int(stats.get('counts_by_tag_sum', 0))
        coverage = (float(sum_tags)/float(total)) if total>0 else 0.0
        complete = bool(stats.get('counts_complete', False))
        cov_pct = int(round(coverage*100))
        lines.append(get_translation('Coverage note:', lang) + f" counts_by_tag_sum={sum_tags} over total={total} (coverage≈{cov_pct}%). {'Complete tag distribution.' if complete else 'Top-tag summary; not all tags may be listed.'}")
        lines.append('')
    except Exception:
        pass
    # Short memory: include up to 3 prior interactions
    prior = history or []
    if prior:
        lines.append(get_translation('--- RECENT CONVERSATION (last 3 Q/A) ---', lang))
        # Expect history as list of {'sender': 'user'|'ai', 'message': '...'} oldest->newest
        count_pairs = 0
        buf = []
        for msg in prior[-6:]:  # up to 6 messages ~ 3 pairs
            role = (msg.get('sender') or '').lower()
            text = str(msg.get('message') or '').strip()
            if not text:
                continue
            if role in ('user','ai','assistant'):
                role_label = 'User' if role == 'user' else 'Assistant'
                buf.append(f"- {role_label}: {text}")
        if buf:
            lines.extend(buf)
        lines.append(get_translation('--- END RECENT CONVERSATION ---', lang))
    lines.append(get_translation("User's Question:", lang) + ' ' + (question or ''))
    lines.append('')
    lines.append(get_translation('Answer in markdown:', lang))
    prompt = "\n".join(lines)

    config = None
    if use_web_search:
        from google.genai import types as _types
        grounding_tool = _types.Tool(google_search=_types.GoogleSearch())
        config = _types.GenerateContentConfig(tools=[grounding_tool])

    try:
        response = client.models.generate_content(
            model=get_gemini_model(model_name),
            contents=prompt,
            config=config
        )
        if use_web_search:
            return add_citations(response)
        return response.text.strip()
    except Exception as e:
        print(f"[ERROR] Failed to generate Tag Report chat response: {e}")
        return None
