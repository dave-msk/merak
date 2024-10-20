from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import pathlib
import uuid


class LazyProperty(object):
  def __init__(self, function):
    self.function = function
    self.name = function.__name__

  def __get__(self, instance, owner):
    instance.__dict__[self.name] = self.function(instance)
    return instance.__dict__[self.name]


class FnCaller(object):
  def __init__(self, fn):
    self._fn = fn
    self._kwargs = {}

  def __setattr__(self, name, value):
    if not name.startswith("_"):
      self._kwargs[name] = value
    else:
      super(FnCaller, self).__setattr__(name, value)

  def __call__(self, *args, **kwargs):
    kw = dict(self._kwargs)
    kw.update(kwargs)
    return self._fn(*args, **kw)


def lock(fn):
  def locked_fn(self, *args, **kwargs):
    with self._lock:
      return fn(self, *args, **kwargs)
  return locked_fn


def walk(root, exts):
  for root_, _, files in os.walk(root):
    for f in files:
      _, ext = os.path.splitext(f)
      if ext in exts:
        file = os.path.join(root, f)
        print("File: {}, {}".format(os.path.isfile(file), file))
        yield os.path.join(root_, f)


def gen_var():
  return "_merak_import_var_{}".format(uuid.uuid4().hex)


def resolve(file):
  if isinstance(file, pathlib.Path): return file.resolve()
  return pathlib.Path(file).resolve()


def split_module(module):
  if isinstance(module, str):
    module = module.split(".")
  if isinstance(module, list):
    module = tuple(module)
  if not isinstance(module, tuple):
    raise TypeError()
  return module
