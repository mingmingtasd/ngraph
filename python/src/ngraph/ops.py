# ******************************************************************************
# Copyright 2017-2020 Intel Corporation
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
# ******************************************************************************

"""Factory functions for all ngraph ops."""
import numpy as np

from ngraph.impl import AxisSet, AxisVector, Coordinate, CoordinateDiff, Function, Node, \
    Shape, Strides, util
from typing import List, Optional, Set, Union
from ngraph.impl.op import (GRN, MVN, ArgMax, ArgMin, BatchNormInference,
                            BatchNormTraining, Broadcast, Constant,
                            DepthToSpace, Dequantize, Dot, Gelu, Gemm,
                            GetOutputElement, HardSigmoid, Parameter, Quantize,
                            QuantizedConvolution, QuantizedDot, ReplaceSlice,
                            RNNCell, ScaleShift, ShuffleChannels, Slice,
                            SpaceToDepth)
from ngraph.utils.broadcasting import get_broadcast_axes
from ngraph.utils.decorators import binary_op, nameable_op, unary_op
from ngraph.utils.input_validation import assert_list_of_ints
from ngraph.utils.reduction import get_reduction_axes
from ngraph.utils.types import NumericType, NumericData, TensorShape, make_constant_node, \
    NodeInput, ScalarData, as_node, as_nodes
from ngraph.utils.types import get_dtype, get_element_type, get_element_type_str
from ngraph.utils.node_factory import NodeFactory


def _get_node_factory(opset_version=None):  # type: (Optional[str]) -> NodeFactory
    """Return NodeFactory configured to create operators from specified opset version."""
    if opset_version:
        return NodeFactory(opset_version)
    else:
        return NodeFactory()


@nameable_op
def parameter(shape, dtype=np.float32, name=None):
    # type: (TensorShape, NumericType, str) -> Parameter
    """Return an ngraph Parameter object."""
    assert_list_of_ints(shape, 'Parameter shape must be a list of integer values.')
    element_type = get_element_type(dtype)
    return Parameter(element_type, Shape(shape))


@nameable_op
def constant(value, dtype=None, name=None):  # type: (NumericData, NumericType, str) -> Constant
    """Create a Constant node from provided value.

    :param value: One of: array of values or scalar to initialize node with.
    :param dtype: The data type of provided data.
    :param name: Optional name for output node.
    :return: The Constant node initialized with provided data.
    """
    return make_constant_node(value, dtype)


@nameable_op
def ctc_greedy_decoder(data, sequence_mask, merge_repeated=True, name=None):
    # type: (NodeInput, NodeInput, bool, str) -> Node
    """Perform greedy decoding on the logits given in input (best path).

    :param data: Logits on which greedy decoding is performed.
    :param sequence_mask: The tensor with sequence masks for each sequence in the batch.
    :param merge_repeated: The flag for merging repeated labels during the CTC calculation.
    :param name: Optional name for output node.
    :return: The new node performing an CTCGreedyDecoder operation on input tensor.
    """
    node_inputs = as_nodes(data, sequence_mask)
    return _get_node_factory().create('CTCGreedyDecoder', node_inputs, {
        'ctc_merge_repeated': merge_repeated})


@nameable_op
def elu(data, alpha, name=None):  # type: (NodeInput, NumericType, str) -> Node
    """Perform Exponential Linear Unit operation element-wise on data from input node.

    Computes exponential linear: alpha * (exp(data) - 1) if < 0, data otherwise.

    For more information refer to:
    `Fast and Accurate Deep Network Learning by Exponential Linear Units (ELUs)
    <http://arxiv.org/abs/1511.07289>`_

    :param data: Input tensor. One of: input node, array or scalar.
    :param alpha: Scalar multiplier for negative values.
    :param name: Optional output node name.
    :return: The new node performing an ELU operation on its input data element-wise.
    """
    return _get_node_factory().create('Elu', [as_node(data)], {'alpha': alpha})


@nameable_op
def shuffle_channels(data, axis, groups, name=None):  # type: (Node, int, int, str) -> Node
    """Perform permutation on data in the channel dimension of the input tensor.

    The operation is the equivalent with the following transformation of the input tensor
    :code:`data` of shape [N, C, H, W]:

    :code:`data_reshaped` = reshape(:code:`data`, [N, group, C / group, H * W])

    :code:`data_trnasposed` = transpose(:code:`data_reshaped`, [0, 2, 1, 3])

    :code:`output` = reshape(:code:`data_trnasposed`, [N, C, H, W])

    For example:

    .. code-block:: python

        Inputs: tensor of shape [1, 6, 2, 2]

                data = [[[[ 0.,  1.], [ 2.,  3.]],
                         [[ 4.,  5.], [ 6.,  7.]],
                         [[ 8.,  9.], [10., 11.]],
                         [[12., 13.], [14., 15.]],
                         [[16., 17.], [18., 19.]],
                         [[20., 21.], [22., 23.]]]]

                axis = 1
                groups = 3

        Output: tensor of shape [1, 6, 2, 2]

                output = [[[[ 0.,  1.], [ 2.,  3.]],
                           [[ 8.,  9.], [10., 11.]],
                           [[16., 17.], [18., 19.]],
                           [[ 4.,  5.], [ 6.,  7.]],
                           [[12., 13.], [14., 15.]],
                           [[20., 21.], [22., 23.]]]]

    :param data: The node with input tensor.
    :param axis: Channel dimension index in the data tensor.
                 A negative value means that the index should be calculated
                 from the back of the input data shape.
    :param group:The channel dimension specified by the axis parameter
                 should be split into this number of groups.
    :param name: Optional output node name.
    :return: The new node performing a permutation on data in the channel dimension
             of the input tensor.
    """
    return ShuffleChannels(data, axis, groups)


@nameable_op
def squeeze(data, axes, name=None):  # type: (Node, NodeInput, str) -> Node
    """Perform squeeze operation on input tensor.

    Remove single-dimensional entries from the shape of a tensor.
    Takes a parameter :code:`axes` with a list of axes to squeeze.
    If :code:`axes` is not provided, all the single dimensions will be removed from the shape.
    If an :code:`axis` is selected with shape entry not equal to one, an error is raised.


    For example:

       Inputs: tensor with shape [1, 2, 1, 3, 1, 1], axes=[2, 4]

       Result: tensor with shape [1, 2, 3, 1]

    :param data: The node with data tensor.
    :param axes: List of non-negative integers, indicate the dimensions to squeeze.
                  One of: input node or array.
    :param name: Optional new name for output node.
    :return: The new node performing a squeeze operation on input tensor.
    """
    return _get_node_factory().create('Squeeze', [data, as_node(axes)])


def unsqueeze(data, axes, name=None):  # type: (Node, NodeInput, str) -> Node
    """Perform unsqueeze operation on input tensor.

    Insert single-dimensional entries to the shape of a tensor. Takes one required argument axes,
    a list of dimensions that will be inserted.
    Dimension indices in axes are as seen in the output tensor.

    For example: Inputs: tensor with shape [3, 4, 5], axes=[0, 4]
                 Result: tensor with shape [1, 3, 4, 5, 1]

    :param data: The node with data tensor.
    :param axes: List of non-negative integers, indicate the dimensions to be inserted.
                  One of: input node or array.
    :return: The new node performing an unsqueeze operation on input tensor.
    """
    return _get_node_factory().create('Unsqueeze', [data, as_node(axes)])


def grn(data, bias, name=None):  # type: (Node, float, str) -> Node
    r"""Perform Global Response Normalization with L2 norm (across channels only).

    Computes GRN operation on channels for input tensor:

    .. math:: output_i = \dfrac{input_i}{\sqrt{\sum_{i}^{C} input_i}}

    :param data: The node with data tensor.
    :param bias: The bias added to the variance. Scalar value.
    :param name: Optional output node name.
    :return: The new node performing a GRN operation on tensor's channels.
    """
    return GRN(data, bias)


@nameable_op
def gather(data, indices, axis, name=None):  # type: (NodeInput, NodeInput, NodeInput, str) -> Node
    """Return Gather node which takes slices from axis of data according to indices.

    :param data: The tensor from which slices are gathered.
    :param indices: Tensor with indexes to gather.
    :param axis: The dimension index to gather data from.
    :param name: Optional name for output node.
    :return: The new node performing a Gather operation on the data input tensor.
    """
    node_inputs = as_nodes(data, indices, axis)
    return _get_node_factory().create('Gather', node_inputs)


@nameable_op
def gather_tree(step_ids, parent_idx, max_seq_len, end_token, name=None):
    # type: (NodeInput, NodeInput, NodeInput, NodeInput, str) -> Node
    """Perform GatherTree operation.

    The GatherTree node generates the complete beams from the indices per each step
    and the parent beam indices.
    GatherTree uses the following logic:

    .. code-block:: python

        for batch in range(BATCH_SIZE):
            for beam in range(BEAM_WIDTH):
                max_sequence_in_beam = min(MAX_TIME, max_seq_len[batch])

                parent = parent_idx[max_sequence_in_beam - 1, batch, beam]

                for level in reversed(range(max_sequence_in_beam - 1)):
                    final_idx[level, batch, beam] = step_idx[level, batch, parent]

                    parent = parent_idx[level, batch, parent]


    :param step_ids: The tensor with indices from per each step.
    :param parent_idx: The tensor with with parent beam indices.
    :param max_seq_len: The tensor with maximum lengths for each sequence in the batch.
    :param end_token: The scalar tensor with value of the end marker in a sequence.
    :param name: Optional name for output node.
    :return: The new node performing a GatherTree operation.
    """
    node_inputs = as_nodes(step_ids, parent_idx, max_seq_len, end_token)
    return _get_node_factory().create('GatherTree', node_inputs)


@nameable_op
def group_convolution(data,                 # type: Node
                      filters,              # type: Node
                      strides,              # type: List[int]
                      pads_begin,           # type: List[int]
                      pads_end,             # type: List[int]
                      dilations,            # type: List[int]
                      auto_pad='EXPLICIT',  # type: str
                      name=None,            # type: str
                      ):
    # type: (...) -> Node
    """Perform Group Convolution operation on data from input node.

    :param data:        The node producing input data.
    :param filters:     The node producing filters data.
    :param strides:     The distance (in pixels) to slide the filter on the feature map
                        over the axes.
    :param pads_begin:  The number of pixels to add at the beginning along each axis.
    :param pads_end:    The number of pixels to add at the end along each axis.
    :param dilations:   The distance in width and height between elements (weights) in the filter.
    :param auto_pad:    Describes how to perform padding. Possible values:
                        EXPLICIT:   Pad dimensions are explicity specified
                        SAME_LOWER: Pad dimensions computed to match input shape
                                    Ceil(num_dims/2) at the beginning and
                                    Floor(num_dims/2) at the end
                        SAME_UPPER: Pad dimensions computed to match input shape
                                    Floor(num_dims/2) at the beginning and
                                    Ceil(num_dims/2) at the end
                        VALID:      No padding
    :param name: Optional output node name.
    :return: The new node performing a Group Convolution operation on tensor from input node.
    """
    return _get_node_factory().create('GroupConvolution',
                                      [data, filters],
                                      {'strides': strides,
                                       'pads_begin': pads_begin,
                                       'pads_end': pads_end,
                                       'dilations': dilations,
                                       'auto_pad': auto_pad.upper()})


