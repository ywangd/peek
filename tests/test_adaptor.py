import os

import pytest

from peek import __file__ as package_root
from peek.spec_adaptor.adaptor import SpecExtractor, SpecBuilder

package_root = os.path.dirname(package_root)
kibana_dir = os.path.join(package_root, 'specs', 'kibana-7.8.1')


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_extract_spec():
    spec_extractor = SpecExtractor(kibana_dir)

    assert spec_extractor.extract('query').endswith('\n};')
    assert spec_extractor.extract('spanWithinTemplate').endswith('\n};')


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_eval_simple_spec():
    spec_extractor = SpecExtractor(kibana_dir)
    spec_builder = SpecBuilder()
    spec_builder.build(spec_extractor.extract('spanWithinTemplate'))


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_extract_all_specs():
    spec_extractor = SpecExtractor(kibana_dir)
    specs = spec_extractor.extract_all()
    print(specs)


@pytest.mark.skipif(not os.path.exists(kibana_dir), reason='Kibana directory not available')
def test_extract_all_specs():
    spec_extractor = SpecExtractor(kibana_dir)
    specs = spec_extractor.extract_all()
    with open('tmp-specs.es', 'w') as outs:
        outs.write(specs)

    print(spec_extractor.parse_all())
