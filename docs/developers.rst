Developer's Guide
#################


\documentclass{article}

\usepackage{array}
\usepackage{color}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage[utf8x]{inputenc}
\usepackage{makeidx}
\usepackage{minitoc}
\usepackage{times}
\usepackage{ucs}
\usepackage{verbatim}

% Code (in small and footnotesize)
\newenvironment{code}{\small\verbatim}{\endverbatim}
\newenvironment{smallcode}{\footnotesize\verbatim}{\endverbatim}


% Document header
\title{\tt ikaaro 0.50\\Developer's Guide}

\author{Juan David Ibáñez Palomar\thanks{Permission is granted to copy,
distribute and/or modify this document under the terms of the GNU Free
Documentation License, Version 1.2 or any later version published by the
Free Software Foundation; with no Invariant Sections, no Front-Cover Texts,
and no Back-Cover Texts.  There is a copy of the license at
http://www.gnu.org/copyleft/fdl.html}\\
\small \texttt{jdavid@itaapy.com}}
\makeindex

\begin{document}

\maketitle
\tableofcontents

\section{{\tt ikaaro} presentation}

{\tt ikaaro} is a Content Management System built on Python and itools.  It's
provide a rich API and tools to design easily websites and web applications.
{\tt ikaaro} uses a filesytem object database which allow to store and manage
all the resources and metadata used by the sites.

In this document, you will discover how to use {\tt ikaaro}.

\section{Resources and Views}

%XXX FINISH ME

\section{Start a new {\tt ikaaro} project}

This section will help you to start a new project with {\tt ikaaro}. The {\tt
examples} folder contains a skeleton package where you can find:

\begin{code}
    .
    |-- __init__.py
    |-- locale
    |   |-- en.po
    |   |-- fr.po
    |   `-- locale.pot
    |-- root.py
    |-- setup.conf
    |-- setup.py
    `-- ui
        `-- style.css
\end{code}

\subsection{The Root}

First thing we want to do is to take control of the application's root.  For
this purpose we define a Root class inherited from the Root class of {\tt
ikaaro} in the {\tt root.py} module:

\begin{code}
# Import from itools
from itools.gettext import MSG

# Import from ikaaro
from ikaaro.registry import register_resource_class
from ikaaro.root import Root as BaseRoot

class Root(BaseRoot):
    class_id = 'myapp'
    class_title = MSG(u'MY ROOT')


register_resource_class(Root)
\end{code}


\subsubsection{Class Metadata}

This code illustrates several things. First the class variables that
describe the class. In the example above there is only the {\em id} and
{\em title}, here a more complete list:

\begin{itemize}
  \item {\tt class\_id}

    Every handler class in {\tt ikaaro} must have a unique id.

  \item {\tt class\_version}

    Used by the upgrade framework.

  \item {\tt class\_title} and {\tt class\_description}

    A short and a long description of the class. Used in the User Interface.

  \item {\tt class\_icon16} and {\tt class\_icon48}

    Two icons for the class, 16x16 and 48x48 pixels respectively. Used in
    the User Interface.
\end{itemize}


\subsubsection{The Registry}

We need to register every CMS object class with a call to {\tt
register\_resource\_class}. This is typically done at the end of the
module where the class is defined.

There is one particularity regarding the root class. We need to import
it in the initialization module ({\tt \_\_init\_\_.py}):

\begin{code}
    [...]
    from root import Root

    [...]
\end{code}


\subsection{The User Interface}

Our application is not only made of Python code. For the user interface
we will have for example:

\begin{itemize}
  \item XHTML templates
  \item CSS files
  \item Javascript files
  \item Images
\end{itemize}

And maybe more. All this stuff goes into the {\tt ui} folder. In our
skeleton the only thing we can find is an empty {\tt style.css} file.

The {\tt ui} folder is what we call a skin. And it must be registered
with a call to {\tt register\_skin}, see in the {\tt \_\_init\_\_.py} file,
the lines:

\begin{code}
[...]
from itools.utils import get_abspath

[...]
from ikaaro.skins import register_skin

[...]
# Register the skin
path = get_abspath('ui')
register_skin('myapp', path)

[...]
\end{code}


\subsection{To be Multilingual}

We assume your application will be multilingual, for this purpose the
skeleton is already internationalized.

First, the {\tt locale} folder keeps the message catalogs (POT and PO
files).

Then, we must define and register our application's domain, see in the {\tt
\_\_init\_\_.py} file, the lines:

\begin{code}
[...]
from itools.utils import get_abspath
from itools.gettext import register_domain

[...]
# Register the domain
path = get_abspath('locale')
register_domain('myapp', path)

[...]
\end{code}

And finally, all the strings to be translated must be constructed with the
{\tt MSG} object like that:

\begin{code}
    class_title = MSG(u'MY ROOT')
\end{code}

You can find more explanations about that in the itools'
documentation\footnote{http://download.hforge.org/doc/i18n/}.

\section{General principles}

%XXX FINISH ME
\subsection{A Class skeleton}


  class\_id = 'ortho'
  class\_title = u"Cabinet d'Orthopédie-Dento-Faciale"
  class\_version = '20080208'

  \_\_fixed\_handlers\_\_

\subsection{Metadata}

\begin{code}
    @classmethod
    def get_metadata_schema(cls):
        schema = WebSite.get_metadata_schema()
        del schema['guests']
        del schema['members']
        schema['website_languages'] = Tokens(default=('fr',))
        schema['pdf_header_left'] = Unicode
        schema['pdf_header_right'] = Unicode
        schema['praticiens'] = Tokens
        schema['assistants'] = Tokens(default=())
        schema['last_brb'] = Date()
        return schema
\end{code}

\section{{\tt ikaaro} objects}

%XXX FINISH ME

\section{ACLS}

For security reasons, the methods you develop in {\tt ikaaro} are
inaccessible. (They are not published.) If you want to make them accessible,
you have to define the method ACL::

    view__access__ = False
    def view(self, context):
        ...
        ...


\begin{table}[ht]
\centering
\begin{tabular}{|p{4cm}|p{8cm}|}
\hline
  ACL Value                 & Description\\\hline
  \tt False (default value) & \tt The view is accesible to anyone. \\\hline
  \tt True                  & \tt The view is accesible to anybody. \\\hline
  \tt is\_admin             & \tt TODO \\\hline
  \tt is\_allowed\_to\_view & \tt TODO \\\hline
  \tt is\_allowed\_to\_edit & \tt TODO \\\hline
\end{tabular}
\end{table}

\section{{\tt ikaaro} "constructor"}

\subsection{The Root constructor}

\begin{code}
    @staticmethod
    def _make_object(cls, folder, email, password):
\end{code}


\section{Users account}

\subsection{Define roles}

    \_\_roles\_\_ = [
          {'name': 'admins', 'title': u'Admins', 'unit': u'Admin'},
          {'name': 'reviewers', 'title': u'Assistants',
           'unit': u'Assistant'}]




\section{Workflow in {\tt ikaaro}}

Developers of {\tt ikaaro} will have noticed the workflow definition from
the example above is taken from the workflow module. So {\tt ikaaro} comes
with a publication workflow out of the box. But the integration goes further.

The first point is the persistent storage. As usual in {\tt ikaaro}, we use
metadata to store the workflow state. The property is named {\em state}, so
you can call {\tt get\_property('state')} and {\tt set\_property('state',
statename)}.  The {\tt ikaaro} version of {\em WorkflowAware} exposes the
property {\em workflow\_state} as a shortcut.

{\em WorkflowAware} also offers a transition form, where the user sees the
current state, chooses from the available transitions, and can look up the
workflow history. The form tries to be as generic as possible so you don't
have to rewrite it.

The integration of the default workflow is spread out through the {\tt ikaaro}
classes.  For example, all File resources are {\em WorkflowAware}, but with a
little writing, you can set up a {\em WorkflowAware} Folder. The basic set up
is similar to the previous example:

\begin{code}
    from ikaaro.folder import Folder
    from ikaaro.workflow import WorkflowAware, workflow

    class Newsletter(Folder, WorkflowAware):
        workflow = workflow
\end{code}

The state is obviously indexed, under the {\em workflow\_state} name. But only
{\em WorkflowAware} instances will see their state indexed.

The workflow also influences the security, because the default access
control lists look up the state to allow or deny access. In the access module,
indeed, the ACL are written as follows.

\begin{itemize}

    \item {\em is\_allowed\_to\_view} access method:

    \begin{tabular}{l|c|c|c}
        Role & Private & Pending & Public\\
        \hline
        Anonymous &   &   & X\\
        \hline
        Logged in & X & X & X\\
        \hline
        Admin     & X & X & X\\
    \end{tabular}

    \item {\em is\_allowed\_to\_edit} and others access methods:

    \begin{tabular}{l|c|c|c}
        Role & Private & Pending & Public\\
        \hline
        Anonymous &   &   &  \\
        \hline
        Logged in & X &   &  \\
        \hline
        Admin     & X & X & X\\
    \end{tabular}

\end{itemize}

The access module also offers the RoleAware class, with two more roles: Member
and Reviewer. These roles allow finer access control lists. But this is
another story.


\section{Forms in {\tt ikaaro}}


\subsection{Introduction}

The {\tt ikaaro} framework contains powerful mechanisms which allow to manage
forms.  Theses mechanisms manage :

\begin{itemize}
  \item Fields that are mandatory or not
  \item Validity of fields (concern a Datatype) (example: Check if Email is
  valid)
  \item Deserialized the data (example transform a str to an Email object)
\end{itemize}

To manage forms, you always have to use two objects:

\begin{itemize}
  \item A schema that describes the data and their types
  \item A function to manage data post by the form.
\end{itemize}

We can place these two definitions in a single view, by example {\tt collect}.
We have the choice to implement this view:

\begin{itemize}
\item "From scratch" and we inherit from {\tt BaseForm}
\item "With a template support" and we inherit from {\tt STLForm}
\item "Auto-generated view" and we inherit from {\tt AutoForm}.
\end{itemize}

So, we must define a new view for our resource {\tt Root} and make the
association:

\begin{code}
class Root(BaseRoot):
    class_id = 'myroot'
    class_title = MSG(u'MY ROOT')

    collect = Collect_View()
\end{code}

With this code, we can access to our view via:

\begin{code}
    http://www.example.com/;collect
\end{code}

And now we must write {\tt Collect\_View}..


\subsection{An example that don't use advanced mechanisms}

With an inheritance from {\tt STLForm} we don't use advance {\tt ikaaro}
mechanisms, but the code remains concise.

We want to create a form that collect names.  The first step is to create the
template for the STL.  This file is "{\tt Root\_collect.xml.en}".  (Root
because we are in Root class and collect because we are in collect view).
Let's see the file's content (as you can see it's a basic form)

\begin{code}
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
      "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
    <stl:block xmlns="http://www.w3.org/1999/xhtml"
      xmlns:stl="http://www.hforge.org/xml-namespaces/stl">

      <form name="loginform" method="post" action=";collect">
          Your name : <br/>
          <input type="text" name="username" />
          <input type="submit" value="Submit" class="button_ok"/>
      </form>
    </stl:block>
\end{code}

The form's action is ";collect". This signifies that when the user click on
"submit", the view "collect" will collect data and manage them.

Now let's see the code:

\begin{code}
    # Import from itools
    from itools.gettext import MSG
    from itools.web import STLForm
    from itools.datatypes import Unicode

    # Import from ikaaro
    from ikaaro.registry import register_resource_class
    from ikaaro.root import Root as BaseRoot


    class Collect_View(STLForm):

        access = True
        template = '/ui/myapp/Root_collect.xml'

        schema = {'username': Unicode}

        def action(self, resource, context, form):
            print form


    class Root(BaseRoot):
        class_id = 'myroot'
        class_title = MSG(u'MY ROOT')

        collect = Collect_View()

    register_resource_class(Root)
\end{code}

The schema:

\begin{code}
        schema = {'username': Unicode}
\end{code}

is used to decode the value send by the user. In the same way you can do
encode it into Email datatype :

\begin{code}
    from itools.datatype import Email

    [...]

        schema = {'username': Email}
\end{code}

This operation check the field validity, and the method will raise an error if
the email is invalid with a message "There are 1 field(s) invalid.".

As you can see it's very easy but this example is not complex.  Let's see a
complex one.


\subsection{ A more complex example}

We always want to collect names. But we also want to collect email.
The name is mandatory, and we want to check if the email is valid.
For this kind of forms, {\tt ikaaro} is very useful.
We define a such template:

\begin{code}
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
      "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
    <stl:block xmlns="http://www.w3.org/1999/xhtml"
      xmlns:stl="http://www.hforge.org/xml-namespaces/stl">

      <form name="loginform" method="post" action=";collect">
        <label class="${username/class}" for="username" >Your name :</label>
        <br/>
        <input type="text" name="username" value="${username/value}"/><br/>

        <br/>

        <label class="${email/class}" for="email" >Your E-Mail :</label>
        <br/>
        <input type="text" name="email" value="${email/value}"/><br/>

        <br/><br/>

        <input type="submit" value="Submit" class="button_ok"/>
      </form>
    </stl:block>
\end{code}

The last example is built with a STL support, but without namespace. Now we
must make a namespace to replace {\tt \$\{username/class\}} \dots. It's very
easy, the {\tt STLForm} has yet a such function: {\tt self.build\_namespace}.

The first time, it returns:
\begin{code}
    {'email': {'class': None,
                'name': 'email',
               'value': None},
  'username': {'class': 'field_is_required',
                'name': 'username',
               'value': ''}}
\end{code}

Now, the new code of {\tt Collect\_View}:
\begin{code}
class Collect_View(STLForm):

    access = True
    template = '/ui/myapp/Root_collect.xml'

    schema = {'username': Unicode(mandatory=True),
              'email': Email}

    def get_namespace(self, resource, context):
        return self.build_namespace(resource, context)

    def action(self, resource, context, form):
        print form
\end{code}

When the FormError is raises, you know which fields are missing or invalid,
and you see a beautiful error message.

\subsection{The forms can be generate automatically}

You also can generate the template automatically.  It's useful for development
purposes, or to develop backoffice quickly.  You have to inherit from {\tt
AutoForm}and specify a schema with the list of html widget to use:

\begin{code}
    # Import from itools
    from itools.gettext import MSG
    from itools.web import STLForm
    from itools.datatypes import Unicode, Email

    # Import from ikaaro
    from ikaaro.registry import register_resource_class
    from ikaaro.root import Root as BaseRoot
    from ikaaro.forms import AutoForm, TextWidget



    class Collect_View(AutoForm):

        access = True
        title = MSG(u'Personal Informations')
        schema = {'username': Unicode(mandatory=True),
                  'email': Email}

        widgets=[TextWidget('username', title=MSG(u'Name')),
                 TextWidget('email', title=MSG(u'E-Mail'))]

        def action(self, resource, context, form):
            print form



    class Root(BaseRoot):
        class_id = 'myroot'
        class_title = MSG(u'MY ROOT')

        collect = Collect_View()

    register_resource_class(Root)
\end{code}

Here a list of widgets:

\begin{itemize}
  \item TextWidget
  \item ReadOnlyWidget
  \item CheckBoxWidget
  \item BooleanCheckBox
  \item BooleanRadio
  \item Select
  \item SelectRadio
  \item DateWidget
\end{itemize}

\end{document}
