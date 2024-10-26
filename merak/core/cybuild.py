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
import shutil
import subprocess
import tempfile
import threading
import uuid

from merak import datalib
from merak.core import base
from merak.core import refactor
from merak.utils import misc
from merak.utils import subproc


class CythonBuilder(base.MerakBase):
  def __init__(self, package_root, exts, sep="_"):
    self._pkg_rs = refactor.PackageRestructurer(package_root, exts)
    self._sep = sep
    self._processed = False
    self._lock = threading.RLock()

  @misc.lock
  def _process_package(self):
    self._logger.info("[Refactor] Started restructuring package ...")
    self._logger.info("[Refactor] Split imports")
    self._pkg_rs.split_imports()

    self._logger.info("[Refactor] Absolufy imports")
    self._pkg_rs.absolufy_imports()

    self._logger.info("[Refactor] Restructure modules")
    self._pkg_rs.restructure_modules(
        refactor.ModuleFlattenFn(sep=self._sep, prefix="___"))

    self._logger.debug("Package: {}".format(self._pkg_rs.package))
    self._logger.debug("Modules: [{}]".format(", ".join(self._pkg_rs.modules)))
    self._logger.debug(
        "Subpackages: [{}]".format(", ".join(self._pkg_rs.subpackages)))

    self._logger.info("[Refactor] Inject finder into __init__")
    finder_code = datalib.Template.PY_INIT.read_text().format(
        package=self._pkg_rs.package,
        modules=self._pkg_rs.modules,
        subpackages=self._pkg_rs.subpackages,
        sep=self._sep)
    self._pkg_rs.inject_code(self._pkg_rs.package, finder_code)
    self._processed = True
    self._logger.info("[Refactor] Done")

  def build(self, output, py_cmd="python", force=False):
    output = misc.resolve(output)
    if not self._processed:
      with self._lock:
        if not self._processed:
          self._process_package()

    with tempfile.TemporaryDirectory() as tmpdir:
      tmpdir = misc.resolve(tmpdir)

      # 1. Save modules to tmpdir
      self._pkg_rs.save_modules(tmpdir)

      # 2. Add setup.py
      tmpdir.joinpath("setup.py").write_text(
          datalib.Template.PY_SETUP.read_text().format(
              package=self._pkg_rs.package))

      # 3. Compile package as extension
      cy_tmp = "cy_tmp_{}".format(uuid.uuid4())
      cy_build = "cy_build_{}".format(uuid.uuid4())
      command = [py_cmd, "setup.py", "build_ext", "-b", cy_build, "-t", cy_tmp]
      result = subproc.run(command, cwd=str(tmpdir))

      try:
        result.check_returncode()
      except subprocess.CalledProcessError:
        raise
        # TODO: Add message
        # pass

      # 4. Copy build result to destination
      target = output.joinpath(self._pkg_rs.package)
      if force and target.exists():
        shutil.rmtree(str(target)) if target.is_dir() else os.remove(str(target))

      shutil.copytree(str(tmpdir.joinpath(cy_build, self._pkg_rs.package)),
                      str(target))

      # 5. Copy package data to destination
      self._pkg_rs.save_data(output)
