# *----------------------------------------------------------------------------*
# * Copyright (C) 2021 Politecnico di Torino, Italy                            *
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
# * Author:  Daniele Jahier Pagliari <daniele.jahier@polito.it>                *
# *----------------------------------------------------------------------------*

import torch
import torch.nn as nn
from torch.nn.parameter import Parameter
from .pit_binarizer import PITBinarizer


class PITTimestepMasker(nn.Module):
    """A nn.Module implementing the creation of timestep masks for PIT.

    Timestep masks are those that influence the layer receptive field.

    :param rf: the static (i.e., maximum) receptive field of the layer to be masked
    :type rf: int
    :param trainable: should the masks be trained, defaults to True
    :type trainable: bool, optional
    :param binarization_threshold: the binarization threshold, defaults to 0.5
    :type binarization_threshold: float, optional
    """
    def __init__(self,
                 rf: int,
                 trainable: bool = True,
                 binarization_threshold: float = 0.5):
        super(PITTimestepMasker, self).__init__()
        self.rf = rf
        self.beta = Parameter(
            torch.empty(self.rf, dtype=torch.float32).fill_(1.0), requires_grad=True)
        # this must be done after creating beta and gamma
        self.trainable = trainable
        self._binarization_threshold = binarization_threshold
        self._keep_alive = self._generate_keep_alive_mask()
        self._c_beta = self._generate_c_matrix()

    def forward(self) -> torch.Tensor:
        """The forward function that generates the binary masks from the trainable floating point
        shadow copies

        Implemented as described in the journal paper.

        :return: the binary masks
        :rtype: torch.Tensor
        """
        keep_alive_beta = torch.abs(self.beta) * (1 - self._keep_alive) + self._keep_alive
        theta_beta = torch.matmul(self._c_beta, keep_alive_beta)
        theta_beta = PITBinarizer.apply(theta_beta, self._binarization_threshold)
        return theta_beta

    def _generate_keep_alive_mask(self) -> torch.Tensor:
        """Method called at creation time, to generate a "keep-alive" mask vector.

        For timestep (i.e., rf) masking, the first mask element (beta_0) should always be preserved.

        :return: a binary keep-alive mask vector, with 1s corresponding to elements that should
        never be masked
        :rtype: torch.Tensor
        """
        ka_beta = torch.tensor([1.0] + [0.0] * (self.rf - 1), dtype=torch.float32)
        return ka_beta

    def _generate_c_matrix(self) -> torch.Tensor:
        """Method called at creation time, to generate the C_beta matrix.

        The C_beta matrix is used to combine different timestep mask elements (beta_i), as
        described in the journal paper.

        :return: the C_beta matrix as tensor
        :rtype: torch.Tensor
        """
        c_beta = torch.triu(torch.ones((self.rf, self.rf), dtype=torch.float32))
        return c_beta

    @property
    def trainable(self) -> bool:
        """Returns true if this mask is trainable

        :return: true if this mask is trainable
        :rtype: bool
        """
        return self.beta.requires_grad

    @trainable.setter
    def trainable(self, value: bool):
        """Set to true to make the channel masker trainable

        :param value: true to make the channel masker trainable
        :type value: bool
        """
        self.beta.requires_grad = value