# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Nicolas Deram <nicolas@itaapy.com>
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

# Import from the Standard Library
from hashlib import sha1, sha256
from random import sample

# Import from other modules
try:
    import tidy
except ImportError:
    tidy = None

# Import from itools
from itools.database import AllQuery, AndQuery, PhraseQuery, OrQuery
from itools.database import RangeQuery
from itools.datatypes import Unicode
from itools.handlers import checkid
from itools.html import HTMLParser, stream_to_str_as_xhtml
from itools.stl import STLTemplate, stl_namespaces
from itools.uri import get_reference, Reference
from itools.web import get_context
from itools.xml import XMLParser


###########################################################################
# CMS Template
###########################################################################

def make_stl_template(data):
    return list(XMLParser(data, stl_namespaces))



class CMSTemplate(STLTemplate):

    template = None

    def get_template(self):
        # Get the template
        template = self.template
        if template is None:
            msg = "%s is missing the 'template' variable"
            raise NotImplementedError, msg % repr(self)

        # Case 1: a ready made list of events
        if type(template) is list:
            return template

        # Case 2: a path to a template in the filesystem (ui)
        if type(template) is str:
            handler = get_context().get_template(template)
            return handler.events

        raise ValueError, 'bad value for the template attribute'



###########################################################################
# Navigation helper functions
###########################################################################
def get_parameters(prefix, **kw):
    """Gets the parameters from the request form, the keyword argument
    specifies which are the parameters to get and which are their default
    values.

    The prefix argument lets to create different namespaces for the
    parameters, so the same page web can have different sections with
    different but equivalent parameters.

    For example, call it like:

      get_parameters('resources', sortby='id', sortorder='up')
    """
    # Get the form field from the request (a zope idiom)
    get_parameter = get_context().get_form_value

    # Get the parameters
    parameters = {}
    for key, value in kw.items():
        parameters[key] = get_parameter('%s_%s' % (prefix, key),
                                        default=value)

    return parameters



###########################################################################
# Languages
###########################################################################

# Mark for translatios
u'Basque'
u'Catalan'
u'English'
u'French'
u'German'
u'Hungarian'
u'Italian'
u'Japanese'
u'Portuguese'
u'Spanish'


###########################################################################
# String format for display
###########################################################################

def reduce_string(title='', word_treshold=15, phrase_treshold=40):
    """Reduce words and string size.
    """
    ellipsis = u'…' if type(title) is unicode else '…'
    words = title.strip().split(' ')
    for i, word in enumerate(words):
        if len(word) > word_treshold:
            words.pop(i)
            word = word[:word_treshold] + ellipsis
            words.insert(i, word)
    title = ' '.join(words)
    if len(title) > phrase_treshold:
        # Remove right trailling whitespaces
        title = title[:phrase_treshold - 1].rstrip()
        # Only add ellipsis if the last word does not already
        # end with one
        if title[-1] != ellipsis:
            title += ellipsis
    return title


encodings = ['utf-8', 'windows-1252', 'cp437']
def process_name(name):
    for encoding in encodings:
        try:
            title = unicode(name, encoding)
            checkid_name = checkid(title, soft=False)
            break
        except UnicodeError:
            pass
    else:
        raise ValueError, name

    if checkid_name is None:
        raise ValueError, name

    # Ok
    return checkid_name, title


###########################################################################
# Tidy HTML
###########################################################################
encodings = ['utf-8', 'windows-1252', 'cp437']
def to_utf8(data):
    for encoding in encodings:
        try:
            return unicode(data, encoding).encode('utf-8')
        except UnicodeError:
            pass

    raise UnicodeError, 'unable to find out encoding'


def tidy_html(body):
    if tidy:
        body = to_utf8(body)
        body = tidy.parseString(body, indent=1, char_encoding='utf8',
                                output_xhtml=1, word_2000=1)
        body = str(body)

    return stream_to_str_as_xhtml(HTMLParser(body))


###########################################################################
# User and Authentication
###########################################################################
# ASCII letters and digits, except the characters: 0, O, 1, l
tokens = 'abcdefghijkmnopqrstuvwxyzABCDEFGHIJKLMNPQRSTUVWXYZ23456789'
def generate_password(length=6):
    return ''.join(sample(tokens, length))



algos = {
    'sha1': sha1,
    'sha256': sha256}
