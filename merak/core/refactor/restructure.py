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
import collections
import io
import pathlib
import re
import shutil
import threading

from merak.core import base
from merak.core import errors
from merak.core.refactor import ast_
from merak.core.refactor import rewrite
from merak.core.refactor import transform
from merak.utils import misc


class PackageRestructurer(base.MerakBase):
  """Restructures a Python package

  Package is first indexed as modules, subpackages and package data, according
  to the following criteria:

    - Module: File with extension specified by `exts`
    - Subpackage: File named `__init__` with extension specified by `exts`
    - Package data: All other files


  """
  _FROM_FUTURE_RE = re.compile(r"^from\s+__future__\s+import.*")

  def __init__(self, package_root, exts):
    self._root = misc.resolve(package_root)
    self._index = ModuleIndex(package_root, exts)
    self._code_injections = {}
    self._mod_fns = []
    self._lock = threading.RLock()

  @misc.LazyProperty
  def _editors(self):
    return {m: Editor(f) for m, f in self._index.itermodules()}

  @property
  def modules(self):
    """Set of all modules under package."""
    return {".".join(self._get_restructured_path(m))
            for m in self._index if len(m) > 1}

  @property
  def subpackages(self):
    """Set of all subpackages under package."""
    return {".".join(m) for m, p in self._index.itermodules()
            if p.stem == "__init__"}

  @property
  def package(self):
    return self._root.stem

  def inject_code(self, module, code):
    """Injects code to beginning of module"""
    self._code_injections[misc.split_module(module)] = code

  def split_imports(self):
    """Split imports into one name per statement"""
    self._transform(misc.FnCaller(transform.ImportSplitter))

  def absolufy_imports(self):
    """Make all import paths absolute"""
    self._transform(misc.FnCaller(transform.ImportAbsolufier))

  def restructure_modules(self, fn):
    """Restructure modules via ModuleFn

    Args:
      fn: `ModuleFn`, redefines module path
    """
    errors.typecheck(fn, ModuleFn, arg_name="fn")
    self._mod_fns.append(fn)
    caller = misc.FnCaller(ImportModuleMover)
    caller.fn = fn
    self._transform(caller)

  def save_modules(self, dest=None):
    """Save updated modules

    This method only save source files. For package data, use `save_data`.

    Args:
      dest: Destination directory. If not specified, the original package
        location is used.
    """
    dest = misc.resolve(dest) if dest else self._root.parent
    file_to_mod = {}
    conflicts = collections.defaultdict(list)

    # Resolve destination path for modules
    for module, path in self._index.itermodules():
      rpath = self._construct_path(module).with_suffix(path.suffix)
      if rpath in file_to_mod:
        conflicts[rpath].append(".".join(module))
      else:
        file_to_mod[rpath] = module

    if conflicts:
      with io.StringIO() as msg:
        for rpath, mod_strs in conflicts.items():
          mod_strs.append(".".join(file_to_mod[rpath]))
          msg.write("{}: ({})\n".format(rpath, ", ".join(mod_strs)))
        raise errors.FileConflictError(
            "Conflicting restructured module paths:\n{}".format(msg))

    # Save modules
    for rpath, mod in file_to_mod.items():
      path = dest.joinpath(rpath)
      path.parent.mkdir(exist_ok=True, parents=True)
      path.write_text(self._construct_text(mod))

  def save_data(self, dest):
    """Save package data

    This method copies package data (i.e. non-source files) to destination.
    If destination is the same as parent of package root directory, no
    operation will be performed.

    Args:
      dest: Destination directory
    """
    dest = misc.resolve(dest)
    if dest == self._root.parent:
      self._logger.warning(
          "Destination same as data source. Package data copy skipped")
      return
    for rdst, src in self._index.iterdata():
      dst = dest.joinpath(rdst)
      dst.parent.mkdir(exist_ok=True, parents=True)
      shutil.copy2(str(src), str(dst))

  def read(self, module):
    """Read module source code

    The input is expected to be the import path of the target module in one of
    the following form:

      - String: "foo.a.b.c"
      - Split: ("foo", "a", "b", "c")

    Args:
      module: Module path, in string or split form
    """
    m = misc.split_module(module)
    return self._editors[m].text

  @misc.lock
  def _transform(self, caller):
    for m, e in self._editors.items():
      e.transform(caller(ctx=transform.ModuleContext(m, self._index)))

  def _get_restructured_path(self, module):
    module = misc.split_module(module)
    for fn in self._mod_fns: module = fn(module)
    return module

  def _construct_path(self, module):
    mod = self._get_restructured_path(module)
    if len(mod) == 1:
      return pathlib.PurePath(mod[0], "__init__")
    return pathlib.PurePath(*mod)

  def _construct_text(self, mod):
    if mod not in self._code_injections:
      return self._editors[mod].text

    tops = []
    editor_lines = []
    for line in self._editors[mod].text.splitlines(keepends=True):
      if self._FROM_FUTURE_RE.match(line):
        tops.append(line)
        continue
      editor_lines.append(line)

    with io.StringIO("".join(tops)) as sio:
      sio.write(self._code_injections[mod])
      sio.write("\n\n")
      sio.write("".join(editor_lines))
      return sio.getvalue()

