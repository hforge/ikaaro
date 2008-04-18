# -*- coding: UTF-8 -*-
# Copyright (C) 2008 Sylvain Taverne <sylvain@itaapy.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.

# Import from itools
from itools.workflow.workflow import Workflow


# Workflow definition
order_workflow = Workflow()

# Specify the workflow states
order_workflow.add_state('open', title=u'Open', description=(u"Order open"))
order_workflow.add_state('close', title=u'Close', description=(u"Order close"))

# Cycle
order_workflow.add_trans('close_order', 'open', 'close',
      title=u"Close Order", description=u"Close the order")
order_workflow.add_trans('reopen_order', 'close', 'open',
      title=u"Re-Open", description=u"Re-open the order")

# Specify the initial state
order_workflow.set_initstate('open')