@nameable_op
def group_convolution_backprop_data(data,                 # type: Node
                                    filters,              # type: Node
                                    strides,              # type: List[int]
                                    output_shape=None,    # type: Node
                                    pads_begin=None,      # type: List[int]
                                    pads_end=None,        # type: List[int]
                                    dilations=None,       # type: List[int]
                                    auto_pad='EXPLICIT',  # type: str
                                    output_padding=None,  # type: List[int]
                                    name=None,            # type: str
                                    ):
    # type: (...) -> Node
    """Perform Group Convolution operation on data from input node.

    :param data:            The node producing input data.
    :param filters:         The node producing filter data.
    :param strides:         The distance (in pixels) to slide the filter on the feature map
                            over the axes.
    :param output_shape:    The node that specifies spatial shape of the output.
    :param pads_begin:      The number of pixels to add at the beginning along each axis.
    :param pads_end:        The number of pixels to add at the end along each axis.
    :param dilations:       The distance in width and height between elements (weights)
                            in the filter.
    :param auto_pad:        Describes how to perform padding. Possible values:
                            EXPLICIT:   Pad dimensions are explicity specified
                            SAME_LOWER: Pad dimensions computed to match input shape
                                        Ceil(num_dims/2) at the beginning and
                                        Floor(num_dims/2) at the end
                            SAME_UPPER: Pad dimensions computed to match input shape
                                        Floor(num_dims/2) at the beginning and
                                        Ceil(num_dims/2) at the end
                            VALID:      No padding
    :param output_padding:  The additional amount of paddings added per each spatial axis
                            in the output tensor.
    :param name: Optional output node name.
    :return: The new node performing a Group Convolution operation on tensor from input node.
    """
    spatial_dim_count = len(strides)
    if dilations is None:
        dilations = [1] * spatial_dim_count
    if output_padding is None:
        output_padding = [0] * spatial_dim_count

    attributes = {'strides': strides,
                  'dilations': dilations,
                  'auto_pad': auto_pad.upper(),
                  'output_padding': output_padding}
    args = [data, filters]

    if output_shape is not None:
        args.append(output_shape)
    else:
        if pads_begin is None:
            pads_begin = [0] * spatial_dim_count
        if pads_end is None:
            pads_end = [0] * spatial_dim_count
        attributes['pads_begin'] = pads_begin
        attributes['pads_end'] = pads_end

    return _get_node_factory().create('GroupConvolutionBackpropData', args, attributes)


@nameable_op
def lstm_cell(X,                       # type: NodeInput
              initial_hidden_state,    # type: NodeInput
              initial_cell_state,      # type: NodeInput
              W,                       # type: NodeInput
              R,                       # type: NodeInput
              B,                       # type: NodeInput
              hidden_size,             # type: int
              activations=None,        # type: List[str]
              activations_alpha=None,  # type: List[float]
              activations_beta=None,   # type: List[float]
              clip=0.,                 # type: float
              name=None,               # type: str
              ):
    # type: (...) -> Node
    """Return a node which performs LSTMCell operation.

    :param X: The input tensor with shape: [batch_size, input_size].
    :param initial_hidden_state: The hidden state tensor with shape: [batch_size, hidden_size].
    :param initial_cell_state: The cell state tensor with shape: [batch_size, hidden_size].
    :param W: The weight tensor with shape: [4*hidden_size, input_size].
    :param R: The recurrence weight tensor with shape: [4*hidden_size, hidden_size].
    :param B: The bias tensor for gates with shape: [4*hidden_size].
    :param hidden_size: Specifies hidden state size.
    :param activations: The list of three activation functions for gates.
    :param activations_alpha: The list of alpha parameters for activation functions.
    :param activations_beta: The list of beta parameters for activation functions.
    :param clip: Specifies bound values [-C, C] for tensor clipping performed before activations.
    :param name: An optional name of the output node.

    :return: The new node represents LSTMCell. Node outputs count: 2.
    """
    if activations is None:
        activations = ['sigmoid', 'tanh', 'tanh']
    if activations_alpha is None:
        activations_alpha = []
    if activations_beta is None:
        activations_beta = []

    node_inputs = as_nodes(X, initial_hidden_state, initial_cell_state, W, R, B)

    # P - nGraph additional input, no such input in the OV spec
    peepholes_count = 3  # nGraph default
    peepholes_shape = [peepholes_count * hidden_size]
    peepholes_array = np.zeros(peepholes_shape)  # nGraph default
    data_dtype = get_dtype(node_inputs[0].get_output_element_type(0))
    default_P = make_constant_node(peepholes_array, dtype=data_dtype)
    node_inputs.append(default_P)

    weights_format = 'fico'  # IE LSTMWeightsFormat, no such attribute in the OV spec
    input_forget = False  # nGraph default, no such attribute in the OV spec

    attributes = {'hidden_size': hidden_size,
                  'activations': activations,
                  'activations_alpha': activations_alpha,
                  'activations_beta': activations_beta,
                  'clip': clip,
                  'weights_format': weights_format,
                  'input_forget': input_forget,
                  }
    return _get_node_factory().create('LSTMCell', node_inputs, attributes)


@nameable_op
def lstm_sequence(X,                       # type: NodeInput
                  initial_hidden_state,    # type: NodeInput
                  initial_cell_state,      # type: NodeInput
                  sequence_lengths,        # type: NodeInput
                  W,                       # type: NodeInput
                  R,                       # type: NodeInput
                  B,                       # type: NodeInput
                  hidden_size,             # type: int
                  direction,               # type: str
                  activations=None,        # type: List[str]
                  activations_alpha=None,  # type: List[float]
                  activations_beta=None,   # type: List[float]
                  clip=0.,                 # type: float
                  name=None,               # type: str
                  ):
    # type: (...) -> Node
    """Return a node which performs LSTMSequence operation.

    :param X: The input tensor. Shape: [seq_length, batch_size, input_size].
    :param initial_hidden_state:    The hidden state tensor.
                                    Shape: [num_directions, batch_size, hidden_size].
    :param initial_cell_state:      The cell state tensor.
                                    Shape: [num_directions, batch_size, hidden_size].
    :param sequence_lengths:        Specifies real sequence lengths for each batch element.
                                    Shape: [batch_size]. Integer type.
    :param W: Tensor with weights for matrix multiplication operation with input portion of data.
              Shape: [num_directions, 4*hidden_size, input_size].
    :param R: The tensor with weights for matrix multiplication operation with hidden state.
              Shape: [num_directions, 4*hidden_size, input_size].
    :param B: The tensor with biases.
              Shape: [num_directions, 4*hidden_size, hidden_size].
    :param hidden_size: Specifies hidden state size.
    :param direction: Specifies if the RNN is forward, reverse, or bidirectional.
    :param activations: The list of three activation functions for gates.
    :param activations_alpha: The list of alpha parameters for activation functions.
    :param activations_beta: The list of beta parameters for activation functions.
    :param clip: Specifies bound values [-C, C] for tensor clipping performed before activations.
    :param name: An optional name of the output node.

    :return: The new node represents LSTMSequence. Node outputs count: 3.
    """
    if activations is None:
        activations = ['sigmoid', 'tanh', 'tanh']
    if activations_alpha is None:
        activations_alpha = []
    if activations_beta is None:
        activations_beta = []

    node_inputs = as_nodes(
        X,
        initial_hidden_state,
        initial_cell_state,
        sequence_lengths,
        W,
        R,
        B)

    # P - nGraph additional input, no such input in the OV spec
    peepholes_count = 3  # nGraph default
    if direction.lower() == 'bidirectional':
        num_directions = 2
    else:
        num_directions = 1
    peepholes_shape = [num_directions, peepholes_count * hidden_size]
    peepholes_array = np.zeros(peepholes_shape)  # nGraph default
    data_dtype = get_dtype(node_inputs[0].get_output_element_type(0))
    default_P = make_constant_node(peepholes_array, dtype=data_dtype)
    node_inputs.append(default_P)

    weights_format = 'fico'  # IE LSTMWeightsFormat, no such attribute in the OV spec
    input_forget = False  # nGraph default, no such attribute in the OV spec

    attributes = {'hidden_size': hidden_size,
                  'direction': direction.lower(),
                  'activations': activations,
                  'activations_alpha': activations_alpha,
                  'activations_beta': activations_beta,
                  'clip': clip,
                  'weights_format': weights_format,
                  'input_forget': input_forget,
                  }
    return _get_node_factory().create('LSTMSequence', node_inputs, attributes)


@nameable_op
def gru_cell(X,                                  # type: NodeInput
             initial_hidden_state,               # type: NodeInput
             W,                                  # type: NodeInput
             R,                                  # type: NodeInput
             B,                                  # type: NodeInput
             hidden_size,                        # type: int
             activations=None,                   # type: List[str]
             activations_alpha=None,             # type: List[float]
             activations_beta=None,              # type: List[float]
             clip=0.,                            # type: float
             linear_before_reset=False,          # type: bool
             name=None,                          # type: str
             ):
    # type: (...) -> Node
    """Perform GRUCell operation on the tensor from input node.

    GRUCell represents a single GRU Cell that computes the output
    using the formula described in the paper: https://arxiv.org/abs/1406.1078

    Note this class represents only single *cell* and not whole *layer*.

    :param X:                       The input tensor with shape: [batch_size, input_size].
    :param initial_hidden_state:    The hidden state tensor at current time step with shape:
                                    [batch_size, hidden_size].
    :param W:                       The weights for matrix multiplication, gate order: zrh.
                                    Shape: [3*hidden_size, input_size].
    :param R:                       The recurrence weights for matrix multiplication.
                                    Shape: [3*hidden_size, hidden_size].
    :param B:                       The sum of biases (weight and recurrence).
                                    For linear_before_reset set True the shape is [4*hidden_size].
                                    Otherwise the shape is [3*hidden_size].
    :param hidden_size:             The number of hidden units for recurrent cell.
                                    Specifies hidden state size.
    :param activations:             The vector of activation functions used inside recurrent cell.
    :param activation_alpha:        The vector of alpha parameters for activation functions in
                                    order respective to activation list.
    :param activation_beta:         The vector of beta parameters for activation functions in order
                                    respective to activation list.
    :param clip:                    The value defining clipping range [-clip, clip] on input of
                                    activation functions.
    :param linear_before_reset:     Flag denotes if the layer behaves according to the modification
                                    of GRUCell described in the formula in the ONNX documentation.
    :param name:                    Optional output node name.
    :returns:   The new node performing a GRUCell operation on tensor from input node.
    """
    if activations is None:
        activations = ['relu', 'sigmoid', 'tanh']
    if activations_alpha is None:
        activations_alpha = []
    if activations_beta is None:
        activations_beta = []

    input_nodes = as_nodes(X, initial_hidden_state, W, R, B)
    attributes = {'hidden_size': hidden_size,
                  'activations': activations,
                  'activations_alpha': activations_alpha,
                  'activations_beta': activations_beta,
                  'linear_before_reset': linear_before_reset,
                  'clip': clip,
                  }
    return _get_node_factory().create('GRUCell', input_nodes, attributes)


@nameable_op
def rnn_cell(X,                      # type: NodeInput
             initial_hidden_state,   # type: NodeInput
             W,                      # type: NodeInput
             R,                      # type: NodeInput
             B,                      # type: NodeInput
             hidden_size,            # type: int
             activations,            # type: List[str]
             activations_alpha,      # type: List[float]
             activations_beta,       # type: List[float]
             clip=0.,                # type: float
             name=None,              # type: str
             ):
    # type: (...) -> Node
    """Perform RNNCell operation on tensor from input node.

    It follows notation and equations defined as in ONNX standard:
    https://github.com/onnx/onnx/blob/master/docs/Operators.md#RNN

    Note this class represents only single *cell* and not whole RNN *layer*.

    :param X:                       The input tensor with shape: [batch_size, input_size].
    :param initial_hidden_state:    The hidden state tensor at current time step with shape:
                                    [batch_size, hidden_size].
    :param W:                       The weight tensor with shape: [hidden_size, input_size].
    :param R:                       The recurrence weight tensor with shape: [hidden_size,
                                    hidden_size].
    :param B:                       The bias tensor for input gate with shape: [2*hidden_size].
    :param hidden_size:             The number of hidden units for recurrent cell.
                                    Specifies hidden state size.
    :param activations:             The vector of activation functions used inside recurrent cell.
    :param activation_alpha:        The vector of alpha parameters for activation functions in
                                    order respective to activation list.
    :param activation_beta:         The vector of beta parameters for activation functions in order
                                    respective to activation list.
    :param clip:                    The value defining clipping range [-clip, clip] on input of
                                    activation functions.
    :param name:                    Optional output node name.
    :returns:   The new node performing a RNNCell operation on tensor from input node.
    """
    if activations is None:
        activations = ['sigmoid', 'tanh']
    if activations_alpha is None:
        activations_alpha = []
    if activations_beta is None:
        activations_beta = []

    input_nodes = as_nodes(X, initial_hidden_state, W, R, B)
    attributes = {'hidden_size': hidden_size,
                  'activations': activations,
                  'activations_alpha': activations_alpha,
                  'activations_beta': activations_beta,
                  'clip': clip,
                  }
    return _get_node_factory().create('RNNCell', input_nodes, attributes)


@nameable_op
def scale_shift(data, scale, shift, name=None):  # type: (Node, Node, Node, str) -> Node
    r"""Perform ScaleShift transformation on input node.

    Computes ScaleShift:

    .. math:: Y = scale\cdot data + shift


    :param data: The node with data tensor.
    :param scale: The node with data tensor that scale input data.
    :param shift: The node with data tensor that shift input data.
    :param name: Optional output node name.
    :return: The new node performing a ScaleShift operation on input tensor.
    """
    return ScaleShift(data, scale, shift)


