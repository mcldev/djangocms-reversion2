
from setuptools import find_packages, setup

from djangocms_reversion2 import __version__

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Framework :: Django',
    'Environment :: Web Environment',
    'Intended Audience :: Developers',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Framework :: Django',
    'Framework :: Django :: 1.11',
    'Framework :: Django :: 2.2',
    'Topic :: Internet :: WWW/HTTP',
    'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Software Development :: Libraries :: Application Frameworks',
]

REQUIREMENTS = [
    'django>=1.11',
    'django-cms>=3.4.3',
    'django-sekizai>=1.0.0',
    'lxml',
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
    keywords=['django', 'Django CMS', 'version history', 'versioning',
              'reversion', 'revision', 'CMS', 'Blueshoe', 'basket', 'bin', 'revert'],
    classifiers=CLASSIFIERS,
    test_suite='tests.settings.run',
)
