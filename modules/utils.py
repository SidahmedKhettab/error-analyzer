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
This module provides a utility function to calculate the byte length of a given text when encoded in UTF-8.
"""

from markupsafe import escape
from typing import Optional

def get_google_api_key() -> Optional[str]:
    """Return the effective Google Gemini API key for the current request.

    Resolution order (for backward compatibility):
    1) Logged-in user's profile (g.current_user['google_api_key'])
    2) Flask app config (app.config['GOOGLE_API_KEY'])
    3) Environment variable GOOGLE_API_KEY

    Returns None if no key is found.
    """
    try:
        # Lazy import to avoid circulars at module import time
        from flask import g, current_app
        key = None
        try:
            if getattr(g, 'current_user', None):
                key = (g.current_user or {}).get('google_api_key')
        except Exception:
            key = None
        if not key:
            try:
                key = current_app.config.get('GOOGLE_API_KEY')
            except Exception:
                key = None
        if not key:
            import os as _os
            key = _os.environ.get('GOOGLE_API_KEY')
        return (key or '').strip() or None
    except Exception:
        return None


def get_utf8_byte_length(text):
    """
    Calculate the byte length of a given text when encoded in UTF-8.

    Args:
        text (str): The text to calculate the byte length for.

    Returns:
        int: The byte length of the text when encoded in UTF-8.
    """
    return len(text.encode('utf-8'))

def sanitize_input(input_str, max_length=255):
    """
    Sanitize input string to prevent XSS and other vulnerabilities.

    Args:
        input_str (str): The input string to sanitize.
        max_length (int): The maximum allowed length of the input.

    Returns:
        str: The sanitized input string.
    """
    # Remove leading and trailing whitespace
    input_str = input_str.strip()
    # Escape HTML to prevent XSS
    input_str = escape(input_str)
    # Validate length
    if len(input_str) > max_length:
        input_str = input_str[:max_length]
    return input_str
