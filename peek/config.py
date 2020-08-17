import logging
import os
import platform
from os.path import expanduser, dirname
from typing import Iterable

from configobj import ConfigObj

_logger = logging.getLogger(__name__)


def config_location():
    from peek import __package__ as package_name
    if 'XDG_CONFIG_HOME' in os.environ:
        return f'%s/{package_name}/' % expanduser(os.environ['XDG_CONFIG_HOME'])
    elif platform.system() == 'Windows':
        return os.getenv('USERPROFILE') + f'\\AppData\\Local\\{package_name}\\'
    else:
        return expanduser(f'~/.config/{package_name}/')


def ensure_dir_exists(path):
    parent_dir = expanduser(dirname(path))
    os.makedirs(parent_dir, exist_ok=True)


def load_config(package_config_file: str,
                config_file: str = None, extra_config_options: Iterable[str] = None):
    config = ConfigObj(package_config_file)
    if config_file is not None:
        config.merge(ConfigObj(config_file))

    if extra_config_options:
        extra_config = {}
        for config_option in extra_config_options:
            parent = extra_config
            key, value = config_option.split('=', 1)
            key_components = key.split('.')
            for key_component in key_components[:-1]:
                child = parent.get(key_component)
                if child is None:
                    parent[key_component] = {}
                elif not isinstance(child, dict):
                    _logger.warning(f'Config key [{key}] conflicts. '
                                    f'Value of [{key_component}] is not a [dict], '
                                    f'but [{type(child)}]')
                    parent = None
                    break
                parent = parent[key_component]

            if isinstance(parent, dict):
                parent[key_components[-1]] = value

        config.merge(ConfigObj(extra_config))

    return config


def get_config(config_file: str = None, extra_config_options: Iterable[str] = None):
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    package_config_file = os.path.join(package_root, 'peekrc')
    default_config_file = expanduser(config_location() + 'peekrc')
    ensure_dir_exists(default_config_file)
    config_file = config_file or default_config_file
    return load_config(package_config_file, config_file, extra_config_options)
