# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from itools
from itools.gettext import MSG
from itools.web import INFO, ERROR



MSG_BAD_KEY = ERROR("Your confirmation key is invalid.")

MSG_BAD_NAME = ERROR(
    'The document name contains illegal characters, choose another one.')

MSG_CAPTION = ERROR('Caption')

MSG_CHANGES_SAVED = INFO('The changes have been saved.')

MSG_CHANGES_SAVED2 = INFO('The changes have been saved ({time}).')

MSG_DELETE_RESOURCE = MSG('Are you sure you want to delete this resource?')

MSG_EDIT_CONFLICT = ERROR(
    'Someone already saved this document, click "Save" again to force.')

MSG_EDIT_CONFLICT2 = ERROR(
    'User {user} already saved this document, click "Save" again to force.')

MSG_EMPTY_FILENAME = ERROR('The file must be entered.')

MSG_EXISTANT_FILENAME = ERROR('A given name already exists.')

MSG_INVALID_EMAIL = ERROR('The email address provided is invalid.')

MSG_NAME_CLASH = ERROR('There is already another resource with this name.')

MSG_NAME_MISSING = ERROR('The name is missing.')

MSG_NEW_RESOURCE = INFO('A new resource has been added.')

MSG_NONE_REMOVED = ERROR('No resource removed.')

MSG_RESOURCES_PASTED = INFO('Resources pasted: {resources}.')

MSG_RESOURCES_REMOVED = INFO('Resources removed: {resources}.')

MSG_RESOURCES_REFERENCED = ERROR(
    'Action impossible (the resources are in use): {resources}.')

MSG_RESOURCES_REFERENCED_HTML = ERROR(u"""
    Action impossible (the resources are in use):
    <stl:inline stl:repeat="resource resources">
        <a href="${resource/href}"
           title="${resource/title}">${resource/title}</a>
        <stl:inline stl:if="not repeat/resource/end">,</stl:inline>
    </stl:inline>""", format='stl')

MSG_RESOURCES_NOT_PASTED = ERROR('Resources not allowed to paste here: '
                                 '{resources}.')

MSG_RESOURCES_NOT_REMOVED = ERROR('Resources not allowed to remove: '
                                  '{resources}.')

MSG_PASSWORD_MISMATCH = ERROR('The provided passwords do not match.')

MSG_REGISTERED = ERROR(
    u"You have already confirmed your registration. "
    u"Try to log in or ask for a new password.")

MSG_PASSWORD_EQUAL_TO_USERNAME = ERROR('Password cannot match the username.')

MSG_NONE_SELECTED = ERROR('No resource selected.')

MSG_NONE_ALLOWED = ERROR(u"No resource allowed.")

MSG_NO_PASTE = ERROR('Nothing to paste.')

MSG_RENAMED = INFO('Resources renamed.')

MSG_COPIED = INFO('Resources copied.')

MSG_CUT = INFO('Resources cut.')

MSG_PUBLISHED = INFO('Resources published.')

MSG_RETIRED = INFO('Resources retired.')

MSG_UNEXPECTED_MIMETYPE = ERROR('Unexpected file of mimetype {mimetype}.')

MSG_LOGIN_WRONG_NAME_OR_PASSWORD = ERROR(
    'The login name or the password is incorrect.')
