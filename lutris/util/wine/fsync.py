"""Module for detecting the availability of the Linux futex
FUTEX_WAIT_MULTIPLE operation, or the Linux futex2 syscalls.

Either of these is required for fsync to work in Wine. Fsync is an
alternative implementation of the Windows synchronization primitives
that are used to guard data from being accessed by multiple threads
concurrently (which would be A Bad Thing™).

Fsync improves upon the previous implementation in Wine of these
primitives, known as esync, which in turn improved upon the original
implementation known as "Server-side synchronization".

The original implementation used a wineserver call for each
synchronization operation, which required multiple context switches per
operation.

Esync instead used file descriptors for synchronization, which can be
passed around between processes and therefore allowed synchronization
to happen directly between the processes involved, instead of going
through the wineserver. This made the synchronization operations
faster and improved performance of games a bit.
A problem with this implementation was that each created synchronization
object required one file descriptor, and there is only a limited amount
of these available for each process. Some games would run out of
available file descriptors, and would stop working. This has been partly
mitigated by raising the per-process file descriptor limit, but there
are also games that leak synchronization objects continuously while
running, and would eventually run out despite the raised limits.

Fsync improved on esync by not requiring a file descriptor for each
created synchronization object, and instead using the Linux kernel's
futex interface for synchronizations. This matches Windows's
implementation more closely and mitigated all the file descriptor
related issues of esync. However, since the default futex interface was
insufficient for implementing all required synchronization operations,
a patch to the Linux kernel was needed, which usually meant that users
needed to compile their own Linux kernel with the patch, or install a
kernel provided by a third-party. It was attempted to get the kernel
patch into the mainline Linux kernel, but it didn't get accepted.

Instead, patches were written that would add a new set of system calls
which extend the original futex system calls, dubbed "futex2", and the
Wine fsync code was adjusted to make use of these new system calls.
The new Wine fsync code is backwards-compatible with the old futex
patch, therefore it makes sense for now to detect the presence of
either patch in the running kernel. The detection of the old patch
can probably be removed when the new patch is merged and in a stable
Linux release.

This module's code is based on https://gist.github.com/openglfreak/715d5ab5902497378f1996061dbbf8ec
"""

import ctypes
import errno
import os
import subprocess

__all__ = ("get_fsync_support",)

from lutris.util import cache_single


# pylint: disable=invalid-name,too-few-public-methods
class timespec(ctypes.Structure):
    """Linux kernel compatible timespec type.

    Fields:
        tv_sec: The whole seconds of the timespec.
        tv_nsec: The nanoseconds of the timespec.
    """

    __slots__ = ()
    _fields_ = [
        ("tv_sec", ctypes.c_long),
        ("tv_nsec", ctypes.c_long),
    ]


