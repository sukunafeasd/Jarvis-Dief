"""Processos de preparacao encerram seus descendentes ao cancelar."""
import ctypes
import os
import signal
import subprocess


def environment():
    env=dict(os.environ)
    for key in list(env):
        if key.startswith('_PYI') or key in {'PYTHONHOME','PYTHONPATH','TCL_LIBRARY','TK_LIBRARY'}:env.pop(key,None)
    return env


def spawn(command,**kwargs):
    kwargs.setdefault('env',environment())
    if os.name!='nt':return subprocess.Popen(command,start_new_session=True,**kwargs)
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):
        _fields_=[('user',ctypes.c_int64),('kernel',ctypes.c_int64),('flags',w.DWORD),
            ('minimum',ctypes.c_size_t),('maximum',ctypes.c_size_t),('active',w.DWORD),
            ('affinity',ctypes.c_size_t),('priority',w.DWORD),('schedule',w.DWORD)]
    class IO(ctypes.Structure):
        _fields_=[(name,ctypes.c_uint64) for name in ('read','write','other','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
            ('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
    class ThreadEntry(ctypes.Structure):
        _fields_=[('size',w.DWORD),('usage',w.DWORD),('thread',w.DWORD),('owner',w.DWORD),
            ('priority',w.LONG),('delta',w.LONG),('flags',w.DWORD)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
    kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];kernel.CreateToolhelp32Snapshot.restype=w.HANDLE
    kernel.Thread32First.argtypes=[w.HANDLE,ctypes.POINTER(ThreadEntry)]
    kernel.Thread32Next.argtypes=[w.HANDLE,ctypes.POINTER(ThreadEntry)]
    kernel.OpenThread.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenThread.restype=w.HANDLE
    kernel.ResumeThread.argtypes=[w.HANDLE];kernel.ResumeThread.restype=w.DWORD
    job=kernel.CreateJobObjectW(None,None)
    if not job:raise ctypes.WinError(ctypes.get_last_error())
    limits=Extended();limits.basic.flags=0x2000
    if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
        kernel.CloseHandle(job);raise ctypes.WinError(ctypes.get_last_error())
    process=None
    try:
        # Associate a suspended process before it can create any helpers.
        kwargs['creationflags']=kwargs.get('creationflags',0)|subprocess.CREATE_NO_WINDOW|0x4
        process=subprocess.Popen(command,**kwargs)
        if not kernel.AssignProcessToJobObject(job,w.HANDLE(int(process._handle))):raise ctypes.WinError(ctypes.get_last_error())
        snapshot=kernel.CreateToolhelp32Snapshot(4,0)
        if snapshot==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        resumed=False
        try:
            entry=ThreadEntry();entry.size=ctypes.sizeof(entry)
            found=kernel.Thread32First(snapshot,ctypes.byref(entry))
            while found:
                if entry.owner==process.pid:
                    thread=kernel.OpenThread(2,False,entry.thread)
                    if not thread:raise ctypes.WinError(ctypes.get_last_error())
                    try:resumed=kernel.ResumeThread(thread)!=0xFFFFFFFF
                    finally:kernel.CloseHandle(thread)
                    break
                found=kernel.Thread32Next(snapshot,ctypes.byref(entry))
        finally:kernel.CloseHandle(snapshot)
        if not resumed:raise RuntimeError('Nao foi possivel iniciar o preparador isolado.')
        process._jarvis_job=(kernel,job,Extended)
        return process
    except Exception:
        kernel.CloseHandle(job)
        if process and process.poll() is None:process.terminate();process.wait(timeout=10)
        raise


def close_tree(process):
    job=getattr(process,'_jarvis_job',None)
    if job:
        process._jarvis_job=None;job[0].CloseHandle(job[1])
    elif os.name!='nt':
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    elif process.poll() is None:process.terminate()
    if process.poll() is None:process.wait(timeout=10)


def detach_tree(process):
    job=getattr(process,'_jarvis_job',None)
    if not job:return
    # Once startup succeeds, applications deliberately opened by the user
    # must not be terminated when the assistant closes normally.
    limits=job[2]()
    if not job[0].SetInformationJobObject(job[1],9,ctypes.byref(limits),ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())
    job[0].CloseHandle(job[1]);process._jarvis_job=None