@nameable_op
def space_to_depth(data, mode, block_size, name=None):  # type: (Node, str, int, str) -> Node
    """Perform SpaceToDepth operation on the input tensor.

    SpaceToDepth rearranges blocks of spatial data into depth.
    The operator returns a copy of the input tensor where values from the height
    and width dimensions are moved to the depth dimension.

    :param data: The node with data tensor.
    :param mode: Specifies how the output depth dimension is gathered from block coordinates.

                 blocks_first: The output depth is gathered from [block_size, ..., block_size, C]
                 depth_first: The output depth is gathered from [C, block_size, ..., block_size]

    :param block_size: The size of the block of values to be moved. Scalar value.
    :param name: Optional output node name.
    :return: The new node performing a SpaceToDepth operation on input tensor.
    """
    return SpaceToDepth(data, mode, block_size)


@nameable_op
def batch_to_space(data, block_shape, crops_begin, crops_end, name=None):
    # type: (Node, NodeInput, NodeInput, NodeInput, str) -> Node
    """Perform BatchToSpace operation on the input tensor.

    BatchToSpace permutes data from the batch dimension of the data tensor into spatial dimensions.

    :param data: Node producing the data tensor.
    :param block_shape: The sizes of the block of values to be moved.
    :param crops_begin: Specifies the amount to crop from the beginning along each axis of `data`.
    :param crops_end: Specifies the amount to crop from the end along each axis of `data`.
    :param name: Optional output node name.
    :return: The new node performing a BatchToSpace operation.
    """
    return _get_node_factory().create('BatchToSpace', [data, as_node(block_shape),
                                                       as_node(crops_begin), as_node(crops_end)])


@nameable_op
def space_to_batch(data, block_shape, pads_begin, pads_end, name=None):
    # type: (Node, NodeInput, NodeInput, NodeInput, str) -> Node
    """Perform SpaceToBatch operation on the input tensor.

    SpaceToBatch permutes data tensor blocks of spatial data into batch dimension.
    The operator returns a copy of the input tensor where values from spatial blocks dimensions
    are moved in the batch dimension

    :param data: Node producing the data tensor.
    :param block_shape: The sizes of the block of values to be moved.
    :param pads_begin: Specifies the padding for the beginning along each axis of `data`.
    :param pads_end: Specifies the padding for the ending along each axis of `data`.
    :param name: Optional output node name.
    :return: The new node performing a SpaceToBatch operation.
    """
    return _get_node_factory().create('SpaceToBatch', [data, as_node(block_shape),
                                                       as_node(pads_begin), as_node(pads_end)])


@nameable_op
def mvn(data, axes, normalize_variance, eps, name=None):
    # type: (Node, Set[int], bool, float, str) -> Node
    r"""Perform Mean Variance Normalization operation on data from input node.

    Computes MVN on the input tensor :code:`data` (called `X`) using formula:

    .. math:: Y = \dfrac{X-EX}{\sqrt{E(X-EX)^2}}

    :param data: The node with data tensor.
    :param axes: A list of axes, along which to reduce. Array of integers.
    :param normalize_variance: Flag that denotes if mean values are shared across channels.
                               Boolen value.
    :param eps: The number added to the variance to avoid division by zero
               when normalizing the value. Scalar value.
    :param name: Optional output node name.
    :return: The new node performing a MVN operation on input tensor.
    """
    return MVN(data, AxisSet(axes), normalize_variance, eps)


@nameable_op
def quantize(data, scale, zero_point, new_type, axes, round_mode, name=None):
    # type: (Node, Node, Node, NumericType, Set[int], Quantize.RoundMode, str) -> Node
    r"""Perform quantize operation on data from input node.

    Computes quantize on the input tensor:

    .. math:: output = ROUND((input / scale) + zero\_point)

    :param data: The node with data tensor.
    :param scale: Scale used for mapping.
    :param zero_point: Zero point used for mapping.
    :param new_type: Output element type.
    :param round_mode: Number describes how to perform ROUND function.

                 ROUND_NEAREST_TOWARD_INFINITY: Round to nearest integer. In case of two
                 equidistant integers round away from zero e.g. 2.5 -> 3,  -3.5 -> -4

                 ROUND_NEAREST_TOWARD_ZERO: Round to nearest integer. In case of two equidistant
                 integers round toward zero e.g. 2.5 -> 2,  -3.5 -> -3

                 ROUND_NEAREST_UPWARD: Round to nearest integer. In case of two equidistant
                 integers round up e.g. 2.5 -> 2,  -3.5 -> -3

                 ROUND_NEAREST_DOWNWARD: Round to nearest integer. In case of two equidistant
                 integers round down e.g. 2.5 -> 2,  -3.5 -> -4

                 ROUND_NEAREST_TOWARD_EVEN: Round to nearest integer. In case of two equidistant
                 integers round down e.g. 2.5 -> 2,  -3.5 -> -4

                 ROUND_TOWARD_INFINITY: Round to nearest integer away from zero.

                 ROUND_TOWARD_ZERO: Round to nearest integer toward zero.

                 ROUND_UP: Round to nearest integer toward infinity (ceiling).

                 ROUND_DOWN: Round to nearest integer toward negative infinity (floor).

    :param name: Optional output node name.
    :return: The new node performing a quantize operation on input tensor.
    """
    new_element_type = get_element_type(new_type)
    return Quantize(data,
                    scale,
                    zero_point,
                    new_element_type,
                    AxisSet(axes),
                    round_mode)


@nameable_op
def dequantize(data, scale, zero_point, element_type, axes, name=None):
    # type: (Node, Node, Node, NumericType, Set[int], str) -> Node
    r"""Perform dequantize operation on data from input node.

    Computes dequantize on the input tensor:

    .. math:: output = (input - zero\_point) * scale

    :param data: The node with data tensor.
    :param scale: Scale used for mapping.
    :param zero_point: Zero point used for mapping.
    :param element_type: Output element type.
    :param name: Optional output node name.
    :return: The new node performing a dequantize operation on input tensor.
    """
    new_element_type = get_element_type(element_type)
    return Dequantize(data, scale, zero_point, new_element_type, AxisSet(axes))


@nameable_op
def quantized_convolution(data,                      # type: Node
                          filters,                   # type: Node
                          window_movement_strides,   # type: List[int]
                          window_dilation_strides,   # type: List[int]
                          padding_below,             # type: List[int]
                          padding_above,             # type: List[int]
                          data_dilation_strides,     # type: List[int]
                          input_scale,               # type: Node
                          input_zero_point,          # type: Node
                          filter_scale,              # type: Node
                          filter_zero_point,         # type: Node
                          output_scale,              # type: Node
                          output_zero_point,         # type: Node
                          output_type,               # type: NumericType
                          input_axes,                # type: Set[int]
                          filter_axes,               # type: Set[int]
                          output_axes,               # type: Set[int]
                          name=None,                 # type: str
                          ):
    # type: (...) -> Node
    r"""Perform quantized convolution operation on data from input node.

    :param data: The node producing the input data batch tensor.
    :param filters: The node producing the filters tensor.
    :param window_movement_strides: The window movement strides.
    :param window_dilation_strides: he window dilation strides.
    :param padding_below: The padding-below sizes.
    :param padding_above: The padding-above sizes.
    :param data_dilation_strides: The data dilation strides.
    :param input_scale: Scale to transform the input.
    :param input_zero_point: Zero point used for mapping.
    :param filter_scale: Scale to transform the filters.
    :param filter_zero_point: Zero point used for mapping.
    :param output_scale: Scale to transform the output.
    :param output_zero_point: Zero point used for mapping.
    :param output_type: Output element type.
    :param input_axes: Input axes set for channel wise quantization.
    :param filter_axes: Filter axes set for channel wise quantization.
    :param output_type: Output axes set for channel wise quantization.
    :param name: Optional output node name.
    :return: The new node performing a quantized convolution operation on input tensor.
    """
    new_output_type = get_element_type(output_type)
    return QuantizedConvolution(data,
                                filters,
                                Strides(window_movement_strides),
                                Strides(window_dilation_strides),
                                CoordinateDiff(padding_below),
                                CoordinateDiff(padding_above),
                                Strides(data_dilation_strides),
                                input_scale,
                                input_zero_point,
                                filter_scale,
                                filter_zero_point,
                                output_scale,
                                output_zero_point,
                                new_output_type,
                                AxisSet(input_axes),
                                AxisSet(filter_axes),
                                AxisSet(output_axes))


@nameable_op
def quantized_dot(input0,                      # type: Node
                  input1,                      # type: Node
                  reduction_axes_count,        # type: int
                  input0_scale,                # type: Node
                  input0_zero_point,           # type: Node
                  input1_scale,                # type: Node
                  input1_zero_point,           # type: Node
                  output_scale,                # type: Node
                  output_zero_point,           # type: Node
                  output_type,                 # type: NumericType
                  input0_axes,                 # type: Set[int]
                  input1_axes,                 # type: Set[int]
                  output_axes,                 # type: Set[int]
                  name=None,                   # type: str
                  ):
    # type: (...) -> Node
    r"""Perform quantized dot operation on data from input node.

    :param input0: The node producing the input data batch tensor.
    :param input1: The node producing the filters tensor.
    :param reduction_axes_count: Number of reduction axes.
    :param input0_scale: Scale to transform the input.
    :param input0_zero_point: Zero point used for mapping.
    :param input1_scale: Scale to transform the filters.
    :param input1_zero_point: Zero point used for mapping.
    :param output_scale: Scale to transform the output.
    :param output_zero_point: Zero point used for mapping.
    :param output_type: Output element type.
    :param input0_axes: Input0 axes set for channel wise quantization
    :param input1_axes: Input1 axes set for channel wise quantization
    :param output_axes: Output axes set for channel wise quantization
    :param name: Optional output node name.
    :return: The new node performing a quantized dot operation on input tensor.
    """
    new_output_type = get_element_type(output_type)
    return QuantizedDot(input0,
                        input1,
                        reduction_axes_count,
                        input0_scale,
                        input0_zero_point,
                        input1_scale,
                        input1_zero_point,
                        output_scale,
                        output_zero_point,
                        new_output_type,
                        AxisSet(input0_axes),
                        AxisSet(input1_axes),
                        AxisSet(output_axes))


# Unary ops
@unary_op
def absolute(node, name=None):  # type: (NodeInput, str) -> Node
    """Return node which applies f(x) = abs(x) to the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with Abs operation applied on it.
    """
    return _get_node_factory().create('Abs', [node])


@unary_op
def acos(node, name=None):  # type: (NodeInput, str) -> Node
    """Apply inverse cosine function on the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with arccos operation applied on it.
    """
    return _get_node_factory().create('Acos', [node])


@unary_op
def asin(node, name=None):  # type: (NodeInput, str) -> Node
    """Apply inverse sine function on the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with arcsin operation applied on it.
    """
    return _get_node_factory().create('Asin', [node])


@unary_op
def atan(node, name=None):  # type: (NodeInput, str) -> Node
    """Apply inverse tangent function on the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with arctan operation applied on it.
    """
    return _get_node_factory().create('Atan', [node])


@unary_op
def cos(node, name=None):  # type: (NodeInput, str) -> Node
    """Apply cosine function on the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with cos operation applied on it.
    """
    return _get_node_factory().create('Cos', [node])


@unary_op
def cosh(node, name=None):  # type: (NodeInput, str) -> Node
    """Apply hyperbolic cosine function on the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with cosh operation applied on it.
    """
    return _get_node_factory().create('Cosh', [node])


@unary_op
def sqrt(node, name=None):  # type: (NodeInput, str) -> Node
    """Return node which applies square root to the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: The new node with sqrt operation applied element-wise.
    """
    return _get_node_factory().create('Sqrt', [node])


@unary_op
def erf(node, name=None):  # type: (NodeInput, str) -> Node
    """Return node which calculates Gauss error function element-wise with given tensor.

    :param node: The node providing data for operation.
    :param name: The optional name for new output node.
    :return: The new node performing element-wise Erf operation.
    """
    return _get_node_factory().create('Erf', [node])


@unary_op
def exp(node, name=None):  # type: (NodeInput, str) -> Node
    """Return node which applies exponential function to the input node element-wise.

    :param node: The node providing data for operation.
    :param name: The optional name for new output node.
    :return: The new node performing natural exponential operation.
    """
    return _get_node_factory().create('Exp', [node])