class ImportModuleMover(transform.ImportTransform):
  """Rewrite import statements with moved modules

  This class takes a ModuleFn that accepts a module path and returns a
  new one in split format. Only absolute imports with target within the package
  (determined by context) are transformed. A
  """
  def __init__(self, ctx, fn):
    super(ImportModuleMover, self).__init__(ctx)
    errors.typecheck(fn, ModuleFlattenFn)
    self._fn = fn

  def _transform_import(self, source):
    from_ = source.from_
    if from_ is None:
      return self._process_import(source)
    return self._process_import_from(source)

  def _process_import(self, source):
    srcs = []
    for alias in source.names:
      parts = alias.name.split(".")
      if parts not in self._ctx.index:
        srcs.append(ast_.Import(alias))
        continue

      no_as = alias.asname is None
      as_ = misc.gen_var() if no_as else alias.asname

      srcs.append(ast_.Import.simple(parts[0], as_=alias.asname))
      for i in range(len(parts) - 1):
        srcs.append(self._import(self._fn(parts[:i+2]), as_=as_))
        if no_as:
          srcs.append(ast_.Assign(".".join(parts[:i+2]), as_))
      if no_as:
        srcs.append(ast_.Delete(as_))
    return srcs

  def _process_import_from(self, source):
    if source.from_.startswith("."): return
    parts = source.from_.split(".")
    if parts not in self._ctx.index: return

    srcs = []
    for alias in source.names:
      as_ = alias.asname or alias.name

      for i in range(len(parts)-1):
        srcs.append(self._import(self._fn(parts[:i+2]), as_=as_))

      full_mod = tuple(parts + [alias.name])
      if full_mod in self._ctx.index:
        srcs.append(self._import(self._fn(full_mod), as_=as_))
      else:
        srcs.append(ast_.Import.simple(
            alias.name,
            from_=".".join(self._fn(parts)),
            as_=alias.asname))
    return srcs

  def _import(self, mod, as_=None):
    from_ = None if len(mod) == 1 else ".".join(mod[:-1])
    return ast_.Import.simple(mod[-1], from_=from_, as_=as_)


class ModuleIndex(base.MerakBase):
  """Index of modules within a package

  The index mainly holds the following mapping:

    -   key: Absolute module path in split form. e.g.: ("foo", "a", "b")
    - value: `pathlib.Path` of module file

  The index also caches paths of package data (non-module files) under the root
  """
  def __init__(self, root, exts):
    self._root = misc.resolve(root)
    self._exts = set(exts)

  @misc.LazyProperty
  def modules(self):
    return self._index["mod"]

  @misc.LazyProperty
  def _data(self):
    return self._index["data"]

  @misc.LazyProperty
  def _index(self):
    # mod: ("mod", "path", "in", "tuple") -> fullpath
    # data: {data fullpath}
    mod, data = {}, set()
    for r, _, fs in self._root.walk():
      for f in fs:
        path = r.joinpath(f)
        if path.suffix in self._exts:
          mod[self.to_module(path)] = path
        else:
          data.add(path)
    return {"mod": mod, "data": data}

  def to_module(self, file):
    path = misc.resolve(file)
    try:
      relative_path = path.relative_to(self._root)
    except ValueError:
      return None
    if path.stem == "__init__":
      return (self._root.name, *relative_path.parts[:-1])
    return (self._root.name, *relative_path.parts[:-1], path.stem)

  def iterdata(self):
    yield from ((p.relative_to(self._root.parent), p) for p in self._data)

  def itermodules(self):
    yield from self.modules.items()

  def __contains__(self, key):
    if isinstance(key, str):
      key = key.split(".")
    if isinstance(key, list):
      key = tuple(key)
    return key in self.modules

  def __iter__(self):
    return iter(self.modules)

  def __getitem__(self, key):
    if isinstance(key, str):
      key = tuple(key.split("."))
    if key not in self.modules:
      raise KeyError(key)
    return self.modules[key]


