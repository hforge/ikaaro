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

# Import from standard library
from os import getpid

# Import from itools
from itools.database import PhraseQuery
from itools.gettext import MSG
from itools.web import STLView
from itools.web.exceptions import NotFound
from itools.web.views import ItoolsView

# Import from ikaaro
from ikaaro.fields import Char_Field, Email_Field, Password_Field
from ikaaro.fields import Boolean_Field
from ikaaro.server import get_config


class Api_View(STLView):
    """Doc of the api
    """

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



class UUIDView(ItoolsView):
    """ Base view for all uuid related views
    """

    def get_resource_from_uuid(self, context):
        uuid = context.path_query['uuid']
        query = PhraseQuery('uuid', uuid)
        search = context.search(query)
        if not search:
            raise NotFound
        resource = search.get_resources().next()
        return resource



class ApiDevPanel_ResourceJSON(UUIDView):
    """ Dump resource uuid as json
    """

    access = 'is_admin'
    query_schema = {'pretty': Boolean_Field(title=MSG(u'Pretty ?'))}

    def GET(self, root, context):
        resource = self.get_resource_from_uuid(context)
        schema = {}
        for name, field in resource.get_fields():
            if context.query.get('pretty'):
                schema[name] = resource.get_value_title(name)
            else:
                schema[name] = resource.get_value(name)
        return self.return_json(schema, context)



class ApiDevPanel_ResourceRaw(UUIDView):
    """ Dump resource uuid row as to_str()
    """

    access = 'is_admin'

    def GET(self, root, context):
        resource = self.get_resource_from_uuid(context)
        metadata = resource.metadata
        context.set_content_type('text/plain')
        return metadata.to_str()


class ApiDevPanel_ResourceHistory(UUIDView):
    """ List history of resource
    """

    access = 'is_admin'

    def GET(self, root, context):
        resource = self.get_resource_from_uuid(context)
        revisions = resource.get_revisions(content=False)
        return self.return_json(revisions, context)



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


class ApiDevPanel_Config(ItoolsView):
    """ Give config.conf file
    """

    access = 'is_admin'

    def GET(self, root, context):
        config = get_config(context.server.target)
        context.set_content_type('text/plain')
        return config.to_str()



class Api_LoginView(ItoolsView):
    """ Login user into app
    """

    access = True
    schema = {'email': Email_Field(title=MSG(u'Username'), required=True),
              'password': Password_Field(title=MSG(u'Password'), required=True)}

    def POST(self, root, context):
        raise NotImplementedError



class ApiDevPanel_Log(ItoolsView):

    access = 'is_admin'
    source_name = None

    def GET(self, root, context):
        context.set_content_type('text/plain')
        try:
            source = '{t}/log/{s}'.format(
                t=context.server.target, s=self.source_name)
            log_file = open(source, 'r')
        except IOError:
            return ''
        context.set_content_type('text/plain')
        data = log_file.read()
        log_file.close()
        return data



class ApiDevPanel_CatalogReindex(ItoolsView):

    access = 'is_admin'

    def POST(self, root, context):
        n = context.database.reindex_catalog(base_abspath='/')
        kw = {'n': n}
        return self.return_json(kw, context)



class ApiDevPanel_ServerView(ItoolsView):

    access = 'is_admin'

    def GET(self, root, context):
        server = context.server
        kw = {'timestamp': server.timestamp,
              'pid': getpid(),
              'port': server.port}
        return self.return_json(kw, context)


class ApiDevPanel_ServerStop(ItoolsView):

    access = 'is_admin'

    def GET(self, root, context):
        context.server.stop()
        kw = {'success': True}
        return self.return_json(kw, context)