@unary_op
def log(node, name=None):  # type: (NodeInput, str) -> Node
    """Return node which applies natural logarithm to the input node element-wise.

    :param node: The input node providing data for operation.
    :param name: The optional new name for output node.
    :return: The new node performing log operation element-wise.
    """
    return _get_node_factory().create('Log', [node])


@unary_op
def negative(node, name=None):  # type: (NodeInput, str) -> Node
    """Return node which applies f(x) = -x to the input node elementwise."""
    return _get_node_factory().create('Negative', [node])


@unary_op
def floor(node, name=None):  # type: (NodeInput, str) -> Node
    """Return node which applies floor to the input node element-wise.

    :param node: The input node providing data.
    :param name: The optional name for new output node.
    :return: The node performing element-wise floor operation.
    """
    return _get_node_factory().create('Floor', [node])


@unary_op
def ceiling(node, name=None):  # type: (NodeInput, str) -> Node
    """Return node which applies ceiling to the input node element-wise.

    :param node: The node providing data to ceiling operation.
    :param name: Optional name for output node.
    :return: The node performing element-wise ceiling.
    """
    return _get_node_factory().create('Ceiling', [node])


@nameable_op
def reshape(node, output_shape, special_zero, name=None):
    # type: (Node, Node, bool, str) -> Node
    """Return reshaped node according to provided parameters.

    :param node: The tensor we want to reshape.
    :param output_shape: The node with a new shape for input tensor.
    :param special_zero: The boolean variable that controls how zero values in shape are
                         interpreted. If special_zero is false, then 0 is interpreted as-is
                         which means that output shape will contain a zero dimension at the
                         specified location. Input and output tensors are empty in this case.
                         If special_zero is true, then all zeros in shape implies the copying
                         of corresponding dimensions from data.shape into the output shape.
                         Range of values: False or True
    """
    return _get_node_factory().create('Reshape',
                                      as_nodes(node, output_shape),
                                      {'special_zero': special_zero})


@unary_op
def relu(node, name=None):  # type: (NodeInput, str) -> Node
    """Perform rectified linear unit operation on input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: The optional output node name.
    :return: The new node performing relu operation on its input element-wise.
    """
    return _get_node_factory().create('Relu', [node])


@nameable_op
def selu(data, alpha, lambda_value, name=None):
    # type: (NodeInput, NodeInput, NodeInput, Optional[str]) -> Node
    """Perform a Scaled Exponential Linear Unit (SELU) operation on input node element-wise.

    :param data: input node, array or scalar.
    :param alpha: Alpha coefficient of SELU operation
    :param lambda_value: Lambda coefficient of SELU operation
    :param name: The optional output node name.
    :return: The new node performing relu operation on its input element-wise.
    """
    return _get_node_factory().create('Selu',
                                      [as_node(data), as_node(alpha), as_node(lambda_value)])


@unary_op
def sign(node, name=None):  # type: (NodeInput, str) -> Node
    """Perform element-wise sign operation.

    :param node: One of: input node, array or scalar.
    :param name: The optional new name for output node.
    :return: The node with mapped elements of the input tensor to -1 (if it is negative),
             0 (if it is zero), or 1 (if it is positive).
    """
    return _get_node_factory().create('Sign', [node])


@unary_op
def sin(node, name=None):  # type: (NodeInput, str) -> Node
    """Apply sine function on the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with sin operation applied on it.
    """
    return _get_node_factory().create('Sin', [node])


@unary_op
def sinh(node, name=None):  # type: (NodeInput, str) -> Node
    """Apply hyperbolic sine function on the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with sin operation applied on it.
    """
    return _get_node_factory().create('Sinh', [node])


@unary_op
def tan(node, name=None):  # type: (NodeInput, str) -> Node
    """Apply tangent function on the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with tan operation applied on it.
    """
    return _get_node_factory().create('Tan', [node])


