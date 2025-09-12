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
from pprint import pformat

from google import genai
from flask import current_app

from ..db import load_text_data, get_project_file, load_nlp_dataframe, load_json_data
from ..translations import get_translation
from ..models import get_gemini_model
from ._common import _lang_reply_instruction
from ._summaries import summarize_tokens, summarize_entities
from .topics import generate_topics_analysis
from .coherence import generate_coherence_analysis
from .morphology import generate_qualitative_morphology_analysis
from .ner import generate_qualitative_ner_analysis


def _diff_counts(a: dict, b: dict):
    out = {}
    keys = set((a or {}).keys()) | set((b or {}).keys())
    for k in keys:
        out[k] = int((b or {}).get(k, 0)) - int((a or {}).get(k, 0))
    return out


def generate_linguistic_analysis(project_name, pair_id, use_ai=None, **kwargs):
    debug = bool(kwargs.get('debug', False))
    lang = kwargs.get('lang', 'en')
    debug_log = []

    def _dbg(msg):
        try:
            s = str(msg)
        except Exception:
            s = repr(msg)
        if debug:
            print(s)
            try:
                debug_log.append(s)
            except Exception:
                pass

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
    tokens_df = load_nlp_dataframe(project_name, 'tokens', current_app.config['DATABASE_PATH'], condition=cond)
    entities_df = load_nlp_dataframe(project_name, 'entities', current_app.config['DATABASE_PATH'], condition=cond)

    try:
        diff_items_all = load_json_data(project_name, 'diff', current_app.config['DATABASE_PATH'])
        diff_items = [it for it in diff_items_all if int(it.get('pair_id', -1)) == int(pair_id)]
    except Exception:
        diff_items = []

    try:
        t_wrong = tokens_df[tokens_df['text_type'] == 'error_text'] if tokens_df is not None and not tokens_df.empty else tokens_df
        t_corr = tokens_df[tokens_df['text_type'] == 'corrected_text'] if tokens_df is not None and not tokens_df.empty else tokens_df
    except Exception:
        t_wrong = tokens_df
        t_corr = tokens_df
    try:
        e_wrong = entities_df[entities_df['text_type'] == 'error_text'] if entities_df is not None and not entities_df.empty else entities_df
        e_corr = entities_df[entities_df['text_type'] == 'corrected_text'] if entities_df is not None and not entities_df.empty else entities_df
    except Exception:
        e_wrong = entities_df
        e_corr = entities_df

    def _extract_dep_tree(df):
        if df is None or df.empty:
            return {'words': [], 'arcs': []}
        df_sorted = df.sort_values(by='position').reset_index(drop=True)
        words = []
        for _, row in df_sorted.iterrows():
            words.append({'text': row['token'], 'tag': row['tag']})
        arcs = []
        for index, row in df_sorted.iterrows():
            head_index = int(row['head_token'])
            if head_index != index:
                direction = 'left' if head_index > index else 'right'
                arcs.append({
                    'start': min(index, head_index),
                    'end': max(index, head_index),
                    'label': row['label'],
                    'dir': direction
                })
        return {'words': words, 'arcs': arcs}

    dep_tree_wrong = _extract_dep_tree(t_wrong)
    dep_tree_corr = _extract_dep_tree(t_corr)

    def _extract_morph_analysis(df):
        if df is None or df.empty:
            return []
        df_sorted = df.sort_values(by='position').reset_index(drop=True)
        morph_data = []
        for _, row in df_sorted.iterrows():
            features = {
                'token': row['token'],
                'lemma': row['lemma'],
                'pos': row['tag'],
                'tense': row.get('tense', 'N/A'),
                'number': row.get('number', 'N/A'),
                'person': row.get('person', 'N/A'),
                'mood': row.get('mood', 'N/A'),
                'voice': row.get('voice', 'N/A'),
                'case': row.get('case', 'N/A'),
                'gender': row.get('gender', 'N/A'),
            }
            features_filtered = {k: v for k, v in features.items() if v != 'N/A' and v is not None}
            morph_data.append(features_filtered)
        return morph_data

    morph_analysis_wrong = _extract_morph_analysis(t_wrong)
    morph_analysis_corr = _extract_morph_analysis(t_corr)

    qualitative_morphology = generate_qualitative_morphology_analysis(project_name, wrong_text, corrected_text, language, lang)

    s_wrong = {'tokens': summarize_tokens(t_wrong), 'entities': summarize_entities(e_wrong)}
    s_corr = {'tokens': summarize_tokens(t_corr), 'entities': summarize_entities(e_corr)}

    pos_delta = _diff_counts(s_wrong['tokens'].get('pos_counts', {}), s_corr['tokens'].get('pos_counts', {}))
    dep_delta = _diff_counts(s_wrong['tokens'].get('dependency_counts', {}), s_corr['tokens'].get('dependency_counts', {}))
    ent_delta = _diff_counts(s_wrong['entities'].get('type_counts', {}), s_corr['entities'].get('type_counts', {}))
    tense_delta = _diff_counts(s_wrong['tokens'].get('tense_counts', {}), s_corr['tokens'].get('tense_counts', {}))
    number_delta = _diff_counts(s_wrong['tokens'].get('number_counts', {}), s_corr['tokens'].get('number_counts', {}))

    surface_edit_counts = {}
    try:
        replaced_tokens = 0
        added_tokens = 0
        deleted_tokens = 0
        for it in diff_items:
            op = it.get('operation')
            text = (it.get('element') or '').strip()
            tcount = len([t for t in text.split() if t])
            if op == 'replaced':
                replaced_tokens += tcount
            elif op == 'replacedby':
                replaced_tokens += tcount
            elif op == 'added':
                added_tokens += tcount
            elif op == 'deleted':
                deleted_tokens += tcount
        surface_edit_counts = {
            'replaced_tokens': int(replaced_tokens),
            'added_tokens': int(added_tokens),
            'deleted_tokens': int(deleted_tokens),
        }
    except Exception:
        surface_edit_counts = {}

    try:
        if not surface_edit_counts or (
            surface_edit_counts.get('replaced_tokens', 0) == 0 and
            surface_edit_counts.get('added_tokens', 0) == 0 and
            surface_edit_counts.get('deleted_tokens', 0) == 0
        ):
            import re, difflib
            def _tok(s):
                return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+", s or '')
            wt = _tok(wrong_text)
            ct = _tok(corrected_text)
            sm = difflib.SequenceMatcher(None, wt, ct)
            rep = add = dele = 0
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'replace':
                    rep += max(i2 - i1, j2 - j1)
                elif tag == 'insert':
                    add += (j2 - j1)
                elif tag == 'delete':
                    dele += (i2 - i1)
            surface_edit_counts = {
                'replaced_tokens': rep,
                'added_tokens': add,
                'deleted_tokens': dele,
            }
    except Exception:
        pass

    categories = []
    layers = []
    findings_morph = []
    wc = s_wrong['tokens']
    cc = s_corr['tokens']
    if wc.get('tense_counts') or cc.get('tense_counts'):
        for tense in set((wc.get('tense_counts') or {}).keys()) | set((cc.get('tense_counts') or {}).keys()):
            wv = int((wc.get('tense_counts') or {}).get(tense, 0))
            cv = int((cc.get('tense_counts') or {}).get(tense, 0))
            if wv != cv:
                direction = get_translation('reduced', lang) if cv < wv else get_translation('increased', lang)
                tense_h = get_translation(str(tense).upper(), lang)
                findings_morph.append({
                    'label': get_translation('Tense usage: {tense}', lang).format(tense=tense_h),
                    'explanation': get_translation('{tense} tense {direction} from {wv} to {cv} in correction.', lang).format(
                        tense=tense_h, direction=direction, wv=wv, cv=cv
                    )
                })
    if wc.get('number_counts') or cc.get('number_counts'):
        for num in set((wc.get('number_counts') or {}).keys()) | set((cc.get('number_counts') or {}).keys()):
            wv = int((wc.get('number_counts') or {}).get(num, 0))
            cv = int((cc.get('number_counts') or {}).get(num, 0))
            if wv != cv:
                direction = get_translation('reduced', lang) if cv < wv else get_translation('increased', lang)
                num_h = get_translation(str(num).upper(), lang)
                findings_morph.append({
                    'label': get_translation('Number: {num}', lang).format(num=num_h),
                    'explanation': get_translation('{num} marking {direction} from {wv} to {cv}.', lang).format(
                        num=num_h, direction=direction, wv=wv, cv=cv
                    )
                })
    if findings_morph:
        cat_morph = {'name': get_translation('Morphology', lang), 'findings': findings_morph}
        categories.append(cat_morph)
        layers.append({'name': get_translation('Micro-linguistics', lang), 'categories': [cat_morph]})

    if dep_delta:
        def _dep_human(x):
            s = str(x)
            m = {
                'NSUBJPASS': get_translation('Nominal subject (passive)', lang),
                'NSUBJ': get_translation('Nominal subject', lang),
                'CSUBJ': get_translation('Clausal subject', lang),
                'DOBJ': get_translation('Direct object', lang),
                'IOBJ': get_translation('Indirect object', lang),
                'POBJ': get_translation('Object of preposition', lang),
                'AUXPASS': get_translation('Passive auxiliary', lang),
                'AMOD': get_translation('Adjectival modifier', lang),
                'ADVMOD': get_translation('Adverbial modifier', lang),
                'NMOD': get_translation('Nominal modifier', lang),
                'CC': get_translation('Coordinating conjunction', lang),
                'CONJ': get_translation('Conjunct', lang),
                'AUX': get_translation('Auxiliary', lang),
                'ROOT': get_translation('Root', lang),
            }
            return m.get(s.upper(), s)

        top_dep = sorted(dep_delta.items(), key=lambda kv: -abs(kv[1]))[:5]
        if top_dep:
            findings_dep = []
            for lab, d in top_dep:
                lab_h = _dep_human(lab)
                findings_dep.append({
                    'label': get_translation('Dependency change: {label}', lang).format(label=lab_h),
                    'explanation': get_translation('Change by {d:+d} occurrences between wrong and corrected.', lang).format(d=d)
                })
            cat_syntax = {'name': get_translation('Syntax (dependencies)', lang), 'findings': findings_dep}
            categories.append(cat_syntax)
            layers.append({'name': get_translation('Syntax', lang), 'categories': [cat_syntax]})

    def _avg_dep_distance(df):
        try:
            if df is None or df.empty:
                return 0.0
            df2 = df.dropna(subset=['position', 'head_token']).copy()
            if df2.empty:
                return 0.0
            return float((df2['position'].astype(int) - df2['head_token'].astype(int)).abs().mean())
        except Exception:
            return 0.0

    if t_wrong is not None and t_corr is not None and not (t_wrong is tokens_df is None):
        avg_w = _avg_dep_distance(t_wrong)
        avg_c = _avg_dep_distance(t_corr)
        if avg_w and avg_c and abs(avg_w - avg_c) > 0.1:
            layers.append({'name': get_translation('Cognitive Proxies', lang), 'categories': [{
                'name': get_translation('Processing Difficulty', lang),
                'findings': [{
                    'label': get_translation('Dependency distance', lang),
                    'explanation': get_translation('Average dependency distance changed from {avg_w:.2f} to {avg_c:.2f}.', lang).format(avg_w=avg_w, avg_c=avg_c)
                }]
            }]})

    hedges = {'maybe','perhaps','seems','appears','apparently','likely','possibly'}
    modals = {'must','should','can','could','may','might','have to'}
    pronouns = {'i','we','you','he','she','they'}
    def _count_set(df, vocab):
        try:
            return int(df['token'].fillna('').astype(str).str.lower().isin(vocab).sum())
        except Exception:
            return 0
    p_findings = []
    if t_wrong is not None and t_corr is not None:
        hedge_delta = _count_set(t_corr, hedges) - _count_set(t_wrong, hedges)
        modal_delta = _count_set(t_corr, modals) - _count_set(t_wrong, modals)
        pron_delta = _count_set(t_corr, pronouns) - _count_set(t_wrong, pronouns)
        if hedge_delta:
            p_findings.append({'label': get_translation('Hedging', lang), 'explanation': get_translation('Hedging markers changed by {hedge_delta:+d}.', lang).format(hedge_delta=hedge_delta)})
        if modal_delta:
            p_findings.append({'label': get_translation('Modality', lang), 'explanation': get_translation('Modals changed by {modal_delta:+d}.', lang).format(modal_delta=modal_delta)})
        if pron_delta:
            p_findings.append({'label': get_translation('Pronouns', lang), 'explanation': get_translation('Personal pronoun usage changed by {pron_delta:+d}.', lang).format(pron_delta=pron_delta)})
    if p_findings:
        layers.append({'name': get_translation('Psychology/Sociology/Anthropology', lang), 'categories': [{'name': get_translation('Register & Stance', lang), 'findings': p_findings}]})

    topics_analysis = generate_topics_analysis(project_name, wrong_text, corrected_text, language, lang)
    cohesion_divergence = generate_coherence_analysis(project_name, wrong_text, corrected_text, language, lang)

    patterns = []
    if (pos_delta.get('PUNCT', 0) or 0) < 0:
        patterns.append(get_translation('Punctuation regularization in corrected text.', lang))
    if (pos_delta.get('DET', 0) or 0) < 0:
        patterns.append(get_translation('Determiner use tightened in correction (articles adjusted).', lang))
    if (pos_delta.get('VERB', 0) or 0) != 0 and (wc.get('tense_counts') or cc.get('tense_counts')):
        patterns.append(get_translation('Verb system adjusted (tense/aspect distribution shifted).', lang))

    evidence = []
    try:
        by_pos = {}
        for it in diff_items:
            pos = int(it.get('position_in_diff', -1))
            by_pos.setdefault(pos, []).append(it)
        for pos, items in by_pos.items():
            ops = {it.get('operation'): it for it in items}
            rep = ops.get('replaced')
            repby = ops.get('replacedby')
            if rep and repby:
                wrong_text_seg = (rep.get('element') or '').strip()
                correct_text_seg = (repby.get('element') or '').strip()
                if wrong_text_seg or correct_text_seg:
                    evidence.append({
                        'label': get_translation('Replacement', lang),
                        'wrong_tokens': ([{'token': wrong_text_seg}] if wrong_text_seg else []),
                        'correct_tokens': ([{'token': correct_text_seg}] if correct_text_seg else []),
                    })
            else:
                add = ops.get('added')
                dele = ops.get('deleted')
                if add:
                    seg = (add.get('element') or '').strip()
                    if seg:
                        evidence.append({
                            'label': get_translation('Addition', lang),
                            'wrong_tokens': [],
                            'correct_tokens': [{'token': seg}],
                        })
                if dele:
                    seg = (dele.get('element') or '').strip()
                    if seg:
                        evidence.append({
                            'label': get_translation('Deletion', lang),
                            'wrong_tokens': [{'token': seg}],
                            'correct_tokens': [],
                        })
    except Exception:
        pass

    if pos_delta:
        top = sorted(pos_delta.items(), key=lambda x: -abs(x[1]))[:3]
        for tag, delta in top:
            try:
                wrong_samples = []
                correct_samples = []
                if t_wrong is not None and not t_wrong.empty:
                    wrong_samples = list(t_wrong[t_wrong['tag'] == tag]['token'].astype(str).head(5).unique())
                if t_corr is not None and not t_corr.empty:
                    correct_samples = list(t_corr[t_corr['tag'] == tag]['token'].astype(str).head(5).unique())
                pos_name = {
                    'ADJ': get_translation('Adjective', lang),
                    'ADP': get_translation('Adposition', lang),
                    'ADV': get_translation('Adverb', lang),
                    'AUX': get_translation('Auxiliary', lang),
                    'CCONJ': get_translation('Coordinating conjunction', lang),
                    'DET': get_translation('Determiner', lang),
                    'INTJ': get_translation('Interjection', lang),
                    'NOUN': get_translation('Noun', lang),
                    'NUM': get_translation('Numeral', lang),
                    'PART': get_translation('Particle', lang),
                    'PRON': get_translation('Pronoun', lang),
                    'PROPN': get_translation('Proper noun', lang),
                    'PUNCT': get_translation('Punctuation', lang),
                    'SCONJ': get_translation('Subordinating conjunction', lang),
                    'SYM': get_translation('Symbol', lang),
                    'VERB': get_translation('Verb', lang),
                    'X': get_translation('Other', lang)
                }
                human = pos_name.get(str(tag).upper(), str(tag))
                evidence.append({
                    'label': get_translation('POS shift: {tag} ({human}) ({delta:+d})', lang).format(tag=tag, human=human, delta=delta),
                    'wrong_tokens': [{'token': x} for x in wrong_samples],
                    'correct_tokens': [{'token': x} for x in correct_samples]
                })
            except Exception:
                pass

    observations = []
    if pos_delta:
        tag, d = max(pos_delta.items(), key=lambda kv: abs(kv[1]))
        try:
            pos_map = {
                'ADJ': get_translation('Adjective', lang),
                'ADP': get_translation('Adposition', lang),
                'ADV': get_translation('Adverb', lang),
                'AUX': get_translation('Auxiliary', lang),
                'CCONJ': get_translation('Coordinating conjunction', lang),
                'DET': get_translation('Determiner', lang),
                'INTJ': get_translation('Interjection', lang),
                'NOUN': get_translation('Noun', lang),
                'NUM': get_translation('Numeral', lang),
                'PART': get_translation('Particle', lang),
                'PRON': get_translation('Pronoun', lang),
                'PROPN': get_translation('Proper noun', lang),
                'PUNCT': get_translation('Punctuation', lang),
                'SCONJ': get_translation('Subordinating conjunction', lang),
                'SYM': get_translation('Symbol', lang),
                'VERB': get_translation('Verb', lang),
                'X': get_translation('Other', lang)
            }
            human = pos_map.get(str(tag).upper(), str(tag))
            observations.append(get_translation('Most prominent POS change: {tag} ({human}) ({d:+d}).', lang).format(tag=tag, human=human, d=d))
        except Exception:
            observations.append(get_translation('Most prominent POS change: {tag} ({d:+d}).', lang).format(tag=tag, d=d))
    if dep_delta:
        lab, d = max(dep_delta.items(), key=lambda kv: abs(kv[1]))
        try:
            def _dep_human_for_obs(x):
                s = str(x)
                m = {
                    'NSUBJPASS': get_translation('Nominal subject (passive)', lang),
                    'NSUBJ': get_translation('Nominal subject', lang),
                    'CSUBJ': get_translation('Clausal subject', lang),
                    'DOBJ': get_translation('Direct object', lang),
                    'IOBJ': get_translation('Indirect object', lang),
                    'POBJ': get_translation('Object of preposition', lang),
                    'AUXPASS': get_translation('Passive auxiliary', lang),
                    'AMOD': get_translation('Adjectival modifier', lang),
                    'ADVMOD': get_translation('Adverbial modifier', lang),
                    'NMOD': get_translation('Nominal modifier', lang),
                    'CC': get_translation('Coordinating conjunction', lang),
                    'CONJ': get_translation('Conjunct', lang),
                    'AUX': get_translation('Auxiliary', lang),
                    'ROOT': get_translation('Root', lang),
                }
                return m.get(s.upper(), s)
            human = _dep_human_for_obs(lab)
            observations.append(get_translation('Key dependency change: {lab} ({human}) ({d:+d}).', lang).format(lab=lab, human=human, d=d))
        except Exception:
            observations.append(get_translation('Key dependency change: {lab} ({d:+d}).', lang).format(lab=lab, d=d))

    # Bundle NER data inside the same response so the frontend can render the NER tab from the cached analysis
    try:
        if entities_df is not None:
            ner_wrong = e_wrong.to_dict(orient='records') if (e_wrong is not None and not e_wrong.empty) else []
            ner_correct = e_corr.to_dict(orient='records') if (e_corr is not None and not e_corr.empty) else []
        else:
            ner_wrong = []
            ner_correct = []
    except Exception:
        ner_wrong = []
        ner_correct = []

    # Qualitative NER analysis (LLM). Mirrors morphology pattern: the function handles missing API keys gracefully.
    try:
        qualitative_ner = generate_qualitative_ner_analysis(project_name, wrong_text, corrected_text, language, lang)
    except Exception:
        qualitative_ner = None

    base_response = {
        'categories': categories,
        'layers': layers,
        'global_patterns': patterns,
        # Keep existing keys for internal use/debugging
        'topics_analysis': topics_analysis,
        'cohesion_divergence': cohesion_divergence,
        'qualitative_morphology': qualitative_morphology,
        'dep_trees': {'wrong': dep_tree_wrong, 'correct': dep_tree_corr},
        'morphology': {'wrong': morph_analysis_wrong, 'correct': morph_analysis_corr},
        # Provide legacy/expected keys for front-end tabs
        'dependency_trees': {'wrong': dep_tree_wrong, 'correct': dep_tree_corr},
        'morphology_analysis': {
            'wrong': morph_analysis_wrong,
            'correct': morph_analysis_corr,
            'qualitative_analysis': qualitative_morphology,
        },
        'topics': topics_analysis,
        'cohesion_analysis': cohesion_divergence,
        'ner_analysis': {
            'wrong': ner_wrong,
            'correct': ner_correct,
            'qualitative_analysis': qualitative_ner,
        },
        'summary_delta': {
            'pos_counts_diff': pos_delta,
            'dependency_counts_diff': dep_delta,
            'entity_type_diff': ent_delta,
            'tense_counts_diff': tense_delta,
            'number_counts_diff': number_delta,
            'surface_edit_counts': surface_edit_counts,
        },
        'evidence': evidence,
        'observations': observations,
        'lang': lang,
    }

    # Build overview notes to enrich the Overview tab (observations, interpretations, limitations)
    try:
        notes_obs = list(observations or [])
    except Exception:
        notes_obs = []
    notes_interps = []
    try:
        ta = topics_analysis or {}
        if isinstance(ta, dict) and ta.get('interpretation'):
            notes_interps.append(str(ta.get('interpretation')))
    except Exception:
        pass
    try:
        ca = cohesion_divergence or {}
        if isinstance(ca, dict) and ca.get('interpretation'):
            notes_interps.append(str(ca.get('interpretation')))
    except Exception:
        pass
    try:
        qm = qualitative_morphology or {}
        if isinstance(qm, dict) and qm.get('interpretation'):
            notes_interps.append(str(qm.get('interpretation')))
    except Exception:
        pass
    # Limitations: conservative defaults + language hint
    notes_limits = []
    try:
        notes_limits.append(get_translation('Heuristic counts and deltas are based on Google NLP outputs and may contain tagging errors.', lang))
        notes_limits.append(get_translation('LLM-enriched summaries are approximations and should be cross-checked against primary evidence (tokens, dependencies, entities).', lang))
        if (lang or '').lower().startswith('fr'):
            pass
    except Exception:
        pass
    base_response['notes'] = {
        'observations': notes_obs,
        'interpretations': notes_interps,
        'limitations': notes_limits,
    }

    api_key = None
    try:
        from ..utils import get_google_api_key as _get_google_api_key
        api_key = _get_google_api_key()
    except Exception:
        api_key = None
    if api_key and (use_ai is True or (use_ai is None)):
        try:
            client = genai.Client(api_key=api_key)
            parts = []
            parts.append(get_translation('You are given several data structures derived from Google Cloud NLP processing of two texts: a wrong (learner) text and its corrected version.', lang))
            parts.append(get_translation('The data includes counts for parts of speech, morphological features, dependencies, entity types, and token-level diffs.', lang))
            parts.append(get_translation('Your task is to produce a refined, coherent analysis in JSON under the key "response" with fields:', lang))
            parts.append('{"categories":[{"name":string,"findings":[{"label":string,"explanation":string}]}],"global_patterns":[string],"evidence":[{"label":string,"wrong_tokens":[{"token":string}],"correct_tokens":[{"token":string}]}],"observations":[string]}')
            parts.append('\n\n')
            parts.append(get_translation('CONTEXT:', lang))
            parts.append(f"\nLANG={lang}\n")
            def _json(x):
                try:
                    return json.dumps(x, ensure_ascii=False)
                except Exception:
                    return str(x)
            parts.append('SUMMARY_WRONG:\n' + _json(s_wrong) + '\n\n')
            parts.append('SUMMARY_CORRECT:\n' + _json(s_corr) + '\n\n')
            def _pos_human_key(k):
                m = {
                    'ADJ': get_translation('Adjective', lang),
                    'ADP': get_translation('Adposition', lang),
                    'ADV': get_translation('Adverb', lang),
                    'AUX': get_translation('Auxiliary', lang),
                    'CCONJ': get_translation('Coordinating conjunction', lang),
                    'DET': get_translation('Determiner', lang),
                    'INTJ': get_translation('Interjection', lang),
                    'NOUN': get_translation('Noun', lang),
                    'NUM': get_translation('Numeral', lang),
                    'PART': get_translation('Particle', lang),
                    'PRON': get_translation('Pronoun', lang),
                    'PROPN': get_translation('Proper noun', lang),
                    'PUNCT': get_translation('Punctuation', lang),
                    'SCONJ': get_translation('Subordinating conjunction', lang),
                    'SYM': get_translation('Symbol', lang),
                    'VERB': get_translation('Verb', lang),
                    'X': get_translation('Other', lang)
                }
                s = str(k).upper()
                return m.get(s, s)
            def _dep_human_key(k):
                s = str(k).upper()
                return s
            def _ent_human_key(k):
                s = str(k).upper()
                return s
            human_pos_delta = { _pos_human_key(k): v for k, v in (pos_delta or {}).items() }
            human_dep_delta = { _dep_human_key(k): v for k, v in (dep_delta or {}).items() }
            human_ent_delta = { _ent_human_key(k): v for k, v in (ent_delta or {}).items() }

            parts.append('DELTA:\n')
            parts.append(_json({
                'pos_counts_diff': human_pos_delta,
                'dependency_counts_diff': human_dep_delta,
                'entity_type_diff': human_ent_delta,
            }, ensure_ascii=False))
            parts.append('\n\n')
            base_for_llm = dict(base_response)
            try:
                sd = dict(base_for_llm.get('summary_delta') or {})
                sd['pos_counts_diff'] = human_pos_delta
                sd['dependency_counts_diff'] = human_dep_delta
                sd['entity_type_diff'] = human_ent_delta
                base_for_llm['summary_delta'] = sd
            except Exception:
                pass
            parts.append(get_translation('CURRENT_BASE_ANALYSIS:', lang))
            parts.append(f"\n{base_for_llm}\n")
            prompt = ''.join(parts)
            sys_instr2 = get_translation(
                'You are an expert linguist and discourse analyst with interdisciplinary lenses (semiotics, psychology, sociology, anthropology, philosophy, cognitive science).',
                lang
            )
            li2 = _lang_reply_instruction(lang)
            if li2:
                sys_instr2 = sys_instr2 + ' ' + li2
            if lang == 'fr':
                sys_instr2 = sys_instr2 + ' Your response must be in French.'
            llm_resp = client.models.generate_content(
                model=get_gemini_model(),
                contents=prompt,
                system_instruction=sys_instr2,
                config=genai.types.GenerateContentConfig(response_mime_type='application/json'),
            )
            raw = ''
            try:
                raw = getattr(llm_resp, 'text', '') or str(llm_resp)
            except Exception:
                raw = ''
            enriched = None
            if raw:
                try:
                    parsed = json.loads(raw)
                    enriched = parsed.get('response', parsed) if isinstance(parsed, dict) else None
                except Exception:
                    import re
                    m = re.search(r'(\{\s*"response"[\s\S]*\})', raw)
                    if m:
                        try:
                            sub = json.loads(m.group(1))
                            enriched = sub.get('response', sub)
                        except Exception:
                            enriched = None
            if isinstance(enriched, dict):
                merged = base_response.copy()
                for k, v in enriched.items():
                    merged[k] = v
                merged['summary_delta'] = base_response.get('summary_delta', {})
                if not enriched.get('evidence'):
                    merged['evidence'] = base_response.get('evidence', [])
                merged['lang'] = base_response.get('lang', lang)
                return {'response': merged}
        except Exception:
            pass
    # include debug log if enabled
    if debug and debug_log:
        try:
            base_response['debug_log'] = list(debug_log)
        except Exception:
            pass
    return {'response': base_response}
