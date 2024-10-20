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
  def _transform(self, source):
    if not isinstance(source, ast_.Import): return
    return self._transform_import(source)

  def _transform_import(self, source):
    pass


class ImportSplitter(ImportTransform):
  def _transform_import(self, source):
    names = source.names
    if len(names) == 1: return

    srcs = []
    for alias in names:
      srcs.append(ast_.Import(alias, from_=source.from_))
    return srcs


class ImportAbsolufier(ImportTransform):
  def _transform_import(self, source):
    target = source.from_
    if target is None or not target.startswith("."): return

    from_ = list(self._ctx.path)
    for m in target.split("."):
      if not m:
        if not from_: return
        from_.pop()
        continue
      from_.append(m)
    return ast_.Import(source.names, from_=".".join(from_))
