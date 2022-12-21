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

from typing import Dict, Any, Optional, Iterator, Tuple, Type
import torch
import torch.fx as fx
import torch.nn as nn
from ..quantizer import Quantizer


# TODO: the quantizer assumes that both weights and activations are quantized
#       then both scale-factors will be available.
#       Need to understand how to manage this operation whether one of
#       weights and activations is not quantized.
# TODO: change name.
class MinMax_Bias(nn.Module, Quantizer):
    """A nn.Module implementing bias quantization.

    :param num_bits: quantization precision
    :type num_bits: int
    :param act_quantizer: activation quantizer
    :type act_quantizer: Quantizer
    :param weight_quantizer: weight quantizer
    :type weight_quantizer: Quantizer
    :param dequantize: whether the output should be fake-quantized or not
    :type dequantize: bool
    """
    def __init__(self,
                 num_bits: int,
                 act_quantizer: Type[Quantizer],
                 weight_quantizer: Type[Quantizer],
                 dequantize: bool = True):
        super(MinMax_Bias, self).__init__()
        self.num_bits = num_bits
        self.act_quantizer = act_quantizer
        self.weight_quantizer = weight_quantizer
        self.dequantize = dequantize
        self.register_buffer('s_b', torch.Tensor())

    def forward(self, input: torch.Tensor) -> torch.Tensor:
        """The forward function of the bias quantizer.

        Compute quantization using the scale-factors of weight and activations
        and implements STE for the backward pass

        :param input: the input float bias tensor
        :type input: torch.Tensor
        :return: the output fake-quantized bias tensor
        :rtype: torch.Tensor
        """
        s_a = self.weight_quantizer.s_a  # type: ignore
        s_w = self.weight_quantizer.s_w  # type: ignore
        self.s_b = s_a * s_w

        scaled_inp = input / self.s_b
        output = Round_STE.apply(scaled_inp)

        if self.dequantize:
            output = self.s_b * output

        return output

    @staticmethod
    def export(n: fx.Node, mod: fx.GraphModule, backend: Optional[str]):
        """Replaces a fx.Node corresponding to a Quantizer, with a "backend-aware" layer
        within a fx.GraphModule

        :param n: the node to be rewritten
        :type n: fx.Node
        :param mod: the parent module, where the new node has to be inserted
        :type mod: fx.GraphModule
        :param backend: an optional string specifying the target backend
        :type backend: Optional[str]
        """
        raise NotImplementedError("TODO")

    def summary(self) -> Dict[str, Any]:
        """Export a dictionary with the optimized layer quantization hyperparameters

        :return: a dictionary containing the optimized layer quantization hyperparameter values
        :rtype: Dict[str, Any]
        """
        return {
            'scale_factor': self.s_b,
        }

    def named_quant_parameters(
            self, prefix: str = '', recurse: bool = False) -> Iterator[Tuple[str, nn.Parameter]]:
        """Returns an iterator over the quantization parameters of this layer, yielding
        both the name of the parameter as well as the parameter itself

        :param prefix: prefix to prepend to all parameter names.
        :type prefix: str
        :param recurse: kept for uniformity with pytorch API,
        but Quantizer never have sub-layers TODO: check if true
        :type recurse: bool
        :return: an iterator over the quantization parameters of this layer
        :rtype: Iterator[nn.Parameter]
        """
        prfx = prefix
        prfx += "." if len(prefix) > 0 else ""
        for name, param in self.named_parameters(
                prfx + "bias_quantizer", recurse):
            yield name, param


class Round_STE(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        return torch.round(x)

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output, None
