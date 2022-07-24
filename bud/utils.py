import logging
import os.path

from mcdreforged.api.types import ServerInterface, PluginServerInterface, MCDReforgedLogger
from mcdreforged.api.rtext import *
from typing import Optional


DEBUG = True
gl_server: PluginServerInterface = ServerInterface.get_instance().as_plugin_server_interface()
TRANSLATION_KEY_PREFIX = gl_server.get_self_metadata().id
LOG_FILE = os.path.join(gl_server.get_data_folder(), 'logs', '{id}.log'.format(id=gl_server.get_self_metadata().id))


class BloomingBlossomLogger(MCDReforgedLogger):
    __verbosity = False

    def debug(self, *args, option=None, no_check: bool = False):
        if self.__verbosity:
            super(BloomingBlossomLogger, self).debug(*args, option, no_check=True)
        elif option is not None:
            super(BloomingBlossomLogger, self).debug(*args, option)

    @classmethod
    def should_log_debug(cls, option=None):
        if cls.__verbosity:
            return True
        return super().should_log_debug(option=option)

    def set_verbose(self, verbosity: bool):
        self.__verbosity = verbosity


logger = BloomingBlossomLogger(plugin_id=gl_server.get_self_metadata().id)
logger.set_file(LOG_FILE)


def tr(translation_key: str, *args, with_prefix=True, **kwargs) -> RTextMCDRTranslation:
    if with_prefix and not translation_key.startswith(TRANSLATION_KEY_PREFIX):
        translation_key = f"{TRANSLATION_KEY_PREFIX}.{translation_key}"
    return gl_server.rtr(translation_key, *args, **kwargs).set_translator(ntr)


def ntr(translation_key: str, *args, with_prefix: bool = True, language: Optional[str] = None,
        allow_failure: bool = True, fallback_language: bool = None, **kwargs) -> str:
    try:
        return gl_server.tr(
            translation_key, *args, language=language, fallback_language=None, allow_failure=False, **kwargs
        )
    except (KeyError, ValueError):
        return gl_server.tr(
            translation_key, *args, language='en_us', allow_failure=allow_failure, **kwargs
        )
