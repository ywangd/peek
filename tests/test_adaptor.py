import os

import pytest

from peek import __file__ as package_root
from peek.spec_adaptor.adaptor import SpecBuilder
from peek.spec_adaptor.evaluator import SpecEvaluator

package_root = os.path.dirname(package_root)
kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_extract_all_specs():
    spec_builder = SpecBuilder(kibana_dir)
    spec_builder.build()
    with open('tmp-raw.es', 'w') as outs:
        outs.write(spec_builder.source)
    spec_builder.save('tmp-specs.es')


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_eval_specs():
    spec_builder = SpecBuilder(kibana_dir)
    nodes = spec_builder.build()
    spec_evaluator = SpecEvaluator()
    print(spec_evaluator.visit(nodes))

