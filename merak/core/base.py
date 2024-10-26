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

import logging

from merak.utils import misc


class LogMixin(object):
  """Provides logger with leaf class name"""
  @misc.LazyProperty
  def _logger(self):
    cls = type(self)
    name = "{}.{}".format(cls.__module__, cls.__qualname__)
    return logging.getLogger(name)


class MerakBase(LogMixin):
  """Base of classes in Merak package"""
  pass
