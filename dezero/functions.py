import numpy as np
import dezero

from dezero import utils
from dezero.core import Function, Variable, as_variable, as_array

# =============================================================================
# Basic functions: sin / cos / tanh / exp / log
# =============================================================================


class Sin(Function):
    def forward(self, x):
        y = np.sin(x)
        return y

    def backward(self, gy):
        (x,) = self.inputs
        gx = gy * cos(x)
        return gx


def sin(x):
    return Sin()(x)


class Cos(Function):
    def forward(self, x):
        y = np.cos(x)
        return y

    def backward(self, gy):
        (x,) = self.inputs
        gx = gy * -sin(x)
        return gx


def cos(x):
    return Cos()(x)


class Tanh(Function):
    def forward(self, x):
        y = np.tanh(x)
        return y

    def backward(self, gy):
        y = self.outputs[0]()
        gx = gy * (1 - y ** 2)
        return gx


def tanh(x):
    return Tanh()(x)


class Exp(Function):
    def forward(self, x):
        return np.exp(x)

    def backward(self, gy):
        y = self.outputs[0]()  # weakref
        gx = gy * y
        return gx


# 클래스 생성 편의함수
def exp(x):
    return Exp()(x)


class Log(Function):
    def forward(self, x):
        y = np.log(x)
        return y

    def backward(self, gy):
        (x,) = self.inputs
        gx = gy / x
        return gx


def log(x):
    return Log()(x)


# =============================================================================
# Tensor operations: reshape / transpose / get_item / expand_dims / flatten
# =============================================================================


class Reshape(Function):
    def __init__(self, shape) -> None:
        self.shape = shape

    def forward(self, x):
        self.x_shape = x.shape
        y = x.reshape(self.shape)
        return y

    def backward(self, gy):
        return reshape(gy, self.x_shape)


def reshape(x, shape):
    if x.shape == shape:
        return as_array(x)
    return Reshape(shape)(x)


class Transpose(Function):
    def __init__(self, axes=None):
        self.axes = axes

    def forward(self, x):
        y = x.transpose(self.axes)
        return y

    def backward(self, gy):
        if self.axes is None:
            return transpose(gy)

        axes_len = len(self.axes)
        inv_axes = tuple(np.argsort([ax % axes_len for ax in self.axes]))
        return transpose(gy, inv_axes)


def transpose(x, axes=None):
    return Transpose(axes)(x)


class GetItemGrad(Function):
    def __init__(self, slices, in_shape) -> None:
        self.slices = slices
        self.in_shpae = in_shape

    def forward(self, gy):
        gx = np.zeros(self.in_shpae)
        np.add.at(gx, self.slices, gy)
        return gx

    def backward(self, ggx):
        return get_item(ggx, self.slices)


class GetItem(Function):
    def __init__(self, slices) -> None:
        self.slices = slices

    def forward(self, x):
        y = x[self.slices]
        return y

    def backward(self, gy):
        (x,) = self.inputs
        f = GetItemGrad(self.slices, x.shape)
        return f(gy)


def get_item(x, slices):
    return GetItem(slices)(x)


# =============================================================================
# sum / sum_to / broadcast_to / average / matmul / linear
# =============================================================================


class Sum(Function):
    def __init__(self, axis, keepdims) -> None:
        self.axis = axis
        self.keepdims = keepdims

    def forward(self, x):
        self.x_shape = x.shape
        y = x.sum(axis=self.axis, keepdims=self.keepdims)
        return y

    def backward(self, gy):
        gy = utils.reshape_sum_backward(gy, self.x_shape, self.axis, self.keepdims)
        gx = broadcast_to(gy, self.x_shape)
        return gx


def sum(x, axis=None, keepdims=False):
    return Sum(axis, keepdims)(x)


class SumTo(Function):
    def __init__(self, shape) -> None:
        self.shape = shape

    def forward(self, x):
        self.x_shape = x.shape
        y = utils.sum_to(x, self.shape)
        return y

    def backward(self, gy):
        gx = broadcast_to(gy, self.x_shape)
        return gx


def sum_to(x, shape):
    if x.shape == shape:
        return as_variable(x)
    return SumTo(shape)(x)


class BroadcastTo(Function):
    def __init__(self, shape) -> None:
        self.shape = shape

    def forward(self, x):
        self.x_shape = x.shape
        y = np.broadcast_to(x, self.shape)
        return y

    def backward(self, gy):
        gx = sum_to(gy, self.x_shape)
        return gx


def broadcast_to(x, shape):
    if x.shape == shape:
        return as_variable(x)
    return BroadcastTo(shape)(x)


class MatMul(Function):
    def forward(self, x, W):
        y = x.dot(W)
        return y

    def backward(self, gy):
        x, W = self.inputs
        gx = matmul(gy, W.T)
        gW = matmul(x.T, gy)
        return gx, gW


def matmul(x, W):
    return MatMul()(x, W)


class Linear(Function):
    def forward(self, x, W, b=None):
        y = x.dot(W)
        if b is not None:
            y += b
        return y

    def backward(self, gy):
        x, W, b = self.inputs
        gb = None if b.data is None else sum_to(gy, b.shape)
        gx = matmul(gy, W.T)
        gW = matmul(x.T, gy)
        return gx, gW, gb


