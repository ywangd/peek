import os

import pytest

from peek import __file__ as package_root
from peek.js_spec.spec_builder import JsSpecParser, JsSpecEvaluator

package_root = os.path.dirname(package_root)
kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_extract_all_specs():
    spec_parser = JsSpecParser()
    spec_parser.parse(kibana_dir)
    # spec_parser.save('tmp-specs.es')


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_eval_specs():
    spec_parser = JsSpecParser()
    nodes = spec_parser.parse(kibana_dir)
    spec_evaluator = JsSpecEvaluator()
    specs = spec_evaluator.visit(nodes)
    print(specs)
    # import json
    # with open('tmp-specs.json', 'w') as outs:
    #     json.dump(specs, outs, indent=2)
