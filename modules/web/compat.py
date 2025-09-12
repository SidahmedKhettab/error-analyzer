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

from flask import Blueprint, redirect, url_for

compat_bp = Blueprint('compat', __name__, url_prefix='')


@compat_bp.route('/home', endpoint='home')
def compat_home():
    return redirect(url_for('site.home'))


@compat_bp.route('/about', endpoint='about')
def compat_about():
    return redirect(url_for('site.about'))
