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

from ._common import _lang_reply_instruction
from .genre import get_genre_and_main_idea
from .title import generate_pair_title
from .nlp_conclusion import generate_nlp_conclusion
from .coherence import generate_coherence_analysis
from .topics import generate_topics_analysis
from .morphology import generate_qualitative_morphology_analysis
from .linguistic import generate_linguistic_analysis
from .notes import generate_notes_report

__all__ = [
    "_lang_reply_instruction",
    "get_genre_and_main_idea",
    "generate_pair_title",
    "generate_nlp_conclusion",
    "generate_coherence_analysis",
    "generate_topics_analysis",
    "generate_qualitative_morphology_analysis",
    "generate_linguistic_analysis",
    "generate_notes_report",
]

