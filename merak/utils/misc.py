from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


class LazyProperty(object):
  def __init__(self, function):
    self.function = function
    self.name = function.__name__

  def __get__(self, instance, owner):
    instance.__dict__[self.name] = self.function(instance)
    return instance.__dict__[self.name]
