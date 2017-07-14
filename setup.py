import os
import re
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
versionfile = open(os.path.join(here, "nodular", "_version.py")).read()

mo = re.search(r"^__version__\s*=\s*['\"]([^'\"]*)['\"]", versionfile, re.M)
if mo:
    version = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in nodular/_version.py.")

requires = [
    'six',
    'simplejson',
    'Flask-SQLAlchemy',
    'SQLAlchemy>=1.0',
    'Flask',
    'coaster>=0.6.dev0',
    ]

dependency_links = [
    'https://github.com/hasgeek/coaster/archive/master.zip#egg=coaster-0.6.dev0'
    ]


setup(
    name='nodular',
    version=version,
    description='Revisioned content objects',
    long_description=README + '\n\n' + CHANGES,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Development Status :: 3 - Alpha',
        'Topic :: Software Development :: Libraries',
        ],
    author='Kiran Jonnalagadda',
    author_email='kiran@hasgeek.com',
    url='https://github.com/hasgeek/nodular',
    keywords='nodular',
    packages=['nodular'],
    include_package_data=True,
    zip_safe=True,
    test_suite='tests',
    install_requires=requires,
    dependency_links=dependency_links,
    )
