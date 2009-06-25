#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) 2009 Juan David Ibáñez Palomar <jdavid@itaapy.com>
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
from datetime import date
from optparse import OptionParser
from subprocess import call

# Import from itools
from itools import __version__
from itools.core import get_pipe
from itools import vfs


def get_commits(target):
    """Returns a list with one tuple for every commit:

        [(<commit hash>, <days since today>), ...]
    """
    cwd = '%s/database' % target
    command = ['git', 'log', '--pretty=format:%H %ct']
    data = get_pipe(command, cwd=cwd)
    today = date.today()

    commits = []
    for line in data.splitlines():
        commit, seconds = line.split()
        delta = today - date.fromtimestamp(float(seconds))
        commits.append((commit, delta.days))

    return commits



def info(parser, target):
    # Get a list of the dates of every commit
    deltas = [ y for (x, y) in get_commits(target) ]
    total = len(deltas)
    if total == 0:
        print 'There is nothing to forget.'
        return

    # Count
    cum = []
    for delta in deltas:
        if cum and cum[-1][0] == delta:
            cum[-1] = (delta, cum[-1][1] + 1)
        else:
            cum.append((delta, 1))

    # Ok
    delta_w = len(str(cum[-1][0]))
    partial_w = len(str(total))
    cum.insert(0, (0, 0))
    msg = 'Remember {0:{1}} days to keep {2:{3}} commits: {4:3}%'
    partial = 0
    for delta, x in cum:
        partial += x
        per = (partial * 100) / total
        print msg.format(delta, delta_w, partial, partial_w, per)



def forget(parser, target, days):
    # Find out the commit to start from
    commits = get_commits(target)
    if len(commits) == 0:
        print 'There is nothing to forget.'
        return

    for commit in commits:
        since, delta = commit
        if delta > days:
            break

    # 1. Bootstrap new database
    print '(1) Bootstrap new database'
    vfs.make_folder('%s/database.new' % target)
    command = ['git', 'init']
    cwd = '%s/database.new' % target
    get_pipe(command, cwd=cwd)

    # 2. Export to new database
    print '(2) Export to new database (may take a while)'
    cwd = '%s/database' % target
    command = 'git fast-export %s.. | (cd ../database.new && git fast-import --quiet)'
    call(command % since, shell=True, cwd=cwd)

    # 3. Checkout
    print '(3) Checkout (may take a while)'
    cwd = '%s/database.new' % target
    command = ['git', 'checkout']
    get_pipe(command, cwd=cwd)

    # 4. Deploy new database
    print '(4) Deploy the new database'
    vfs.move('%s/database' % target, '%s/database.bak' % target)
    vfs.move('%s/database.new' % target, '%s/database' % target)



if __name__ == '__main__':
    # The command line parser
    usage = '%prog [OPTIONS] TARGET'
    version = 'itools %s' % __version__
    description = (
        'Forgets the old history from the Git archive, reducing disk space '
        'and improving performance.')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option('-d', '--days', type='int',
        help="How many days to remember (default is 28).")

    # Parse arguments
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('incorrect number of arguments')

    # Ok
    target = args[0]
    days = options.days
    if days is None:
        info(parser, target)
    else:
        forget(parser, target, days)
