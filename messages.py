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



MSG_BAD_KEY = ERROR(u"Your confirmation key is invalid.")

MSG_BAD_NAME = ERROR(
    u'The document name contains illegal characters, choose another one.')

MSG_CAPTION = ERROR(u'Caption')

MSG_CHANGES_SAVED = INFO(u'The changes have been saved.')

MSG_CHANGES_SAVED2 = INFO(u'The changes have been saved ({time}).')

MSG_DELETE_RESOURCE = MSG(u'Are you sure you want to delete this resource?')

MSG_EDIT_CONFLICT = ERROR(
    u'Someone already saved this document, click "Save" again to force.')

MSG_EDIT_CONFLICT2 = ERROR(
    u'User {user} already saved this document, click "Save" again to force.')

MSG_EMPTY_FILENAME = ERROR(u'The file must be entered.')

MSG_EXISTANT_FILENAME = ERROR(u'A given name already exists.')

MSG_INVALID_EMAIL = ERROR(u'The email address provided is invalid.')

MSG_NAME_CLASH = ERROR(u'There is already another resource with this name.')

MSG_NAME_MISSING = ERROR(u'The name is missing.')

MSG_NEW_RESOURCE = INFO(u'A new resource has been added.')

MSG_NONE_REMOVED = ERROR(u'No resource removed.')

MSG_RESOURCES_PASTED = INFO(u'Resources pasted: {resources}.')

MSG_RESOURCES_REMOVED = INFO(u'Resources removed: {resources}.')

MSG_RESOURCES_REFERENCED = ERROR(
    u'Action impossible (the resources are in use): {resources}.')

MSG_RESOURCES_REFERENCED_HTML = ERROR(u"""
    Action impossible (the resources are in use):
    <stl:inline stl:repeat="resource resources">
        <a href="${resource/href}"
           title="${resource/title}">${resource/title}</a>
        <stl:inline stl:if="not repeat/resource/end">,</stl:inline>
    </stl:inline>""", format='stl')

MSG_RESOURCES_NOT_PASTED = ERROR(u'Resources not allowed to paste here: '
                                 u'{resources}.')

MSG_RESOURCES_NOT_REMOVED = ERROR(u'Resources not allowed to remove: '
                                  u'{resources}.')

MSG_PASSWORD_MISMATCH = ERROR(u'The provided passwords do not match.')

MSG_REGISTERED = ERROR(
    u"You have already confirmed your registration. "
    u"Try to log in or ask for a new password.")

MSG_PASSWORD_EQUAL_TO_USERNAME = ERROR(u'Password cannot match the username.')

MSG_NONE_SELECTED = ERROR(u'No resource selected.')

MSG_NONE_ALLOWED = ERROR(u"No resource allowed.")

MSG_NO_PASTE = ERROR(u'Nothing to paste.')

MSG_RENAMED = INFO(u'Resources renamed.')

MSG_COPIED = INFO(u'Resources copied.')

MSG_CUT = INFO(u'Resources cut.')

MSG_PUBLISHED = INFO(u'Resources published.')

MSG_RETIRED = INFO(u'Resources retired.')

MSG_UNEXPECTED_MIMETYPE = ERROR(u'Unexpected file of mimetype {mimetype}.')

MSG_LOGIN_WRONG_NAME_OR_PASSWORD = ERROR(
    u'The login name or the password is incorrect.')
