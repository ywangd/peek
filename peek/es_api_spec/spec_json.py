import json
import logging
import os

_logger = logging.getLogger(__name__)


def load_json_specs(kibana_dir):
    oss_path = os.path.join(
        kibana_dir, 'src', 'plugins', 'console', 'server', 'lib', 'spec_definitions')
    xpack_path = os.path.join(
        kibana_dir, 'x-pack', 'plugins', 'console_extensions', 'server', 'lib', 'spec_definitions')
    specs = _do_load_json_specs(os.path.join(oss_path, 'json'))
    specs.update(_do_load_json_specs(os.path.join(xpack_path, 'json')))
    return specs


def _do_load_json_specs(base_dir):
    _logger.debug(f'Loading json specs from: {base_dir!r}')
    specs = {}
    for sub_dir in ('generated', 'overrides'):
        d = os.path.join(base_dir, sub_dir)
        if not os.path.exists(d):
            _logger.warning(f'JSON specs directory does not exist: {d}')
            continue
        for f in os.listdir(d):
            if f == '_common.json':
                continue
            with open(os.path.join(d, f)) as ins:
                spec = json.load(ins)
            if sub_dir == 'generated':
                specs.update(spec)
            else:
                for k, v in spec.items():
                    if k in specs:
                        specs[k].update(v)
                    else:
                        if k.startswith('xpack.'):
                            specs[k[6:]].update(v)
                        else:
                            specs['xpack.' + k].update(v)
    return specs
