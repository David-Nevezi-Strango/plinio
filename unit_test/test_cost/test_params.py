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
# * Author: Daniele Jahier Pagliari <daniele.jahier@polito.it>                 *
# *----------------------------------------------------------------------------*
import unittest
import torchinfo
import torch.nn as nn
import random
from plinio.cost import params


class TestParams(unittest.TestCase):
    """Verify correctness of the params cost model, using torchinfo as reference."""

    def test_params_conv1d(self):
        cin = random.randint(1, 20)
        cout = random.randint(1, 20)
        k = random.randint(1, 20)
        # with bias
        conv = nn.Conv1d(cin, cout, k)
        self._compute_and_assert(conv, (random.randint(1, 20), cin, random.randint(k, 20)),
                                 "Error in Conv1d with bias")
        # without bias
        conv = nn.Conv1d(cin, cout, k, bias=False)
        self._compute_and_assert(conv, (random.randint(1, 20), cin, random.randint(k, 20)),
                                 "Error in Conv1d without bias")
        # depth-wise
        conv = nn.Conv1d(cin, cin, k, groups=cin)
        self._compute_and_assert(conv, (random.randint(1, 20), cin, random.randint(k, 20)),
                                 "Error in Conv1d depth-wise")

    def test_params_conv2d(self):
        cin = random.randint(1, 20)
        cout = random.randint(1, 20)
        kx = random.randint(1, 20)
        ky = random.randint(1, 20)
        # with bias
        conv = nn.Conv2d(cin, cout, (kx, ky))
        self._compute_and_assert(conv, (random.randint(1, 20), cin, random.randint(kx, 20), random.randint(ky, 20)),
                                 "Error in Conv2d with bias")
        # without bias
        conv = nn.Conv2d(cin, cout, (kx, ky), bias=False)
        self._compute_and_assert(conv, (random.randint(1, 20), cin, random.randint(kx, 20), random.randint(ky, 20)),
                                 "Error in Conv2d without bias")
        # depth-wise
        conv = nn.Conv2d(cin, cin, (kx, ky), groups=cin)
        self._compute_and_assert(conv, (random.randint(1, 20), cin, random.randint(kx, 20), random.randint(ky, 20)),
                                 "Error in Conv2d depth-wise")

    def test_params_linear(self):
        fin = random.randint(1, 20)
        fout = random.randint(1, 20)
        # with bias
        lin = nn.Linear(fin, fout)
        self._compute_and_assert(lin, (random.randint(1, 20), fin), "Error in linear with bias")
        # without bias
        lin = nn.Linear(fin, fout, bias=False)
        self._compute_and_assert(lin, (random.randint(1, 20), fin), "Error in linear without bias")

    def _compute_and_assert(self, layer, input_size, message):
        est_cost = params[type(layer), vars(layer)](vars(layer))
        model_summary = torchinfo.summary(layer, input_size, verbose=False)
        ref_cost = model_summary.total_params
        self.assertEqual(est_cost, ref_cost, message)


if __name__ == '__main__':
    unittest.main(verbosity=2)
