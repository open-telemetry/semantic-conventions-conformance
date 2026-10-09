# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Windows process-tree cleanup and positional capture reads."""

from __future__ import annotations

import ctypes
import msvcrt
import subprocess
from ctypes import wintypes
from typing import Protocol


class _Capture(Protocol):
    def fileno(self) -> int: ...


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("per_process_time", ctypes.c_int64),
        ("per_job_time", ctypes.c_int64),
        ("flags", wintypes.DWORD),
        ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t),
        ("active_processes", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "read_operations",
            "write_operations",
            "other_operations",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicLimit),
        ("io", _IoCounters),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


class _ThreadEntry(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
        ("thread_id", wintypes.DWORD),
        ("owner_pid", wintypes.DWORD),
        ("base_priority", wintypes.LONG),
        ("delta_priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
    ]


_kernel = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
_kernel.CreateJobObjectW.restype = wintypes.HANDLE
_kernel.SetInformationJobObject.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    wintypes.DWORD,
]
_kernel.SetInformationJobObject.restype = wintypes.BOOL
_kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
_kernel.AssignProcessToJobObject.restype = wintypes.BOOL
_kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
_kernel.TerminateJobObject.restype = wintypes.BOOL
_kernel.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel.CloseHandle.restype = wintypes.BOOL
_kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_kernel.Thread32First.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(_ThreadEntry),
]
_kernel.Thread32First.restype = wintypes.BOOL
_kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)]
_kernel.Thread32Next.restype = wintypes.BOOL
_kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel.OpenThread.restype = wintypes.HANDLE
_kernel.ResumeThread.argtypes = [wintypes.HANDLE]
_kernel.ResumeThread.restype = wintypes.DWORD
_kernel.CreateFileMappingW.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPCWSTR,
]
_kernel.CreateFileMappingW.restype = wintypes.HANDLE
_kernel.MapViewOfFile.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_size_t,
]
_kernel.MapViewOfFile.restype = ctypes.c_void_p
_kernel.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
_kernel.UnmapViewOfFile.restype = wintypes.BOOL


class WindowsJob:
    """Own a scenario's descendants even when its launcher has exited."""

    def __init__(self) -> None:
        self.handle = _kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimit()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def __enter__(self) -> WindowsJob:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def assign(self, process: subprocess.Popen[str]) -> None:
        if not _kernel.AssignProcessToJobObject(
            self.handle, int(getattr(process, "_handle"))
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def resume(self, process: subprocess.Popen[str]) -> None:
        """Start the suspended primary thread only after job assignment."""
        snapshot = _kernel.CreateToolhelp32Snapshot(
            0x00000004, 0
        )  # SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = _ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            found = _kernel.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.owner_pid == process.pid:
                    thread = _kernel.OpenThread(0x0002, False, entry.thread_id)
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if _kernel.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                    finally:
                        _kernel.CloseHandle(thread)
                    return
                found = _kernel.Thread32Next(snapshot, ctypes.byref(entry))
            raise OSError(f"No primary thread found for process {process.pid}")
        finally:
            _kernel.CloseHandle(snapshot)

    def terminate(self) -> None:
        if not _kernel.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            _kernel.CloseHandle(self.handle)
            self.handle = None


def read_snapshot(capture: _Capture, size: int) -> bytes:
    """Map the fixed file length without seeking the inherited writer handle."""
    original = msvcrt.get_osfhandle(capture.fileno())
    mapping = _kernel.CreateFileMappingW(original, None, 0x02, 0, 0, None)
    if not mapping:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        view = _kernel.MapViewOfFile(mapping, 0x04, 0, 0, size)
        if not view:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(view, size)
        finally:
            _kernel.UnmapViewOfFile(view)
    finally:
        _kernel.CloseHandle(mapping)
