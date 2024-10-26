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
import logging

from merak.commands import base
from merak.core import cybuild


class CythonizeCommand(base.Command):
  """Build binary Python package with Cython."""
  __command__ = "cythonize"

  arg_path = (["package"],
              dict(help="Python package path"))
  arg_output = (["output"],
                dict(help="Output directory"))
  arg_sep = (["-s", "--sep"],
             dict(default="_",
                  help="Module layer separator, must be Python identifier. "
                       "Defaults to '_'"))
  arg_force = (["-f", "--force"],
               dict(action="store_true",
                    default=False,
                    help="Force overwrite if target path exists"))
  arg_pycmd = (["--py-cmd"],
               dict(type=str,
                    default=os.environ.get("PYTHON_CMD", "python"),
                    dest="py_cmd",
                    help="Python interpreter to be used for building Cython "
                         "package. Defaults to value of environment variable "
                         "\"PYTHON_CMD\", or \"python\" if \"PYTHON_CMD\" not "
                         "specified."))

  def __call__(self, contr):
    super(CythonizeCommand, self).__call__(contr)
    logger = logging.getLogger(__name__)
    args = contr.app.pargs

    logger.info("Building binary package ...")
    builder = cybuild.CythonBuilder(args.package, {".py"}, sep=args.sep)
    try:
      builder.build(args.output, py_cmd=args.py_cmd, force=args.force)
    except Exception:
      logger.fatal("Package building failed")
      raise
    logger.info("Binary package built successfully!")


class Cythonize(base.Controller):
  class Meta:
    label = "cythonize"
    stacked_on = "base"
    stacked_type = "embedded"

  cmd_cythonize = CythonizeCommand()
