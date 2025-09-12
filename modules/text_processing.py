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

"""
This module provides utility functions for text processing, including functions to determine if a character is punctuation,
connect text fragments by handling leading/trailing spaces and punctuation, and find tokens in a CSV file containing morphosyntactic details.
"""

import string

def is_punctuation(char):
    """
    Check if a character is a punctuation mark.

    Args:
        char (str): The character to check.

    Returns:
        bool: True if the character is a punctuation mark, False otherwise.
    """
    return char in string.punctuation

def connect_text(text, previous_char, next_char):
    """
    Connect text fragments by handling leading/trailing spaces and punctuation.

    Args:
        text (str): The text to connect.
        previous_char (str): The character preceding the text.
        next_char (str): The character following the text.

    Returns:
        str: The connected text.
    """
    text_stripped = text.strip()
    has_leading_space = text.startswith(' ')
    has_trailing_space = text.endswith(' ')
    has_leading_punctuation = is_punctuation(text_stripped[0]) if text_stripped else False
    has_trailing_punctuation = is_punctuation(text_stripped[-1]) if text_stripped else False

    if not has_leading_space and not has_leading_punctuation:
        if previous_char and not previous_char[-1].isspace() and not is_punctuation(previous_char[-1]):
            text_stripped = previous_char + text_stripped

    if not has_trailing_space and not has_trailing_punctuation:
        if next_char and not next_char[0].isspace() and not is_punctuation(next_char[0]):
            text_stripped = text_stripped + next_char

    return text_stripped


def find_token_in_csv(tokens, position, text_type, df):
    """
    Find tokens in a DataFrame containing morphosyntactic details or entity details.

    Args:
        tokens (list): List of tokens to find.
        position (int): The position of the token in the text.
        text_type (str): The type of the text ('text1' or 'text2').
        df (DataFrame): The DataFrame containing the CSV data.

    Returns:
        list: List of dictionaries containing the matched rows from the DataFrame.
    """
    results = []

    # Determine the DataFrame type based on the columns
    if 'token' in df.columns:
        column_to_search = 'token'
    elif 'name' in df.columns:
        column_to_search = 'name'
    else:
        raise ValueError("DataFrame does not have the expected columns ('token' or 'name').")

    for token in tokens:
        if token.strip() == '':
            continue
        token_lower = token.lower()
        matched_rows = df[(df[column_to_search].str.lower().str.contains(token_lower, regex=False)) & (
                    df['text_type'] == text_type)].copy()
        if not matched_rows.empty:
            matched_rows.loc[:, 'distance'] = (matched_rows['position'] - position).abs()
            closest_row = matched_rows.loc[matched_rows['distance'].idxmin()]
            results.append(closest_row.to_dict())
        else:
            mask = (df['position'] >= position - 5) & (df['position'] <= position + 5) & (df['text_type'] == text_type)
            matched_rows = df[mask].copy()
            if not matched_rows.empty:
                matched_rows.loc[:, 'distance'] = (matched_rows['position'] - position).abs()
                closest_row = matched_rows.loc[matched_rows['distance'].idxmin()]
                results.append(closest_row.to_dict())

    return results