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
import io
import csv
import openpyxl
import yaml
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import tempfile
from dicttoxml import dicttoxml
from flask import Response
import sqlite3
import json
import re
from flask import Blueprint, request, jsonify, session, current_app
from google import genai
from google.genai import types
from modules.utils import get_google_api_key

from modules.translations import get_translation
from modules.webutils import project_access_required
import multiprocessing

from modules.db import (
    load_json_data, save_annotation, get_tags, create_tag, update_tag, delete_tag, delete_tags,
    delete_annotation, get_chat_history, create_note, get_notes_for_pair,
    update_note, delete_note as db_delete_note, migrate_project_db,
    get_all_notes, get_notes_count,
    get_nlp_conclusion as db_get_nlp_conclusion,
    save_nlp_conclusion as db_save_nlp_conclusion,
    get_linguistic_analysis as db_get_linguistic_analysis,
    save_linguistic_analysis as db_save_linguistic_analysis,
    create_auto_tagging_job, get_auto_tagging_job,
    load_text_pair, update_auto_tagging_job_status
)
from modules.ai_chat import (
    get_gemini_chat_response,
    generate_note_title,
    get_gemini_tag_report_chat_response,
)
from modules.gemini import generate_notes_report, generate_nlp_conclusion, generate_linguistic_analysis
from modules.gemini.ner import generate_ner_analysis
from modules.models import get_gemini_model
from modules.gemini._common import _lang_reply_instruction
from modules.web.views import ProjectDataLoader


def sanitize_filename(name):
    """
    Sanitizes a string to be used as a filename.
    - Replaces spaces with underscores.
    - Removes characters that are not alphanumeric, underscores, or hyphens.
    """
    if not name:
        return ''
    # Replace spaces and problematic characters with underscores
    name = re.sub(r'[\\/:"*?<>|\' ]+', '_', name)
    # Whitelist allowed characters (alphanumeric, underscore, hyphen, dot)
    name = re.sub(r'[^a-zA-Z0-9_.-]', '', name)
    # Avoid names that are just dots or start with a dot
    if name.startswith('.'):
        name = '_' + name[1:]
    return name

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/tags', methods=['POST'])
@project_access_required
def create_tag_route():
    data = request.get_json()
    project_name = data.get('project_name')
    name = data.get('name')
    description = data.get('description')
    parent_tag_id = data.get('parent_tag_id')
    color = data.get('color', '#000000')
    if not project_name or not name:
        return jsonify({'error': get_translation('Project name and tag name are required')}), 400
    try:
        tag = create_tag(project_name, name, description, parent_tag_id, color, current_app.config.get('DATABASE_PATH', 'databases'))
        return jsonify(tag), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': get_translation('Tag name must be unique')}), 409


