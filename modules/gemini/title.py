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
from flask import current_app, session

from ..translations import get_translation
from ..models import get_gemini_model
from ..db import get_project_file
from ._common import _lang_reply_instruction


def generate_pair_title(project_name, text1, text2, api_key):
    if not api_key:
        print("[ERROR] Gemini API key not configured.")
        return None

    client = genai.Client(api_key=api_key)

    try:
        project_details = get_project_file(project_name, current_app.config['DATABASE_PATH'])
        language = project_details[2] if project_details else 'en'
    except Exception:
        language = 'en'

    # UI language for translations
    try:
        ui_lang = session.get('language', 'en')
    except Exception:
        ui_lang = 'en'

    base_prompt = get_translation(
        'Generate a short, 3-5 word title that summarizes the topic of the following text pair. The first text is an incorrect version, and the second is the corrected version. Base the title on the corrected text.',
        ui_lang
    )
    incorrect_text_label = get_translation('Incorrect Text:', ui_lang)
    corrected_text_label = get_translation('Corrected Text:', ui_lang)
    title_label = get_translation('Title:', ui_lang)

    prompt = (
        f"{base_prompt}\n\n"
        f"{incorrect_text_label}\n{text1}\n\n"
        f"{corrected_text_label}\n{text2}\n\n"
        f"{title_label}"
    )

    generation_config = genai.types.GenerateContentConfig(
        temperature=0.7,
        top_p=0.95,
        top_k=40,
        max_output_tokens=50,
    )
    sys_instr = get_translation('You are a helpful assistant that generates short, descriptive titles.', ui_lang)
    li = _lang_reply_instruction(ui_lang)
    if li:
        sys_instr = sys_instr + ' ' + li

    def _extract_text_from_response(resp):
        try:
            t = getattr(resp, 'text', None)
            if t:
                return str(t).strip()
        except Exception:
            pass
        try:
            data = resp.to_dict() if hasattr(resp, 'to_dict') else None
            if isinstance(data, dict):
                cands = data.get('candidates') or []
                for c in cands:
                    try:
                        fr = c.get('finish_reason')
                        if fr not in (None, 0):
                            continue
                    except Exception:
                        pass
                    parts = ((c.get('content') or {}).get('parts')) or []
                    for p in parts:
                        t = p.get('text')
                        if t:
                            return str(t).strip()
        except Exception:
            pass
        return None

    def _heuristic_title(text, lang_code='en'):
        try:
            import re
            s = (text or '').strip()
            if not s:
                return None
            words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:'[A-Za-zÀ-ÖØ-öø-ÿ]+)?", s)
            if not words:
                return None
            stop_en = {
                'the','a','an','and','or','but','so','to','of','in','on','for','with','by','from','that','this','these','those','it','its','as','at','is','are','was','were','be','been','being','their','they','them','we','our','you','your','he','she','his','her','i','my','me','not','do','does','did','have','has','had','will','would','can','could','may','might','should','about','into','over','under','between','among','also','more','most','such','than'
            }
            stop_fr = {
                'le','la','les','un','une','des','et','ou','mais','donc','or','ni','car','de','du','des','au','aux','en','sur','pour','par','avec','sans','dans','que','qui','ce','ces','cette','cet','il','elle','ils','elles','nous','vous','tu','te','ton','ta','tes','son','sa','ses','leurs','leur','est','sont','était','étaient','être','avoir','a','ont','ai','avais','avaient','sera','serait','peut','pourrait','doit','devrait'
            }
            stops = stop_en if (lang_code or 'en').startswith('en') else stop_fr
            keywords = [w for w in words if len(w) > 3 and w.lower() not in stops]
            if not keywords:
                keywords = words[:5]
            title_words = keywords[:5]
            title = ' '.join(title_words).strip()
            if not title:
                return None
            title = ' '.join(w[:1].upper() + w[1:] for w in title.split())
            return title
        except Exception:
            return None

    try:
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt + ("\n" + li if li else ''),
            config=generation_config
        )
        title = _extract_text_from_response(response)
        if title:
            return title.splitlines()[0].strip()
        fallback = _heuristic_title(text2, language)
        if fallback:
            return fallback
        return None
    except Exception:
        fallback = _heuristic_title(text2, language)
        if fallback:
            return fallback
        return None
