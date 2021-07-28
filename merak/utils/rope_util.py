from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import re


SEP = "/"


class SubpackageImportNameMatcher(object):
  def __init__(self, package_name):
    py_id = "[a-zA-Z_][a-zA-Z0-9_]*"
    self._p = re.compile(r"from\s+({pkg}|\.+)(\.{py_id})*\s+import\s+(.*)"
                         .format(pkg=package_name, py_id=py_id))

  def match(self, line):
    m = self._p.match(line)
    if not m: return []
    return [name.split(" as ")[-1].strip()
            for name in m.groups()[-1].split(",")]


class SubPathDetailFactory(object):
  def __init__(self, offset=0):
    self._offset = offset

  def __call__(self, file_resource):
    return SubPathDetail(file_resource, offset=self._offset)


class SubPathDetail(object):
  def __init__(self, file_resource, offset=0):
    self._r = file_resource
    self._fullname, self._ext = os.path.splitext(file_resource.path[offset:])
    self._name = os.path.basename(self._fullname)

  @property
  def fullname(self):
    return self._fullname

  @property
  def name(self):
    return self._name

  @property
  def ext(self):
    return self._ext

  @property
  def at_root(self):
    return SEP not in self._fullname


def key_by_depth_and_mod(pyfile_resource):
  path = pyfile_resource.path
  dirname = os.path.dirname(path)
  basename = os.path.basename(path)
  name, _ = os.path.splitext(basename)
  init_flag = 0 if name == "__init__" else 1
  return path.count(SEP), dirname, init_flag, basename
