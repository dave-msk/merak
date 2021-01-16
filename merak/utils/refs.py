# Copyright 2021 (David) Siu-Kei Muk. All Rights Reserved.
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


def _get_lib_root():
  root = os.path.join(os.path.dirname(__file__), "..")
  return os.path.abspath(root)


class _PrefixPathDict(dict):
  def __init__(self, prefix):
    super(_PrefixPathDict, self).__init__()
    self._prefix = prefix

  def __setitem__(self, key, value):
    if isinstance(value, str):
      value = os.path.join(self._prefix, value)
    super(_PrefixPathDict, self).__setitem__(key, value)


def _PackageDataMeta(prefix):
  class _Meta(type):
    @classmethod
    def __prepare__(metacls, name, bases):
      origin = super(_Meta, _Meta).__prepare__(metacls=metacls,
                                               __name=name,
                                               __bases=bases)
      pfx_path_dict = _PrefixPathDict(
          os.path.join(_get_lib_root(), prefix))
      if origin: pfx_path_dict.update(origin)
      return pfx_path_dict
  return _Meta


class Template(metaclass=_PackageDataMeta("data")):
  PY_INIT = "__init__.tmpl"
  PY_SETUP = "setup.tmpl"