def get_secure_hash(password, algo, salt=None):
    if salt is None:
        salt = generate_password()

    return algos[algo](password + salt).digest(), salt



###########################################################################
# Generate next name
###########################################################################
def generate_name(name, used, suffix='_'):
    """Generate a name which is not in list "used" based on name and suffix.
    Example:
      With name='toto.txt', used=['toto.txt', 'toto_0.txt']
      --> toto.txt and toto_0.txt are used so it returns toto_1.txt
      With name='toto.txt', used=['toto.txt', 'toto_0.txt'], suffix='_copy_'
      --> toto.txt is used so it returns toto_copy_0.txt
    """
    if name not in used:
        return name

    items = name.split('.', 1)
    basename = items[0]
    extent = ''
    if len(items) > 1:
        extent = '.%s' % items[1]

    # 1st time called
    if suffix not in basename:
        index = 0
    else:
        basename, index = basename.rsplit(suffix, 1)
        try:
            index = int(index) + 1
        except ValueError:
            basename = '%s%s%s' % (basename, suffix, index)
            index = 0

    name = ''.join([basename, suffix, str(index), extent])
    while name in used:
        index += 1
        name = ''.join([basename, suffix, str(index), extent])

    return str(name)



###########################################################################
# Index and Search
###########################################################################
def get_base_path_query(path, min_depth=1, max_depth=None):
    """Builds a query that will return all the objects within the given
    absolute path, like it is returned by 'resource.abspath'.

    The minimum and maximum depth parameters are relative to the given path:

    - If the minimum depth is zero it means include the container
    - If the maximum depth is None it means unlimited.
    """
    # Preprocess input data
    if type(path) is not str:
        path = str(path)

    if max_depth is not None and max_depth < min_depth:
        err = 'maximum depth (%d) smaller than minimum depth (%d)'
        raise ValueError, err % (max_depth, min_depth)

    # Special case: everything
    if path == '/' and min_depth == 0 and max_depth is None:
        return AllQuery()

    # Special case: just the given path
    if min_depth == 0 and max_depth == 0:
        return PhraseQuery('abspath', path)

    # Standard case
    query = PhraseQuery('parent_paths', path)
    if min_depth > 1 or max_depth is not None:
        path_depth = path.rstrip('/').count('/')
        a = path_depth + min_depth
        b = path_depth + max_depth if max_depth is not None else None
        query = AndQuery(query, RangeQuery('abspath_depth', a, b))

    if min_depth == 0:
        return OrQuery(query, PhraseQuery('abspath', path))

    return query


###########################################################################
# Used by the add-form
###########################################################################
def get_content_containers(context, class_id=None):
    query = AndQuery(
        PhraseQuery('base_classes', 'folder'),
        PhraseQuery('is_content', True))

    root = context.root
    for container in context.search(query).get_resources():
        if not root.has_permission(context.user, 'add', container, class_id):
            continue

        if class_id is None:
            yield container
            continue

        for cls in container.get_document_types():
            if class_id == cls.class_id:
                yield container
                break


###########################################################################
# Used by *_links and menu
###########################################################################
def split_reference(ref):
    """Return the reference associated to the path, the path and the optional
    view without query/fragment.
    ref: Reference
    path: Path
    view: string
    """
    # XXX specific case for the menu
    # Be robust if the path is multilingual
    type_ref = type(ref)
    if type_ref is unicode:
        ref = Unicode.encode(ref)
    if type_ref is not Reference:
        ref = get_reference(ref)
    # Split path and view
    path = ref.path
    view = ''
    name = path.get_name()
    # Strip the view
    if name and name[0] == ';':
        view = '/' + name
        path = path[:-1]
    return ref, path, view


###########################################################################
# Fancy box (javascript)
###########################################################################

_close_fancybox = """
    <html>
    <head>
      <script src="/ui/jquery.js" type="text/javascript"></script>
    </head>
    <body>
      <script type="text/javascript">
        $(document).ready(function() { parent.$.fancybox.close(); });
      </script>
    </body>
    </html>
    """

def close_fancybox(context, default=None):
    # Case 1: fancybox
    fancybox = context.get_query_value('fancybox')
    if fancybox:
        context.set_content_type('text/html')
        return _close_fancybox

    # Case 2: normal
    goto = context.get_form_value('referrer') or default
    return get_reference(goto) if type(goto) is str else goto
