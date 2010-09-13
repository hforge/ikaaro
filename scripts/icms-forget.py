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
from datetime import date, datetime
from optparse import OptionParser
from subprocess import call
from sys import exit
from traceback import print_exc

# Import from itools
from itools import __version__
from itools.core import get_pipe

# Import from ikaaro
from ikaaro.server import get_pid


def get_commits(target):
    """Returns a list with one tuple for every commit:

        [(<commit hash>, <days since today>), ...]
    """
    cwd = '%s/database' % target
    command = ['git', 'log', '--pretty=format:%H %at']
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



def forget(parser, target, options):
    # Find out the commit to start from
    commits = get_commits(target)
    if len(commits) == 0:
        print 'There is nothing to forget.'
        return

    if options.commits is not None:
        if len(commits) > options.commits:
            since = commits[options.commits][0]
        else:
            print 'There is nothing to forget'
            return
    else:
        if commits[len(commits) - 1][1] <= options.days:
            print 'There is nothing to forget.'
            return
        for commit in commits:
            since, delta = commit
            if delta > options.days:
                break

    # Check the server is not running
    pid = get_pid('%s/pid' % target)
    if pid is not None:
        print 'The server is running. Stop it before running this command.'
        return

    # Export to new database
    print '* Make new branch with shorter history (may take a while)'
    cwd = '%s/database' % target
    command = (
        'git fast-export --no-data --progress=1000 %s.. | '
        'sed "s|refs/heads/master|refs/heads/new|" | '
        'git fast-import --quiet')
    # FIXME This does not work if the error comes from git-fast-export,
    # because execution continues and sed returns 0. See the hack just below.
    returncode = call(command % since, shell=True, cwd=cwd)
    if returncode:
        exit()

    # Verify the step before was fine
    try:
        get_pipe(['git', 'log', '-n', '0', 'new'], cwd=cwd)
    except EnvironmentError:
        print_exc()
        exit()

    # Backup old branch and deploy new one
    print '* Deploy new branch and backup old branch'
    now = datetime.now().strftime('%Y%m%d%H%M')
    command = ['git', 'branch', '-m', 'master', now]
    get_pipe(command, cwd=cwd)
    command = ['git', 'branch', '-m', 'new', 'master']
    get_pipe(command, cwd=cwd)
    command = ['git', 'checkout', 'master']
    get_pipe(command, cwd=cwd)

    # Ok
    print 'Done. Backup branch is %s' % now



if __name__ == '__main__':
    # The command line parser
    usage = '%prog [OPTIONS] TARGET'
    version = 'itools %s' % __version__
    description = (
        'Forgets the old history from the Git archive, reducing disk space '
        'and improving performance.  If no options are giving, it will show '
        'some statistics.')
    parser = OptionParser(usage, version=version, description=description)
    parser.add_option('-d', '--days', type='int',
        help="How many days to remember.")
    parser.add_option('-c', '--commits', type='int',
        help="How many commits to keep")

    # Parse arguments
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error('incorrect number of arguments')
    if options.days is not None and options.commits is not None:
        parser.error('--days and --commits are mutually exclusive.')

    # Ok
    target = args[0]
    if options.days is None and options.commits is None:
        info(parser, target)
    else:
        forget(parser, target, options)
