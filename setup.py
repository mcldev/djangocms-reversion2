
from setuptools import find_packages, setup

from djangocms_reversion2 import __version__

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Framework :: Django',
    'Framework :: Django :: 4.2',
    'Framework :: Django CMS :: 3.11',
    'Environment :: Web Environment',
    'Intended Audience :: Developers',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Topic :: Internet :: WWW/HTTP',
    'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Software Development :: Libraries :: Application Frameworks',
]

REQUIREMENTS = [
    'django>=4.2,<5.0',
    'django-cms>=3.11,<3.12',
    'django-sekizai>=4.0.0',
    'lxml',
    'lxml-html-clean',
]

setup(
    name='djangocms-reversion2',
    packages=find_packages(exclude=('test_app', 'docs')),
    include_package_data=True,
    version=__version__,
    description='page versioning for django-cms',
    author='Daniel Pollithy, Michael Carder',
    url='https://github.com/mcldev/djangocms-reversion2',
    download_url='https://github.com/mcldev/djangocms-reversion2/archive/{}.zip'.format(__version__),
    install_requires=REQUIREMENTS,
    python_requires='>=3.9',
    keywords=['django', 'Django CMS', 'version history', 'versioning',
              'reversion', 'revision', 'CMS', 'Blueshoe', 'basket', 'bin', 'revert'],
    classifiers=CLASSIFIERS,
    test_suite='tests.settings.run',
)
