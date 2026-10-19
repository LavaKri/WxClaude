"""A minimal UI Automation provider for one window, written with ctypes (Windows only).

Windows documents the procedure for a custom control hosted in a window: the window answers
``WM_GETOBJECT`` with its provider (``UiaReturnRawElementProvider``) and the provider implements
``IRawElementProviderSimple``, hosted in that same window. Events are then raised through it.
Navigation, identity and bounds come from the host window, so no fragment interface is needed.
"""

import ctypes
import os
import sys
import uuid
from collections.abc import Callable

import wx

from wxclaude.core.errors import ScreenReaderOutputError

# ProviderOptions_ServerSideProvider | ProviderOptions_UseComThreading (calls come on our thread)
_PROVIDER_OPTIONS = 0x2 | 0x20
_WM_GETOBJECT = 0x003D
_UIA_ROOT_OBJECT_ID = -25
_S_OK = 0
_E_NOINTERFACE = ctypes.c_long(0x80004002).value

_IID_UNKNOWN = uuid.UUID("00000000-0000-0000-C000-000000000046").bytes_le
_IID_SIMPLE = uuid.UUID("D6DD68D1-86FD-4332-8666-9ABEDEA2D24C").bytes_le

_VT_I4 = 3
_VT_BSTR = 8
_VT_BOOL = 11
_PROPERTY_PROCESS_ID = 30002
_PROPERTY_CONTROL_TYPE = 30003
_PROPERTY_NAME = 30005
_PROPERTY_IS_ENABLED = 30010
_PROPERTY_IS_CONTROL_ELEMENT = 30016
_PROPERTY_IS_CONTENT_ELEMENT = 30017
_PROPERTY_NATIVE_WINDOW_HANDLE = 30020
_CONTROL_TYPE_TEXT = 50020
_TRUE_PROPERTIES = (
    _PROPERTY_IS_ENABLED,
    _PROPERTY_IS_CONTROL_ELEMENT,
    _PROPERTY_IS_CONTENT_ELEMENT,
)

# UiaRaiseNotificationEvent: notification kind "other", processing "important, most recent only".
NOTIFICATION_KIND_OTHER = 4
PROCESSING_IMPORTANT_MOST_RECENT = 1

_HRESULT = ctypes.c_long
_VOID_P = ctypes.c_void_p  # a pointer, or the address of an output parameter (None when NULL)


def _store(address: int | None, value: int) -> None:
    """Write the pointer-sized ``value`` at ``address`` (an output parameter), if there is one."""
    if address:
        ctypes.c_void_p.from_address(address).value = value


#: Every provider created, kept alive for the whole run (see ``UiaProvider.__init__``).
_PROVIDERS: list[UiaProvider] = []


