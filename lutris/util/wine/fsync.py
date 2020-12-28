'''Module for detecting the availability of the Linux futex
FUTEX_WAIT_MULTIPLE operation, or the Linux futex2 syscalls.

Based on https://gist.github.com/openglfreak/715d5ab5902497378f1996061dbbf8ec
'''
import ctypes
import errno
import functools
import os
import subprocess

__all__ = ('is_fsync_supported',)


# pylint: disable=invalid-name,too-few-public-methods
class timespec(ctypes.Structure):
    '''Linux kernel compatible timespec type.

    Fields:
        tv_sec: The whole seconds of the timespec.
        tv_nsec: The nanoseconds of the timespec.
    '''
    __slots__ = ()
    _fields_ = [
        ('tv_sec', ctypes.c_long),
        ('tv_nsec', ctypes.c_long),
    ]


# Hardcode some of the most commonly used architectures's
# futex syscall numbers.
_NR_FUTEX_PER_ARCH = {
    ('i386', 32): 240,
    ('i686', 32): 240,
    ('x86_64', 32): 240,
    ('x86_64', 64): 202,
    ('aarch64', 64): 240,
    ('aarch64_be', 64): 240,
    ('armv8b', 32): 240,
    ('armv8l', 32): 240,
}


def _get_futex_syscall_nr():
    '''Get the syscall number of the Linux futex() syscall.

    Returns:
        The futex() syscall number.

    Raises:
        RuntimeError: When the syscall number could not be determined.
    '''
    bits = ctypes.sizeof(ctypes.c_void_p) * 8

    try:
        return _NR_FUTEX_PER_ARCH[(os.uname()[4], bits)]
    except KeyError:
        pass

    try:
        with subprocess.Popen(
                ('cpp', '-m' + str(bits), '-E', '-P', '-x', 'c', '-'),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                universal_newlines=True,
        ) as popen:
            stdout, stderr = popen.communicate(
                '#include <sys/syscall.h>\n'
                '__NR_futex\n'
            )
    except FileNotFoundError as ex:
        raise RuntimeError(
            'failed to determine futex syscall number: '
            'cpp not installed or not in PATH'
        ) from ex

    if popen.returncode:
        raise RuntimeError(
            'failed to determine futex syscall number: '
            'cpp returned nonzero exit code',
            stderr
        )

    if not stdout:
        raise RuntimeError(
            'failed to determine futex syscall number: '
            'no output from cpp'
        )

    last_line = stdout.splitlines()[-1]

    if last_line == '__NR_futex':
        raise RuntimeError(
            'failed to determine futex syscall number: '
            '__NR_futex not expanded'
        )

    try:
        return int(last_line)
    except ValueError as ex:
        raise RuntimeError(
            'failed to determine futex syscall number: '
            '__NR_futex not a valid number: ' + last_line
        ) from ex

    assert False


def _is_ctypes_obj(obj):
    return (
        hasattr(obj, '_b_base_')
        and hasattr(obj, '_b_needsfree_')
        and hasattr(obj, '_objects')
    )


def _is_ctypes_obj_pointer(obj):
    return hasattr(obj, '_type_') and hasattr(obj, 'contents')


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
    '''Create a function that can be used to execute the Linux futex()
    syscall.

    Returns:
        A proxy function for the Linux futex() syscall.

    Raises:
        AttributeError: When the libc has no syscall() function.
        RuntimeError: When the syscall number could not be determined.
    '''
    futex_syscall = ctypes.CDLL(None, use_errno=True).syscall
    futex_syscall.argtypes = (ctypes.c_long, ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_int, ctypes.POINTER(timespec),
                              ctypes.c_void_p, ctypes.c_int)
    futex_syscall.restype = ctypes.c_int
    futex_syscall_nr = _get_futex_syscall_nr()

    # pylint: disable=too-many-arguments
    def _futex_syscall(uaddr, futex_op, val, timeout, uaddr2, val3):
        '''Invoke the Linux futex() syscall with the provided arguments.

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
        '''
        error = futex_syscall(
            futex_syscall_nr,
            _coerce_to_pointer(uaddr),
            futex_op,
            val,
            _coerce_to_pointer(timeout or timespec()),
            _coerce_to_pointer(uaddr2),
            val3
        )
        return error, (ctypes.get_errno() if error == -1 else 0)

    return _futex_syscall


def _get_futex_wait_multiple_op(futex_syscall):
    ret = futex_syscall(None, 31, 0, None, None, 0)
    if ret[1] != errno.ENOSYS:
        return 31
    ret = futex_syscall(None, 13, 0, None, None, 0)
    if ret[1] != errno.ENOSYS:
        return 13
    return None


@functools.lru_cache(None)
def is_futex_wait_multiple_supported():
    '''Checks whether the Linux futex FUTEX_WAIT_MULTIPLE operation is
    supported on this kernel.

    Returns:
        Whether this kernel supports the FUTEX_WAIT_MULTIPLE operation.
    '''
    try:
        futex_syscall = _get_futex_syscall()
        futex_wait_multiple_op = _get_futex_wait_multiple_op(futex_syscall)
    except (AttributeError, RuntimeError):
        return False
    if futex_wait_multiple_op is None:
        return False

    return futex_syscall(
        None,
        futex_wait_multiple_op,
        0,
        None,
        None,
        0
    )[1] != errno.ENOSYS


@functools.lru_cache(None)
def is_futex2_supported():
    '''Checks whether the Linux futex2 syscall is supported on this
    kernel.

    Returns:
        Whether this kernel supports the futex2 syscall.
    '''
    try:
        for filename in ('wait', 'waitv', 'wake'):
            with open('/sys/kernel/futex2/' + filename, 'rb') as file:
                if not file.readline().strip().isdigit():
                    return False
    except OSError:
        return False
    return True


@functools.lru_cache(None)
def is_fsync_supported():
    return is_futex_wait_multiple_supported() or is_futex2_supported()
