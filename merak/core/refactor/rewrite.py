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
import itertools

from merak.core import base
from merak.core import errors
from merak.core.refactor import ast_
from merak.core.refactor import transform


class Rewrite(base.MerakBase):
  """Rewrite details of an `ast` node.

  This class is a specification of rewriting the source code of a particular
  `ast` node. Each instance contains the target's location information and
  a set of `ast_.Source`s whose texts replace the original code.

  The actual code re-definition is done by the incoming `transform.Transform`s
  which define the refactoring strategies.
  """
  def __init__(self, lineno, end_lineno=0, col_offset=0):
    self._start = lineno
    self._end = max(end_lineno, lineno)
    self._offset = col_offset
    self._srcs = []

  def add(self, source):
    """Add source code to rewrite specification

    Args:
      source: `ast_.Source` instance
    """
    errors.typecheck(source, ast_.Source, arg_name="source")
    self._srcs.append(source)

  def transform(self, fn):
    """Transform rewrite code set

    Args:
      fn: Source code transform
    """
    errors.typecheck(fn, transform.Transform, arg_name="fn")
    self._srcs = list(itertools.chain.from_iterable(fn(s) for s in self._srcs))

  @property
  def text(self):
    indent = " " * self._offset
    return "".join("{}{}\n".format(indent, s.text) for s in self._srcs)

  @property
  def start(self):
    return self._start

  @property
  def end(self):
    return self._end

  @classmethod
  def from_node(cls, node):
    return cls(node.lineno,
               end_lineno=node.end_lineno,
               col_offset=node.col_offset)


class Plan(base.MerakBase):
  """Collection of Rewrites for a single source code file."""
  def __init__(self):
    self._rewrites = []

  def add(self, rewrite):
    """Add rewrite to plan

    Args:
      rewrite: Code rewrite specification
    """
    errors.typecheck(rewrite, Rewrite, arg_name="rewrite")
    self._rewrites.append(rewrite)

  def transform(self, fn):
    """Transform rewrites

    Args:
      fn: Source code transform
    """
    [rw.transform(fn) for rw in self._rewrites]

  def __iter__(self):
    return iter(sorted(self._rewrites, key=lambda r: r.start))


class RewritePlanVisitor(ast.NodeVisitor, base.MerakBase):
  """AST Node visitor with a rewrite plan"""
  def __init__(self, plan=None):
    errors.typecheck(plan, Plan, allow_none=True, arg_name="plan")
    self._plan = plan or Plan()

  @property
  def plan(self):
    return self._plan
