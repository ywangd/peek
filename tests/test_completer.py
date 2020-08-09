import os

from peek.completer import load_specs


def test_load_specs():
    from peek import __file__ as package_root
    package_root = os.path.dirname(package_root)
    kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')
    specs = load_specs(kibana_dir)
    # Skip the test if no specs are found
    if specs:
        # Make sure loading and merging work
        print(specs['indices.create']['data_autocomplete_rules'])
        print(specs['security.put_user']['data_autocomplete_rules'])