class ModuleFn(base.MerakBase):
  """Redefine module location

  The module function is responsible for redefining a module's location.
  It accepts a module path, either in string or tuple/list (e.g. `"foo.a.b"`,
  `("foo", "a", "b")`), and returns a module path in the split (i.e. tuple/list)
  form.

  The core method is `_move` where the input is guaranteed to be a module path
  in the split form. If None is returned, the input is returned in the split
  form.
  """
  def _move(self, module):
    return

  def __call__(self, module):
    mod = module
    if isinstance(mod, str):
      mod = mod.split(".")
    if (not isinstance(mod, (tuple, list))
        or not all(isinstance(s, str) for s in mod)):
      raise TypeError()
    if any(m == "" for m in mod) or len(mod) < 2: return module
    dest = self._move(mod)
    if not dest: return mod
    if (not isinstance(dest, (tuple, list))
        or not all(isinstance(s, str) for s in dest)):
      raise TypeError()
    return dest


class ModuleFlattenFn(ModuleFn):
  """Flattens module paths

  Suppose a module has an absolute path "foo.a.b.c", with `sep="_"` and
  `prefix="___"` set, the resulting path would be "foo.___a_b_c"
  """
  def __init__(self, sep="_", prefix="___"):
    self._sep = sep
    self._prefix = prefix

  def _move(self, module):
    pkg = module[0]
    return pkg, "{}{}".format(self._prefix, self._sep.join(module[1:]))



class Editor(base.MerakBase):
  """Abstraction of loaded Python source file.

  This class is an abstraction of loaded Python source files. All import
  statements are extracted as rewrite items for transformations. The resulting
  text can be generated via the `Editor.text` property.
  """
  def __init__(self, file):
    self._file = misc.resolve(file)
    self._plan = None
    self._lock = threading.RLock()

  @property
  def text(self):
    it = iter(self.plan)
    with io.StringIO() as sout:
      try:
        rw = next(it)
      except StopIteration:
        rw = None
      for lineno, line in enumerate(self._orig_text.splitlines(keepends=True),
                                    start=1):
        if rw and lineno > rw.end:
          try:
            rw = next(it)
          except StopIteration:
            rw = None

        if rw is None or lineno < rw.start:
          sout.write(line)
        elif lineno == rw.start:
          sout.write(rw.text)
      return sout.getvalue()

  @property
  def plan(self):
    if self._plan is None:
      with self._lock:
        if self._plan is None:
          self.reset()
    return self._plan

  @misc.LazyProperty
  def _orig_text(self):
    return self._file.read_text()

  @misc.lock
  def reset(self):
    visitor = ImportCollectionVisitor()
    visitor.visit(ast.parse(self._orig_text))
    self._plan = visitor.plan

  def transform(self, fn):
    self.plan.transform(fn)

  def save(self, file=None):
    file = misc.resolve(file) if file else self._file
    file.write_text(self.text)


class ImportCollectionVisitor(rewrite.RewritePlanVisitor):
  """Collects all import nodes in a module as rewrite items"""
  def _add_import(self, node):
    rw = rewrite.Rewrite.from_node(node)
    rw.add(ast_.Import.from_node(node))
    self._plan.add(rw)

  def visit_Import(self, node):
    self._add_import(node)
    return self.generic_visit(node)

  def visit_ImportFrom(self, node):
    self._add_import(node)
    return self.generic_visit(node)