# Binary ops
@binary_op
def divide(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which applies f(x) = A/B to the input nodes element-wise.

    :param left_node: The node providing dividend data.
    :param right_node: The node providing divisor data.
    :param auto_broadcast: Specifies rules used for auto-broadcasting of input tensors.
    :param name: Optional name for output node.
    :return: The node performing element-wise division.
    """
    return _get_node_factory().create('Divide',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def floor_mod(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node performing element-wise FloorMod (division reminder) with two given tensors.

    :param left_node: The first input node for FloorMod operation.
    :param right_node: The second input node for FloorMod operation.
    :param auto_broadcast: Specifies rules used for auto-broadcasting of input tensors.
    :param name: Optional name for output node.
    :return: The node performing element-wise FloorMod operation.
    """
    return _get_node_factory().create('FloorMod',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def mod(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node performing element-wise division reminder with two given tensors.

    :param left_node: The first input node for mod operation.
    :param right_node: The second input node for mod operation.
    :param auto_broadcast: Specifies rules used for auto-broadcasting of input tensors.
    :param name: Optional name for output node.
    :return: The node performing element-wise Mod operation.
    """
    return _get_node_factory().create('Mod',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def multiply(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which applies f(x) = A*B to the input nodes elementwise."""
    return _get_node_factory().create('Multiply',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast})


@binary_op
def subtract(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which applies f(x) = A-B to the input nodes element-wise.

    :param left_node: The node providing data for left hand side of operator.
    :param right_node: The node providing data for right hand side of operator.
    :param auto_broadcast: The type of broadcasting that specifies mapping of input tensor axes
                           to output shape axes. Range of values: numpy, explicit.
    :param name: The optional name for output node.
    :return: The new output node performing subtraction operation on both tensors element-wise.
    """
    return _get_node_factory().create('Subtract',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def add(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which applies f(x) = A+B to the input nodes element-wise."""
    return _get_node_factory().create('Add',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def minimum(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which applies the minimum operation to input nodes elementwise."""
    return _get_node_factory().create('Minimum',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def maximum(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which applies the maximum operation to input nodes elementwise."""
    return _get_node_factory().create('Maximum',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def power(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which perform element-wise exponentiation operation.

    :param left_node: The node providing the base of operation.
    :param right_node: The node providing the exponent of operation.
    :param name: The optional name for the new output node.
    :param auto_broadcast: The type of broadcasting specifies rules used for
                           auto-broadcasting of input tensors.
    :return: The new node performing element-wise exponentiation operation on input nodes.
    """
    return _get_node_factory().create('Power',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast})


# Logical ops
@binary_op
def equal(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which checks if input nodes are equal element-wise.

    :param left_node: The first input node for equal operation.
    :param right_node: The second input node for equal operation.
    :param auto_broadcast: The type of broadcasting specifies rules used for
                           auto-broadcasting of input tensors.
    :param name: The optional name for output new node.
    :return: The node performing element-wise equality check.
    """
    return _get_node_factory().create('Equal',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast})


@binary_op
def not_equal(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which checks if input nodes are unequal element-wise.

    :param left_node: The first input node for not-equal operation.
    :param right_node: The second input node for not-equal operation.
    :param auto_broadcast: The type of broadcasting specifies rules used for
                           auto-broadcasting of input tensors.
    :param name: The optional name for output new node.
    :return: The node performing element-wise inequality check.
    """
    return _get_node_factory().create('NotEqual',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast})


@binary_op
def greater(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which checks if left input node is greater than the right node element-wise.

    :param left_node: The first input node providing data.
    :param right_node: The second input node providing data.
    :param auto_broadcast: The type of broadcasting specifies rules used for
                           auto-broadcasting of input tensors.
    :param name: The optional new name for output node.
    :return: The node performing element-wise check whether left_node is greater than right_node.
    """
    return _get_node_factory().create('Greater',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast})


@binary_op
def greater_equal(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which checks if left node is greater or equal to the right node element-wise.

    :param left_node: The first input node providing data.
    :param right_node: The second input node providing data.
    :param auto_broadcast: The type of broadcasting specifies rules used for
                           auto-broadcasting of input tensors.
    :param name: The optional new name for output node.
    :return: The node performing element-wise check whether left_node is greater than or equal
             right_node.
    """
    return _get_node_factory().create('GreaterEqual',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast})


@binary_op
def less(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which checks if left input node is less than the right node element-wise.

    :param left_node: The first input node providing data.
    :param right_node: The second input node providing data.
    :param auto_broadcast: The type of broadcasting specifies rules used for
                           auto-broadcasting of input tensors.
    :param name: The optional new name for output node.
    :return: The node performing element-wise check whether left_node is less than the right_node.
    """
    return _get_node_factory().create('Less',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast})


@binary_op
def less_equal(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which checks if left input node is less or equal the right node element-wise.

    :param left_node: The first input node providing data.
    :param right_node: The second input node providing data.
    :param auto_broadcast: The type of broadcasting specifies rules used for
                           auto-broadcasting of input tensors.
    :param name: The optional new name for output node.
    :return: The node performing element-wise check whether left_node is less than or equal the
             right_node.
    """
    return _get_node_factory().create('LessEqual',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast})


@binary_op
def logical_and(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which perform logical and operation on input nodes element-wise.

    :param left_node: The first input node providing data.
    :param right_node: The second input node providing data.
    :param auto_broadcast: The type of broadcasting that specifies mapping of input tensor axes
                           to output shape axes. Range of values: numpy, explicit.
    :param name: The optional new name for output node.
    :return: The node performing logical and operation on input nodes corresponding elements.
    """
    return _get_node_factory().create('LogicalAnd',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def logical_or(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which performs logical OR operation on input nodes element-wise.

    :param left_node: The first input node providing data.
    :param right_node: The second input node providing data.
    :param auto_broadcast: The type of broadcasting that specifies mapping of input tensor axes
                           to output shape axes. Range of values: numpy, explicit.
    :param name: The optional new name for output node.
    :return: The node performing logical or operation on input nodes corresponding elements.
    """
    return _get_node_factory().create('LogicalOr',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@binary_op
def logical_xor(left_node, right_node, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Return node which performs logical XOR operation on input nodes element-wise.

    :param left_node: The first input node providing data.
    :param right_node: The second input node providing data.
    :param auto_broadcast: The type of broadcasting that specifies mapping of input tensor axes
                           to output shape axes. Range of values: numpy, explicit.
    :param name: The optional new name for output node.
    :return: The node performing logical or operation on input nodes corresponding elements.
    """
    return _get_node_factory().create('LogicalXor',
                                      [left_node, right_node],
                                      {'auto_broadcast': auto_broadcast.upper()})


@unary_op
def logical_not(node, name=None):  # type: (Node, str) -> Node
    """Return node which applies element-wise logical negation to the input node.

    :param node: The input node providing data.
    :param name: The optional new name for output node.
    :return: The node performing element-wise logical NOT operation with given tensor.
    """
    return _get_node_factory().create('LogicalNot', [node])


@binary_op
def squared_difference(x1, x2, auto_broadcast='NUMPY', name=None):
    # type: (NodeInput, NodeInput, str, Optional[str]) -> Node
    """Perform an element-wise squared difference between two tensors.

    .. math:: y[i] = (x_1[i] - x_2[i])^2

    :param x1: The node with first input tensor.
    :param x2: The node with second input tensor.
    :param auto_broadcast: The type of broadcasting that specifies mapping of input tensor axes
                           to output shape axes. Range of values: numpy, explicit.
    :param name: Optional new name for output node.
    :return: The new node performing a squared difference between two tensors.
    """
    return _get_node_factory().create('SquaredDifference',
                                      [x1, x2],
                                      {'auto_broadcast': auto_broadcast.upper()})


# Extend Node class to support binary operators
Node.__add__ = add
Node.__sub__ = subtract
Node.__mul__ = multiply
Node.__div__ = divide
Node.__truediv__ = divide
Node.__radd__ = lambda left, right: add(right, left)
Node.__rsub__ = lambda left, right: subtract(right, left)
Node.__rmul__ = lambda left, right: multiply(right, left)
Node.__rdiv__ = lambda left, right: divide(right, left)
Node.__rtruediv__ = lambda left, right: divide(right, left)
Node.__eq__ = equal
Node.__ne__ = not_equal
Node.__lt__ = less
Node.__le__ = less_equal
Node.__gt__ = greater
Node.__ge__ = greater_equal


# Custom ops
@nameable_op
def broadcast(data, target_shape, axes_mapping=None, broadcast_spec='NUMPY', name=None):
    # type: (Node, NodeInput, Optional[NodeInput], str, Optional[str]) -> Node
    """Create a node which broadcasts the input node's values along specified axes to a desired shape.

    :param data: The node with input tensor data.
    :param target_shape: The node with a new shape we want to broadcast tensor to.
    :param axes_mapping: The node with a axis positions (0-based) in the result
                           that are being broadcast.
    :param broadcast_spec: The type of broadcating that specifies mapping of input tensor axes
                           to output shape axes. Range of values: NUMPY, EXPLICIT, BIDIRECTIONAL.
    :param name: Optional new name for output node.
    :return: New node with broadcast shape.
    """
    inputs = [data, as_node(target_shape)]
    if broadcast_spec.upper() == 'EXPLICIT':
        inputs.append(as_node(axes_mapping))
    return _get_node_factory().create('Broadcast',
                                      inputs,
                                      {'broadcast_spec': broadcast_spec.upper()})


@nameable_op
def broadcast_to(node, new_shape, axis=None, name=None):
    # type: (Node, TensorShape, int, str) -> Node
    """Create a node which broadcasts the input node's values to a desired shape.

    `broadcast_to` will attempt to automatically determine which axes need broadcasting.

    The optional `axis` parameter specifies the starting axis position (0-based) in the output
    shape from which the current shape of the tensor matches the desired new shape.

    e.g. current_shape: [4, 5], new_shape: [2, 3, 4, 5, 6], axis: 2

    By using the `axis` parameter you can control which output axis to broadcast along.

    Example:

    >>> input_node = ng.constant([1, 2, 3])
    >>> current_shape = [3]
    >>> new_shape = [3, 3]
    >>> ng.broadcast_to(input_node, new_shape, axis=1)
    array([[1, 2, 3],
           [1, 2, 3],
           [1, 2, 3]])

    >>> ng.broadcast_to(input_node, new_shape, axis=0)
    array([[1, 1, 1],
           [2, 2, 2],
           [3, 3, 3]])

    If the `axis` parameter is not specified, `broadcast_to` will attempt to match shapes,
    assuming the current shape matches the rightmost positions of the desired new shape.
    This behaviour is similar to NumPy's broadcasting.

    i.e. default `axis = len(new_shape) - len(current_shape)`

    :param node: The node with input tensor data.
    :param new_shape: The new shape we want to broadcast tensor to.
    :param axis: The axis along which we perform broadcasting.
    :param name: Optional new name for output node.
    :return: New node with broadcast shape.
    """
    return Broadcast(node, Shape(new_shape), get_broadcast_axes(new_shape, node.shape, axis))


@nameable_op
def fake_quantize(data, input_low, input_high, output_low, output_high,
                  levels, auto_broadcast='NUMPY', name=None):
    # type: (Node, Node, Node, Node, Node, int, str, str) -> Node
    r"""Perform an element-wise linear quantization on input data.

    Input floating point values are quantized into a discrete set of floating point values.

    .. code-block:: python
        if x <= input_low:
            output = output_low
        if x > input_high:
            output = output_high
        else:
            output = fake_quantize(output)

    Fake quantize uses the following logic:

    .. math:: output =
            \dfrac{round( \dfrac{data - input\_low}{(input\_high - input\_low)\cdot (levels-1)})}
            {(levels-1)\cdot (output\_high - output\_low)} + output\_low

    :param data:           The node with data tensor.
    :param input_low:      The node with the minimum for input values.
    :param input_high:     The node with the maximum for input values.
    :param output_low:     The node with the minimum quantized value.
    :param output_high:    The node with the maximum quantized value.
    :param levels:         The number of quantization levels. Integer value.
    :param auto_broadcast: The type of broadcasting specifies rules used for
                           auto-broadcasting of input tensors.
    :return: New node with quantized value.
    """
    return _get_node_factory().create('FakeQuantize',
                                      [data, input_low, input_high, output_low, output_high],
                                      {'levels': levels, 'auto_broadcast': auto_broadcast})


@nameable_op
def gemm(A,                      # type: Node
         B,                      # type: Node
         C,                      # type: Node
         alpha,                  # type: ScalarData
         beta,                   # type: ScalarData
         transA,                 # type: bool
         transB,                 # type: bool
         name=None,              # type: str
         ):
    # type: (...) -> Node
    r"""Perform General matrix-matrix multiplication on input tensors A, B and C.

    Computes:

    .. math:: Y = alpha\cdot A'\cdot B' +  beta\cdot C

    :code:`A'` is the transpose of matrix :code:`A` with shape (M, K),
    if :code:`transA` is :code:`True`, otherwise :code:`A` with shape (K, N).

    :code:`B'` is the transpose of matrix :code:`B` with shape (K, N),
    if :code:`transB` is :code:`True`, otherwise :code:`B` with shape (N, K).

    :code:`C`: Matrix broadcastable to shape (M, N).

    :code:`Y`: Matrix with shape (M, N).

    :param A: The node with input tensor A.
    :param B: The node with input tensor B.
    :param C: The node with input tensor C.
    :param alpha: Scalar multiplier for the product of input tensors A * B.
    :param beta: Scalar multiplier for input tensor C.
    :param transA: Whether A should be transposed. Boolean value.
    :param transB: Whether B should be transposed. Boolean value.
    :param name: Optional name for the output node.
    :return: Return node with tensor of shape (M, N).
    """
    return Gemm(A, B, C, alpha, beta, transA, transB)


@nameable_op
def convert(data, destination_type, name=None):
    # type: (Node, Union[str, NumericType], str) -> Node
    """Return node which casts input node values to specified type.

    :param data: Node which produces the input tensor.
    :param destination_type: Provides the target type for the conversion.
    :param name: Optional name for the output node.
    :return: New node performing the conversion operation.
    """
    if not isinstance(destination_type, str):
        destination_type = get_element_type_str(destination_type)
    return _get_node_factory().create('Convert', [data],
                                      {'destination_type': destination_type.lower()})


@binary_op
def convert_like(data, like, name=None):  # type: (Node, NumericType, str) -> Node
    """Return node which casts data node values to the type of another node.

    :param data: Node which produces the input tensor
    :param like: Node which provides the target type information for the conversion
    :param name: Optional name for the output node.
    :return: New node performing the conversion operation.
    """
    return _get_node_factory().create('ConvertLike', [data, like])


@nameable_op
def depth_to_space(node, mode, block_size, name=None):  # type: (Node, str, int, str) -> Node
    """Rearranges input tensor from depth into blocks of spatial data.

    Values from the height and width dimensions are moved to the depth dimension.

    Input tensor has shape [N,C,H,W], where N is the batch axis, C is the channel or depth,
    H is the height and W is the width.

    Output node produces a tensor with shape:

    [N, C * :code:`block_size` * :code:`block_size`, H / :code:`block_size`, W / :code:`block_size`]

    :param node: The node with input tensor data.
    :param mode: Specifies how the input depth dimension is split to block coordinates

                 blocks_first: The input is divided to [block_size, ..., block_size, new_depth]
                 depth_first: The input is divided to [new_depth, block_size, ..., block_size]

    :param block_size: The size of the spatial block of values describing
                       how the tensor's data is to be rearranged.
    :param name: Optional output node name.
    :return: The new node performing an DepthToSpace operation on its input tensor.
    """
    return DepthToSpace(node, mode, block_size)


def gelu(node, name=None):  # type: (NodeInput, str) -> Node
    r"""Perform Gaussian Error Linear Unit operation element-wise on data from input node.

    Computes GELU function:

    .. math:: f(x) = 0.5\cdot x\cdot(1 + erf( \dfrac{x}{\sqrt{2}})

    For more information refer to:
    `Gaussian Error Linear Unit (GELU) <https://arxiv.org/pdf/1606.08415.pdf>`_

    :param node: Input tensor. One of: input node, array or scalar.
    :param name: Optional output node name.
    :return: The new node performing a GELU operation on its input data element-wise.
    """
    return Gelu(as_node(node))


@nameable_op
def select(cond, then_node, else_node, auto_broadcast='numpy', name=None):
    # type: (Node, NodeInput, NodeInput, str, Optional[str]) -> Node
    """Perform an element-wise selection operation on input tensors.

    :param cond: Tensor with selection mask of type `boolean`.
    :param then_node: Tensor providing data to be selected if respective `cond`
                        item value is `True`.
    :param else_node: Tensor providing data to be selected if respective `cond`
                        item value is `False`.
    :param auto_broadcast: Mode specifies rules used for auto-broadcasting of input tensors.
    :param name: The optional new name for output node.
    :return: The new node with values selected according to provided arguments.
    """
    inputs = [cond, as_node(then_node), as_node(else_node)]
    return _get_node_factory().create('Select', inputs, {'auto_broadcast': auto_broadcast.upper()})


# Non-linear ops
@unary_op
def tanh(node, name=None):  # type: (Node, str) -> Node
    """Return node which applies hyperbolic tangent to the input node element-wise.

    :param node: One of: input node, array or scalar.
    :param name: Optional new name for output node.
    :return: New node with tanh operation applied on it.
    """
    return _get_node_factory().create('Tanh', [node])


@nameable_op
def clamp(data, min_value, max_value, name=None):
    # type: (NodeInput, ScalarData, ScalarData, str) -> Node
    """Perform clamp element-wise on data from input node.

    Performs a clipping operation on an input value between a pair of boundary values.

    For each element in :code:`data`, if the element's value is lower than :code:`min_value`,
    it will be replaced with :code:`min_value`. If the value is higher than :code:`max_value`,
    it will be replaced by :code:`max_value`.
    Intermediate values of :code:`data` are returned without change.

    Clamp uses the following logic:

    .. code-block:: python

        if data < min_value:
            data=min_value
        elif data > max_value:
            data=max_value

    :param data: Input tensor. One of: input node, array or scalar.
    :param min_value: The lower bound of the <min_value;max_value> range. Scalar value.
    :param max_value: The upper bound of the <min_value;max_value> range. Scalar value.
    :param name: Optional output node name.
    :return: The new node performing a clamp operation on its input data element-wise.
    """
    return _get_node_factory().create('Clamp', [as_node(data)],
                                      {'min': min_value, 'max': max_value})


# matmul ops
@nameable_op
def dot(left_node, right_node, reduction_axes_count=None, name=None):
    # type: (Node, Node, int, str) -> Node
    """Return node which performs generalized dot product of two input nodes.

    This operation is capable of performing scalar-tensor, matrix-vector product and matrix
    multiplication.

    :param left_node: The node providing left hand side data.
    :param right_node: The node providing right hand side data.
    :param reduction_axes_count: The number of axes to reduce during dot-product.
    :param name: The optional name for output node.
    :return: The new node performing dot-product on input two nodes.
    """
    if reduction_axes_count is None:
        return Dot(left_node, right_node)
    else:
        return Dot(left_node, right_node, reduction_axes_count)


@nameable_op
def binary_convolution(data,                           # type: Node
                       filters,                        # type: Node
                       strides,                        # type: List[int]
                       pads_begin,                     # type: List[int]
                       pads_end,                       # type: List[int]
                       dilations,                      # type: List[int]
                       mode,                           # type: str
                       pad_value,                      # type: float
                       auto_pad='EXPLICIT',            # type: str
                       name=None,                      # type: str
                       ):
    # type: (...) -> Node
    """Create node performing convolution with binary weights, binary input and integer output.

    :param data: The node providing data batch tensor.
    :param filter: The node providing filters tensor.
    :param strides: The kernel window movement strides.
    :param pads_begin: The number of pixels to add to the beginning along each axis.
    :param pads_end: The number of pixels to add to the end along each axis.
    :param dilations: The distance in width and height between elements (weights) in the filter.
    :param mode: Defines how input tensor 0/1 values and weights 0/1 are interpreted.
    :param pad_value: Floating-point value used to fill pad area.
    :param auto_pad: The type of padding. Range of values: explicit, same_upper, same_lower, valid.
    :param name: The optional new name for output node.
    :return: New node performing binary convolution operation.
    """
    return _get_node_factory().create('BinaryConvolution',
                                      [data, filters],
                                      {'strides': strides,
                                       'pads_begin': pads_begin,
                                       'pads_end': pads_end,
                                       'dilations': dilations,
                                       'mode': mode,
                                       'pad_value': pad_value,
                                       'auto_pad': auto_pad})


# convpool ops
@nameable_op
def convolution(data,                           # type: Node
                filters,                        # type: Node
                strides,                        # type: List[int]
                pads_begin,                     # type: List[int]
                pads_end,                       # type: List[int]
                dilations,                      # type: List[int]
                auto_pad='EXPLICIT',            # type: str
                name=None,                      # type: str
                ):
    # type: (...) -> Node
    """Return node performing batched convolution operation.

    :param data: The node providing data batch tensor.
    :param filter: The node providing filters tensor.
    :param strides: The kernel window movement strides.
    :param pads_begin: The number of zero padding elements to add on each axis below 0 coordinate.
    :param pads_end: The number of zero padding elements to add on each axis above max coordinate
    :param dilations: The data batch dilation strides.
    :param auto_pad: The type of padding. Range of values: explicit, same_upper, same_lower, valid.
    :param name: The optional new name for output node.
    :return: New node performing batched convolution operation.
    """
    return _get_node_factory().create('Convolution',
                                      [data, filters],
                                      {'strides': strides,
                                       'pads_begin': pads_begin,
                                       'pads_end': pads_end,
                                       'dilations': dilations,
                                       'auto_pad': auto_pad})


@nameable_op
def convolution_backprop_data(data,                 # type: Node
                              filters,              # type: Node
                              strides,              # type: List[int]
                              output_shape=None,    # type: Node
                              pads_begin=None,      # type: List[int]
                              pads_end=None,        # type: List[int]
                              dilations=None,       # type: List[int]
                              auto_pad=None,        # type: str
                              output_padding=None,  # type: List[int]
                              name=None,            # type: str
                              ):
    # type: (...) -> Node
    """Create node performing a batched-convolution backprop data operation.

    :param      data:         The node producing data from forward-prop
    :param      filters:      The node producing the filters from forward-prop.
    :param      output_shape: The node producing output delta.
    :param      strides:      The distance (in pixels) to slide the filter on the feature map
                              over the axes.
    :param      pads_begin:   The number of pixels to add to the beginning along each axis.
    :param      pads_end:     The number of pixels to add to the end along each axis.
    :param      dilations:    The distance in width and height between elements (weights)
                              in the filter.
    :param      name:         The node name.

    :returns:   The node object representing ConvolutionBackpropData  operation.
    """
    spatial_dim_count = len(strides)
    if pads_begin is None:
        pads_begin = [0] * spatial_dim_count
    if pads_end is None:
        pads_end = [0] * spatial_dim_count
    if dilations is None:
        dilations = [1] * spatial_dim_count
    if auto_pad is None:
        auto_pad = 'explicit'
    if output_padding is None:
        output_padding = [0] * spatial_dim_count
    args = [data, filters]
    if output_shape is not None:
        args.append(output_shape)

    return _get_node_factory().create('ConvolutionBackpropData',
                                      args,
                                      {'strides': strides,
                                       'pads_begin': pads_begin,
                                       'pads_end': pads_end,
                                       'dilations': dilations,
                                       'auto_pad': auto_pad.upper(),
                                       'output_padding': output_padding})


@nameable_op
def deformable_convolution(data,                           # type: Node
                           deformable_values,              # type: Node
                           filters,                        # type: Node
                           strides,                        # type: List[int]
                           pads_begin,                     # type: List[int]
                           pads_end,                       # type: List[int]
                           dilations,                      # type: List[int]
                           auto_pad='EXPLICIT',            # type: str
                           group=1,                        # type: int
                           deformable_group=1,             # type: int
                           name=None,                      # type: str
                           ):
    # type: (...) -> Node
    """Create node performing deformable convolution.

    :param data: The node providing data batch tensor.
    :param filter: The node providing filters tensor.
    :param strides: The distance (in pixels) to slide the filter on the feature map over the axes.
    :param pads_begin: The number of pixels to add to the beginning along each axis.
    :param pads_end: The number of pixels to add to the end along each axis.
    :param dilations: The distance in width and height between elements (weights) in the filter.
    :param auto_pad: The type of padding. Range of values: explicit, same_upper, same_lower, valid.
    :param group: The number of groups which both output and input should be split into.
    :param deformable_group: The number of groups which deformable values and output should be split
                             into along the channel axis.
    :param name: The optional new name for output node.
    :return: New node performing deformable convolution operation.
    """
    return _get_node_factory().create('DeformableConvolution',
                                      [data, deformable_values, filters],
                                      {'strides': strides,
                                       'pads_begin': pads_begin,
                                       'pads_end': pads_end,
                                       'dilations': dilations,
                                       'auto_pad': auto_pad,
                                       'group': group,
                                       'deformable_group': deformable_group,
                                       })


@nameable_op
def deformable_psroi_pooling(feature_maps,                   # type: NodeInput
                             coords,                         # type: NodeInput
                             output_dim,                     # type: int
                             spatial_scale,                  # type: float
                             group_size=1,                   # type: int
                             mode='bilinear_deformable',     # type: str
                             spatial_bins_x=1,               # type: int
                             spatial_bins_y=1,               # type: int
                             trans_std=1.0,                  # type: float
                             part_size=1,                    # type: int
                             offsets=None,                   # type: NodeInput
                             name=None,                      # type: str
                             ):
    # type: (...) -> Node
    """Return node performing DeformablePSROIPooling operation.

    DeformablePSROIPooling computes position-sensitive pooling
    on regions of interest specified by input.

    :param feature_maps: 4D tensor with feature maps.
    :param coords: 2D tensor describing box consisting of tuples: [batch_id, x_1, y_1, x_2, y_2].
    :param output_dim: A pooled output channel number.
    :param spatial_scale: A multiplicative spatial scale factor to translate ROI.
    :param group_size: The number of groups to encode position-sensitive score.
    :param mode: Specifies mode for pooling. Range of values: ['bilinear_deformable'].
    :param spatial_bins_x: Specifies numbers of bins to divide the input feature maps over width.
    :param spatial_bins_y: Specifies numbers of bins to divide the input feature maps over height.
    :param trans_std: The value that all transformation (offset) values are multiplied with.
    :param part_size: The number of parts the output tensor spatial dimensions are divided into.
    :param offsets: Optional node. 4D input blob with transformation values (offsets).
    :param name: The optional new name for output node.
    :return: New node performing DeformablePSROIPooling operation.
    """
    node_inputs = as_nodes(feature_maps, coords)
    if offsets is not None:
        node_inputs.append(as_node(offsets))

    return _get_node_factory().create('DeformablePSROIPooling',
                                      node_inputs,
                                      {'output_dim': output_dim,
                                       'spatial_scale': spatial_scale,
                                       'group_size': group_size,
                                       'mode': mode,
                                       'spatial_bins_x': spatial_bins_x,
                                       'spatial_bins_y': spatial_bins_y,
                                       'trans_std': trans_std,
                                       'part_size': part_size,
                                       })


@nameable_op
def avg_pool(data_batch,            # type: Node
             strides,               # type: List[int]
             pads_begin,            # type: TensorShape
             pads_end,              # type: TensorShape
             kernel_shape,          # type: TensorShape
             exclude_pad,           # type: bool
             rounding_type='floor',  # type: str
             auto_pad=None,         # type: str
             name=None,             # type: str
             ):
    # type: (...) -> Node
    """Return average pooling node.

    :param data_batch:      The input node providing data.
    :param strides:         The window movement strides.
    :param pads_begin:      The input data optional padding below filled with zeros.
    :param pads_end:        The input data optional padding below filled with zeros.
    :param kernel_shape:    The pooling window shape.
    :param exclude_pad:     Whether or not to include zero padding in average computations.
    :param rounding_type:   Determines used rounding schema when computing output shape. Acceptable
                            values are: ['floor', 'ceil']
    :param auto_pad:        Determines how the padding is calculated. Acceptable values:
                            [None, 'same_upper', 'same_lower', 'valid']
    :param name:            Optional name for the new output node.

    :return: New node with AvgPool operation applied on its data.
    """
    if auto_pad is None:
        auto_pad = 'explicit'
    return _get_node_factory().create('AvgPool',
                                      [data_batch],
                                      {'strides': strides,
                                       'pads_begin': pads_begin,
                                       'pads_end': pads_end,
                                       'kernel': kernel_shape,
                                       'exclude_pad': exclude_pad,
                                       'rounding_type': rounding_type.upper(),
                                       'auto_pad': auto_pad.upper()})


@nameable_op
def max_pool(data,                    # type: Node
             strides,                 # type: List[int]
             pads_begin,              # type: List[int]
             pads_end,                # type: List[int]
             kernel_shape,            # type: TensorShape
             rounding_type='floor',   # type: str
             auto_pad=None,           # type: str
             name=None,               # type: str
             ):
    # type: (...) -> Node
    """Perform max pooling operation with given parameters on provided data.

    :param  data:           The node providing input data.
    :param  strides:        The distance (in pixels) to slide the filter on the feature map
                            over the axes.
    :param  pads_begin:     The number of pixels to add at the beginning along each axis.
    :param  pads_end:       The number of pixels to add at the end along each axis.
    :param  kernel_shape:   The pooling operation kernel shape.
    :param  rounding_type:  Determines used rounding schema when computing output shape. Acceptable
                            values are: ['floor', 'ceil']
    :param  auto_pad:       Determines how the padding is calculated. Acceptable values:
                            [None, 'same_upper', 'same_lower', 'valid']
    :param  name:           The optional name for the created output node.

    :returns:   The new node performing max pooling operation.
    """
    if auto_pad is None:
        auto_pad = 'explicit'
    return _get_node_factory().create('MaxPool',
                                      [data],
                                      {'strides': strides,
                                       'pads_begin': pads_begin,
                                       'pads_end': pads_end,
                                       'kernel': kernel_shape,
                                       'rounding_type': rounding_type.upper(),
                                       'auto_pad': auto_pad.upper()})


# reduction ops
@nameable_op
def reduce_sum(node, reduction_axes, keep_dims=False, name=None):
    # type: (Node, Node, bool, str) -> Node
    """Perform element-wise sums of the input tensor, eliminating the specified reduction axes.

    :param node:           The node providing data for operation.
    :param reduction_axes: The axes to eliminate through summation.
    :param keep_dims:      If set to True it holds axes that are used for reduction
    :param name:           The optional new name for output node.
    :return: The new node performing summation along `reduction_axes` element-wise.
    """
    return _get_node_factory().create('ReduceSum', [node, reduction_axes], {'keep_dims': keep_dims})


@nameable_op
def reduce_max(node, reduction_axes, keep_dims=False, name=None):
    # type: (Node, Node, bool, str) -> Node
    """Max-reduction operation on input tensor, eliminating the specified reduction axes.

    :param node:           The tensor we want to max-reduce.
    :param reduction_axes: The axes to eliminate through max operation.
    :param keep_dims:      If set to True it holds axes that are used for reduction
    :param name: Optional name for output node.
    """
    return _get_node_factory().create('ReduceMax', [node, reduction_axes], {'keep_dims': keep_dims})


@nameable_op
def reduce_min(node, reduction_axes, keep_dims=False, name=None):
    # type: (Node, Node, bool, str) -> Node
    """Min-reduction operation on input tensor, eliminating the specified reduction axes.

    :param node:           The tensor we want to min-reduce.
    :param reduction_axes: The axes to eliminate through min operation.
    :param keep_dims:      If set to True it holds axes that are used for reduction
    :param name:           Optional name for output node.
    """
    return _get_node_factory().create('ReduceMin', [node, reduction_axes], {'keep_dims': keep_dims})


@nameable_op
def reduce_prod(node, reduction_axes, keep_dims=False, name=None):
    # type: (Node, Node, bool, str) -> Node
    """Product-reduction operation on input tensor, eliminating the specified reduction axes.

    :param node:           The tensor we want to product-reduce.
    :param reduction_axes: The axes to eliminate through product operation.
    :param keep_dims:      If set to True it holds axes that are used for reduction
    :param name:           Optional name for output node.
    :return: The new node performing product-reduction operation.
    """
    return _get_node_factory().create('ReduceProd',
                                      [node, reduction_axes],
                                      {'keep_dims': keep_dims})


@nameable_op
def reduce_mean(node, reduction_axes, keep_dims=False, name=None):
    # type: (Node, Node, bool, str) -> Node
    """Mean-reduction operation on input tensor, eliminating the specified reduction axes.

    :param node:           The tensor we want to mean-reduce.
    :param reduction_axes: The axes to eliminate through mean operation.
    :param keep_dims:      If set to True it holds axes that are used for reduction
    :param name:           Optional name for output node.
    :return: The new node performing mean-reduction operation.
    """
    return _get_node_factory().create('ReduceMean',
                                      [node, reduction_axes],
                                      {'keep_dims': keep_dims})


@nameable_op
def reduce_logical_and(node, reduction_axes, keep_dims=False, name=None):
    # type: (Node, Node, bool, str) -> Node
    """Logical AND reduction operation on input tensor, eliminating the specified reduction axes.

    :param node:           The tensor we want to reduce.
    :param reduction_axes: The axes to eliminate through AND operation.
    :param keep_dims:      If set to True it holds axes that are used for reduction
    :param name:           Optional name for output node.
    :return: The new node performing reduction operation.
    """
    return _get_node_factory().create('ReduceLogicalAnd',
                                      [node, reduction_axes],
                                      {'keep_dims': keep_dims})


@nameable_op
def reduce_logical_or(node, reduction_axes, keep_dims=False, name=None):
    # type: (Node, Node, bool, str) -> Node
    """Logical OR reduction operation on input tensor, eliminating the specified reduction axes.

    :param node:           The tensor we want to reduce.
    :param reduction_axes: The axes to eliminate through OR operation.
    :param keep_dims:      If set to True it holds axes that are used for reduction
    :param name:           Optional name for output node.
    :return: The new node performing reduction operation.
    """
    return _get_node_factory().create('ReduceLogicalOr',
                                      [node, reduction_axes],
                                      {'keep_dims': keep_dims})


@nameable_op
def cum_sum(arg, axis, exclusive=False, reverse=False, name=None):
    # type: (NodeInput, NodeInput, bool, bool, str) -> Node
    """Construct a cumulative summation operation.

    :param arg: The tensor to be summed.
    :param axis: zero dimension tensor specifying axis position along which sum will be performed.
    :param exclusive: if set to true, the top element is not included
    :param reverse: if set to true, will perform the sums in reverse direction
    :return: New node performing the operation
    """
    return _get_node_factory().create('CumSum', as_nodes(arg, axis),
                                      {'exclusive': exclusive, 'reverse': reverse})


@nameable_op
def prelu(data, slope, name=None):  # type: (Node, Node, str) -> Node
    """Perform Parametrized Relu operation element-wise on data from input node.

    PRelu uses the following logic:

    .. code-block:: python

        if data < 0:
            data = data * slope
        elif data >= 0:
            data = data

    :param data: The node with data tensor.
    :param slope: The node with the multipliers for negative values.
    :param name: Optional output node name.
    :return: The new node performing a PRelu operation on tensor's channels.
    """
    return _get_node_factory().create('PRelu', [data, slope])


@nameable_op
def hard_sigmoid(data, alpha, beta, name=None):  # type: (Node, float, float, str) -> Node
    """Perform Hard Sigmoid operation element-wise on data from input node.

    Hard Sigmoid uses the following logic:

    .. code-block:: python

        y = max(0, min(1, alpha * data + beta))

    :param data: The node with data tensor.
    :param alpha: Alpha parameter. Scalar value.
    :param beta: Beta parameter. Scalar value.
    :param name: Optional output node name.
    :return: The new node performing a Hard Sigmoid element-wise on input tensor.
    """
    return HardSigmoid(data, alpha, beta)


# reshape ops
@nameable_op
def slice(node, lower_bounds, upper_bounds, strides=None, name=None):
    # type: (Node, List[int], List[int], List[int], str) -> Node
    """Take a slice of an input tensor, (sub-tensor) that resides within a bounding box.

    Optionally this function may be provided with stride along each axis.

    :param node: The tensor we want to slice.
    :param lower_bounds: The (inclusive) lower-bound coordinates for the tensor slice.
    :param upper_bounds: The (exclusive) upper-bound coordinates for the tensor slice.
    :param strides: The strides for the tensor slice.
    :param name: Optional name for the output node.
    :return: Return node that represents a slice of input nodes data.
    """
    if strides is None:
        return Slice(node, Coordinate(lower_bounds), Coordinate(upper_bounds))
    else:
        return Slice(node, Coordinate(lower_bounds), Coordinate(upper_bounds), Strides(strides))


@nameable_op
def concat(nodes, axis, name=None):  # type: (List[Node], int, str) -> Node
    """Concatenate input nodes into single new node along specified axis.

    :param nodes: The nodes we want concatenate into single new node.
    :param axis: The axis along which we want to concatenate input nodes.
    :param name: The optional new name for output node.
    :return: Return new node that is a concatenation of input nodes.
    """
    return _get_node_factory().create('Concat', nodes, {'axis': axis})


@nameable_op
def softmax(data, axis):  # type: (Node, int) -> Node
    """Apply softmax operation on each element of input tensor.

    :param data: The tensor providing input data.
    :param axis: An axis along which Softmax should be calculated
    :return: The new node with softmax operation applied on each element.
    """
    return _get_node_factory().create('Softmax', [data], {'axis': axis})


@nameable_op
def pad(arg,                 # type: Node
        pads_begin,          # type: NodeInput
        pads_end,            # type: NodeInput
        pad_mode,            # type: str
        arg_pad_value=None,  # type: Optional[NodeInput]
        name=None,           # type: str
        ):
    # type: (...) -> Node
    """Return a generic padding operation.

    :param arg: The node producing input tensor to be padded.
    :param pads_begin: number of padding elements to be added before position 0
                       on each axis of arg.
    :param pads_end: number of padding elements to be added after the last element.
    :param pad_mode: "constant", "edge", "reflect" or "symmetric"
    :param arg_pad_value: value used for padding if pad_mode is "constant"
    :return: Pad operation node.
    """
    input_nodes = [arg, as_node(pads_begin), as_node(pads_end)]
    if arg_pad_value:
        input_nodes.append(as_node(arg_pad_value))

    pad_mode = pad_mode.upper()
    return _get_node_factory().create('Pad', input_nodes, {'pad_mode': pad_mode})


@nameable_op
def one_hot(indices, depth, on_value, off_value, axis, name=None):
    # type: (Node, NodeInput, NodeInput, NodeInput, int, Optional[str]) -> Node
    """Create node performing one-hot encoding on input data.

    :param indices: Input tensor of rank N with indices of any supported integer data type.
    :param depth: Scalar of any supported integer type that specifies number of classes and
                  the size of one-hot dimension.
    :param on_value: Scalar of any type that is the value that the locations
                     in output tensor represented by indices in input take.
    :param off_value: Scalar of any type that is the value that the locations not represented
                      by indices in input take.

    :param name: The optional name for new output node.
    :return: New node performing one-hot operation.
    """
    return _get_node_factory().create('OneHot', as_nodes(indices, depth, on_value, off_value),
                                      {'axis': axis})


@nameable_op
def replace_slice(dest_node,        # type: Node
                  src_node,         # type: Node
                  lower_bounds,     # type: List[int]
                  upper_bounds,     # type: List[int]
                  strides=None,     # type: List[int]
                  name=None,        # type: str
                  ):
    # type: (...) -> Node
    """Return a copy of `dest_node` with the specified slice overwritten by the `src_node` data.

    :param dest_node: The node providing data to be overwritten by the specified slice.
    :param src_node: The node providing data for overwriting.
    :param lower_bounds: The (inclusive) lower-bound coordinates for the replaced slice.
    :param upper_bounds: The (exclusive) upper-bound coordinates for the replaced slice.
    :param strides: The strides for the replaced slice.
    :param name: The optional name for the output new node.
    :return: The new node with copy of `dest_node` with the specified slice overwritten
             by the `src_node`.
    """
    if strides is None:
        return ReplaceSlice(dest_node, src_node, Coordinate(lower_bounds), Coordinate(upper_bounds))
    else:
        return ReplaceSlice(dest_node, src_node, Coordinate(lower_bounds), Coordinate(upper_bounds),
                            Strides(strides))


@nameable_op
def reverse(data, axis, mode, name=None):  # type: (Node, NodeInput, str, Optional[str]) -> Node
    """Perform axis-reverse operation.

    :param data: The input node on which operation will be carried out.
    :param axis: The list of indices of axes to be reversed.
    :param mode: The mode specifies how the second input tensor should be interpreted:
                 as a set of indices or a mask. Range of values: index, mask.
    :param name: The optional name of the output node.
    :return: The new node with reversed axes.
    """
    return _get_node_factory('opset1').create('Reverse', [data, as_node(axis)],
                                              {'mode': mode.lower()})


@nameable_op
def batch_norm_inference(data,            # type: Node
                         gamma,           # type: NodeInput
                         beta,            # type: NodeInput
                         mean,            # type: NodeInput
                         variance,        # type: NodeInput
                         epsilon,         # type: float
                         name=None,       # type: Optional[str]
                         ):
    # type: (...) -> Node
    """Perform layer normalizes a input tensor by mean and variance with appling scale and offset.

    :param data: The input tensor with data for normalization.
    :param gamma: The scalar scaling for normalized value.
    :param beta: The bias added to the scaled normalized value.
    :param mean: The value for mean normalization.
    :param variance: The value for variance normalization.
    :param epsilon: The  number to be added to the variance to avoid division
                    by zero when normalizing a value.
    :param name: The optional name of the output node.
    :return: The new node which performs BatchNormInference.
    """
    inputs = [as_node(gamma), as_node(beta), data, as_node(mean), as_node(variance)]
    return _get_node_factory().create('BatchNormInference', inputs, {'epsilon': epsilon})


@nameable_op
def normalize_l2(data, axes, eps, eps_mode, name=None):
    # type: (NodeInput, NodeInput, float, str, Optional[str]) -> Node
    """Construct an NormalizeL2 operation.

    :param data: Node producing the input tensor
    :param axes: Node indicating axes along which L2 reduction is calculated
    :param eps: The epsilon added to L2 norm
    :param eps_mode: how eps is combined with L2 value (`add` or `max`)
    :return: New node which performs the L2 normalization.
    """
    return _get_node_factory().create('NormalizeL2', as_nodes(data, axes),
                                      {'eps': eps, 'mode': eps_mode})


@nameable_op
def lrn(data,       # type: Node
        axes,       # type: NodeInput
        alpha=1,    # type: float
        beta=0.5,   # type: float
        bias=1,     # type: float
        size=5,     # type: int
        name=None,  # type: Optional[str]
        ):
    # type: (...) -> Node
    """Return a node which performs element-wise Local Response Normalization (LRN) operation.

    :param data: Input data.
    :param alpha: A scale factor (usually positive).
    :param beta: An exponent.
    :param bias: An offset (usually positive) to avoid dividing by 0.
    :param size: Width of the 1-D normalization window.
    :param name: An optional name of the output node.
    :return: The new node which performs LRN.
    """
    attributes = {'alpha': alpha, 'beta': beta, 'bias': bias, 'size': size}
    return _get_node_factory().create('LRN', [data, as_node(axes)], attributes)


@nameable_op
def argmax(data,     # type: Node
           axis=0,   # type: int
           ):
    # type: (...) -> Node
    """Return a node which performs ArgMax index reduction operation.

    :param data: Input data.
    :param axis: Reduction Axis.
    :return: The new node which performs ArgMax
    """
    return ArgMax(data, axis, get_element_type(np.int32))


@nameable_op
def argmin(data,    # type: Node
           axis=0,  # type: int
           ):
    # type: (...) -> Node
    """Return a node which performs ArgMin index reduction operation.

    :param data: Input data.
    :param axis: Reduction Axis.
    :return: The new node which performs ArgMin
    """
    return ArgMin(data, axis, get_element_type(np.int32))


@nameable_op
def non_max_suppression(boxes,                              # type: Node
                        scores,                             # type: NodeInput
                        max_output_boxes_per_class=None,    # type: Optional[NodeInput]
                        iou_threshold=None,                 # type: Optional[NodeInput]
                        score_threshold=None,               # type: Optional[NodeInput]
                        box_encoding='corner',              # type: str
                        sort_result_descending=True,        # type: bool
                        output_type='i64',                  # type: str
                        name=None,                          # type: Optional[str]
                        ):
    # type: (...) -> Node
    """Return a node which performs NonMaxSuppression.

    :param boxes: Tensor with box coordinates.
    :param scores: Tensor with box scores.
    :param max_output_boxes_per_class: Tensor Specifying maximum number of boxes
                                        to be selected per class.
    :param iou_threshold: Tensor specifying intersection over union threshold
    :param score_threshold: Tensor specifying minimum score to consider box for the processing.
    :param box_encoding: Format of boxes data encoding.
    :param sort_result_descending: Flag that specifies whenever it is necessary to sort selected
                                   boxes across batches or not.
    :param output_type: Output element type.
    :return: The new node which performs NonMaxSuppression
    """
    if max_output_boxes_per_class is None:
        max_output_boxes_per_class = make_constant_node(0, np.int64)
    if iou_threshold is None:
        iou_threshold = make_constant_node(0, np.float32)
    if score_threshold is None:
        score_threshold = make_constant_node(0, np.float32)

    inputs = [boxes, as_node(scores), as_node(max_output_boxes_per_class),
              as_node(iou_threshold), as_node(score_threshold)]
    attributes = {'box_encoding': box_encoding,
                  'sort_result_descending': sort_result_descending,
                  'output_type': output_type}

    return _get_node_factory().create('NonMaxSuppression', inputs, attributes)


@nameable_op
def non_zero(data,                # type: Node
             output_type='i64',   # type: str
             name=None,           # type: Optional[str]
             ):
    # type: (...) -> Node
    """Return the indices of the elements that are non-zero.

    :param data: Input data.
    :param output_type: Output tensor type.

    :return: The new node which performs NonZero
    """
    return _get_node_factory().create('NonZero', [data], {'output_type': output_type})


@nameable_op
def topk(data,                      # type: Node
         k,                         # type: NodeInput
         axis,                      # type: int
         mode,                      # type: str
         sort,                      # type: str
         index_element_type='i32',  # type: str
         name=None,                 # type: Optional[str]
         ):
    # type: (...) -> Node
    """Return a node which performs TopK.

    :param data: Input data.
    :param k: K.
    :param axis: TopK Axis.
    :param mode: Compute TopK largest ('max') or smallest ('min')
    :param sort: Order of output elements (sort by: 'none', 'index' or 'value')
    :param index_element_type: Type of output tensor with indices.
    :return: The new node which performs TopK (both indices and values)
    """
    return _get_node_factory().create('TopK', [data, as_node(k)],
                                      {'axis': axis, 'mode': mode, 'sort': sort,
                                       'index_element_type': index_element_type})


@nameable_op
def roi_align(data,             # type: Node
              rois,             # type: NodeInput
              batch_indices,    # type: NodeInput
              pooled_h,         # type: int
              pooled_w,         # type: int
              sampling_ratio,   # type: int
              spatial_scale,    # type: float
              mode,             # type: str
              name=None,        # type: Optional[str]
              ):
    # type: (...) -> Node
    """Return a node which performs ROIAlign.

    :param data: Input data.
    :param rois: RoIs (Regions of Interest) to pool over.
    :param batch_indices: Tensor with each element denoting the index of
                          the corresponding image in the batch.
    :param pooled_h: Height of the ROI output feature map.
    :param pooled_w: Width of the ROI output feature map.
    :param sampling_ratio: Number of bins over height and width to use to calculate
                           each output feature map element.
    :param spatial_scale: Multiplicative spatial scale factor to translate ROI coordinates.
    :param mode: Method to perform pooling to produce output feature map elements.

    :return: The new node which performs ROIAlign
    """
    inputs = [data, as_node(rois), as_node(batch_indices)]
    attributes = {'pooled_h': pooled_h, 'pooled_w': pooled_w,
                  'sampling_ratio': sampling_ratio,
                  'spatial_scale': spatial_scale, 'mode': mode}
    return _get_node_factory().create('ROIAlign', inputs, attributes)


@nameable_op
def get_output_element(data, index):  # type: (Node, int) -> Node
    """Return the n-th element of the input tuple."""
    return GetOutputElement(data, index)


@nameable_op
def matmul(data_a, data_b, transpose_a, transpose_b):  # type: (Node, Node, bool, bool) -> Node
    """Return the Matrix Multiplication operation.

    :param data_a: left-hand side matrix
    :param data_b: right-hand side matrix
    :param transpose_a: should the first matrix be transposed before operation
    :param transpose_b: should the second matrix be transposed
    :return: MatMul operation node
    """
    print('transpose_a', transpose_a, 'transpose_b', transpose_b)
    return _get_node_factory().create('MatMul', [data_a, data_b],
                                      {'transpose_a': transpose_a, 'transpose_b': transpose_b})


@nameable_op
def variadic_split(data, axis, split_lengths):  # type: (Node, Node, Node) -> Node
    """Return a node which splits the input tensor into variadic length slices.

    :param data: The input tensor to be split
    :param axis: Axis along which the input data will be split
    :param split_lengths: Sizes of the output tensors along the split axis
    :return: VariadicSplit node
    """
    return _get_node_factory().create('VariadicSplit', [data, axis, split_lengths])


@nameable_op
def transpose(data, input_order):  # type: (Node, Node) -> Node
    """Return a node which transposes the data in the input tensor.

    :param data: The input tensor to be transposed
    :param input_order: Permutation of axes to be applied to the input tensor
    :return: Transpose node
    """
    return _get_node_factory().create('Transpose', [data, input_order])


@nameable_op
def tile(data, repeats):  # type: (Node, Node) -> Node
    """Return a node which dynamically repeats(replicates) the input data tensor.

    :param data: The input tensor to be tiled
    :param repeats: Per-dimension replication factors
    :return: Tile node
    """
    return _get_node_factory().create('Tile', [data, repeats])


@nameable_op
def strided_slice(data,                   # type: Node
                  begin,                  # type: Node
                  end,                    # type: Node
                  strides,                # type: Node
                  begin_mask,             # type: List[int]
                  end_mask,               # type: List[int]
                  new_axis_mask=None,     # type: List[int]
                  shrink_axis_mask=None,  # type: List[int]
                  ellipsis_mask=None,     # type: List[int]
                  ):
    # type: (...) -> Node
    """Return a node which dynamically repeats(replicates) the input data tensor.

    :param      data:              The tensor to be sliced
    :param      begin:             1D tensor with begin indexes for input blob slicing
    :param      end:               1D tensor with end indexes for input blob slicing
    :param      strides:           The slicing strides
    :param      begin_mask:        A mask applied to the 'begin' input indicating which elements
                                   shoud be ignored
    :param      end_mask:          A mask applied to the 'end' input indicating which elements
                                   shoud be ignored
    :param      new_axis_mask:     A mask indicating dimensions where '1' should be inserted
    :param      shrink_axis_mask:  A mask indicating which dimensions should be deleted
    :param      ellipsis_mask:     Indicates positions where missing dimensions should be inserted
    :returns:   StridedSlice node
    """
    if new_axis_mask is None:
        new_axis_mask = []
    if shrink_axis_mask is None:
        shrink_axis_mask = []
    if ellipsis_mask is None:
        ellipsis_mask = []
    attributes = {'begin_mask': begin_mask, 'end_mask': end_mask, 'new_axis_mask': new_axis_mask,
                  'shrink_axis_mask': shrink_axis_mask, 'ellipsis_mask': ellipsis_mask}

    return _get_node_factory().create('StridedSlice', [data, begin, end, strides], attributes)


@nameable_op
def split(data, axis, num_splits):  # type: (Node, Node, int) -> Node
    """Return a node which splits the input tensor into same-length slices.

    :param data: The input tensor to be split
    :param axis: Axis along which the input data will be split
    :param num_splits: Number of the output tensors that should be produced
    :return: Split node
    """
    return _get_node_factory().create('Split', [data, axis], {'num_splits': num_splits})


@nameable_op
def sigmoid(data):  # type: (Node) -> Node
    """Return a node which applies the sigmoid function element-wise.

    :param data: The tensor containing the input data
    :return: Sigmoid node
    """
    return _get_node_factory().create('Sigmoid', [data])


@nameable_op
def shape_of(data, output_type='i64', name=None):  # type: (Node, str, Optional[str]) -> Node
    """Return a node which produces a tensor containing the shape of its input data.

    :param data: The tensor containing the input data.
    :para output_type: Output element type.
    :return: ShapeOf node
    """
    return _get_node_factory().create('ShapeOf', [data], {'output_type': output_type})


@nameable_op
def result(data):  # type: (Node) -> Node
    """Return a node which represents an output of a graph (Function).

    :param data: The tensor containing the input data
    :return: Result node
    """
    return _get_node_factory().create('Result', [data])


@nameable_op
def scatter_update(data, indices, updates, axis):
    # type: (Node, NodeInput, NodeInput, NodeInput) -> Node
    """Return a node which produces a ScatterUpdate operation.

    ScatterUpdate sets new values to slices from data addressed by indices.

    :param data:    The input tensor to be updated.
    :param indices: The tensor with indexes which will be updated.
    :param updates: The tensor with update values.
    :param axis:    The axis at which elements will be updated.
    :return: ScatterUpdate node
    """
    return _get_node_factory().create('ScatterUpdate', [data, as_node(indices),
                                                        as_node(updates), as_node(axis)])


@nameable_op
def scatter_elements_update(data, indices, updates, axis):
    # type: (Node, NodeInput, NodeInput, NodeInput) -> Node
    """Return a node which produces a ScatterElementsUpdate operation.

    ScatterElementsUpdate creates a copy of the first input tensor with updated elements
    specified with second and third input tensors.


    For each entry in `updates`, the target index in `data` is obtained by combining
    the corresponding entry in `indices` with the index of the entry itself: the
    index-value for dimension equal to `axis` is obtained from the value of the
    corresponding entry in `indices` and the index-value for dimension not equal
    to `axis` is obtained from the index of the entry itself.

    :param data:    The input tensor to be updated.
    :param indices: The tensor with indexes which will be updated.
    :param updates: The tensor with update values.
    :param axis:    The axis for scatter.
    :return: ScatterElementsUpdate node
    """
    return _get_node_factory().create('ScatterElementsUpdate', [data, as_node(indices),
                                                                as_node(updates), as_node(axis)])


@nameable_op
def roi_pooling(input, coords, output_size, spatial_scale, method, name=None):
    # type: (Node, NodeInput, TensorShape, NumericData, str, str) -> Node
    """Return a node which produces an ROIPooling operation.

    :param input:          Input feature map {N, C, ...}
    :param coords:         Coordinates of bounding boxes
    :param output_size:    Height/Width of ROI output features (shape)
    :param spatial_scale:  Ratio of input feature map over input image size (float)
    :param method:         Method of pooling - string: "max" or "bilinear"
    :return:               ROIPooling node
    """
    method = method.lower()
    return _get_node_factory().create('ROIPooling', [input, as_node(coords)],
                                      {'output_size': Shape(output_size),
                                       'spatial_scale': spatial_scale,
                                       'method': method})


@nameable_op
def psroi_pooling(input,  # type: Node
                  coords,  # type: NodeInput
                  output_dim,  # type: int
                  group_size,  # type: int
                  spatial_scale,  # type: float
                  spatial_bins_x,  # type: int
                  spatial_bins_y,  # type: int
                  mode,  # type: str
                  name=None,  # type: str
                  ):  # type: (...) -> Node
    """Return a node which produces a PSROIPooling operation.

    :param input: Input feature map {N, C, ...}
    :param coords: Coordinates of bounding boxes
    :param output_dim: Output channel number
    :param group_size: Number of groups to encode position-sensitive scores
    :param spatial_scale: Ratio of input feature map over input image size
    :param spatial_bins_x: Numbers of bins to divide the input feature maps over
    :param spatial_bins_y: Numbers of bins to divide the input feature maps over
    :param mode: Mode of pooling - "avg" or "bilinear"
    :return: PSROIPooling node
    """
    mode = mode.lower()
    return _get_node_factory().create('PSROIPooling', [input, as_node(coords)],
                                      {
                                          'output_dim': output_dim,
                                          'group_size': group_size,
                                          'spatial_scale': spatial_scale,
                                          'spatial_bins_x': spatial_bins_x,
                                          'spatial_bins_y': spatial_bins_y,
                                          'mode': mode,
    })


@nameable_op
def reverse_sequence(input, seq_lengths, batch_axis, seq_axis, name=None):
    # type: (Node, NodeInput, NumericData, NumericData, str) -> Node
    """Return a node which produces a ReverseSequence operation.

    :param input: tensor with input data to reverse
    :param seq_lengths: 1D tensor of integers with sequence lengths in the input tensor.
    :param batch_axis: index of the batch dimension.
    :param seq_axis: index of the sequence dimension.
    :return: ReverseSequence node
    """
    return _get_node_factory().create('ReverseSequence', [input, as_node(seq_lengths)],
                                      {'batch_axis': batch_axis, 'seq_axis': seq_axis})
