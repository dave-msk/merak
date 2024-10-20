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
    """Set of all modules under package.
    """
    return {".".join(self._get_restructured_path(m))
            for m in self._index if len(m) > 1}

  @property
  def subpackages(self):
    return {".".join(m) for m, p in self._index.itermodules()
            if p.stem == "__init__"}

  @property
  def package(self):
    return self._root.stem

  def inject_code(self, module, code):
    self._code_injections[misc.split_module(module)] = code

  def split_imports(self):
    self._transform(misc.FnCaller(transform.ImportSplitter))

  def absolufy_imports(self):
    self._transform(misc.FnCaller(transform.ImportAbsolufier))

  def restructure_modules(self, fn):
    errors.typecheck(fn, ModuleFn, arg_name="fn")
    self._mod_fns.append(fn)
    caller = misc.FnCaller(ImportMover)
    caller.fn = fn
    self._transform(caller)

  def save_modules(self, root=None):
    root = misc.resolve(root) if root else self._root.parent
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
      path = root.joinpath(rpath)
      path.parent.mkdir(exist_ok=True, parents=True)
      path.write_text(self._construct_text(mod))

  def save_data(self, root):
    root = misc.resolve(root)
    if root == self._root.parent:
      # TODO: Add log message
      return
    for rdst, src in self._index.iterdata():
      dst = root.joinpath(rdst)
      dst.parent.mkdir(exist_ok=True, parents=True)
      shutil.copy2(str(src), str(dst))

  def read(self, module):
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

class ImportMover(transform.ImportTransform):
  def __init__(self, ctx, fn):
    super(ImportMover, self).__init__(ctx)
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
    if not dest: return module
    if (not isinstance(dest, (tuple, list))
        or not all(isinstance(s, str) for s in dest)):
      raise TypeError()
    return dest


class ModuleFlattenFn(ModuleFn):
  def __init__(self, sep="_", prefix="___"):
    self._sep = sep
    self._prefix = prefix

  def _move(self, module):
    pkg = module[0]
    return pkg, "{}{}".format(self._prefix, self._sep.join(module[1:]))



class Editor(base.MerakBase):
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
        if rw and lineno >= rw.end:
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
