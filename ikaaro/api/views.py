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
from itools.gettext import MSG
from itools.web import STLView
from itools.web.exceptions import NotFound, Forbidden, Unauthorized
from itools.web.views import ItoolsView

# Import from ikaaro
from ikaaro.fields import Boolean_Field, Char_Field, Integer_Field
from ikaaro.fields import Email_Field, Password_Field, Datetime_Field
from ikaaro.utils import get_resource_by_uuid_query


class Api_DocView(STLView):
    """Doc of the api
    """

    access = 'is_admin'
    template = '/ui/ikaaro/root/api_docs.xml'

    def get_namespace(self, resource, context):
        i = 1
        dispatcher = context.server.dispatcher
        namespace = {'endpoints': []}
        for pattern, data in dispatcher.patterns.items():
            regex, view = data
            if not pattern.startswith('/api/'):
                continue
            path_query_schema = view.get_path_query_schema()
            query_schema = view.get_query_schema()
            form_schema = view.get_schema(resource, context)
            response_schema = view.response_schema
            kw = {'id': str(i),
                  'route': pattern,
                  'access': view.access,
                  'path_query_l': self.get_view_query_as_list(view, path_query_schema),
                  'query_l': self.get_view_query_as_list(view, query_schema),
                  'form_l': self.get_view_query_as_list(view, form_schema),
                  'response_l': self.get_view_query_as_list(view, response_schema),
                  'methods': view.known_methods,
                  'description': view.__doc__}
            namespace['endpoints'].append(kw)
            i +=1
        return namespace


    def get_view_query_as_list(self, view, schema):
        l = []
        for key, field in schema.items():
            kw = {'name': key,
                  'datatype': field.get_datatype(),
                  'required': field.required,
                  'title': field.title}
            l.append(kw)
        return l




class Api_View(ItoolsView):

    response_schema = {}
    route = None


    @classmethod
    def get_route(cls):
        """
        :return: The route associated to the class
        """
        return cls.route


    def get_resource(self, context, with_acls=True):
        return context.resource


    def is_access_allowed(self, context):
        with_acls = False if context.method == 'OPTIONS' else True
        resource = self.get_resource(context, with_acls=with_acls)
        if not resource:
            raise NotFound
        return context.is_access_allowed(resource, self)



class ApiStatus_View(Api_View):
    """Return server timestamp
    """

    access = True
    known_methods = ['GET']

    def GET(self, root, context):
        kw = {'ts': context.server.timestamp,
              'up': True}
        return self.return_json(kw, context)



class UUIDView(Api_View):
    """ Base view for all uuid related views
    """

    class_id = None
    bases_class_id = []
    access = True
    known_methods = ['DELETE']

    path_query_schema = {'uuid': Char_Field(title=MSG(u'The uuid of a resource in DB'))}

    def get_resource(self, context, with_acls=True):
        query = get_resource_by_uuid_query(
            uuid=context.path_query_base['uuid'],
            bases_class_id=self.bases_class_id,
            class_id=self.class_id)
        if with_acls is True:
            search = context.search(query)
        else:
            search = context.database.search(query)
        if not search:
            if context.database.search(query):
                # Exist but ...
                # Unauthorized (401)
                if context.user is None:
                    raise Unauthorized
                # Forbidden (403)
                raise Forbidden
            raise NotFound
        return search.get_resources(size=1).next()


    access_DELETE = 'is_allowed_to_remove'
    def DELETE(self, resource, context):
        resource = self.get_resource(context)
        resource.parent.del_resource(resource.name)
        return None



class ApiDevPanel_ResourceJSON(UUIDView):
    """ Dump resource uuid as json
    """

    access = 'is_admin'
    known_methods = ['GET', 'DELETE']
    query_schema = {'pretty': Boolean_Field(title=MSG(u'Pretty ?'))}

    def GET(self, root, context):
        resource = self.get_resource(context)
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
    known_methods = ['GET', 'DELETE']

    def GET(self, root, context):
        resource = self.get_resource(context)
        metadata = resource.metadata
        context.set_content_type('text/plain')
        return metadata.to_str()


class ApiDevPanel_ResourceHistory(UUIDView):
    """ List history of resource
    """

    access = 'is_admin'
    known_methods = ['GET', 'DELETE']
    response_schema = {
        'sha': Char_Field(title=MSG(u'SHA of the commit')),
        'author_date': Datetime_Field(title=MSG("Datetime of commit")),
        'author_name': Char_Field(title=MSG(u"Commit's author name")),
        'message_short': Char_Field(title=MSG(u"Commit's title"))
    }
    def GET(self, root, context):
        resource = self.get_resource(context)
        revisions = resource.get_revisions(content=False)
        return self.return_json(revisions, context)



class ApiDevPanel_ClassidViewList(Api_View):
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



class ApiDevPanel_ClassidViewDetails(Api_View):
    """ Give details about a class_id
    """

    access = 'is_admin'

    path_query_schema = {
        'class_id': Char_Field(title=MSG(u'A class_id registered in DB'))
    }
    response_schema = {
        'class_title': Char_Field(title=MSG(u'The class_title of the resource cls')),
        'class_id': Char_Field(title=MSG(u'The class_id of the resource cls'))
    }


    def GET(self, root, context):
        class_id = context.path_query['class_id']
        cls = context.database.get_resource_class(class_id)
        kw = {'class_title': cls.class_title,
              'class_id': class_id}
        return self.return_json(kw, context)


class ApiDevPanel_Config(Api_View):
    """ Give config.conf file
    """

    access = 'is_admin'

    def GET(self, root, context):
        config = context.server.config
        context.set_content_type('text/plain')
        return config.to_str()



class Api_LoginView(Api_View):
    """ Login user into app
    """

    access = True
    known_methods = ['POST']
    schema = {'email': Email_Field(title=MSG(u'Username'), required=True),
              'password': Password_Field(title=MSG(u'Password'), required=True)}

    def POST(self, root, context):
        raise NotImplementedError



class ApiDevPanel_Log(Api_View):
    """ Return the dump of a log file
    """

    access = 'is_admin'
    source_name = None
    known_methods = ['GET']

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



class ApiDevPanel_CatalogReindex(Api_View):
    """ Reindex the catalog
    """

    access = 'is_admin'
    known_methods = ['POST']

    def POST(self, root, context):
        n = context.database.reindex_catalog(base_abspath='/')
        kw = {'n': n}
        return self.return_json(kw, context)



class ApiDevPanel_ServerView(Api_View):
    """ Return informations about server timestamp / pid / port
    """

    access = 'is_admin'
    known_methods = ['GET']
    response_schema = {
        'timestamp': Char_Field(title=MSG(u"Server's start timestamp")),
        'pid': Integer_Field(title=MSG(u"Server's PID")),
        'port': Integer_Field(title=MSG(u"Server's port"))
    }

    def GET(self, root, context):
        server = context.server
        kw = {'timestamp': server.timestamp,
              'pid': getpid(),
              'port': server.port}
        return self.return_json(kw, context)



class ApiDevPanel_ServerStop(Api_View):
    """ Stop the web server
    """

    access = 'is_admin'
    known_methods = ['POST']

    def POST(self, root, context):
        context.server.stop()
        kw = {'success': True}
        return self.return_json(kw, context)
