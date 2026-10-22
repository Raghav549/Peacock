"""Dependency-free tensor compute backends, including a real OpenCL 1.2 path.

The CPU backend is always available and is the reference implementation.  The
OpenCL backend dynamically loads the platform driver, selects an actual GPU or
accelerator, compiles kernels, allocates device buffers and waits for completion.
No hardware claim is made when no such driver/device exists.  ``auto`` may use
CPU; an explicit ``opencl`` request never silently falls back.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import threading
from dataclasses import dataclass

from . import tensor as T
from .tensor import Tensor, TensorError


class GPUError(RuntimeError):
    """Device discovery, compilation, transfer or kernel execution failed."""


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    backend: str
    name: str
    vendor: str
    version: str
    hardware: bool

    def lines(self) -> list[str]:
        return [
            f"backend={self.backend}", f"device={self.name}",
            f"vendor={self.vendor}", f"version={self.version}",
            f"hardware={'yes' if self.hardware else 'no'}",
        ]


class CPUBackend:
    info = DeviceInfo("cpu", "Python binary64 reference", "PEACOCK", "0.4", False)

    def close(self):
        return None

    @staticmethod
    def _check(a: Tensor, b: Tensor | None = None):
        tensors = (a,) if b is None else (a, b)
        for tensor in tensors:
            if tensor.dtype not in T.FLOAT_DTYPES or not tensor.data:
                raise GPUError("accelerate operations require nonempty Float32/Float64 tensors")
        if b is not None and a.shape != b.shape:
            raise GPUError(f"accelerate elementwise operations require equal shapes, got {a.shape} and {b.shape}")

    def add(self, a, b):
        self._check(a, b)
        return T.add(a, b)

    def multiply(self, a, b):
        self._check(a, b)
        return T.mul(a, b)

    def relu(self, a):
        self._check(a)
        return T.relu(a)

    def matmul(self, a, b):
        self._check(a)
        self._check(b)
        if len(a.shape) != 2 or len(b.shape) != 2 or a.shape[1] != b.shape[0]:
            raise GPUError(f"accelerate matmul requires [m,k] × [k,n], got {a.shape} and {b.shape}")
        return T.matmul(a, b)


_KERNEL_SOURCE = r"""
__kernel void peacock_add(__global const float *a, __global const float *b,
                          __global float *out) {
    size_t i = get_global_id(0);
    out[i] = a[i] + b[i];
}
__kernel void peacock_multiply(__global const float *a, __global const float *b,
                               __global float *out) {
    size_t i = get_global_id(0);
    out[i] = a[i] * b[i];
}
__kernel void peacock_relu(__global const float *a, __global float *out) {
    size_t i = get_global_id(0);
    out[i] = fmax(a[i], 0.0f);
}
__kernel void peacock_matmul(__global const float *a, __global const float *b,
                             __global float *out, int m, int k, int n) {
    size_t col = get_global_id(0);
    size_t row = get_global_id(1);
    if (row >= (size_t)m || col >= (size_t)n) return;
    float sum = 0.0f;
    for (int j = 0; j < k; ++j)
        sum += a[row * (size_t)k + (size_t)j] * b[(size_t)j * (size_t)n + col];
    out[row * (size_t)n + col] = sum;
}
"""

_CL_DEVICE_NOT_FOUND = -1
_CL_DEVICE_TYPE_GPU = 1 << 2
_CL_DEVICE_TYPE_ACCELERATOR = 1 << 3
_CL_MEM_WRITE_ONLY = 1 << 1
_CL_MEM_READ_ONLY = 1 << 2
_CL_MEM_COPY_HOST_PTR = 1 << 5
_CL_CONTEXT_PLATFORM = 0x1084
_CL_DEVICE_NAME = 0x102B
_CL_DEVICE_VENDOR = 0x102C
_CL_DEVICE_VERSION = 0x102F
_CL_PROGRAM_BUILD_LOG = 0x1183
_MAX_ELEMENTS = 16_777_216


def _library_candidates():
    found = ctypes.util.find_library("OpenCL")
    names = [found] if found else []
    names.extend(["libOpenCL.so.1", "libOpenCL.so", "OpenCL.dll", "/System/Library/Frameworks/OpenCL.framework/OpenCL"])
    return tuple(dict.fromkeys(name for name in names if name))


class _OpenCLAPI:
    def __init__(self):
        errors = []
        self.lib = None
        for name in _library_candidates():
            try:
                self.lib = ctypes.CDLL(name)
                break
            except OSError as exc:
                errors.append(str(exc))
        if self.lib is None:
            raise GPUError("no OpenCL platform library is installed")
        lib = self.lib
        vp = ctypes.c_void_p
        self._configure(lib.clGetPlatformIDs, [ctypes.c_uint32, ctypes.POINTER(vp), ctypes.POINTER(ctypes.c_uint32)])
        self._configure(lib.clGetDeviceIDs, [vp, ctypes.c_uint64, ctypes.c_uint32, ctypes.POINTER(vp), ctypes.POINTER(ctypes.c_uint32)])
        self._configure(lib.clCreateContext, [ctypes.POINTER(ctypes.c_ssize_t), ctypes.c_uint32, ctypes.POINTER(vp), vp, vp, ctypes.POINTER(ctypes.c_int32)], vp)
        self._configure(lib.clCreateCommandQueue, [vp, vp, ctypes.c_uint64, ctypes.POINTER(ctypes.c_int32)], vp)
        self._configure(lib.clCreateProgramWithSource, [vp, ctypes.c_uint32, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_int32)], vp)
        self._configure(lib.clBuildProgram, [vp, ctypes.c_uint32, ctypes.POINTER(vp), ctypes.c_char_p, vp, vp])
        self._configure(lib.clCreateKernel, [vp, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int32)], vp)
        self._configure(lib.clSetKernelArg, [vp, ctypes.c_uint32, ctypes.c_size_t, vp])
        self._configure(lib.clCreateBuffer, [vp, ctypes.c_uint64, ctypes.c_size_t, vp, ctypes.POINTER(ctypes.c_int32)], vp)
        self._configure(lib.clEnqueueNDRangeKernel, [vp, vp, ctypes.c_uint32, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t), ctypes.c_uint32, vp, vp])
        self._configure(lib.clEnqueueReadBuffer, [vp, vp, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_size_t, vp, ctypes.c_uint32, vp, vp])
        self._configure(lib.clFinish, [vp])
        for name in ("clReleaseMemObject", "clReleaseKernel", "clReleaseProgram", "clReleaseCommandQueue", "clReleaseContext"):
            self._configure(getattr(lib, name), [vp])
        self._configure(lib.clGetDeviceInfo, [vp, ctypes.c_uint32, ctypes.c_size_t, vp, ctypes.POINTER(ctypes.c_size_t)])
        self._configure(lib.clGetProgramBuildInfo, [vp, vp, ctypes.c_uint32, ctypes.c_size_t, vp, ctypes.POINTER(ctypes.c_size_t)])

    @staticmethod
    def _configure(function, arguments, result=ctypes.c_int32):
        function.argtypes = arguments
        function.restype = result

    def check(self, status, operation):
        if status != 0:
            raise GPUError(f"{operation} failed with OpenCL status {status}")

    def platforms_devices(self):
        count = ctypes.c_uint32()
        self.check(self.lib.clGetPlatformIDs(0, None, ctypes.byref(count)), "clGetPlatformIDs")
        if not count.value:
            return []
        platforms = (ctypes.c_void_p * count.value)()
        self.check(self.lib.clGetPlatformIDs(count, platforms, None), "clGetPlatformIDs")
        found = []
        for platform in platforms:
            device_count = ctypes.c_uint32()
            status = self.lib.clGetDeviceIDs(
                platform, _CL_DEVICE_TYPE_GPU | _CL_DEVICE_TYPE_ACCELERATOR,
                0, None, ctypes.byref(device_count),
            )
            if status == _CL_DEVICE_NOT_FOUND:
                continue
            self.check(status, "clGetDeviceIDs")
            devices = (ctypes.c_void_p * device_count.value)()
            self.check(self.lib.clGetDeviceIDs(
                platform, _CL_DEVICE_TYPE_GPU | _CL_DEVICE_TYPE_ACCELERATOR,
                device_count, devices, None,
            ), "clGetDeviceIDs")
            found.extend((platform, device) for device in devices)
        return found

    def device_string(self, device, parameter):
        size = ctypes.c_size_t()
        self.check(self.lib.clGetDeviceInfo(device, parameter, 0, None, ctypes.byref(size)), "clGetDeviceInfo")
        if not size.value or size.value > 65536:
            raise GPUError("OpenCL device returned an invalid information size")
        buffer = ctypes.create_string_buffer(size.value)
        self.check(self.lib.clGetDeviceInfo(device, parameter, size, buffer, None), "clGetDeviceInfo")
        return buffer.value.decode("utf-8", "replace")


def opencl_devices() -> list[tuple[DeviceInfo, object, object]]:
    """Return actual accelerator handles; an empty list means unavailable."""

    try:
        api = _OpenCLAPI()
        pairs = api.platforms_devices()
        return [(
            DeviceInfo(
                "opencl", api.device_string(device, _CL_DEVICE_NAME),
                api.device_string(device, _CL_DEVICE_VENDOR),
                api.device_string(device, _CL_DEVICE_VERSION), True,
            ), platform, device,
        ) for platform, device in pairs]
    except (GPUError, OSError, AttributeError):
        return []


class OpenCLBackend:
    """One OpenCL context/queue with explicit, bounded synchronous operations."""

    def __init__(self, device_index: int = 0):
        self.api = _OpenCLAPI()
        pairs = self.api.platforms_devices()
        if not pairs:
            raise GPUError("no OpenCL GPU/accelerator device is available")
        if not isinstance(device_index, int) or not 0 <= device_index < len(pairs):
            raise GPUError(f"OpenCL device index must be in 0..{len(pairs) - 1}")
        platform, self.device = pairs[device_index]
        self.info = DeviceInfo(
            "opencl", self.api.device_string(self.device, _CL_DEVICE_NAME),
            self.api.device_string(self.device, _CL_DEVICE_VENDOR),
            self.api.device_string(self.device, _CL_DEVICE_VERSION), True,
        )
        self.context = self.queue = self.program = None
        self._lock = threading.Lock()
        error = ctypes.c_int32()
        properties = (ctypes.c_ssize_t * 3)(_CL_CONTEXT_PLATFORM, platform.value or 0, 0)
        self.context = self.api.lib.clCreateContext(properties, 1, ctypes.byref(self.device), None, None, ctypes.byref(error))
        self.api.check(error.value, "clCreateContext")
        try:
            self.queue = self.api.lib.clCreateCommandQueue(self.context, self.device, 0, ctypes.byref(error))
            self.api.check(error.value, "clCreateCommandQueue")
            encoded = _KERNEL_SOURCE.encode("utf-8")
            source = (ctypes.c_char_p * 1)(encoded)
            lengths = (ctypes.c_size_t * 1)(len(encoded))
            self.program = self.api.lib.clCreateProgramWithSource(self.context, 1, source, lengths, ctypes.byref(error))
            self.api.check(error.value, "clCreateProgramWithSource")
            status = self.api.lib.clBuildProgram(self.program, 1, ctypes.byref(self.device), b"", None, None)
            if status != 0:
                size = ctypes.c_size_t()
                self.api.lib.clGetProgramBuildInfo(self.program, self.device, _CL_PROGRAM_BUILD_LOG, 0, None, ctypes.byref(size))
                log = "no build log"
                if 0 < size.value <= 1_048_576:
                    buffer = ctypes.create_string_buffer(size.value)
                    self.api.lib.clGetProgramBuildInfo(self.program, self.device, _CL_PROGRAM_BUILD_LOG, size, buffer, None)
                    log = buffer.value.decode("utf-8", "replace")
                raise GPUError(f"OpenCL kernel compilation failed ({status}): {log}")
        except Exception:
            self.close()
            raise

    def close(self):
        for attribute, release in (
            ("program", "clReleaseProgram"), ("queue", "clReleaseCommandQueue"),
            ("context", "clReleaseContext"),
        ):
            handle = getattr(self, attribute, None)
            if handle:
                getattr(self.api.lib, release)(handle)
                setattr(self, attribute, None)

    def __del__(self):  # pragma: no cover - explicit close is the tested path
        try:
            self.close()
        except Exception:
            pass

    @staticmethod
    def _array(tensor: Tensor):
        if tensor.dtype not in T.FLOAT_DTYPES or not tensor.data:
            raise GPUError("OpenCL operations require nonempty Float32/Float64 tensors")
        if len(tensor.data) > _MAX_ELEMENTS:
            raise GPUError(f"OpenCL tensor exceeds {_MAX_ELEMENTS} elements")
        try:
            return (ctypes.c_float * len(tensor.data))(*tensor.data)
        except (TypeError, ValueError, OverflowError) as exc:
            raise GPUError(f"tensor cannot be converted to finite OpenCL float32: {exc}") from exc

    def _buffer(self, flags, array=None, size=None):
        error = ctypes.c_int32()
        byte_count = size if size is not None else ctypes.sizeof(array)
        pointer = ctypes.cast(array, ctypes.c_void_p) if array is not None else None
        if array is not None:
            flags |= _CL_MEM_COPY_HOST_PTR
        handle = self.api.lib.clCreateBuffer(self.context, flags, byte_count, pointer, ctypes.byref(error))
        self.api.check(error.value, "clCreateBuffer")
        return handle

    def _execute(self, kernel_name, inputs, output_count, dimensions, scalars=()):
        if not 0 < output_count <= _MAX_ELEMENTS:
            raise GPUError("OpenCL output size exceeds device-operation limits")
        kernel = output = None
        buffers = []
        try:
            error = ctypes.c_int32()
            kernel = self.api.lib.clCreateKernel(self.program, kernel_name.encode("ascii"), ctypes.byref(error))
            self.api.check(error.value, "clCreateKernel")
            index = 0
            for array in inputs:
                handle = self._buffer(_CL_MEM_READ_ONLY, array)
                buffers.append(handle)
                self.api.check(self.api.lib.clSetKernelArg(kernel, index, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(ctypes.c_void_p(handle))), "clSetKernelArg(input)")
                index += 1
            output = self._buffer(_CL_MEM_WRITE_ONLY, size=output_count * ctypes.sizeof(ctypes.c_float))
            self.api.check(self.api.lib.clSetKernelArg(kernel, index, ctypes.sizeof(ctypes.c_void_p), ctypes.byref(ctypes.c_void_p(output))), "clSetKernelArg(output)")
            index += 1
            for scalar in scalars:
                value = ctypes.c_int32(scalar)
                self.api.check(self.api.lib.clSetKernelArg(kernel, index, ctypes.sizeof(value), ctypes.byref(value)), "clSetKernelArg(scalar)")
                index += 1
            global_size = (ctypes.c_size_t * len(dimensions))(*dimensions)
            self.api.check(self.api.lib.clEnqueueNDRangeKernel(
                self.queue, kernel, len(dimensions), None, global_size, None, 0, None, None,
            ), "clEnqueueNDRangeKernel")
            self.api.check(self.api.lib.clFinish(self.queue), "clFinish")
            result = (ctypes.c_float * output_count)()
            self.api.check(self.api.lib.clEnqueueReadBuffer(
                self.queue, output, 1, 0, ctypes.sizeof(result), result, 0, None, None,
            ), "clEnqueueReadBuffer")
            return list(result)
        finally:
            if output:
                self.api.lib.clReleaseMemObject(output)
            for handle in buffers:
                self.api.lib.clReleaseMemObject(handle)
            if kernel:
                self.api.lib.clReleaseKernel(kernel)

    def _elementwise(self, name, a, b=None):
        CPUBackend._check(a, b)
        arrays = [self._array(a)] + ([] if b is None else [self._array(b)])
        with self._lock:
            data = self._execute(name, arrays, len(a.data), (len(a.data),))
        return Tensor(data, a.shape, dtype="Float32")

    def add(self, a, b):
        return self._elementwise("peacock_add", a, b)

    def multiply(self, a, b):
        return self._elementwise("peacock_multiply", a, b)

    def relu(self, a):
        return self._elementwise("peacock_relu", a)

    def matmul(self, a, b):
        CPUBackend._check(a)
        CPUBackend._check(b)
        if len(a.shape) != 2 or len(b.shape) != 2 or a.shape[1] != b.shape[0]:
            raise GPUError(f"OpenCL matmul requires [m,k] × [k,n], got {a.shape} and {b.shape}")
        m, k, n = a.shape[0], a.shape[1], b.shape[1]
        if m * n > _MAX_ELEMENTS:
            raise GPUError("OpenCL matmul output exceeds element limit")
        with self._lock:
            data = self._execute("peacock_matmul", [self._array(a), self._array(b)], m * n, (n, m), (m, k, n))
        return Tensor(data, (m, n), dtype="Float32")


def backend_names() -> list[str]:
    return ["cpu"] + (["opencl"] if opencl_devices() else [])


def create_backend(name: str = "auto"):
    """Create ``cpu``, ``opencl`` or auto (OpenCL when available, else CPU)."""

    if name == "cpu":
        return CPUBackend()
    if name == "opencl":
        return OpenCLBackend()
    if name != "auto":
        raise GPUError(f"unknown compute backend {name!r}; expected auto, cpu or opencl")
    try:
        return OpenCLBackend()
    except GPUError:
        return CPUBackend()


__all__ = ["CPUBackend", "DeviceInfo", "GPUError", "OpenCLBackend", "backend_names", "create_backend", "opencl_devices"]
