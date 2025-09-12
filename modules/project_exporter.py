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
import zipfile

def export_project_to_zip(project_name, db_path, output_folder):
    project_db_file = f"{project_name}.db"
    project_db_path = os.path.join(db_path, project_db_file)

    if not os.path.exists(project_db_path):
        raise Exception("Project database not found.")

    zip_file_name = f"{project_name}.zip"
    zip_path = os.path.join(output_folder, zip_file_name)

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write(project_db_path, arcname=project_db_file)

    return zip_path
