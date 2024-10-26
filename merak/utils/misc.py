# Copyright 2024 (David) Siu-Kei Muk. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
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
