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

import pathlib

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parent


class _AttrPathDict(dict):
  def __init__(self, root):
    super(_AttrPathDict, self).__init__()
    if isinstance(root, str):
      root = pathlib.Path(root).resolve()
    if not isinstance(root, pathlib.Path):
      raise TypeError()
    self._root = root

  def __setitem__(self, key, value):
    if key.isupper():
      if isinstance(value, str):
        value = (value,)
      if isinstance(value, (list, tuple)):
        value = pathlib.PurePath(*value)
      value = self._root.joinpath(value)
    super(_AttrPathDict, self).__setitem__(key, value)


def _PackageDataMeta(path):
  class _Meta(type):
    @classmethod
    def __prepare__(metacls, name, bases):
      origin = super(_Meta, _Meta).__prepare__(metacls=metacls,
                                               __name=name,
                                               __bases=bases)
      dict_ = _AttrPathDict(PACKAGE_ROOT.joinpath(path))
      if origin: dict_.update(origin)
      return dict_
  return _Meta


class Template(metaclass=_PackageDataMeta("data")):
  PY_INIT = "__init__.tmpl"
  PY_SETUP = "setup.tmpl"
