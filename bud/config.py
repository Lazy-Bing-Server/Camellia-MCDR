import os

from pydantic import BaseModel, validator, ValidationError
from pydantic.fields import ModelField
from enum import EnumMeta
from typing import Union, List, Any
from ruamel import yaml

from bud.utils import gl_server, logger, tr


CONFIG_PATH = os.path.join(gl_server.get_data_folder(), 'config.yml')


class LeaveABlank(object):
    pass


class EmptyConfigFile(Exception):
    pass


_BLANK = LeaveABlank()


def allow_blanks(*types: type):
    ret = LeaveABlank
    for item in types:
        ret = Union[ret, item]
    return ret


class BlossomConfigModel(BaseModel):
    # It's impossible to make both pycharm & pydantic happy
    # Due to pydantic force the first parameter name to "cls"
    class Config:
        arbitrary_types_allowed = True

    @validator('*', pre=True, allow_reuse=True)
    def ensure_enum(cls, v, *, field: ModelField = None):
        try:
            if isinstance(field.type_, EnumMeta):
                return field.type_[v]
            return v
        except KeyError:
            raise TypeError(f'"{v}" is not a valid enum name')

    def dict(self, *args, with_blank: bool = False, **kwargs):
        return_dict = {}
        for key, value in super().dict(*args, **kwargs).items():
            if isinstance(value.__class__, EnumMeta):
                value = value.name
            if not isinstance(value, LeaveABlank) or with_blank:
                return_dict[key] = value
        return return_dict


class SingleErrorMessage(BlossomConfigModel):
    loc: List[str] = []
    msg: str = ''
    type: str = ''

    @property
    def location(self):
        return self.loc.copy()


class PermissionRequirements(BlossomConfigModel):
    reload: int = 3


class Configuration(BlossomConfigModel):
    command_prefix: Union[str, List[str]] = '!!template'
    permission_requirements: PermissionRequirements = PermissionRequirements()
    verbosity: allow_blanks(bool) = _BLANK
    debug_commands: allow_blanks(bool) = _BLANK

    @property
    def is_verbose(self):
        return self.dict().get('verbosity', False)

    @property
    def is_debug(self):
        return self.dict().get('debug_commands', False)

    @property
    def prefix(self) -> List[str]:
        return list(set(self.command_prefix)) if isinstance(self.command_prefix, list) else [self.command_prefix]

    @property
    def primary_prefix(self) -> str:
        return self.prefix[0]

    def get_perm(self, cmd: str) -> int:
        return self.permission_requirements.dict().get(cmd, 1)

    @classmethod
    def load(cls, echo_in_console: bool = True) -> 'Configuration':
        def log(tr_key: str, *args, **kwargs):
            if gl_server is not None and echo_in_console:
                return logger.info(tr(tr_key, *args, **kwargs))

        # file existence check
        if not os.path.isfile(CONFIG_PATH):
            default = cls()
            default.save()
            log('server_interface.load_config_simple.failed', 'File is not found', with_prefix=False)
            return default

        # load
        needs_save, needs_log_fix = False, True
        try:
            with open(CONFIG_PATH, 'r', encoding='UTF-8') as f:
                raw_ret = yaml.round_trip_load(f)
            if raw_ret is None:
                raise EmptyConfigFile
        except (yaml.YAMLError, EmptyConfigFile):
            default = cls()
            default.save()
            log('server_interface.load_config_simple.failed', 'Invalid config file', with_prefix=False)
            return default
        key_list = list(raw_ret.keys())
        try:
            ret = cls(**raw_ret)
        except ValidationError as exc:
            needs_save, default = True, cls().dict(with_blank=True)
            for item in exc.errors():
                loc = SingleErrorMessage(**dict(item)).location
                loc_to_pop = loc.copy()
                data = raw_ret
                while len(loc_to_pop) > 1:
                    data = data[loc_to_pop.pop(0)]
                data[loc_to_pop[0]] = get_multi_layer_key(default, loc)
            ret = cls(**raw_ret)
            log('load_config.validation_error_handle', exc)
        except Exception as exc:
            needs_save, ret, needs_log_fix = True, cls(), False
            log('server_interface.load_config_simple.failed', exc, with_prefix=False)
            logger.exception('Load config failed, using default')

        if needs_log_fix:
            new_keys = list(filter(lambda key: key not in key_list, list(ret.dict().keys())))
            if len(new_keys) != 0:
                log('load_config.missing_keys_handle', keys=", ".join(new_keys))

        logger.set_verbose(ret.is_verbose)

        # save file
        if needs_save:
            ret.save()
        log('server_interface.load_config_simple.succeed', with_prefix=False)
        return ret

    def save(self, keep_fmt=True):
        to_save = self.dict()
        if os.path.isfile(CONFIG_PATH) and keep_fmt:
            with open(CONFIG_PATH, 'r', encoding='UTF-8') as f:
                fmt = yaml.round_trip_load(f)
                try:
                    self.validate(fmt)
                except:
                    pass
                else:
                    fmt.update(to_save)
                    to_save = fmt
        with open(CONFIG_PATH, 'w', encoding='UTF-8') as f:
            logger.debug(to_save)
            yaml.round_trip_dump(to_save, f, allow_unicode=True)


def get_multi_layer_key(data: Any, keys: list):
    if len(keys) == 0:
        return data
    if not isinstance(data, dict):
        return None
    keys = keys.copy()
    next_layer = data[keys.pop(0)]
    if len(keys) == 0:
        return next_layer
    return get_multi_layer_key(next_layer, keys)


config: Configuration = Configuration.load()
