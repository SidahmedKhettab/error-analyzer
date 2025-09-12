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

import pandas as pd


def summarize_tokens(df):
    if df is None or df.empty:
        return {}

    def vc(col, top=None):
        try:
            s = df[col].replace(['N/A', None, ''], pd.NA).dropna().astype(str)
            counts = s.value_counts()
            if top:
                counts = counts.head(top)
            return counts.to_dict()
        except Exception:
            return {}

    return {
        'pos_counts': vc('tag', top=15),
        'tense_counts': vc('tense', top=10),
        'number_counts': vc('number', top=10),
        'mood_counts': vc('mood', top=10),
        'voice_counts': vc('voice', top=10),
        'dependency_counts': vc('label', top=15),
    }


def summarize_entities(df):
    if df is None or df.empty:
        return {}
    try:
        s = df['type'].replace(['N/A', None, ''], pd.NA).dropna().astype(str)
        type_counts = s.value_counts().to_dict()
    except Exception:
        type_counts = {}
    try:
        s2 = df['common_or_proper'].replace(['N/A', None, ''], pd.NA).dropna().astype(str)
        properness = s2.value_counts().to_dict()
    except Exception:
        properness = {}
    top_examples = []
    try:
        for _, row in df.head(10).iterrows():
            top_examples.append({
                'name': row.get('name'),
                'type': row.get('type'),
                'content': row.get('content')
            })
    except Exception:
        pass
    return {
        'type_counts': type_counts,
        'properness': properness,
        'examples': top_examples,
    }

