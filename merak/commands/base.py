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

import inspect
import logging
import types

import cement
import colorlog


class Controller(cement.Controller):
  def __init__(self, *args, **kwargs):
    super(Controller, self).__init__(*args, **kwargs)
    for k, cmd in vars(type(self)).items():
      if k.startswith("cmd_"):
        setattr(self, k[4:], types.MethodType(cmd, self))


class Command(object):
  __command__ = None
  __label__ = None

  arg_verbose = (["-v", "--verbose"],
                 dict(action="count",
                      default=0,
                      help="Log verbosity level. Default -> WARNING, "
                           "-v -> INFO, -vv or above -> DEBUG."))
  arg_color = (["-k", "--color"],
               dict(action="store_true",
                    default=False,
                    help="Display logging messages in colors."))

  def __new__(cls, *args, **kwargs):
    if not cls.__command__ or not isinstance(cls.__command__, str):
      raise NotImplementedError("'{}.__command__': {}"
                                .format(cls.__name__, cls.__command__))

    cmd = super(Command, cls).__new__(cls, *args, **kwargs)
    cmd.__name__ = cls.__command__
    return cement.ex(arguments=cls.arguments(),
                     label=cls.__label__,
                     **cls.parser_options())(cmd)

  @classmethod
  def parser_options(cls):
    return {"help": inspect.cleandoc(cls.__doc__)}

  @classmethod
  def arguments(cls):
    args = []
    memo = set()
    conflicts = set()
    for c in reversed(cls.mro()):
      for k, v in vars(c).items():
        if not k.startswith("arg_"): continue
        if k in memo: conflicts.add(k)
        memo.add(k)
        args.append(v)

    if conflicts:
      raise ArgumentConflictError("Conflicted arguments detected: {}"
                                  .format(sorted(k[4:] for k in conflicts)))

    return args

  @classmethod
  def expose(cls):
    if not cls.__command__ or not isinstance(cls.__command__, str):
      raise NotImplementedError("'{}.__command__': {}"
                                .format(cls.__name__, cls.__command__))
    cmd = cls()
    cmd.__name__ = cls.__command__
    return cement.ex(arguments=cls.arguments(),
                     label=cls.__label__,
                     **cls.parser_options())(cmd)

  def __call__(self, contr):
    verbose = min(contr.app.pargs.verbose, 2)
    level = [logging.WARNING, logging.INFO, logging.DEBUG][verbose]
    logger = logging.getLogger("merak")
    logger.propagate = False
    log_fmt = "%(asctime)s (%(levelname)s) %(name)s : %(message)s"

    if contr.app.pargs.color:
      log_colors = {
          "DEBUG": "cyan",
          "INFO": "green",
          "WARNING": "yellow",
          "ERROR": "red",
          "CRITICAL": "red,bg_white",
      }
      formatter = colorlog.ColoredFormatter(fmt="%(log_color)s" + log_fmt,
                                            log_colors=log_colors)
    else:
      formatter = logging.Formatter(fmt=log_fmt)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)


class ArgumentConflictError(Exception):
  pass
