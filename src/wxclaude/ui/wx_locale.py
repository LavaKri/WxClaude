"""Language of wxWidgets' own texts (stock buttons such as Cancel, standard dialogs)."""

import wx

_WX_LANGUAGES = {"fr": wx.LANGUAGE_FRENCH, "en": wx.LANGUAGE_ENGLISH}


def init_wx_locale(language: str) -> wx.Locale:
    """Make wx use ``language`` for its own texts. Keep the result alive as long as the app runs.

    The application texts are translated by ``wxclaude.i18n``; this covers what wx itself
    shows, for example the buttons of its standard dialogs.
    """
    return wx.Locale(_WX_LANGUAGES.get(language, wx.LANGUAGE_DEFAULT))
