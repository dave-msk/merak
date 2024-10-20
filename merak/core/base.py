from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging

from merak.utils import misc


class LogMixin(object):
  @misc.LazyProperty
  def _logger(self):
    cls = type(self)
    name = "{}.{}".format(cls.__module__, cls.__qualname__)
    return logging.getLogger(name)


class MerakBase(LogMixin):
  pass
