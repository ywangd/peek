#!/usr/bin/env python

"""The setup script."""
import os
import re

from setuptools import find_packages, setup


def get_version():
    with open(os.path.join(os.path.dirname(__file__), 'peek', '__init__.py')) as ins:
        return re.search("__version__ = ['\"]([^'\"]+)['\"]", ins.read()).group(1)


with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

with open('requirements.txt') as requirements_file:
    requirements = [line.strip() for line in requirements_file.read().splitlines() if line.strip()]

setup_requirements = [
    'pytest-runner',
]

test_requirements = [
    'pytest>=3',
]

setup(
    author="Yang Wang",
    author_email='ywangd@gmail.com',
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    description="Peek into elasticsearch clusters",
    entry_points={
        'console_scripts': [
            'peek=peek.cli:main',
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='peek,elasticsearch,cli',
    name='es-peek',
    packages=find_packages(include=['peek', 'peek.*']),
    setup_requires=setup_requirements,
    extras_require={'full': ['kerberos~=1.3.1', 'pyperclip~=1.8.2']},
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/ywangd/peek',
    version=get_version(),
    zip_safe=False,
)