def _get_syscall_nr_from_headers(syscall_name):
    bits = ctypes.sizeof(ctypes.c_void_p) * 8

    try:
        with subprocess.Popen(
            ("cpp", "-m" + str(bits), "-E", "-P", "-x", "c", "-"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            universal_newlines=True,
        ) as popen:
            stdout, stderr = popen.communicate("#include <sys/syscall.h>\n__NR_" + syscall_name + "\n")
    except FileNotFoundError as ex:
        raise RuntimeError(
            "failed to determine " + syscall_name + " syscall number: cpp not installed or not in PATH"
        ) from ex

    if popen.returncode:
        raise RuntimeError(
            "failed to determine " + syscall_name + " syscall number: cpp returned nonzero exit code", stderr
        )

    if not stdout:
        raise RuntimeError("failed to determine " + syscall_name + " syscall number: no output from cpp")

    last_line = stdout.splitlines()[-1]

    if last_line == "__NR_futex":
        raise RuntimeError(
            "failed to determine " + syscall_name + " syscall number: __NR_" + syscall_name + " not expanded"
        )

    try:
        return int(last_line)
    except ValueError as ex:
        raise RuntimeError(
            "failed to determine " + syscall_name + " syscall number: "
            "__NR_" + syscall_name + " not a valid number: " + last_line
        ) from ex

    assert False


# Hardcode some of the most commonly used architectures's
# futex syscall numbers.
_NR_FUTEX_PER_ARCH = {
    ("i386", 32): 240,
    ("i686", 32): 240,
    ("x86_64", 32): 240,
    ("x86_64", 64): 202,
    ("aarch64", 64): 240,
    ("aarch64_be", 64): 240,
    ("armv8b", 32): 240,
    ("armv8l", 32): 240,
}


def _get_futex_syscall_nr():
    """Get the syscall number of the Linux futex() syscall.

    Returns:
        The futex() syscall number.

    Raises:
        RuntimeError: When the syscall number could not be determined.
    """
    bits = ctypes.sizeof(ctypes.c_void_p) * 8

    try:
        return _NR_FUTEX_PER_ARCH[(os.uname()[4], bits)]
    except KeyError:
        pass

    return _get_syscall_nr_from_headers("futex")


def _is_ctypes_obj(obj):
    return hasattr(obj, "_b_base_") and hasattr(obj, "_b_needsfree_") and hasattr(obj, "_objects")


def _is_ctypes_obj_pointer(obj):
    return hasattr(obj, "_type_") and hasattr(obj, "contents")


def _coerce_to_pointer(obj):
    if obj is None:
        return None

    if _is_ctypes_obj(obj):
        if _is_ctypes_obj_pointer(obj):
            return obj
        return ctypes.pointer(obj)

    obj = tuple(obj)
    return (obj[0].__class__ * len(obj))(*obj)


def _get_futex_syscall():
    """Create a function that can be used to execute the Linux futex()
    syscall.

    Returns:
        A proxy function for the Linux futex() syscall.

    Raises:
        AttributeError: When the libc has no syscall() function.
        RuntimeError: When the syscall number could not be determined.
    """
    futex_syscall = ctypes.CDLL(None, use_errno=True).syscall
    futex_syscall.argtypes = (
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(timespec),
        ctypes.c_void_p,
        ctypes.c_int,
    )
    futex_syscall.restype = ctypes.c_int
    futex_syscall_nr = _get_futex_syscall_nr()

    # pylint: disable=too-many-arguments
    def _futex_syscall(uaddr, futex_op, val, timeout, uaddr2, val3):
        """Invoke the Linux futex() syscall with the provided arguments.

        Args:
            See the description of the futex() syscall for the parameter
            meanings.
            `uaddr` and `uaddr2` are automatically converted to pointers.
            If timeout is None, a zero timeout is passed.

        Returns:
            A tuple of the return value of the syscall and the error code
            in case an error occurred.

        Raises:
            AttributeError: When the libc has no syscall() function.
            RuntimeError: When the syscall number could not be determined.
            TypeError: If `uaddr` or `uaddr2` is not a pointer and can't be
                converted into one.
        """
        error = futex_syscall(
            futex_syscall_nr,
            _coerce_to_pointer(uaddr),
            futex_op,
            val,
            _coerce_to_pointer(timeout or timespec()),
            _coerce_to_pointer(uaddr2),
            val3,
        )
        return error, (ctypes.get_errno() if error == -1 else 0)

    return _futex_syscall


def _get_futex_wait_multiple_op(futex_syscall):
    """Detects which (if any) futex opcode is used for the
    FUTEX_WAIT_MULTIPLE operation on this kernel.

    Returns:
        The opcode number, or None if the operation is not supported.
    """
    ret = futex_syscall(None, 31, 0, None, None, 0)
    if ret[1] != errno.ENOSYS:
        return 31
    ret = futex_syscall(None, 13, 0, None, None, 0)
    if ret[1] != errno.ENOSYS:
        return 13
    return None


@cache_single
def is_futex_wait_multiple_supported():
    """Checks whether the Linux futex FUTEX_WAIT_MULTIPLE operation is
    supported on this kernel.

    Returns:
        Whether this kernel supports the FUTEX_WAIT_MULTIPLE operation.
    """
    try:
        return _get_futex_wait_multiple_op(_get_futex_syscall()) is not None
    except (AttributeError, RuntimeError):
        return False


@cache_single
def is_futex2_supported():
    """Checks whether the Linux futex2 syscall is supported on this
    kernel.

    Returns:
        Whether this kernel supports the futex2 syscall.
    """
    try:
        for filename in ("wait", "waitv", "wake"):
            with open("/sys/kernel/futex2/" + filename, "rb") as file:
                if not file.readline().strip().isdigit():
                    return False
    except OSError:
        return False
    return True


# Hardcode some of the most commonly used architectures's
# futex_waitv syscall numbers.
_NR_FUTEX_WAITV_PER_ARCH = {
    ("i386", 32): 449,
    ("i686", 32): 449,
    ("x86_64", 32): 449,
    ("x86_64", 64): 449,
    ("aarch64", 64): 449,
    ("aarch64_be", 64): 449,
    ("armv8b", 32): 449,
    ("armv8l", 32): 449,
}


def _get_futex_waitv_syscall_nr():
    """Get the syscall number of the Linux futex_waitv() syscall.

    Returns:
        The futex_waitv() syscall number.

    Raises:
        RuntimeError: When the syscall number could not be determined.
    """
    bits = ctypes.sizeof(ctypes.c_void_p) * 8

    try:
        return _NR_FUTEX_WAITV_PER_ARCH[(os.uname()[4], bits)]
    except KeyError:
        pass

    return _get_syscall_nr_from_headers("futex_waitv")


# pylint: disable=invalid-name,too-few-public-methods
class futex_waitv(ctypes.Structure):
    """Linux kernel compatible futex_waitv type.

    Fields:
        val: The expected value.
        uaddr: The address to wait for.
        flags: The type and size of the futex.
    """

    __slots__ = ()
    _fields_ = [
        ("val", ctypes.c_uint64),
        ("uaddr", ctypes.c_void_p),
        ("flags", ctypes.c_uint),
    ]


def _get_futex_waitv_syscall():
    """Create a function that can be used to execute the Linux
    futex_waitv() syscall.

    Returns:
        A proxy function for the Linux futex_waitv() syscall.

    Raises:
        AttributeError: When the libc has no syscall() function.
        RuntimeError: When the syscall number could not be determined.
    """
    futex_waitv_syscall = ctypes.CDLL(None, use_errno=True).syscall
    futex_waitv_syscall.argtypes = (
        ctypes.c_long,
        ctypes.POINTER(futex_waitv),
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.POINTER(timespec),
    )
    futex_waitv_syscall.restype = ctypes.c_long
    futex_waitv_syscall_nr = _get_futex_waitv_syscall_nr()

    # pylint: disable=too-many-arguments
    def _futex_waitv_syscall(waiters, nr_futexes, flags, timeout):
        """Invoke the Linux futex_waitv() syscall with the provided
        arguments.

        Args:
            See the description of the futex_waitv() syscall for the
            parameter meanings.
            `waiters` is automatically converted to a pointer.
            If timeout is None, a zero timeout is passed.

        Returns:
            A tuple of the return value of the syscall and the error code
            in case an error occurred.

        Raises:
            AttributeError: When the libc has no syscall() function.
            RuntimeError: When the syscall number could not be determined.
            TypeError: If `waiters` is not a pointer and can't be
                converted into one.
        """
        error = futex_waitv_syscall(
            futex_waitv_syscall_nr, _coerce_to_pointer(waiters), nr_futexes, flags, _coerce_to_pointer(timeout)
        )
        return error, (ctypes.get_errno() if error == -1 else 0)

    return _futex_waitv_syscall


@cache_single
def is_futex_waitv_supported():
    """Checks whether the Linux 5.16 futex_waitv syscall is supported on
    this kernel.

    Returns:
        Whether this kernel supports the futex_waitv syscall.
    """
    try:
        ret = _get_futex_waitv_syscall()(None, 0, 0, None)
        return ret[1] != errno.ENOSYS
    except (AttributeError, RuntimeError):
        return False


@cache_single
def get_fsync_support():
    """Checks whether the FUTEX_WAIT_MULTIPLE operation, the futex2
    syscalls, or the futex_waitv syscall is supported on this kernel.

    Returns:
        The result of the check.
    """
    if is_futex_waitv_supported():
        return True
    if is_futex2_supported():
        return True
    if is_futex_wait_multiple_supported():
        return True
    return False
