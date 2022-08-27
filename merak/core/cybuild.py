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

import glob
import io
import logging
import os
import shutil
import subprocess
import tempfile
import uuid

import absolufy_imports as abs_imp
from rope.base import project as rope_project
from rope.base import change as rope_change
from rope.refactor import move as rope_move
from rope.refactor import rename as rope_rename

from merak.utils import refs
from merak.utils import rope_util
from merak.utils import subproc

SUFFIXES = {".py"}


def build_package_cython_extension(package_root,
                                   output_dir,
                                   force=False,
                                   sep="_",
                                   py_cmd="python"):
  logger = logging.getLogger(__name__)
  # 0. Create temporary directory
  with tempfile.TemporaryDirectory() as tmp_dir:
    # ---------------------------
    # 1. Copy package to temp dir
    # ---------------------------
    logger.info("1. Copying package to temporary directory ...")
    package = os.path.basename(package_root)
    tmp_proot = os.path.join(tmp_dir, package)
    shutil.copytree(package_root, tmp_proot)
    logging.info("1. Done!")

    # ------------------------------------
    # 2. Restructure package (in temp dir)
    # ------------------------------------
    logger.info("2. Restructuring package ...")

    # 2.0. Transform imports to absolute
    logger.info("2.0. Transforming imports to absolute ...")
    srcs = [tmp_dir]
    for suffix in SUFFIXES:
      for f in glob.glob(os.path.join(tmp_proot, "**/*%s" % suffix)):
        abs_imp.absolute_imports(f, srcs, never=False)
    logger.info("2.0. Done!")

    # 2.1. Modify package
    # 2.1.1. Restructure package and get modules and
    logger.info("2.1. Restructuring Python modules ...")
    mods, sub_pkgs = _restructure_package(tmp_proot, sep=sep)

    logger.info("2.1. Done!")

    # 2.2. Inject finder to package `__init__` file
    logger.info("2.2. Injecting finder to main `__init__` ...")

    # 2.2.1. Inject finder logic to the beginning of `__init__.py`
    package_init = os.path.join(tmp_proot, "__init__.py")
    if os.path.isfile(package_init):
      with open(package_init, "r") as fin:
        init_content = _inject_finder(fin, package, mods, sub_pkgs, sep)
    else:
      init_content = _inject_finder([], package, mods, sub_pkgs, sep)

    # 2.2.2. Write content to `__init__.py`
    with open(package_init, "w") as fout:
      fout.write(init_content)
    logger.info("2.2. Done!")

    # -----------------
    # 3. Add setup file
    # -----------------
    logger.info("3. Adding Cython setup file ...")
    with open(os.path.join(tmp_dir, "setup.py"), "w") as fout:
      with open(refs.Template.PY_SETUP, "r") as fin:
        fout.write(fin.read().format(package=package))
    logger.info("3. Done!")

    # ----------
    # 4. Compile
    # ----------
    logger.info("4. Compiling package binary ...")
    cy_tmp = "cy_tmp_%s" % uuid.uuid4()
    cy_build = "cy_build_%s" % uuid.uuid4()
    command = [py_cmd, "setup.py", "build_ext", "-b", cy_build, "-t", cy_tmp]
    logger.debug("Running command \"{}\" from directory \"{}\" ..."
                 .format(command, tmp_dir))
    result = subproc.run(command, cwd=tmp_dir)

    try:
      result.check_returncode()
    except subprocess.CalledProcessError:
      logger.error("Failed to compile package!")
      return False

    logger.info("4. Done!")

    # -----------------------------------
    # 5. Copy build result to destination
    # -----------------------------------
    logger.info("5. Copying result to destination ...")
    os.makedirs(output_dir, exist_ok=True)
    target = os.path.join(output_dir, package)
    if force and os.path.exists(target):
      shutil.rmtree(target) if os.path.isdir(target) else os.remove(target)
    shutil.copytree(os.path.join(tmp_dir, cy_build, package),
                    os.path.join(output_dir, package))
    logger.info("5. Done!")
    return True


def _inject_finder(code_lines, package, modules, subpackages, sep):
  tops = []
  if code_lines:
    with io.StringIO() as ss:
      [tops.append(l) if l.startswith("from __future__ import") else ss.write(l)
       for l in code_lines]
      content = ss.getvalue()
  else:
    content = ""

  with io.StringIO() as ss:
    if tops: [ss.write(l) for l in tops + ["\n", "\n"]]
    with open(refs.Template.PY_INIT, "r") as fin:
      ss.write(fin.read().format(
          package=package,
          modules=modules,
          subpackages=subpackages,
          sep=sep))
    ss.write(content)
    return ss.getvalue()


def _restructure_package(package_path, sep="_"):
  package_path = os.path.abspath(package_path)

  pkg_name = os.path.basename(package_path)
  offset = len(pkg_name) + len(os.path.sep)
  pkg_root = package_path[:-offset]

  project = rope_project.Project(pkg_root)
  pkg_rsrc = project.get_folder(pkg_name)
  spd_fct = rope_util.SubPathDetailFactory(offset=offset)

  extra_imps = {}
  sub_pkgs = []
  mods = []

  # 1st pass: Rename and move modules
  for r in sorted(project.get_python_files(),
                  key=rope_util.key_by_depth_and_mod,
                  reverse=True):
    path = r.path
    if not path.startswith(pkg_name): continue
    spd = spd_fct(r)
    if spd.fullname == "__init__": continue
    is_package = spd.name == "__init__"
    if is_package:
      r = r.parent
      spd = spd_fct(r)
      sub_pkgs.append(
          "%s.%s" % (pkg_name, spd.fullname.replace(rope_util.SEP, ".")))

    rn_target = "___" + spd.fullname.replace(rope_util.SEP, sep)
    mod_name = "%s.%s" % (pkg_name, rn_target)
    mods.append(mod_name)
    if is_package: sub_pkgs.append(mod_name)
    extra_imps[rn_target] = (
        "from {} import {} as {}".format(pkg_name, rn_target, spd.name))

    rename = rope_rename.Rename(project, r)
    rename_cs = rename.get_changes(rn_target)
    rename_cs.changes = [c for c in rename_cs.changes
                         if not (isinstance(c, rope_change.ChangeContents)
                                 and c.resource == r)]
    project.do(rename_cs)

    if not spd.at_root:

      r = project.get_resource(
          rope_util.SEP.join([os.path.dirname(r.path), rn_target + spd.ext]))
      move = rope_move.create_move(project, r)
      move_cs = move.get_changes(pkg_rsrc)
      project.do(move_cs)

    if r.is_folder():
      dirname = os.path.join(package_path, rn_target)
      shutil.move(os.path.join(dirname, "__init__.py"), dirname + ".py")
      shutil.rmtree(dirname)

  # 2nd pass: Add imports with original aliases
  matcher = rope_util.SubpackageImportNameMatcher(pkg_name)
  for r in project.get_python_files():
    sio = io.StringIO()
    for line in r.read().split(os.linesep):
      sio.write(line)
      sio.write(os.linesep)

      for name in matcher.match(line):
        if name in extra_imps:
          sio.write(extra_imps[name])
          sio.write(os.linesep)

    r.write(sio.getvalue())

  return mods, sub_pkgs
