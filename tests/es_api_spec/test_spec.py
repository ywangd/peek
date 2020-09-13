import os

from peek.es_api_spec.spec import matchable_specs
from peek.es_api_spec.spec_json import load_json_specs


def test_load_specs():
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')
    specs = load_json_specs(kibana_dir)
    # Skip the test if no specs are found
    if not specs:
        return

    # Make sure loading and merging work
    print(specs['indices.create']['data_autocomplete_rules'])
    print(specs['security.put_user']['data_autocomplete_rules'])

    next(matchable_specs('POST', ['_security', 'api_key'], specs))

    next(matchable_specs('POST', ['_security', 'oauth2', 'token'], specs,
                         required_field='data_autocomplete_rules'))