class UiaProvider:
    """The provider of the window ``hwnd``: a text element whose name is ``name``.

    It hooks the window procedure to give itself to UI Automation; ``disconnect`` undoes that when
    the window is destroyed. ``raise_notification`` says a text through it.
    """

    def __init__(self, hwnd: int) -> None:
        if sys.platform != "win32":
            raise ScreenReaderOutputError("UI Automation exists only on Windows.")
        self.hwnd = hwnd
        self.name = ""
        try:
            self._uia = ctypes.WinDLL("UIAutomationCore.dll")
            self._ole = ctypes.WinDLL("oleaut32.dll")
            self._comctl = ctypes.WinDLL("comctl32.dll")
        except OSError as error:
            raise ScreenReaderOutputError(str(error)) from error
        self._declare_functions()
        function = ctypes.WINFUNCTYPE
        methods: tuple[tuple[type, Callable[..., int]], ...] = (
            (function(_HRESULT, _VOID_P, _VOID_P, _VOID_P), self._query_interface),
            (function(ctypes.c_ulong, _VOID_P), self._add_ref),
            (function(ctypes.c_ulong, _VOID_P), self._release),
            (function(_HRESULT, _VOID_P, _VOID_P), self._provider_options),
            (function(_HRESULT, _VOID_P, ctypes.c_int, _VOID_P), self._pattern_provider),
            (function(_HRESULT, _VOID_P, ctypes.c_int, _VOID_P), self._property_value),
            (function(_HRESULT, _VOID_P, _VOID_P), self._host_provider),
        )
        self._callbacks = tuple(prototype(method) for prototype, method in methods)
        self._table = (ctypes.c_void_p * len(methods))(
            *(ctypes.cast(callback, ctypes.c_void_p) for callback in self._callbacks)
        )
        self._object = ctypes.c_void_p(ctypes.addressof(self._table))
        #: The ``IRawElementProviderSimple`` pointer: the address of an object that starts with
        #: the address of its table of methods.
        self.address = ctypes.addressof(self._object)
        self._subclass = function(
            ctypes.c_ssize_t,
            _VOID_P,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
            ctypes.c_size_t,
            ctypes.c_size_t,
        )(self._window_proc)
        if not self._comctl.SetWindowSubclass(hwnd, self._subclass, 1, 0):
            raise ScreenReaderOutputError("The window could not be hooked for UI Automation.")
        self._connected = True
        # UI Automation may still call a provider after its window is gone (it releases its
        # references later), so the object and its callbacks are never freed.
        _PROVIDERS.append(self)

    def disconnect(self) -> None:
        """Unhook the window and tell UI Automation to let go of this provider (idempotent).

        To be called when the window is destroyed, as Microsoft documents for providers.
        """
        if not self._connected:
            return
        self._connected = False
        self._comctl.RemoveWindowSubclass(self.hwnd, self._subclass, 1)
        # Not now: this runs while the window is being destroyed, and a COM call made from
        # inside a window message is refused. Once the message is over it goes through.
        wx.CallAfter(self._uia.UiaDisconnectProvider, self.address)

    def _declare_functions(self) -> None:
        self._ole.SysAllocString.restype = ctypes.c_void_p
        self._ole.SysAllocString.argtypes = [ctypes.c_wchar_p]
        self._ole.SysFreeString.restype = None
        self._ole.SysFreeString.argtypes = [ctypes.c_void_p]
        self._comctl.DefSubclassProc.restype = ctypes.c_ssize_t
        self._comctl.DefSubclassProc.argtypes = [
            _VOID_P,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        ]
        self._uia.UiaReturnRawElementProvider.restype = ctypes.c_ssize_t
        self._uia.UiaReturnRawElementProvider.argtypes = [
            _VOID_P,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
            _VOID_P,
        ]
        self._comctl.RemoveWindowSubclass.restype = ctypes.c_int
        self._comctl.RemoveWindowSubclass.argtypes = [_VOID_P, _VOID_P, ctypes.c_size_t]
        self._uia.UiaDisconnectProvider.restype = _HRESULT
        self._uia.UiaDisconnectProvider.argtypes = [_VOID_P]
        self._uia.UiaHostProviderFromHwnd.restype = _HRESULT
        self._uia.UiaHostProviderFromHwnd.argtypes = [_VOID_P, ctypes.POINTER(ctypes.c_void_p)]
        self._uia.UiaRaiseNotificationEvent.restype = _HRESULT
        self._uia.UiaRaiseNotificationEvent.argtypes = [
            _VOID_P,
            ctypes.c_int,
            ctypes.c_int,
            _VOID_P,
            _VOID_P,
        ]

    def raise_notification(self, text: str, activity: str) -> None:
        """Make the screen reader say ``text``, which also becomes the name of the element."""
        self.name = text
        text_bstr = self._ole.SysAllocString(text)
        activity_bstr = self._ole.SysAllocString(activity)
        try:
            result = self._uia.UiaRaiseNotificationEvent(
                self.address,
                NOTIFICATION_KIND_OTHER,
                PROCESSING_IMPORTANT_MOST_RECENT,
                text_bstr,
                activity_bstr,
            )
        finally:
            for bstr in (text_bstr, activity_bstr):
                if bstr:
                    self._ole.SysFreeString(bstr)
        if result < 0:
            code = result & 0xFFFFFFFF
            raise ScreenReaderOutputError(f"UiaRaiseNotificationEvent failed (0x{code:08X}).")

    def _window_proc(
        self, hwnd: int, message: int, wparam: int, lparam: int, subclass_id: int, data: int
    ) -> int:
        if message == _WM_GETOBJECT and lparam == _UIA_ROOT_OBJECT_ID:
            return int(self._uia.UiaReturnRawElementProvider(hwnd, wparam, lparam, self.address))
        return int(self._comctl.DefSubclassProc(hwnd, message, wparam, lparam))

    # IUnknown (the object lives as long as the window, so references are not counted)

    def _query_interface(self, this: int, riid: int, out: int | None) -> int:
        found = ctypes.string_at(riid, 16) in (_IID_UNKNOWN, _IID_SIMPLE)
        _store(out, self.address if found else 0)
        return _S_OK if found else _E_NOINTERFACE

    def _add_ref(self, this: int) -> int:
        return 2

    def _release(self, this: int) -> int:
        return 1

    # IRawElementProviderSimple

    def _provider_options(self, this: int, out: int | None) -> int:
        if out:
            ctypes.c_int.from_address(out).value = _PROVIDER_OPTIONS
        return _S_OK

    def _pattern_provider(self, this: int, pattern_id: int, out: int | None) -> int:
        _store(out, 0)
        return _S_OK

    def _property_value(self, this: int, property_id: int, out: int | None) -> int:
        if not out:
            return _S_OK
        ctypes.memset(out, 0, 24)  # a VARIANT of type VT_EMPTY: "the host window gives it"
        if property_id == _PROPERTY_NATIVE_WINDOW_HANDLE:
            self._set_variant(out, _VT_I4, ctypes.c_long, self.hwnd)
        elif property_id == _PROPERTY_PROCESS_ID:
            self._set_variant(out, _VT_I4, ctypes.c_long, os.getpid())
        elif property_id == _PROPERTY_CONTROL_TYPE:
            self._set_variant(out, _VT_I4, ctypes.c_long, _CONTROL_TYPE_TEXT)
        elif property_id in _TRUE_PROPERTIES:
            self._set_variant(out, _VT_BOOL, ctypes.c_short, -1)
        elif property_id == _PROPERTY_NAME:
            self._set_variant(out, _VT_BSTR, ctypes.c_void_p, self._ole.SysAllocString(self.name))
        return _S_OK

    @staticmethod
    def _set_variant(
        address: int,
        vt: int,
        value_type: type[ctypes.c_long] | type[ctypes.c_short] | type[ctypes.c_void_p],
        value: int,
    ) -> None:
        ctypes.c_ushort.from_address(address).value = vt
        value_type.from_address(address + 8).value = value

    def _host_provider(self, this: int, out: int | None) -> int:
        provider = ctypes.c_void_p()
        result = int(self._uia.UiaHostProviderFromHwnd(self.hwnd, ctypes.byref(provider)))
        _store(out, provider.value or 0)
        return result
