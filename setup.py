# -*- coding: UTF-8 -*-
# Copyright (C) 2004-2012 J. David Ibáñez <jdavid.ibp@gmail.com>
# Copyright (C) 2008 David Versmisse <versmisse@lil.univ-littoral.fr>
# Copyright (C) 2009 Hervé Cauwelier <herve@oursours.net>
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
from distutils.core import setup
from os.path import join as join_path
from pip.download import PipSession
from pip.req import parse_requirements
from setuptools import find_packages

if __name__ == '__main__':
    description = """A Content Management System built on Python & itools"""
    classifiers = [
      'Development Status :: 4 - Beta',
      'Intended Audience :: Developers',
      'License :: OSI Approved :: GNU General Public License (GPL)',
      'Programming Language :: Python',
      'Topic :: Internet',
      'Topic :: Internet :: WWW/HTTP',
      'Topic :: Software Development',
    ]
    packages = find_packages()
    scripts = [
      "scripts/icms-forget.py",
      "scripts/icms-init.py",
      "scripts/icms-start.py",
      "scripts/icms-stop.py",
      "scripts/icms-update.py",
      "scripts/icms-update-catalog.py"]
    install_requires = parse_requirements(
        'requirements.txt', session=PipSession())
    install_requires = [str(ir.req) for ir in install_requires]
    # The data files
    package_data = {'ikaaro': []}
    filenames = [ x.strip() for x in open('MANIFEST').readlines() ]
    filenames = [ x for x in filenames if not x.endswith('.py') ]
    for line in filenames:
        if not line.startswith('ikaaro/'):
            continue
        path = line.split('/')
        subpackage = 'ikaaro.%s' % (path[1])
        if subpackage in packages:
            files = package_data.setdefault(subpackage, [])
            files.append(join_path(*path[2:]))
        else:
            package_data['ikaaro'].append(join_path(*path[1:]))
    setup(name="ikaaro",
          version="1.0",
          # Metadata
          author="J. David Ibáñez",
          author_email="jdavid.ibp@gmail.com" ,
          license="GNU General Public License (GPL)",
          url="http://www.hforge.org/ikaaro",
          description=description,
          classifiers=classifiers,
          install_requires=install_requires,
          # Packages
          packages=packages,
          package_data=package_data,
          # Scripts
          scripts=scripts)