def linear(x, W, b=None):
    return Linear()(x, W, b)


def linear_simple(x, W, b=None):
    t = matmul(x, W)
    if b is None:
        return t

    y = t + b
    t.data = None  # Release t.data (ndarray) for memory efficiency
    return y


# =============================================================================
# activation function: sigmoid / relu / softmax / log_softmax / leaky_relu
# =============================================================================


class Sigmoid(Function):
    def forward(self, x):
        y = 1 / (1 + np.exp(-x))
        return y

    def backward(self, gy):
        y = self.outputs[0]()
        gx = gy * y * (1 - y)
        return gx


def sigmoid(x):
    return Sigmoid()(x)


def sigmoid_simple(x):
    x = as_variable(x)
    y = 1 / (1 + exp(-x))
    return y


class Softmax(Function):
    def __init__(self, axis=1):
        self.axis = axis

    def forward(self, x):
        y = np.exp(x)
        y /= y.sum(axis=self.axis, keepdims=True)
        return y

    def backward(self, gy):
        y = self.outputs[0]()
        gx = y * gy
        sumdx = gx.sum(axis=self.axis, keepdims=True)
        gx -= y * sumdx
        return gx


def softmax(x, axis=1):
    return Softmax(axis)(x)


def softmax_simple(x, axis=1):
    x = as_variable(x)
    y = exp(y)
    sum_y = sum(y, axis=axis, keepdims=True)
    return y / sum_y


# =============================================================================
# loss function: mean_squared_error / softmax_cross_entropy / sigmoid_cross_entropy / binary_cross_entropy
# =============================================================================


class MeanSquareError(Function):
    def forward(self, x0, x1):
        diff = x0 - x1
        y = (diff ** 2).sum() / len(diff)
        return y

    def backward(self, gy):
        x0, x1 = self.inputs
        diff = x0 - x1
        gx0 = gy * diff * (2.0 / len(diff))
        gx1 = -gx0
        return gx0, gx1


def mean_squared_error(x0, x1):
    return MeanSquareError()(x0, x1)


def softmax_cross_entropy_simple(x, t):
    x, t = as_variable(x), as_variable(t)
    N = x.shape[0]
    p = softmax(x)
    p = clip(p, 1e-15, 1.0)  # To avoid log(0)
    log_p = log(p)
    tlog_p = log_p[np.arange(N), t.data]
    y = -1 * sum(tlog_p) / N
    return y


class SoftmaxCrossEntropy(Function):
    def forward(self, x, t):
        N = x.shape[0]
        log_z = utils.logsumexp(x, axis=1)
        log_p = x - log_z
        log_p = log_p[np.arange(N), t.ravel()]
        y = -log_p.sum() / np.float32(N)
        return y

    def backward(self, gy):
        x, t = self.inputs
        N, CLS_NUM = x.shape

        gy *= 1 / N
        y = softmax(x)
        # convert to one-hot
        # xp = cuda.get_array_module(t.data)
        t_onehot = np.eye(CLS_NUM)[t.data]
        y = (y - t_onehot) * gy
        return y


def softmax_cross_entropy(x, t):
    return SoftmaxCrossEntropy()(x, t)


# =============================================================================
# max / min / clip
# =============================================================================


class Max(Function):
    def __init__(self, axis=None, keepdims=False):
        self.axis = axis
        self.keepdims = keepdims

    def forward(self, x):
        y = x.max(axis=self.axis, keepdims=self.keepdims)
        return y

    def backward(self, gy):
        x = self.inputs[0]
        y = self.outputs[0]()  # weakref

        shape = utils.max_backward_shape(x, self.axis)
        gy = reshape(gy, shape)
        y = reshape(y, shape)
        cond = x.data == y.data
        gy = broadcast_to(gy, cond.shape)
        return gy * cond


class Min(Max):
    def forward(self, x):
        y = x.min(axis=self.axis, keepdims=self.keepdims)
        return y


def max(x, axis=None, keepdims=False):
    return Max(axis, keepdims)(x)


def min(x, axis=None, keepdims=False):
    return Min(axis, keepdims)(x)


class Clip(Function):
    def __init__(self, x_min, x_max):
        self.x_min = x_min
        self.x_max = x_max

    def forward(self, x):
        y = np.clip(x, self.x_min, self.x_max)
        return y

    def backward(self, gy):
        (x,) = self.inputs
        mask = (x.data >= self.x_min) * (x.data <= self.x_max)
        gx = gy * mask
        return gx


def clip(x, x_min, x_max):
    return Clip(x_min, x_max)(x)


def accuracy(y, t):
    y, t = as_variable(y), as_variable(t)

    pred = y.data.argmax(axis=1).reshape(t.shape)
    result = pred == t.data
    acc = result.mean()
    return Variable(as_array(acc))


from dezero.core import add
from dezero.core import sub
from dezero.core import rsub
from dezero.core import mul
from dezero.core import div
from dezero.core import neg
from dezero.core import pow
