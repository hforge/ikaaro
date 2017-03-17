# -*- coding: UTF-8 -*-
# Copyright (C) 2017 Taverne Sylvain <taverne.sylvain@gmail.com>
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
from ikaaro.urls import urlpattern

# Import from here
from views import Api_DocView, ApiStatus_View
from views import Api_LoginView
from views import ApiDevPanel_ResourceJSON, ApiDevPanel_ResourceRaw, ApiDevPanel_ResourceHistory
from views import ApiDevPanel_ClassidViewDetails, ApiDevPanel_ClassidViewList
from views import ApiDevPanel_Config, ApiDevPanel_Log
from views import ApiDevPanel_CatalogReindex, UUIDView
from views import ApiDevPanel_ServerView, ApiDevPanel_ServerStop


urlpatterns = [
    urlpattern('', Api_DocView),
    urlpattern('/status', ApiStatus_View),
    urlpattern('/login', Api_LoginView),
    # Class id
    urlpattern('/devpanel/config', ApiDevPanel_Config),
    urlpattern('/devpanel/classid', ApiDevPanel_ClassidViewList),
    urlpattern('/devpanel/classid/{class_id}', ApiDevPanel_ClassidViewDetails),
    # Resource
    urlpattern('/devpanel/resource/{uuid}', UUIDView),
    urlpattern('/devpanel/resource/{uuid}/json', ApiDevPanel_ResourceJSON),
    urlpattern('/devpanel/resource/{uuid}/raw', ApiDevPanel_ResourceRaw),
    urlpattern('/devpanel/resource/{uuid}/history', ApiDevPanel_ResourceHistory),
    # Logs
    urlpattern('/devpanel/log/access', ApiDevPanel_Log(source_name='access')),
    urlpattern('/devpanel/log/events', ApiDevPanel_Log(source_name='events')),
    urlpattern('/devpanel/log/update', ApiDevPanel_Log(source_name='update')),
    # Catalog
    urlpattern('/devpanel/catalog/reindex', ApiDevPanel_CatalogReindex),
    # Server
    urlpattern('/devpanel/server', ApiDevPanel_ServerView),
    urlpattern('/devpanel/server/stop', ApiDevPanel_ServerStop),
]