@api_bp.route('/tags', methods=['GET'])
@project_access_required
def get_tags_route():
    project_name = request.args.get('project_name')
    if not project_name:
        return jsonify({'error': get_translation('Project name is required')}), 400
    tags = get_tags(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
    return jsonify(tags)


@api_bp.route('/tags/<int:tag_id>', methods=['PUT'])
@project_access_required
def update_tag_route(tag_id):
    data = request.get_json()
    project_name = data.get('project_name')
    if not project_name:
        return jsonify({'error': get_translation('Project name is required')}), 400
    update_data = {}
    if 'name' in data:
        update_data['name'] = data['name']
    if 'description' in data:
        update_data['description'] = data['description']
    if 'parent_tag_id' in data:
        update_data['parent_tag_id'] = data['parent_tag_id']
    if 'color' in data:
        update_data['color'] = data['color']
    try:
        tag = update_tag(project_name, tag_id, current_app.config.get('DATABASE_PATH', 'databases'), **update_data)
        return jsonify(tag)
    except sqlite3.IntegrityError:
        return jsonify({'error': get_translation('Tag name must be unique')}), 409


@api_bp.route('/tags/<int:tag_id>', methods=['DELETE'])
@project_access_required
def delete_tag_route(tag_id):
    project_name = request.args.get('project_name')
    if not project_name:
        return jsonify({'error': get_translation('Project name is required')}), 400
    delete_tag(project_name, tag_id, current_app.config.get('DATABASE_PATH', 'databases'))
    return jsonify({'message': get_translation('Tag deleted successfully')})


@api_bp.route('/tags/batch_delete', methods=['DELETE'])
@project_access_required
def batch_delete_tags_route():
    data = request.get_json()
    project_name = data.get('project_name')
    tag_ids = data.get('tag_ids')
    if not project_name or not tag_ids:
        return jsonify({'error': get_translation('Project name and tag IDs are required')}), 400
    try:
        delete_tags(project_name, tag_ids, current_app.config.get('DATABASE_PATH', 'databases'))
        return jsonify({'message': get_translation('Tags deleted successfully')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/annotate_text', methods=['POST'])
@project_access_required
def annotate_text_route():
    data = request.get_json()
    project_name = data.get('project_name')
    pair_id = data.get('pair_id')
    data_type = data.get('data_type')
    start_offset = data.get('start_offset')
    end_offset = data.get('end_offset')
    tag_id = data.get('tag_id')
    text = data.get('text')
    if not all([project_name, pair_id, data_type, tag_id, text]) or start_offset is None or end_offset is None:
        return jsonify({'error': get_translation('Missing required fields')}), 400
    annotation = save_annotation(project_name, pair_id, data_type, start_offset, end_offset, tag_id, text, current_app.config.get('DATABASE_PATH', 'databases'))
    project_db_name = os.path.join(current_app.config.get('DATABASE_PATH', 'databases'), f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT
            a.id, a.project_name, a.pair_id, a.data_type,
            a.start_offset, a.end_offset, a.tag_id, a.text,
            t.name as tag_name, t.color as tag_color, t.parent_tag_id
        FROM annotations a
        JOIN tags t ON a.tag_id = t.id
        WHERE a.id = ?
    ''', (annotation['id'],))
    new_annotation_details = c.fetchone()
    conn.close()
    return jsonify(dict(new_annotation_details)), 201


@api_bp.route('/notes_count', methods=['GET'])
@project_access_required
def notes_count_route():
    project_name = request.args.get('project_name')
    if not project_name:
        return jsonify({'error': 'Project name is required'}), 400
    try:
        from modules.db import get_notes_count
        count = get_notes_count(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/notes_report/<project_name>', methods=['GET'])
@project_access_required
def notes_report_route(project_name):
    """Backward-compatible endpoint used by static/tag_report.js to fetch the notes report.

    Returns a JSON object: { "report": string }
    If there are no notes with content, returns an empty string for report.
    """
    lang = session.get('language', 'en')
    try:
        notes = get_all_notes(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if not notes or not any((n.get('content') or '').strip() for n in notes):
        return jsonify({'report': ''})
    try:
        report = generate_notes_report(project_name, notes, lang=lang)
        return jsonify({'report': report or ''})
    except Exception as e:
        return jsonify({'error': f'Failed to generate notes report: {e}'}), 500


@api_bp.route('/generate_notes_report/<project_name>', methods=['GET'])
@project_access_required
def generate_notes_report_route(project_name):
    lang = session.get('language', 'en')
    try:
        notes = get_all_notes(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    if not notes or not any((n.get('content') or '').strip() for n in notes):
        return jsonify({'report': get_translation('No notes available for reporting.', lang)})
    try:
        report = generate_notes_report(project_name, notes, lang=lang)
        return jsonify({'report': report or get_translation('Failed to generate notes report.', lang)})
    except Exception as e:
        return jsonify({'error': f'Failed to generate notes report: {e}'}), 500


@api_bp.route('/nlp_summary/<project_name>', methods=['GET'])
@project_access_required
def nlp_summary_route(project_name):
    return jsonify(_compute_nlp_summary(project_name))
def _compute_nlp_summary(project_name):
    import math
    project_db_name = os.path.join(current_app.config.get('DATABASE_PATH', 'databases'), f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    def _total_tokens():
        c.execute("SELECT text_type, COUNT(*) AS n FROM tokens GROUP BY text_type")
        wrong_token_count = 0
        correct_token_count = 0
        for row in c.fetchall():
            if row['text_type'] == 'error_text':
                wrong_token_count = int(row['n'] or 0)
            elif row['text_type'] == 'corrected_text':
                correct_token_count = int(row['n'] or 0)
        return wrong_token_count, correct_token_count
    wrong_total_tokens, correct_total_tokens = _total_tokens()
    c.execute("SELECT pair_id, text_type, COUNT(*) AS n FROM tokens GROUP BY pair_id, text_type")
    per_pair_tokens = {}
    for row in c.fetchall():
        pair_id = int(row['pair_id'])
        text_type = row['text_type']
        count = int(row['n'] or 0)
        per_pair_tokens.setdefault(pair_id, {})[text_type] = count
    def _fetch_counts(table, col):
        c.execute(f"""
            SELECT {col} as label,
                   SUM(CASE WHEN text_type='error_text' THEN 1 ELSE 0 END) AS wrong,
                   SUM(CASE WHEN text_type='corrected_text' THEN 1 ELSE 0 END) AS correct
            FROM {table}
            WHERE {col} IS NOT NULL AND {col} <> 'N/A'
            GROUP BY {col}
        """)
        rows = c.fetchall()
        wrong = {}; correct = {}; delta = {}
        for row in rows:
            label = row['label']
            wrong_count = int(row['wrong'] or 0)
            correct_count = int(row['correct'] or 0)
            wrong[label] = wrong_count
            correct[label] = correct_count
            delta[label] = correct_count - wrong_count
        c.execute(f"""
            SELECT pair_id, text_type, {col} AS label, COUNT(*) AS n
            FROM {table}
            WHERE {col} IS NOT NULL AND {col} <> 'N/A'
            GROUP BY pair_id, text_type, {col}
        """)
        per_pair = {}
        for row in c.fetchall():
            pair_id = int(row['pair_id']); text_type = row['text_type']; label = row['label']; count = int(row['n'] or 0)
            per_pair.setdefault(label, {}).setdefault(pair_id, {}).setdefault(text_type, 0)
            per_pair[label][pair_id][text_type] = count
        alpha = 1.0
        entries = []
        pvals = []
        tmp = []
        for label in sorted(set(list(wrong.keys()) + list(correct.keys()))):
            freq_wrong = wrong.get(label, 0); freq_correct = correct.get(label, 0)
            rate_wrong = (freq_wrong / wrong_total_tokens * 1000.0) if wrong_total_tokens > 0 else 0.0
            rate_correct = (freq_correct / correct_total_tokens * 1000.0) if correct_total_tokens > 0 else 0.0
            delta_rate = rate_correct - rate_wrong
            total_wrong = max(wrong_total_tokens, 1); total_correct = max(correct_total_tokens, 1)
            logit_wrong = math.log((freq_wrong + alpha) / (total_wrong - freq_wrong + alpha))
            logit_correct = math.log((freq_correct + alpha) / (total_correct - freq_correct + alpha))
            log_odds = logit_correct - logit_wrong
            variance = 1.0/(freq_wrong + alpha) + 1.0/(total_wrong - freq_wrong + alpha) + 1.0/(freq_correct + alpha) + 1.0/(total_correct - freq_correct + alpha)
            z_score = log_odds / math.sqrt(variance) if variance > 0 else 0.0
            p_value = float(2.0 * 0.5 * math.erfc(abs(z_score) / math.sqrt(2.0)))
            deltas = []
            for pair_id, tokens_in_pair in per_pair_tokens.items():
                num_wrong_tokens = tokens_in_pair.get('error_text', 0)
                num_correct_tokens = tokens_in_pair.get('corrected_text', 0)
                if num_wrong_tokens <= 0 and num_correct_tokens <= 0: continue
                label_count_wrong = per_pair.get(label, {}).get(pair_id, {}).get('error_text', 0)
                label_count_correct = per_pair.get(label, {}).get(pair_id, {}).get('corrected_text', 0)
                rate_wrong_in_pair = (label_count_wrong / num_wrong_tokens * 1000.0) if num_wrong_tokens > 0 else 0.0
                rate_correct_in_pair = (label_count_correct / num_correct_tokens * 1000.0) if num_correct_tokens > 0 else 0.0
                deltas.append(rate_correct_in_pair - rate_wrong_in_pair)
            num_pairs = len(deltas)
            mean_delta_rate = sum(deltas)/num_pairs if num_pairs > 0 else 0.0
            standard_error = 0.0; ci_low = mean_delta_rate; ci_high = mean_delta_rate
            if num_pairs > 1:
                mean = mean_delta_rate
                variance_of_deltas = sum((x-mean)*(x-mean) for x in deltas)/(num_pairs-1)
                standard_error = math.sqrt(variance_of_deltas / num_pairs)
                ci_low = mean - 1.96*standard_error
                ci_high = mean + 1.96*standard_error
            tmp.append({
                'label': label, 'wrong_count': freq_wrong, 'correct_count': freq_correct,
                'wrong_rate': rate_wrong, 'correct_rate': rate_correct, 'delta_rate': delta_rate,
                'log_odds': log_odds, 'z': z_score, 'p': p_value,
                'paired': {
                    'n_pairs': num_pairs, 'mean_delta_rate': mean_delta_rate, 'se': standard_error,
                    'ci_low': ci_low, 'ci_high': ci_high
                }
            })
            pvals.append(p_value)
        mtests = len(pvals) if pvals else 1
        order = sorted(range(len(pvals)), key=lambda i: pvals[i])
        qvals = [None]*len(pvals)
        min_q = 1.0
        for rank, idx in enumerate(reversed(order), start=1):
            i = len(pvals) - rank
            pi = pvals[order[i]]
            q = pi * mtests / (i+1)
            if q < min_q: min_q = q
            qvals[order[i]] = min_q
        entries = []
        for i, entry in enumerate(tmp):
            entry['q'] = float(qvals[i]) if qvals[i] is not None else float(entry['p'])
            entries.append(entry)
        return {'totals': {'wrong_tokens': wrong_total_tokens,'correct_tokens': correct_total_tokens},'entries': entries,'simple_counts': {'wrong': wrong, 'correct': correct, 'delta': delta}}
    pos = _fetch_counts('tokens', 'tag')
    dep = _fetch_counts('tokens', 'label')
    tense = _fetch_counts('tokens', 'tense')
    number = _fetch_counts('tokens', 'number')
    ent = _fetch_counts('entities', 'type')
    edits = {'added': 0, 'deleted': 0, 'replaced': 0}
    try:
        items = load_json_data(project_name, 'diff', current_app.config.get('DATABASE_PATH', 'databases'))
        for it in items:
            op = (it.get('operation') or '').lower()
            if op == 'added': edits['added'] += 1
            elif op == 'deleted': edits['deleted'] += 1
            elif op in ('replaced', 'replacedby'): edits['replaced'] += 1
    except Exception:
        pass
    conn.close()
    return {'pos': pos, 'dep': dep, 'ent': ent, 'tense': tense, 'number': number, 'edits': edits}




@api_bp.route('/download_notes_report/<project_name>/<string:file_format>')
@project_access_required
def download_notes_report(project_name, file_format):
    lang = session.get('language', 'en')
    try:
        # Fetch the generated report from the new endpoint
        report_response = generate_notes_report_route(project_name)
        if report_response.status_code != 200:
            return report_response # Return error from generation endpoint
        report = report_response.json.get('report', '')
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve notes report: {e}'}), 500
    from html import escape
    def to_md(): return report, 'text/markdown; charset=utf-8', 'md'
    def to_txt(): return report, 'text/plain; charset=utf-8', 'txt'
    def to_html(): return f"<html><head><meta charset='utf-8'></head><body><pre>{escape(report)}</pre></body></html>", 'text/html; charset=utf-8', 'html'
    dispatch={'md':to_md,'txt':to_txt,'html':to_html}
    fn = dispatch.get(file_format.lower())
    if not fn: return jsonify({'error':'Invalid format'}), 400
    content, mimetype, ext = fn()
    sanitized_project_name = sanitize_filename(project_name)
    return Response(content, mimetype=mimetype, headers={'Content-Disposition': f'attachment; filename={sanitized_project_name}_notes_report.{ext}'})


@api_bp.route('/export_chart/<string:file_format>', methods=['POST'])
@project_access_required
def export_chart(file_format):
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'Invalid JSON payload'}), 400
    title = (data or {}).get('title') or 'chart'
    project_name = (data or {}).get('project_name') or 'project'
    labels = (data or {}).get('labels') or []
    datasets = (data or {}).get('datasets') or []
    # Dispatch exporters
    def _build_dataframe():
        import pandas as _pd
        df = _pd.DataFrame({'Label': labels})
        for ds in datasets:
            name = str(ds.get('label') or 'Series')
            vals = ds.get('data') or []
            # pad/truncate to length of labels
            if len(vals) < len(labels):
                vals = list(vals) + [None]*(len(labels)-len(vals))
            elif len(vals) > len(labels):
                vals = list(vals)[:len(labels)]
            df[name] = vals
        return df

    def to_csv():
        df = _build_dataframe()
        out = io.StringIO(); df.to_csv(out, index=False); return out.getvalue().encode('utf-8'), 'text/csv', 'csv'
    def to_excel():
        df = _build_dataframe()
        out = io.BytesIO(); wb = openpyxl.Workbook(); sh = wb.active; sh.title = str(title)[:31]
        sh.append(list(df.columns))
        for _, r in df.iterrows(): sh.append([r.get(col) for col in df.columns])
        wb.save(out); return out.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'
    def to_json():
        import json as _json
        payload = {'title': title, 'labels': labels, 'datasets': datasets}
        # Return as a generic downloadable stream to avoid client-side XHR quirks with JSON blobs
        return _json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'), 'application/octet-stream', 'json'
    def to_yaml():
        payload = {'title': title, 'labels': labels, 'datasets': datasets}
        return yaml.dump(payload, allow_unicode=True).encode('utf-8'), 'text/yaml', 'yaml'
    def to_parquet():
        df = _build_dataframe()
        out = io.BytesIO(); pq.write_table(pa.Table.from_pandas(df), out); return out.getvalue(), 'application/vnd.apache.parquet', 'parquet'
    def to_html():
        df = _build_dataframe()
        # Return UTF-8 encoded HTML table
        return df.to_html(index=False).encode('utf-8'), 'text/html; charset=utf-8', 'html'
    dispatch={'csv':to_csv,'excel':to_excel,'json':to_json,'yaml':to_yaml,'parquet':to_parquet,'html':to_html}
    fn = dispatch.get(file_format.lower())
    if not fn: return jsonify({'error':'Invalid format'}), 400
    content, mimetype, ext = fn()
    sanitized_project_name = sanitize_filename(project_name)
    fname = f"{sanitized_project_name}_{(data or {}).get('chart_id') or 'chart'}.{ext}"
    return Response(content, mimetype=mimetype, headers={'Content-Disposition': f'attachment; filename={fname}'})


@api_bp.route('/nlp_visual_report/<project_name>', methods=['GET'])
@project_access_required
def nlp_visual_report(project_name):
    lang = session.get('language', 'en')
    try:
        summary = _compute_nlp_summary(project_name)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    api_key = get_google_api_key()
    if not api_key:
        # No AI configured: return an explicit error so the UI shows a failure instead of blank
        return jsonify({'error': get_translation('AI analysis is not configured.', lang)}), 500
    try:
        client = genai.Client(api_key=api_key)
        li = _lang_reply_instruction(lang)
        # Localized section titles
        H_MAIN = get_translation('NLP Visual Report', lang)
        H_POS = get_translation('POS (per 1k rates) — Observations', lang)
        H_DEP = get_translation('Dependencies (per 1k rates) — Observations', lang)
        H_DEP_DELTA = get_translation('Dependencies Δ (Correct - Wrong) — Observations', lang)
        H_DEP_SLOPE = get_translation('Dependencies Slope (Wrong → Correct) — Observations', lang)
        H_DEP_VOLCANO = get_translation('Dependencies Volcano (effect vs reliability) — Observations', lang)
        H_ENT = get_translation('Entities (per 1k rates) — Observations', lang)
        H_TENSE = get_translation('Tense (per 1k rates) — Observations', lang)
        H_NUMBER = get_translation('Number (per 1k rates) — Observations', lang)
        H_EDITS = get_translation('Surface Edits — Observations', lang)
        H_INTERP = get_translation('Interdisciplinary Interpretation', lang)

        sys_instr = (
            get_translation('You are an expert NLP analyst.', lang) + ' ' +
            get_translation('Given project-wide summaries of POS, dependencies, entities, tense, number, and surface edits (diffs), produce a well-structured Markdown report describing what changed between wrong and corrected texts.', lang) + ' ' +
            get_translation('For each section, first provide a concise academic definition of the concept and how it is measured here; then present 3–6 clear, human-readable bullet observations with numbers (per-1k rate differences, effect size, significance) where available.', lang) + ' ' +
            get_translation('After the observations in each section, add a short Interpretation subsection (2–4 bullets) explaining what those observations likely mean, written in accessible academic prose.', lang) + ' ' +
            get_translation('Avoid jargon without definition, do not repeat the same point across sections, and do not invent data. Use a professional, academic tone.', lang) + ' ' +
            get_translation('Conclude with a multidisciplinary interpretation (e.g., discourse, psycholinguistics, sociolinguistics) that ties observations to possible explanations.', lang) + ' '
        )
        if li:
            sys_instr += ' ' + li
        prompt = (
            sys_instr + '\n\n' +
            get_translation('Project NLP Summary (JSON):', lang) + '\n' + json.dumps(summary, ensure_ascii=False) + '\n\n' +
            get_translation('Write the report in this exact outline and language:', lang) + '\n\n' +
            f"# {H_MAIN}\n\n" +
            f"## {H_POS}\n\n" +
            f"## {H_DEP}\n\n" +
            f"## {H_DEP_DELTA}\n\n" +
            f"## {H_DEP_SLOPE}\n\n" +
            f"## {H_DEP_VOLCANO}\n\n" +
            f"## {H_ENT}\n\n" +
            f"## {H_TENSE}\n\n" +
            f"## {H_NUMBER}\n\n" +
            f"## {H_EDITS}\n\n" +
            f"## {H_INTERP}\n\n"
        )
        resp = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=8192)
        )
        text = getattr(resp, 'text', '') or str(resp)
        if not text.strip():
            # Model returned empty: do not use heuristic
            return jsonify({'report': '', 'warning': get_translation('AI analysis returned an empty response.', lang)})
        return jsonify({'report': text})
    except Exception as e:
        # On any LLM error, return explicit error so UI can surface failure
        current_app.logger.error(f"Error generating NLP report with LLM: {e}")
        print(e)
        return jsonify({'error': f"Failed to generate NLP report: {str(e)}"}), 500


# Note: No heuristic report generator is used for NLP Visual Report. When the
# AI is unavailable or fails, the endpoint returns an empty report string.





@api_bp.route('/text_pairs/<project_name>', methods=['GET'])
@project_access_required
def api_text_pairs(project_name):
    try:
        from modules.db import load_text_data
        pairs = load_text_data(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
        out = [{'id': p.get('id'), 'title': p.get('title') or f"Pair {p.get('id')}"} for p in pairs]
        return jsonify({'pairs': out})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/dep_tree/<project_name>/<int:pair_id>', methods=['GET'])
@project_access_required
def api_dep_tree(project_name, pair_id):
    project_db_name = os.path.join(current_app.config.get('DATABASE_PATH', 'databases'), f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("SELECT token, position, tag, head_token, label, text_type FROM tokens WHERE pair_id=? ORDER BY position ASC", (pair_id,))
        rows = c.fetchall()
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
    conn.close()
    def build_tree(rows, text_type):
        seq = [r for r in rows if r['text_type'] == text_type]
        words = [{'text': r['token'], 'tag': r['tag']} for r in seq]
        arcs = []
        for idx, r in enumerate(seq):
            try:
                head = int(r['head_token'])
            except Exception:
                head = idx
            if head == idx:
                continue
            start = min(idx, head); end = max(idx, head)
            direction = 'left' if head > idx else 'right'
            arcs.append({'start': start, 'end': end, 'label': r['label'], 'dir': direction})
        return {'words': words, 'arcs': arcs}
    return jsonify({'wrong': build_tree(rows, 'error_text'), 'correct': build_tree(rows, 'corrected_text')})


@api_bp.route('/dep_compare/<project_name>/<int:pair_id>', methods=['GET'])
@project_access_required
def api_dep_compare(project_name, pair_id):
    # Keeping as placeholder; implement as needed or copy from app.py if extended there
    return jsonify({'status': 'not_implemented'}), 501


@api_bp.route('/annotations', methods=['GET'])
@project_access_required
def get_annotations():
    project_name = request.args.get('project_name')
    if not project_name:
        return jsonify({'error': get_translation('Project name is required')}), 400
    tag_name_filter = request.args.get('tag_name', None)
    data_type_filter = request.args.get('data_type', None)
    search_query = request.args.get('search_query', None)
    sort_by = request.args.get('sort_by', 'pair_id')
    limit = request.args.get('limit', default=100, type=int)
    offset = request.args.get('offset', default=0, type=int)
    project_db_name = os.path.join(current_app.config.get('DATABASE_PATH', 'databases'), f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = '''
        SELECT
            a.id, a.project_name, a.pair_id, a.data_type, a.start_offset, a.end_offset, a.tag_id, a.text,
            t.name as tag_name, t.description as tag_description, t.color as tag_color, t.parent_tag_id,
            c.error_text, c.corrected_text, d.diff_text
        FROM annotations a
        JOIN tags t ON a.tag_id = t.id
        LEFT JOIN csv_data c ON a.pair_id = c.id
        LEFT JOIN diff_data d ON a.pair_id = d.pair_id
        WHERE a.project_name = ?
    '''
    params = (project_name,)
    if tag_name_filter:
        query += " AND t.name LIKE ?"; params += (f'%{tag_name_filter}%',)
    if data_type_filter:
        query += " AND a.data_type = ?"; params += (data_type_filter,)
    if search_query:
        query += " AND (c.error_text LIKE ? OR c.corrected_text LIKE ?)"; params += (f'%{search_query}%', f'%{search_query}%')
    chart_filter = request.args.get('chart_filter', None)
    if chart_filter:
        query += " AND t.name = ?"; params += (chart_filter,)
    query += " LIMIT ? OFFSET ?"; params += (limit, offset)
    c.execute(query, params)
    annotations_rows = c.fetchall()
    count_query = """
        SELECT COUNT(*)
        FROM annotations a
        JOIN tags t ON a.tag_id = t.id
        LEFT JOIN csv_data c ON a.pair_id = c.id
        LEFT JOIN diff_data d ON a.pair_id = d.pair_id
        WHERE a.project_name = ?
    """
    count_params = (project_name,)
    if tag_name_filter:
        count_query += " AND t.name LIKE ?"; count_params += (f'%{tag_name_filter}%',)
    if data_type_filter:
        count_query += " AND a.data_type = ?"; count_params += (data_type_filter,)
    if search_query:
        count_query += " AND (c.error_text LIKE ? OR c.corrected_text LIKE ?)"; count_params += (f'%{search_query}%', f'%{search_query}%')
    if chart_filter:
        count_query += " AND t.name = ?"; count_params += (chart_filter,)
    c.execute(count_query, count_params)
    total_annotations = c.fetchone()[0]
    conn.close()
    annotations = [dict(row) for row in annotations_rows]
    return jsonify({'annotations': annotations, 'total': total_annotations})


@api_bp.route('/tag_report/chat', methods=['POST'])
@project_access_required
def tag_report_chat_route():
    """
    New feature: Gemini-powered chat for Tag Report exploration.

    Body JSON:
      - project_name (str) required
      - question (str) required
      - filters (dict) optional: { tag_name, data_type, search_query, sort_by }
      - use_web_search (bool) optional
      - model_name (str) optional
      - sample_limit (int) optional (default 100)
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({'error': 'Invalid JSON payload'}), 400

    project_name = data.get('project_name')
    question = (data.get('question') or '').strip()
    filters = data.get('filters') or {}
    use_web_search = bool(data.get('use_web_search') or False)
    model_name = data.get('model_name')
    sample_limit = data.get('sample_limit') or 100
    lang = session.get('language', 'en')

    if not project_name or not question:
        return jsonify({'error': get_translation('Project name and question are required', lang)}), 400

    # Build a filtered query mirroring /api/annotations but with an upper cap
    project_db_name = os.path.join(current_app.config.get('DATABASE_PATH', 'databases'), f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    base_where = ["a.project_name = ?"]
    where = list(base_where)
    params = [project_name]
    tag_name_filter = (filters.get('tag_name') or '').strip()
    data_type_filter = (filters.get('data_type') or '').strip()
    search_query = (filters.get('search_query') or '').strip()
    sort_by = (filters.get('sort_by') or 'pair_id').strip()
    chart_filter = (filters.get('chart_filter') or '').strip()

    if tag_name_filter:
        where.append("t.name LIKE ?"); params.append(f"%{tag_name_filter}%")
    if data_type_filter:
        where.append("a.data_type = ?"); params.append(data_type_filter)
    if search_query:
        where.append("(c.error_text LIKE ? OR c.corrected_text LIKE ?)"); params.extend([f"%{search_query}%", f"%{search_query}%"])
    if chart_filter:
        where.append("t.name = ?"); params.append(chart_filter)

    order_clause = "a.pair_id ASC, a.start_offset ASC" if sort_by == 'pair_id' else "a.start_offset ASC, a.pair_id ASC"

    base_query = f'''
        SELECT
            a.id, a.pair_id, a.data_type, a.text AS annotated_text,
            t.name AS tag_name, t.color AS tag_color,
            c.error_text, c.corrected_text
        FROM annotations a
        JOIN tags t ON a.tag_id = t.id
        LEFT JOIN csv_data c ON a.pair_id = c.id
        WHERE {' AND '.join(where)}
        ORDER BY {order_clause}
        LIMIT ?
    '''
    params_for_rows = list(params) + [int(sample_limit)]

    # counts
    count_total_query = f"""
        SELECT COUNT(*) AS n
        FROM annotations a
        JOIN tags t ON a.tag_id = t.id
        LEFT JOIN csv_data c ON a.pair_id = c.id
        WHERE {' AND '.join(where)}
    """
    count_by_tag_query = f"""
        SELECT t.name AS tag_name, COUNT(*) AS n
        FROM annotations a
        JOIN tags t ON a.tag_id = t.id
        LEFT JOIN csv_data c ON a.pair_id = c.id
        WHERE {' AND '.join(where)}
        GROUP BY t.name
        ORDER BY n DESC
        LIMIT 50
    """
    count_by_dtype_query = f"""
        SELECT a.data_type AS data_type, COUNT(*) AS n
        FROM annotations a
        JOIN tags t ON a.tag_id = t.id
        LEFT JOIN csv_data c ON a.pair_id = c.id
        WHERE {' AND '.join(where)}
        GROUP BY a.data_type
    """

    try:
        c.execute(base_query, params_for_rows)
        rows = [dict(r) for r in c.fetchall()]

        # Clean and truncate long fields for prompt friendliness
        import re
        from html import unescape as _html_unescape
        def strip_html(s):
            if s is None:
                return ''
            txt = str(s)
            txt = re.sub(r'<\s*br\s*/?>', '\n', txt, flags=re.I)
            txt = re.sub(r'</\s*p\s*>', '\n', txt, flags=re.I)
            txt = re.sub(r'<[^>]+>', '', txt)
            txt = _html_unescape(txt)
            txt = re.sub(r'[\t\r]+', ' ', txt)
            txt = re.sub(r'\s+\n', '\n', txt)
            return txt.strip()
        def trunc(s, n=140):
            s = (s or '').strip()
            return s if len(s) <= n else s[:n-1] + '…'
        samples = []
        for r in rows:
            samples.append({
                'pair_id': r.get('pair_id'),
                'data_type': r.get('data_type'),
                'tag_name': r.get('tag_name'),
                'annotated_text': trunc(strip_html(r.get('annotated_text'))),
                'wrong_text': trunc(strip_html(r.get('error_text'))),
                'corrected_text': trunc(strip_html(r.get('corrected_text'))),
            })

        # Stats: compute filtered and (when no filters) full totals explicitly
        c.execute(count_total_query, params)
        total_filtered = int((c.fetchone() or [0])[0])
        filters_active = any([tag_name_filter, data_type_filter, search_query, chart_filter])
        if filters_active:
            total_annotations = total_filtered
        else:
            # Count across entire project, but only annotations that still have a valid tag
            c.execute(
                f"""
                    SELECT COUNT(*) AS n
                    FROM annotations a
                    JOIN tags t ON a.tag_id = t.id
                    WHERE {' AND '.join(base_where)}
                """,
                (project_name,)
            )
            total_annotations = int((c.fetchone() or [0])[0])

        # Compute counts by tag and data type for filtered view
        c.execute(count_by_tag_query, params)
        by_tag_rows = c.fetchall()
        counts_by_tag = {r['tag_name']: int(r['n']) for r in by_tag_rows}

        c.execute(count_by_dtype_query, params)
        by_dtype_rows = c.fetchall()
        counts_by_dtype = {r['data_type']: int(r['n']) for r in by_dtype_rows}

        # If no filters are active, recompute counts across the entire project explicitly
        if not filters_active:
            c.execute(
                """
                SELECT t.name AS tag_name, COUNT(*) AS n
                FROM annotations a
                JOIN tags t ON a.tag_id = t.id
                WHERE a.project_name = ?
                GROUP BY t.name
                ORDER BY n DESC
                """,
                (project_name,)
            )
            by_tag_rows = c.fetchall()
            counts_by_tag = {r['tag_name']: int(r['n']) for r in by_tag_rows}

            c.execute(
                """
                SELECT a.data_type AS data_type, COUNT(*) AS n
                FROM annotations a
                JOIN tags t ON a.tag_id = t.id
                WHERE a.project_name = ?
                GROUP BY a.data_type
                """,
                (project_name,)
            )
            by_dtype_rows = c.fetchall()
            counts_by_dtype = {r['data_type']: int(r['n']) for r in by_dtype_rows}

        # Compute unique tags count after finalizing counts_by_tag (both cases)
        unique_tags = len(counts_by_tag)
        counts_by_tag_sum = sum(int(v) for v in counts_by_tag.values())
        counts_by_dtype_sum = sum(int(v) for v in counts_by_dtype.values())
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass

    context = {
        'filters': {
            'tag_name': tag_name_filter or None,
            'data_type': data_type_filter or None,
            'search_query': search_query or None,
            'sort_by': sort_by or None,
        },
        'stats': {
            'total_annotations': total_annotations,
            'unique_tags': unique_tags,
            'counts_by_tag': counts_by_tag,
            'counts_by_data_type': counts_by_dtype,
            'counts_by_tag_sum': counts_by_tag_sum,
            'counts_by_dtype_sum': counts_by_dtype_sum,
            'counts_complete': (not filters_active),
        },
        'samples': samples,
    }
    # Load last 3 interactions (6 messages) for short memory
    try:
        from modules.db import get_tr_chat_history, save_tr_chat_message
        prior_messages = get_tr_chat_history(project_name, limit=6, db_path=current_app.config.get('DATABASE_PATH', 'databases'))
    except Exception:
        prior_messages = []

    # Save user question to history before calling the model
    try:
        save_tr_chat_message(project_name, 'user', question, current_app.config.get('DATABASE_PATH', 'databases'))
    except Exception:
        pass

    answer = get_gemini_tag_report_chat_response(
        project_name=project_name,
        question=question,
        context=context,
        lang=lang,
        use_web_search=use_web_search,
        model_name=model_name,
        history=prior_messages,
    )

    if not answer:
        return jsonify({'error': get_translation('Failed to get response from AI', lang)}), 500
    # Save AI answer to history
    try:
        save_tr_chat_message(project_name, 'ai', answer, current_app.config.get('DATABASE_PATH', 'databases'))
    except Exception:
        pass
    return jsonify({'response': answer, 'context_summary': context['stats']})


@api_bp.route('/tag_report/chat/history', methods=['GET'])
@project_access_required
def tag_report_chat_history_route():
    project_name = request.args.get('project_name')
    limit = request.args.get('limit', type=int, default=50)
    if not project_name:
        return jsonify({'error': get_translation('Project name is required')}), 400
    from modules.db import get_tr_chat_history
    try:
        messages = get_tr_chat_history(project_name, limit=limit, db_path=current_app.config.get('DATABASE_PATH', 'databases'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'history': messages})


@api_bp.route('/annotations/<int:annotation_id>', methods=['DELETE'])
@project_access_required
def delete_annotation_route(annotation_id):
    project_name = request.args.get('project_name')
    if not project_name:
        return jsonify({'error': get_translation('Project name is required')}), 400
    delete_annotation(project_name, annotation_id, current_app.config.get('DATABASE_PATH', 'databases'))
    return jsonify({'message': get_translation('Annotation deleted successfully')})


@api_bp.route('/ai_chat', methods=['POST'])
@project_access_required
def ai_chat_route():
    data = request.get_json()
    project_name = data.get('project_name')
    question = data.get('question')
    context = data.get('context')
    pair_id = data.get('pair_id')
    use_web_search = data.get('use_web_search', False)
    model_name = data.get('model_name')
    lang = session.get('language', 'en')
    if not all([project_name, question, context, pair_id]):
        return jsonify({'error': get_translation('Missing required fields', lang)}), 400
    from modules.db import save_chat_message
    save_chat_message(project_name, pair_id, 'user', question, current_app.config.get('DATABASE_PATH', 'databases'))
    response = get_gemini_chat_response(project_name, question, context, lang, use_web_search=use_web_search, model_name=model_name)
    if response:
        save_chat_message(project_name, pair_id, 'ai', response, current_app.config.get('DATABASE_PATH', 'databases'))
        return jsonify({'response': response})
    else:
        return jsonify({'error': get_translation('Failed to get response from AI', lang)}), 500


@api_bp.route('/auto_tag/plan', methods=['POST'])
@project_access_required
def auto_tag_plan_route():
    data = request.get_json()
    project_name = data.get('project_name')
    instruction = data.get('instruction')
    wrong_text = data.get('wrong_text', '')
    correct_text = data.get('correct_text', '')
    model_name = data.get('model_name')
    lang = session.get('language', 'en')

    if not all([project_name, instruction]):
        return jsonify({'error': get_translation('Missing required fields', lang)}), 400

    api_key = get_google_api_key()
    if not api_key:
        return jsonify({'error': get_translation('GOOGLE_API_KEY is not configured', lang)}), 500

    try:
        client = genai.Client(api_key=api_key)
        
        all_tags = get_tags(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
        tag_names = [tag['name'] for tag in all_tags]

        lang_instruction = ""
        if lang == 'fr':
            lang_instruction = "IMPORTANT: Your entire response, including all keys and values in the JSON output, must be in French."

        prompt = f"""You are a sophisticated AI assistant specializing in Error Analysis, integrated within an analysis application. Your primary role is to interpret a user's request and devise an expert tagging strategy by analyzing the divergence between a "Wrong Text" and a "Corrected Text".

Your expertise is vast and multidisciplinary, spanning the full spectrum of human and social sciences. You can adopt any analytical framework—from linguistics and discourse analysis to psychology, sociology, anthropology, and beyond—as needed to satisfy the user's instruction.

Your ultimate goal is to translate the user's instruction into a concrete, machine-executable plan to create and apply new tags.

**User Instruction:** "{instruction}"

**Wrong Text:**
---
{wrong_text}
---

**Corrected Text:**
---
{correct_text}
---

**Existing Tags:** {json.dumps(tag_names)}

{lang_instruction}

**Your Task:**
1.  **Adopt the Relevant Analytical Stance:** Based on the user's instruction, determine the most appropriate analytical framework (e.g., linguistic, discursive, psychological, sociological).
2.  **Analyze the Divergence to Define Tagging Criteria:** Compare the two texts through that lens to define clear criteria for tagging.
3.  **Generate an Expert Tagging Plan:** Create a plan to automatically create and apply tags based on your analysis. The plan should be a list of "sub-plans", where each sub-plan has:
    - `tag_to_apply`: A precise and descriptive tag name that reflects your expert analysis (e.g., "Discourse:Shift-in-Focus", "Psycho:Cognitive-Dissonance-Marker", "Socio:Formality-Mismatch"). Refine any generic user suggestions into expert-level tags. These tags will be created if they don't exist.
    - `tag_description`: A detailed, clear description of what this tag represents, suitable for display in a qualitative analysis report. Explain the analytical significance of the tag.
    - `ai_instruction`: A detailed, specific instruction for a subordinate AI model that will execute this sub-plan. This instruction must clearly define the phenomenon to be identified for tagging.

**Output Format:**
Generate a single, valid JSON object with a "plans" key, which is a list of sub-plans.

**Example:**
Instruction: "tag where the corrected text sounds more professional"
Output:
{{
    "description": "I will create and apply tags to identify specific changes that increase professionalism, such as replacing colloquialisms and adjusting sentence structure.",
    "is_runnable": true,
    "plans": [
        {{
            "tag_to_apply": "Socio:Formality-Upgrade",
            "tag_description": "This tag identifies instances where informal or colloquial language in the 'Wrong Text' is replaced with more formal, professional, or standard language in the 'Corrected Text'. It is useful for analyzing changes in register and adherence to professional communication norms.",
            "ai_instruction": "Identify any word or phrase in the 'Wrong Text' that is a colloquialism or slang and has been replaced by a more formal equivalent in the 'Corrected Text'."
        }},
        {{
            "tag_to_apply": "Discourse:Sentence-Consolidation",
            "tag_description": "This tag marks instances where multiple short, simple sentences from the 'Wrong Text' are merged into a single, more complex sentence in the 'Corrected Text'. This often indicates an increase in syntactic complexity and rhetorical sophistication.",
            "ai_instruction": "Identify instances where multiple short, choppy sentences in the 'Wrong Text' are combined into a single, more complex and professional-sounding sentence in the 'Corrected Text'."
        }}
    ]
}}

Now, generate the JSON plan based on the user's instruction and the provided texts, adopting the most relevant expert perspective to create a tagging strategy.
"""

        response = client.models.generate_content(
            model=get_gemini_model(model_name),
            contents=prompt
        )

        rtext = getattr(response, 'text', None)
        clean_response = (rtext or '').strip().replace('```json', '').replace('```', '').strip()
        ai_plan = json.loads(clean_response or '{}')

        plans_list = ai_plan.get('plans') or []
        if not isinstance(plans_list, list):
            plans_list = []
        is_runnable = bool(ai_plan.get('is_runnable', False))

        # For now, we don't have a good way to estimate matches for AI-based plans.
        estimated_matches = -1  # Indicates unknown

        tag_label = ", ".join([
            (p.get('tag_to_apply') or 'Misc') for p in plans_list if isinstance(p, dict)
        ])

        plan = {
            "instruction": instruction,
            "description": ai_plan.get('description') or 'No description provided.',
            "estimated_matches": estimated_matches,
            "tag_to_apply": tag_label,
            "machine_readable_plan": {
                "criteria_type": "ai_multi",
                "plans": plans_list,
                "is_runnable": is_runnable
            },
            "model_name": model_name
        }

        return jsonify(plan)

    except Exception as e:
        return jsonify({'error': f"Failed to generate AI plan: {str(e)}"}), 500


import random

def generate_random_color():
    return f'#{random.randint(0, 0xFFFFFF):06x}'

def run_auto_tag_job(job_id, project_name, pair_id, plan, target_text, db_path, gemini_model, api_key=None):
    try:
        update_auto_tagging_job_status(project_name, job_id, 'IN_PROGRESS', None, db_path)

        # Ensure Gemini API is configured in this worker process
        client = None
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
            except Exception:
                pass
        
        if not client:
            raise Exception("Gemini API key not configured or invalid.")

        # Load the original texts and convert to lowercase to match the diff handler
        pair = load_text_pair(project_name, pair_id, db_path)
        wrong_text = pair['error_text'].lower()
        correct_text = pair['corrected_text'].lower()

        print(f"GEMINI_DEBUG: wrong_text: '{wrong_text}'")

        machine_plan = plan.get('machine_readable_plan', {})
        sub_plans = machine_plan.get('plans', [])

        all_tags = get_tags(project_name, db_path)
        tag_map = {tag['name']: tag['id'] for tag in all_tags}

        for sub_plan in sub_plans:
            tag_name = sub_plan.get('tag_to_apply')
            if tag_name and tag_name not in tag_map:
                # Assign a random color to newly created tags to make them visually distinct
                color = generate_random_color()
                tag_description = sub_plan.get('tag_description', 'Auto-created tag')
                created_tag = create_tag(project_name, tag_name, tag_description, None, color, db_path)
                tag_map[tag_name] = created_tag['id']

        annotations_created = 0
        
        if not gemini_model:
            from modules.models import get_gemini_model as _get_gemini_model
            gemini_model = _get_gemini_model()
        
        if not gemini_model:
            raise Exception("Gemini model not found")

        for sub_plan in sub_plans:
            ai_instruction = sub_plan.get('ai_instruction')
            tag_name_to_apply = sub_plan.get('tag_to_apply')
            tag_id_to_apply = tag_map.get(tag_name_to_apply)

            print(f"--- Auto-tagging for sub-plan: {tag_name_to_apply} ---")
            print(f"AI Instruction: {ai_instruction}")

            if not all([ai_instruction, tag_name_to_apply, tag_id_to_apply]):
                continue

            texts_to_process = []
            if target_text == 'wrong_text':
                texts_to_process.append(('error_text', wrong_text))
            elif target_text == 'correct_text':
                texts_to_process.append(('corrected_text', correct_text))
            else: # Default to both if not specified or 'both'
                texts_to_process.append(('error_text', wrong_text))
                texts_to_process.append(('corrected_text', correct_text))

            for data_type, text_content in texts_to_process:
                if not text_content:
                    continue

                print(f"Processing text type: {data_type}")

                # 1. Tokenize the text
                import re
                tokens = []
                for match in re.finditer(r'\w+|[^\w\s]', text_content):
                    tokens.append({
                        'text': match.group(0),
                        'start': match.start(),
                        'end': match.end(),
                        'index': len(tokens)
                    })
                
                prompt_tokens = [(token['text'], token['index']) for token in tokens]

                # 2. Create the new prompt
                prompt = f'''
                You are a precision AI assistant for linguistic analysis. Your task is to identify which tokens in a given text match a specific instruction.

                **Instruction:** "{ai_instruction}"

                **Context:**
                - **Wrong Text:** "{wrong_text}"
                - **Corrected Text:** "{correct_text}"

                **Text to Analyze (Tokenized):**
                {prompt_tokens}

                **Your Task:**
                Return a JSON object with a single key "matches". The value should be a list of lists, where each inner list contains the integer indices of the tokens that form a single match.

                **Example:**
                Instruction: "Identify any instance of subject-verb agreement error."
                Tokenized Text: [('The', 0), ('dogs', 1), ('runs', 2), ('fast', 3), ('.', 4)]
                
                Your JSON response should be:
                ```json
                {{
                  "matches": [
                    [2]
                  ]
                }}
                ```

                **Another Example (multi-token match):**
                Instruction: "Identify the phrase 'very fast'."
                Tokenized Text: [('The', 0), ('car', 1), ('is', 2), ('very', 3), ('fast', 4), ('.', 5)]

                Your JSON response should be:
                ```json
                {{
                  "matches": [
                    [3, 4]
                  ]
                }}
                ```

                **Important:**
                - Respond with only the JSON.
                - If you find no matches, return an empty list: `{{"matches": []}}`.

                Now, analyze the provided texts and generate the JSON response.
                '''
                response = client.models.generate_content(model=gemini_model, contents=prompt, config=genai.types.GenerateContentConfig(response_mime_type='application/json'))
                rtext = getattr(response, 'text', None)
                clean_response = (rtext or '').strip().replace('```json', '').replace('```', '').strip()
                
                print(f"AI Response: {clean_response}")

                matches = []
                if clean_response:
                    try:
                        parsed_response = json.loads(clean_response)
                        if isinstance(parsed_response, dict) and 'matches' in parsed_response and isinstance(parsed_response['matches'], list):
                            matches = parsed_response['matches']
                        else:
                            print(f"AI response is not in the expected format.")
                    except json.JSONDecodeError:
                        print(f"AI returned invalid JSON.")
                
                print(f"Found {len(matches)} matches.")

                for token_indices in matches:
                    if not token_indices:
                        continue
                    
                    try:
                        # 3. Map token indices back to character offsets
                        first_token_index = min(token_indices)
                        last_token_index = max(token_indices)
                        
                        start_offset = tokens[first_token_index]['start']
                        end_offset = tokens[last_token_index]['end']
                        annotated_text = text_content[start_offset:end_offset]

                        print(f"  - Saving annotation: '{annotated_text}' (start: {start_offset}, end: {end_offset}) from tokens {token_indices}")
                        
                        # 4. Save the annotation
                        save_annotation(
                            project_name=project_name,
                            pair_id=pair_id,
                            data_type=data_type,
                            start_offset=start_offset,
                            end_offset=end_offset,
                            tag_id=tag_id_to_apply,
                            text=annotated_text,
                            db_path=db_path
                        )
                        annotations_created += 1
                    except (IndexError, TypeError) as e:
                        print(f"Error processing token indices {token_indices}: {e}")

        result = {'annotations_created': annotations_created}
        if annotations_created == 0:
            status_message = "SUCCESS_NO_ANNOTATIONS"
            error_detail = "Auto-tagging completed, but no annotations were created. This might be because the AI did not find any matches based on the instruction, or the matches found were invalid."
            update_auto_tagging_job_status(project_name, job_id, status_message, {'annotations_created': 0, 'detail': error_detail}, db_path)
        else:
            update_auto_tagging_job_status(project_name, job_id, 'SUCCESS', result, db_path)
    except Exception as e:
        update_auto_tagging_job_status(project_name, job_id, 'FAILURE', {'error': str(e)}, db_path)



@api_bp.route('/auto_tag/execute', methods=['POST'])
@project_access_required
def auto_tag_execute_route():
    data = request.get_json()
    project_name = data.get('project_name')
    plan = data.get('plan')
    pair_id = data.get('pair_id')
    target_text = data.get('target_text')
    lang = session.get('language', 'en')

    if not all([project_name, plan, pair_id]):
        return jsonify({'error': get_translation('Missing required fields', lang)}), 400

    instruction = plan.get('instruction', '')
    job_id = create_auto_tagging_job(project_name, pair_id, instruction, plan, current_app.config.get('DATABASE_PATH', 'databases'))

    # Resolve model and API key with safe fallbacks
    model_name = plan.get('model_name')
    if not model_name:
        try:
            from modules.models import get_gemini_model as _get_gemini_model
            model_name = current_app.config.get('GEMINI_MODEL') or _get_gemini_model()
        except Exception:
            model_name = current_app.config.get('GEMINI_MODEL') or 'gemini-2.5-flash'
    api_key = get_google_api_key()
    if not api_key:
        return jsonify({'error': get_translation('GOOGLE_API_KEY is not configured', lang)}), 500

    p = multiprocessing.Process(
        target=run_auto_tag_job,
        args=(job_id, project_name, pair_id, plan, target_text, current_app.config.get('DATABASE_PATH', 'databases'), model_name, api_key)
    )
    p.start()

    return jsonify({'job_id': job_id, 'message': get_translation('Auto-tagging job started', lang)})



@api_bp.route('/auto_tag/status/<int:job_id>', methods=['GET'])
@project_access_required
def auto_tag_status_route(job_id):
    project_name = request.args.get('project_name')
    if not project_name:
        return jsonify({'error': get_translation('Project name is required')}), 400

    job = get_auto_tagging_job(project_name, job_id, current_app.config.get('DATABASE_PATH', 'databases'))
    if not job:
        return jsonify({'error': get_translation('Job not found')}), 404

    return jsonify(job)


@api_bp.route('/chat_history/<project_name>/<int:pair_id>', methods=['GET'])
@project_access_required
def chat_history_route(project_name, pair_id):
    history = get_chat_history(project_name, pair_id, current_app.config.get('DATABASE_PATH', 'databases'))
    return jsonify(history)


@api_bp.route('/download/<project_name>/<string:file_format>')
@project_access_required
def download_project_data(project_name, file_format):
    # Export annotations used in Tag Report (not the UI highlights from HTML JSON)
    # This mirrors the data served by /api/annotations but pulls all rows for the project.
    project_db_name = os.path.join(current_app.config.get('DATABASE_PATH', 'databases'), f'{project_name}.db')
    conn = sqlite3.connect(project_db_name)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT
            a.id, a.project_name, a.pair_id, a.data_type,
            a.start_offset, a.end_offset, a.tag_id, a.text,
            t.name as tag_name, t.description as tag_description, t.color as tag_color, t.parent_tag_id,
            c2.error_text, c2.corrected_text, d.diff_text
        FROM annotations a
        JOIN tags t ON a.tag_id = t.id
        LEFT JOIN csv_data c2 ON a.pair_id = c2.id
        LEFT JOIN diff_data d ON a.pair_id = d.pair_id
        WHERE a.project_name = ?
        ORDER BY a.pair_id ASC, a.start_offset ASC
    ''', (project_name,))
    import re
    from html import unescape as _html_unescape

    def _strip_html(s: str) -> str:
        if s is None:
            return ''
        try:
            txt = str(s)
            # normalize breaks to newlines before stripping tags
            txt = re.sub(r'<\s*br\s*/?>', '\n', txt, flags=re.I)
            txt = re.sub(r'</\s*p\s*>', '\n', txt, flags=re.I)
            # strip tags
            txt = re.sub(r'<[^>]+>', '', txt)
            # unescape entities
            txt = _html_unescape(txt)
            # collapse excessive whitespace
            txt = re.sub(r'[\t\r]+', ' ', txt)
            txt = re.sub(r'\n\s*\n+', '\n', txt)
            return txt.strip()
        except Exception:
            return str(s)

    def _clean_row(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if isinstance(v, str):
                out[k] = _strip_html(v)
            else:
                out[k] = v
        return out

    rows_raw = [dict(r) for r in c.fetchall()]
    rows = [_clean_row(r) for r in rows_raw]
    conn.close()
    df = pd.DataFrame(rows)

    # Build a human-friendly export view: rename columns and order them
    rename_map = {
        'id': 'Annotation ID',
        'pair_id': 'Pair ID',
        'data_type': 'Data Type',
        'start_offset': 'Start Offset',
        'end_offset': 'End Offset',
        'tag_id': 'Tag ID',
        'tag_name': 'Tag Name',
        'tag_description': 'Tag Description',
        'tag_color': 'Tag Color',
        'parent_tag_id': 'Parent Tag ID',
        'text': 'Annotated Text',
        'error_text': 'Wrong Text',
        'corrected_text': 'Corrected Text',
        'diff_text': 'Diff Text',
        'project_name': 'Project Name',
    }
    # Determine export columns (only include those that exist in df)
    preferred_order = [
        'Project Name','Pair ID','Annotation ID','Tag ID','Tag Name','Tag Description','Tag Color','Parent Tag ID',
        'Data Type','Start Offset','End Offset','Annotated Text','Wrong Text','Corrected Text','Diff Text',
    ]
    if not df.empty:
        df_export = df.rename(columns=rename_map)
        # Keep only columns that exist; then order them
        cols = [c for c in preferred_order if c in df_export.columns]
        # Append any other columns at the end
        other_cols = [c for c in df_export.columns if c not in cols]
        df_export = df_export[cols + other_cols]
    else:
        df_export = df.copy()

    def to_csv():
        out = io.StringIO()
        if not df_export.empty:
            df_export.to_csv(out, index=False)
        else:
            out.write('')
        return out.getvalue(), 'text/csv', 'csv'

    def to_excel():
        out = io.BytesIO()
        wb = openpyxl.Workbook(); sh = wb.active
        if not df_export.empty:
            sh.append(list(df_export.columns))
            for _, r in df_export.iterrows():
                sh.append([r.get(col) for col in df_export.columns])
        else:
            sh.append(["No data"]) 
        wb.save(out)
        return out.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'

    def to_xml():
        payload = {'project': project_name, 'annotations': df_export.to_dict(orient='records')}
        xml_bytes = dicttoxml(payload, custom_root='export', attr_type=False)
        return xml_bytes, 'text/xml', 'xml'

    def to_yaml():
        payload = {'project': project_name, 'annotations': df_export.to_dict(orient='records')}
        y = yaml.dump(payload, allow_unicode=True)
        return y, 'text/yaml', 'yaml'

    def to_parquet():
        out = io.BytesIO()
        pq.write_table(pa.Table.from_pandas(df_export if not df_export.empty else pd.DataFrame()), out)
        return out.getvalue(), 'application/vnd.apache.parquet', 'parquet'

    def to_sqlite():
        # Use a temporary file for SQLite then return its bytes
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            path = tmp.name
        try:
            conn = sqlite3.connect(path)
            (df_export if not df_export.empty else pd.DataFrame()).to_sql('annotations', conn, if_exists='replace', index=False)
            conn.close()
            with open(path, 'rb') as f:
                b = f.read()
            return b, 'application/x-sqlite3', 'db'
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

    def to_html():
        html = (df_export if not df_export.empty else pd.DataFrame()).to_html(index=False)
        return html, 'text/html', 'html'

    dispatch = {
        'csv': to_csv,
        'excel': to_excel,
        'xml': to_xml,
        'yaml': to_yaml,
        'parquet': to_parquet,
        'sqlite': to_sqlite,
        'html': to_html,
    }
    fn = dispatch.get(file_format.lower())
    if not fn:
        return jsonify({'error': 'Invalid format'}), 400
    content, mimetype, ext = fn()
    sanitized_project_name = sanitize_filename(project_name)

    return Response(
        content,
        mimetype=mimetype,
        headers={
            'Content-Disposition': f'attachment; filename={sanitized_project_name}_annotations.{ext}'
        }
    )


@api_bp.route('/notes', methods=['POST'])
@project_access_required
def create_note_route():
    data = request.get_json()
    project_name = data.get('project_name')
    pair_id = data.get('pair_id')
    title = data.get('title')
    content = data.get('content')
    lang = session.get('language', 'en')
    if not all([project_name, pair_id, title]):
        return jsonify({'error': get_translation('Missing required fields', lang)}), 400
    if title == 'AI Response':
        title = generate_note_title(project_name, content, lang)
    note = create_note(project_name, pair_id, title, content, current_app.config.get('DATABASE_PATH', 'databases'))
    return jsonify(note), 201


@api_bp.route('/notes/<project_name>/<int:pair_id>', methods=['GET'])
@project_access_required
def get_notes_route(project_name, pair_id):
    notes = get_notes_for_pair(project_name, pair_id, current_app.config.get('DATABASE_PATH', 'databases'))
    return jsonify(notes)


@api_bp.route('/notes/<int:note_id>', methods=['PUT'])
@project_access_required
def update_note_route(note_id):
    data = request.get_json()
    project_name = data.get('project_name')
    title = data.get('title')
    content = data.get('content')
    if not all([project_name, title]):
        return jsonify({'error': get_translation('Missing required fields')}), 400
    note = update_note(project_name, note_id, title, content, current_app.config.get('DATABASE_PATH', 'databases'))
    return jsonify(note)


@api_bp.route('/notes/<project_name>/<int:note_id>', methods=['DELETE'])
@project_access_required
def delete_note_route_api(project_name, note_id):
    db_delete_note(project_name, note_id, current_app.config.get('DATABASE_PATH', 'databases'))
    return jsonify({'message': get_translation('Note deleted successfully')}), 200


@api_bp.route('/nlp_conclusion/<project_name>/<int:pair_id>', methods=['GET'])
@project_access_required
def nlp_conclusion_route(project_name, pair_id):
    migrate_project_db(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
    refresh = request.args.get('refresh', default=0, type=int)
    lang = session.get('language', 'en')
    if not refresh:
        cached = db_get_nlp_conclusion(project_name, pair_id, current_app.config.get('DATABASE_PATH', 'databases'))
        if cached:
            return jsonify(cached)
    result = generate_nlp_conclusion(project_name, pair_id, lang)
    if not result:
        return jsonify({'error': get_translation('Failed to generate NLP conclusion', lang)}), 500
    try:
        db_save_nlp_conclusion(project_name, pair_id, result.get('conclusion', ''), result.get('inconsistencies', []), current_app.config.get('DATABASE_PATH', 'databases'))
    except Exception:
        pass
    return jsonify(result)


@api_bp.route('/linguistic_analysis/<project_name>/<int:pair_id>', methods=['GET'])
@project_access_required
def linguistic_analysis_route(project_name, pair_id):
    migrate_project_db(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
    refresh = request.args.get('refresh', default=0, type=int)
    ai = request.args.get('ai', default=1, type=int)
    debug = request.args.get('debug', default=0, type=int)
    lang = session.get('language', 'en')
    if not refresh:
        cached = db_get_linguistic_analysis(project_name, pair_id, current_app.config.get('DATABASE_PATH', 'databases'))
        if cached:
            try:
                cached_lang = (cached.get('response') or {}).get('lang')
            except Exception:
                cached_lang = None
            cur = (str(lang) or 'en').lower()
            if cached_lang and str(cached_lang).lower().startswith(cur[:2]):
                return jsonify(cached)
    try:
        result = generate_linguistic_analysis(project_name, pair_id, use_ai=bool(ai), debug=bool(debug), lang=lang)
        if not result:
            return jsonify({'error': get_translation('Failed to generate linguistic analysis', lang)}), 500
        db_save_linguistic_analysis(project_name, pair_id, result, current_app.config.get('DATABASE_PATH', 'databases'))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/ner_analysis/<project_name>/<int:pair_id>', methods=['GET'])
@project_access_required
def ner_analysis_route(project_name, pair_id):
    migrate_project_db(project_name, current_app.config.get('DATABASE_PATH', 'databases'))
    lang = session.get('language', 'en')
    try:
        result = generate_ner_analysis(project_name, pair_id, lang=lang)
        if not result:
            return jsonify({'error': get_translation('Failed to generate NER analysis', lang)}), 500
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
