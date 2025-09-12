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

import spacy
import pandas as pd
from .diff_match_patch import diff_match_patch as dmp_module
from .text_processing import connect_text, find_token_in_csv
import json
from .utils import get_utf8_byte_length
from .db import load_csv_data, save_json_data_if_not_exists, load_nlp_dataframe, save_title_to_db, save_diff_text
from .gemini import generate_pair_title

def compare_texts(text1, text2, project_name, pair_id, db_path):
    """
    Perform a text comparison between two French texts using SpaCy and diff-match-patch.
    Generate HTML representations of the changes and include morphosyntactic details from a CSV file.

    Args:
    text1 (str): The first text to compare.
    text2 (str): The second text to compare.
    project_name (str): The name of the project for saving JSON data.

    Returns:
    tuple: A tuple containing three JSON strings: html_wrong_json, html_correct_json, html_diff_json.
    """

    # Load the table tokens into a DataFrame
    df_tokens = load_nlp_dataframe(project_name, "tokens", db_path)

    # Load the table classifications into a DataFrame
    df_classifications = load_nlp_dataframe(project_name, "classifications", db_path)

    # Load the table entities into a DataFrame
    df_entities = load_nlp_dataframe(project_name, "entities", db_path)

    # Load the SpaCy French model for natural language processing
    nlp = spacy.load("fr_core_news_sm")

    # Convert texts to lowercase
    text1 = text1.lower()
    text2 = text2.lower()

    # Initialize the diff-match-patch object
    dmp = dmp_module()

    # Compute the differences between the two texts
    diff = dmp.diff_main(text1, text2)
    dmp.diff_cleanupSemantic(diff)

    # Initialize lists to hold the HTML representations of the differences
    html_diff = []
    html_wrong = []
    html_correct = []

    # Initialize positions for tracking the byte length positions in the texts
    position_in_correct = 0
    position_in_wrong = 0
    position_in_diff = 0

    # Process each difference
    for index, x in enumerate(diff):
        text = x[1]
        text_byte_length = get_utf8_byte_length(text)

        if index > 0:
            previous = diff[index - 1]
        else:
            previous = (None, '')

        if index < len(diff) - 1:
            next = diff[index + 1]
        else:
            next = (None, '')

        if x[0] == -1 and next[0] == 1:
            # Handle replaced text
            doc = nlp(text)
            tokens = [token.text for token in doc]
            morphology = find_token_in_csv(tokens, position_in_wrong, "error_text", df_tokens)
            entities = find_token_in_csv(tokens, position_in_wrong, "error_text", df_entities)


            html_diff_replaced_element = {
                "operation": "replaced",
                "pair_id": pair_id,
                "position_in_diff": position_in_diff,
                "position_in_wrong": position_in_wrong,
                "element": text,
                "morphology": [morphology],
                "entities": [entities],
                "Highlights": []
            }
            html_diff.append(html_diff_replaced_element)

            html_wrong_replaced_element = {
                "operation": "replaced",
                "pair_id": pair_id,
                "position_in_diff": position_in_diff,
                "position_in_wrong": position_in_wrong,
                "element": text,
                "morphology": [morphology],
                "entities": [entities],
                "Highlights": []
            }
            html_wrong.append(html_wrong_replaced_element)

            connected_text = connect_text(text, previous[1], next[1])
            position_in_diff += text_byte_length
            position_in_wrong += text_byte_length

        elif previous[0] == -1 and x[0] == 1:
            # Handle replaced by text
            doc = nlp(text)
            tokens = [token.text for token in doc]
            morphology = find_token_in_csv(tokens, position_in_correct, "corrected_text", df_tokens)
            entities = find_token_in_csv(tokens, position_in_correct, "corrected_text", df_entities)

            html_diff_replacedby_element = {
                "operation": "replacedby",
                "pair_id": pair_id,
                "position_in_diff": position_in_diff,
                "position_in_correct": position_in_correct,
                "element": text,
                "morphology": [morphology],
                "entities": [entities],
                "Highlights": []
            }
            html_diff.append(html_diff_replacedby_element)

            html_correct_replacedby_element = {
                "operation": "replacedby",
                "pair_id": pair_id,
                "position_in_diff": position_in_diff,
                "position_in_correct": position_in_correct,
                "element": text,
                "morphology": [morphology],
                "entities": [entities],
                "Highlights": []
            }
            html_correct.append(html_correct_replacedby_element)

            connected_text = connect_text(text, previous[1], next[1])
            position_in_diff += text_byte_length
            position_in_correct += text_byte_length

        else:
            if x[0] == 0:
                # Handle unchanged text
                doc = nlp(text)
                tokens = [token.text for token in doc]
                morphology = find_token_in_csv(tokens, position_in_wrong, "error_text", df_tokens)
                morphology_correct = find_token_in_csv(tokens, position_in_correct, "corrected_text", df_tokens)
                entities = find_token_in_csv(tokens, position_in_wrong, "error_text", df_entities)
                entities_correct = find_token_in_csv(tokens, position_in_correct, "corrected_text", df_entities)

                html_diff_unchanged_element = {
                    "operation": "unchanged",
                    "pair_id": pair_id,
                    "position_in_diff": position_in_diff,
                    "position_in_wrong": position_in_wrong,
                    "position_in_correct": position_in_correct,
                    "element": text,
                    "morphology": [morphology],
                    "entities": [entities],
                    "Highlights": []
                }
                html_diff.append(html_diff_unchanged_element)

                html_wrong_unchanged_element = {
                    "operation": "unchanged",
                    "pair_id": pair_id,
                    "position_in_diff": position_in_diff,
                    "position_in_wrong": position_in_wrong,
                    "position_in_correct": position_in_correct,
                    "element": text,
                    "morphology": [morphology],
                    "entities": [entities],
                    "Highlights": []
                }
                html_wrong.append(html_wrong_unchanged_element)

                html_correct_unchanged_element = {
                    "operation": "unchanged",
                    "pair_id": pair_id,
                    "position_in_diff": position_in_diff,
                    "position_in_wrong": position_in_wrong,
                    "position_in_correct": position_in_correct,
                    "element": text,
                    "morphology": [morphology_correct],
                    "entities": [entities_correct],
                    "Highlights": []
                }
                html_correct.append(html_correct_unchanged_element)

                position_in_diff += text_byte_length
                position_in_wrong += text_byte_length
                position_in_correct += text_byte_length

            if x[0] == 1:
                # Handle added text
                doc = nlp(text)
                tokens = [token.text for token in doc]
                morphology = find_token_in_csv(tokens, position_in_correct, "corrected_text", df_tokens)
                entities = find_token_in_csv(tokens, position_in_correct, "corrected_text", df_entities)

                html_diff_added_element = {
                    "operation": "added",
                    "pair_id": pair_id,
                    "position_in_diff": position_in_diff,
                    "position_in_correct": position_in_correct,
                    "element": text,
                    "morphology": [morphology],
                    "entities": [entities],
                    "Highlights": []
                }
                html_diff.append(html_diff_added_element)

                html_correct_added_element = {
                    "operation": "added",
                    "pair_id": pair_id,
                    "position_in_diff": position_in_diff,
                    "position_in_correct": position_in_correct,
                    "element": text,
                    "morphology": [morphology],
                    "entities": [entities],
                    "Highlights": []
                }
                html_correct.append(html_correct_added_element)

                connected_text = connect_text(text, previous[1], next[1])
                position_in_diff += text_byte_length
                position_in_correct += text_byte_length

            elif x[0] == -1:
                # Handle deleted text
                doc = nlp(text)
                tokens = [token.text for token in doc]
                morphology = find_token_in_csv(tokens, position_in_wrong, "error_text", df_tokens)
                entities = find_token_in_csv(tokens, position_in_wrong, "error_text", df_entities)

                html_diff_deleted_element = {
                    "operation": "deleted",
                    "pair_id": pair_id,
                    "position_in_diff": position_in_diff,
                    "position_in_wrong": position_in_wrong,
                    "element": text,
                    "morphology": [morphology],
                    "entities": [entities],
                    "Highlights": []
                }
                html_diff.append(html_diff_deleted_element)

                html_wrong_deleted_element = {
                    "operation": "deleted",
                    "pair_id": pair_id,
                    "position_in_diff": position_in_diff,
                    "position_in_wrong": position_in_wrong,
                    "element": text,
                    "morphology": [morphology],
                    "entities": [entities],
                    "Highlights": []
                }
                html_wrong.append(html_wrong_deleted_element)

                connected_text = connect_text(text, previous[1], next[1])
                position_in_diff += text_byte_length
                position_in_wrong += text_byte_length

    # Convert the resulting HTML elements to JSON
    html_wrong_json = json.dumps(html_wrong)
    html_correct_json = json.dumps(html_correct)
    html_diff_json = json.dumps(html_diff)
    html_diff_raw = dmp.diff_prettyHtml(diff)

    return html_wrong_json, html_correct_json, html_diff_json, html_diff_raw


def process_and_save_text_pairs(project_name, db_path, api_key):
    """
    Process each pair of texts from the csv_data table and save the results in the json_items table.
    """
    # Load the text pairs from the csv_data table
    text_pairs = load_csv_data(project_name, db_path)

    # Loop through each text pair
    for pair in text_pairs:
        pair_id = pair['id']
        text1 = pair['error_text']
        text2 = pair['corrected_text']

        # Generate title
        title = generate_pair_title(project_name, text1, text2, api_key)
        if title:
            save_title_to_db(project_name, pair_id, title, db_path)

        # Perform the text comparison
        html_wrong_json, html_correct_json, html_diff_json, html_diff_raw = compare_texts(text1, text2, project_name, pair_id, db_path)

        # Save the comparison results
        save_json_data_if_not_exists(project_name, pair_id, 'wrong', html_wrong_json, db_path)
        save_json_data_if_not_exists(project_name, pair_id, 'correct', html_correct_json, db_path)
        save_json_data_if_not_exists(project_name, pair_id, 'diff', html_diff_json, db_path)
        save_diff_text(project_name, pair_id, html_diff_raw, db_path)