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
from itools.database import PhraseQuery
from itools.gettext import MSG
from itools.web import STLView
from itools.web.views import ItoolsView

# Import from ikaaro
from ikaaro.fields import Char_Field, Email_Field, Password_Field


class Api_View(STLView):

    access = 'is_admin'
    template = '/ui/root/api_docs.xml'

    def get_namespace(self, resource, context):
        dispatcher = context.server.dispatcher
        namespace = {'endpoints': []}
        for pattern, data in dispatcher.patterns.items():
            regex, view = data
            if not pattern.startswith('/api/'):
                continue
            query_schema = view.get_query_schema()
            form_schema = view.get_schema(resource, context)
            kw = {'route': pattern,
                  'access': view.access,
                  'query_l': self.get_view_query_as_list(view, query_schema),
                  'form_l': self.get_view_query_as_list(view, form_schema),
                  'methods': ['GET'],
                  'description': view.__doc__}
            namespace['endpoints'].append(kw)
        return namespace


    def get_view_query_as_list(self, view, schema):
        l = []
        for key, field in schema.items():
            kw = {'name': key,
                  'required': field.required,
                  'title': field.title}
            l.append(kw)
        return l




class ApiStatus_View(ItoolsView):
    """Return server timestamp
    """

    access = True

    def GET(self, root, context):
        kw = {'ts': context.server.timestamp,
              'up': True}
        return self.return_json(kw, context)



class ApiDevPanel_ResourceDump(ItoolsView):
    """ Dump resource uuid
    """

    access = 'is_admin'
    query_schema = {'format': Char_Field(
      title=MSG(u'Format du dump'), required=True)}

    def GET(self, root, context):
        uuid = context.path_query['uuid']
        query = PhraseQuery('uuid', uuid)
        search = context.search(query)
        if not search:
            return context.set_default_response(404)
        resource = search.get_resources().next()
        schema = {}
        for name, field in resource.get_fields():
            schema[name] = field.rest()
        return self.return_json(schema, context)



class ApiDevPanel_ClassidViewList(ItoolsView):
    """ List all class ids of the database
    """

    access = 'is_admin'

    def GET(self, root, context):
        l = []
        for cls in context.database.get_resource_classes():
            kw = {'class_title': cls.class_title,
                  'class_id': cls.class_id}
            l.append(kw)
        return self.return_json(l, context)



class ApiDevPanel_ClassidViewDetails(ItoolsView):
    """ Give details about a class_id
    """

    access = 'is_admin'

    def GET(self, root, context):
        class_id = context.path_query['class_id']
        cls = context.database.get_resource_class(class_id)
        kw = {'class_title': cls.class_title,
              'class_id': class_id}
        return self.return_json(kw, context)



class Api_LoginView(ItoolsView):
    """ Login user into app
    """

    access = True
    schema = {'email': Email_Field(title=MSG(u'Username'), required=True),
              'password': Password_Field(title=MSG(u'Password'), required=True)}

    def POST(self, root, context):
        raise NotImplementedError
