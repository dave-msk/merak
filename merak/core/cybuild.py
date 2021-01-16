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

import io
import logging
import os
import shutil
import tempfile
import uuid

from merak.utils import refs
from merak.utils import subproc

SUFFIXES = {".py", ".pyx"}


def build_package_cython_extension(package_root,
                                   output_dir,
                                   force=False,
                                   sep="_"):
  logger = logging.getLogger(__name__)
  # 0. Create temporary directory
  with tempfile.TemporaryDirectory() as tmpdir:
    # 1. Copy package to temp dir
    logger.info("1. Copying package to temporary directory ...")
    package = os.path.basename(package_root)
    tmp_proot = os.path.join(tmpdir, package)
    tmp_pr_len = len(tmp_proot)
    shutil.copytree(package_root, tmp_proot)
    logging.info("1. Done!")

    # 2. Restructure package (in temp dir)
    logger.info("2. Restructuring package ...")
    # 2.1. Restructure package
    # 2.1.1. Get rename and subpackage information
    logger.info("2.1. Renaming Python modules ...")
    rel_paths = (os.path.join(r, f)[tmp_pr_len:].lstrip(os.path.sep)
                 for r, _, fs in os.walk(tmp_proot) for f in fs)
    renames, subpkgs = _analyze_structure(rel_paths, sep)

    # 2.1.2. Flatten files
    for dst, src in renames.items():
      if dst == src: continue
      shutil.move(os.path.join(tmp_proot, src),
                  os.path.join(tmp_proot, dst))
    logger.info("2.1. Done!")

    # 2.2. Inject finder to package `__init__` file
    #   If `__init__.py` and `__init__.pyx` both exists, `__init__.pyx`
    #   takes precedence.
    logger.info("2.2. Injecting finder to main `__init__` ...")

    # 2.2.1. Inject finder logic to the beginning of `__init__.pyx`
    package_init = os.path.join(tmp_proot, "__init__.pyx")
    if os.path.isfile(package_init):
      with open(package_init, "r") as fin:
        init_content = _inject_finder(fin, package, subpkgs, sep)
    else:
      init_content = _inject_finder([], package, subpkgs, sep)

    # 2.2.2. Write content to `__init__.pyx`
    with open(package_init, "w") as fout:
      fout.write(init_content)
    logger.info("2.2. Done!")

    # 3. Add setup file
    logger.info("3. Adding Cython setup file ...")
    with open(os.path.join(tmpdir, "setup.py"), "w") as fout:
      with open(refs.Template.PY_SETUP, "r") as fin:
        fout.write(fin.read().format(package=package))
    logger.info("3. Done!")

    # 4. Compile
    logger.info("4. Compiling package binary ...")
    cy_tmp = "cy_tmp_%s" % uuid.uuid4()
    cy_build = "cy_build_%s" % uuid.uuid4()
    subproc.run(
        ["python", "setup.py", "build_ext", "-b", cy_build, "-t", cy_tmp],
        cwd=tmpdir)
    logger.info("4. Done!")

    # 5. Copy build result to destination
    logger.info("5. Copying result to destination ...")
    os.makedirs(output_dir, exist_ok=True)
    target = os.path.join(output_dir, package)
    if force and os.path.exists(target):
      shutil.rmtree(target) if os.path.isdir(target) else os.remove(target)
    shutil.copytree(os.path.join(tmpdir, cy_build, package),
                    os.path.join(output_dir, package))
    logger.info("5. Done!")


def _analyze_structure(relative_paths, sep):
  init_suffix = "%s__init__" % sep
  init_suffix_len = len(init_suffix)
  subpkgs = set()
  renames = {}
  duplicated = []

  for p in relative_paths:
    name, ext = os.path.splitext(p)
    if ext not in SUFFIXES: continue
    dst = name.replace(os.path.sep, sep)
    if dst.endswith(init_suffix):
      dst = dst[:-init_suffix_len].rstrip(os.path.sep)
      subpkgs.add(name.replace(os.path.sep, ".")[:-9])
    dst += ".pyx"
    if dst in renames:
      # Duplicated module, both ".pyx" and ".py" exist
      duplicated.append((renames[dst], p))
    else:
      renames[dst] = p

  if duplicated:
    raise ModuleConflictError("Duplicated modules detected: {}"
                              .format(duplicated))

  return renames, subpkgs


def _inject_finder(code_lines, package, subpackages, sep):
  tops = []
  if code_lines:
    with io.StringIO() as ss:
      [tops.append(l) if l.startswith("from __future__ import") else ss.write(l)
       for l in code_lines]
      content = ss.getvalue()
  else:
    content = ""

  subpkgs = "{%s}" % ", ".join(
      "'%s.%s'" % (package, sp) for sp in sorted(subpackages))

  with io.StringIO() as ss:
    if tops: [ss.write(l) for l in tops + ["\n", "\n"]]
    with open(refs.Template.PY_INIT, "r") as fin:
      ss.write(fin.read().format(
          package=package,
          subpackages=subpkgs,
          sep=sep))
    ss.write(content)
    return ss.getvalue()


class ModuleConflictError(Exception):
  pass
