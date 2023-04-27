# *----------------------------------------------------------------------------*
# * Copyright (C) 2022 Politecnico di Torino, Italy                            *
# * SPDX-License-Identifier: Apache-2.0                                        *
# *                                                                            *
# * Licensed under the Apache License, Version 2.0 (the "License");            *
# * you may not use this file except in compliance with the License.           *
# * You may obtain a copy of the License at                                    *
# *                                                                            *
# * http://www.apache.org/licenses/LICENSE-2.0                                 *
# *                                                                            *
# * Unless required by applicable law or agreed to in writing, software        *
# * distributed under the License is distributed on an "AS IS" BASIS,          *
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.   *
# * See the License for the specific language governing permissions and        *
# * limitations under the License.                                             *
# *                                                                            *
# * Author:  Matteo Risso <matteo.risso@polito.it>                             *
# *----------------------------------------------------------------------------*

from enum import Enum, auto
from typing import cast, Dict, Tuple, Type

import torch
import torch.fx as fx
import torch.nn as nn

from plinio.methods.mixprec.quant.quantizers import Quantizer


class Backend(Enum):
    ONNX = auto()
    DORY = auto()
    DIANA = auto()
    # Add new backends here

    @classmethod
    def has_entry(cls, value) -> bool:
        return value.name in cls.__members__


class IntegerizationTracer(fx.Tracer):
    """Consider layers contained in `target_layers` as leaf modules.

    :param target_layers: modules that should be considered as a leaf
    :type target_layers: Tuple[Type[nn.Module]]
    """

    def __init__(self, target_layers: Tuple[Type[nn.Module], ...]):
        super().__init__()
        self.target_layers = target_layers

    def is_leaf_module(
        self,
        m: nn.Module,
        module_qualified_name: str
    ) -> bool:
        if isinstance(m, self.target_layers):
            return True
        if isinstance(m, Quantizer):
            return True
        else:
            return m.__module__.startswith('torch.nn') and \
                not isinstance(m, torch.nn.Sequential)


# N.B., ugly but is needed to avoid circular import
def get_map():
    from .dory.base import dory_layer_map

    # Add new supported backends here:
    maps = {
        'dory': dory_layer_map,
    }
    return maps


def backend_solver(layer: nn.Module, backend: Backend) -> nn.Module:
    """Depending on the specific `layer` and specified `backend` returns
    the appropriate backend-specific layer implementation.

    :param layer: the layer to be converted
    :type layer: nn.Module
    :param backend: the backend to be used
    :type backend: Backend
    :param backend: the specific backend to be used
    :type backend: Backend
    :return: the backend specific layer implementation
    :rtype: nn.Module
    """
    if Backend.has_entry(backend):
        backend_name = backend.name.lower()
        maps = get_map()
        layer_map = maps[backend_name]
        layer_map = cast(Dict, layer_map)
        if type(layer) in layer_map.keys():
            return layer_map[type(layer)]
        else:
            msg = f'Layer of type {type(layer)} is not supported by {backend_name} backend.'
            raise ValueError(msg)
    else:
        msg = f'The {backend} is not supported.'
        raise ValueError(msg)


def integerize_arch(model: nn.Module,
                    backend: Backend
                    ) -> nn.Module:
    """Convert a Fake Quantized model to a backend specific integer model

    :param model: the input Fake Quantized model
    :type model: nn.Module
    :param backend: the backend to be used
    :type backend: Backend
    """
    if Backend.has_entry(backend):
        backend_name = backend.name.lower()
        maps = get_map()
        layer_map = maps[backend_name]
        layer_map = cast(Dict, layer_map)
    else:
        msg = f'The {backend} is not supported.'
        raise ValueError(msg)
    target_layers = tuple(layer_map.keys())
    tracer = IntegerizationTracer(target_layers=target_layers)
    graph = tracer.trace(model.eval())
    name = model.__class__.__name__
    mod = fx.GraphModule(tracer.root, graph, name)
    modules = dict(mod.named_modules())
    # TODO: how to manage inp quantization????
    for n in mod.graph.nodes:
        m = modules.get(n.target)
        if isinstance(m, target_layers):
            m.export(n, mod, backend)
    mod.delete_all_unused_submodules()
    mod.graph.lint()
    mod.recompile()
    return mod
