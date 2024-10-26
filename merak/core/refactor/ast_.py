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

import ast

from merak.core import base
from merak.core import errors


class Source(base.MerakBase):
  """Base class of Source code representation.

  This class mimics nodes defined in the standard `ast` library. This is
  used in source code analysis and refactoring.
  """
  @property
  def text(self):
    return ""


class Alias(Source):
  """Represents an `ast.alias` in an import statement."""
  def __init__(self, name, asname=None):
    self._name = name
    self._asname = asname

  @property
  def name(self):
    return self._name

  @property
  def asname(self):
    return self._asname

  @property
  def text(self):
    if self._asname: return "{} as {}".format(self._name, self._asname)
    return self._name

  @classmethod
  def from_node(cls, node):
    errors.typecheck(node, ast.alias)
    return cls(node.name, asname=node.asname)


class Import(Source):
  """Represents an import statement.

  This class takes care of both `ast.Import` and `ast.ImportFrom`, where
  `ast.Import` simply has `from_` set to None.

  A class method `simple` is provided to instantiate a single alias import
  statement for convenience.
  """
  def __init__(self, names, from_=None):
    if isinstance(names, (ast.alias, Alias)):
      names = [names]
    errors.typecheck(names, (list, tuple))
    names = [Alias.from_node(n) if isinstance(n, ast.alias) else n
             for n in names]
    for n in names: errors.typecheck(n, Alias)

    self._names = names
    self._from = from_

  @property
  def names(self):
    return list(self._names)

  @property
  def from_(self):
    return self._from

  @property
  def text(self):
    text = "import {}".format(", ".join(n.text for n in self._names))
    if self._from:
      text = "from {} {}".format(self._from, text)
    return text

  @classmethod
  def from_node(cls, node):
    errors.typecheck(node, (ast.Import, ast.ImportFrom), arg_name="node")
    if isinstance(node, ast.Import):
      return cls(node.names)
    return cls(node.names, from_="." * node.level + (node.module or ""))

  @classmethod
  def simple(cls, name, from_=None, as_=None):
    return cls(Alias(name, asname=as_), from_=from_)


class Assign(Source):
  """Represents an assignment statement (`ast.Assign`)"""
  def __init__(self, variable, value):
    self._var = variable
    self._val = value

  @property
  def text(self):
    return "{} = {}".format(self._var, self._val)


class Delete(Source):
  """Represents a delete statement (`ast.Delete`)"""
  def __init__(self, targets):
    ts = targets
    if isinstance(ts, str):
      ts = [s.strip() for s in targets.split(",")]
    if (not isinstance(ts, (tuple, list))
        or any(not isinstance(s, str) for s in ts)):
      raise TypeError()
    if not ts:
      raise ValueError()
    self._targets = ts

  @property
  def text(self):
    return "del {}".format(", ".join(self._targets))
