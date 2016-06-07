from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()

version = '1.0'

requires = [
    'chaussette',
    'gevent',
    'pyelliptic',
    'pyramid',
    'pyramid_exclog',
    'pytz',
    'rfc6266',
    'setuptools',
]
test_requires = requires + [
    'webtest',
    'python-coveralls',
]
docs_requires = requires + [
    'sphinxcontrib-httpdomain',
]
entry_points = {
    'paste.app_factory': [
        'main = openprocurement.documentservice:main'
    ],
    'openprocurement.documentservice.plugins': [
        'memory = openprocurement.documentservice.storage:includeme'
    ]
}

setup(name='openprocurement.documentservice',
      version=version,
      description="Document service for OpenProcurement",
      long_description=README,
      classifiers=[
          "Framework :: Pylons",
          "License :: OSI Approved :: Apache Software License",
          "Programming Language :: Python",
          "Topic :: Internet :: WWW/HTTP",
          "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"
      ],
      keywords='web services',
      author='Quintagroup, Ltd.',
      author_email='info@quintagroup.com',
      url='https://github.com/openprocurement/openprocurement.documentservice',
      license='Apache License 2.0',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['openprocurement'],
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=test_requires,
      extras_require={'test': test_requires, 'docs': docs_requires},
      test_suite="openprocurement.documentservice.tests.main.suite",
      entry_points=entry_points)
