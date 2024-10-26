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

from merak.core import base
from merak.core import errors
from merak.core.refactor import ast_


class ModuleContext(base.MerakBase):
  """Context of a module.

  This class provides the information of the module a transform works on.
  It contains the following details:

    - path: Module path in tuple
    - index: Collection of all modules for `if module in ctx.index` queries
  """
  def __init__(self, path, index):
    self._path = path
    self._index = index

  @property
  def path(self):
    return self._path

  @property
  def index(self):
    return self._index


class Transform(base.MerakBase):
  """Source tramsform function.

  This class is the abstraction of the function: Source -> [Source...].
  It takes a single source and returns a list of sources that replaces
  the input in a Rewrite.

  Each descendant must implement the `_transform` method where the `source`
  argument is guaranteed to be a `Source` instance. The method can return
  None, a single `Source`, or a list of `Source`s. If None is returned by
  `_transform`, the input parameter is returned to the function caller

  The instantiation of a Transform requires a `ModuleContext` (`ctx`) which
  contains information of the module that the transform is working on.
  """
  def __init__(self, ctx):
    errors.typecheck(ctx, ModuleContext, arg_name="ctx")
    self._ctx = ctx

  def _transform(self, source):
    return None

  def __call__(self, source):
    errors.typecheck(source, ast_.Source, arg_name="source")
    srcs = self._transform(source)
    if srcs is None: srcs = source
    if isinstance(srcs, ast_.Source): srcs = [srcs]
    errors.typecheck(srcs, (tuple, list))
    for s in srcs: errors.typecheck(s, ast_.Source)
    return srcs


class ImportTransform(Transform):
  """Base class of Transforms that works on `Import`

  The core method is `_transform_import`, where the input is guaranteed
  to be an `Import`.
  """
  def _transform(self, source):
    if not isinstance(source, ast_.Import): return
    return self._transform_import(source)

  def _transform_import(self, source):
    pass


class ImportSplitter(ImportTransform):
  """Split imports into one alias per statement.

  This transform splits a multi-name import statement into multiple
  single name ones. For example:

  ```py
  # Input
  from a import b, c as cn, d
  import x.y, w.u.v

  # Output
  from a import b
  from a import c as cn
  from a import d
  import x.y
  import w.u.v
  ```
  """
  def _transform_import(self, source):
    names = source.names
    if len(names) == 1: return

    srcs = []
    for alias in names:
      srcs.append(ast_.Import(alias, from_=source.from_))
    return srcs


class ImportAbsolufier(ImportTransform):
  """Convert relative imports into absolute ones

  This transform converts relative imports into absolute import statements.
  For instance:

  ```py
  # Input (In module a.b.c)
  from ..e.f import g

  # Output
  from a.e.f import g
  ```
  """
  def _transform_import(self, source):
    target = source.from_
    if target is None or not target.startswith("."): return

    from_ = list(self._ctx.path)
    target_path = target.split(".")
    if not target_path[-1]: target_path.pop()

    for m in target_path:
      if not m:
        if not from_: return
        from_.pop()
        continue
      from_.append(m)
    return ast_.Import(source.names, from_=".".join(from_))
