#!/usr/bin/env python

"""Setup script for taglib"""

import sys

if sys.hexversion < 0x02060000:
    print >> sys.stderr, 'Sorry, Python 2.6 is required.'
    sys.exit(1)

from distutils.core import setup

sys.dont_write_bytecode = True  # don't leave turds
from taglib import __version__

def main():
    setup(name='taglib',
          author='Chris Jones',
          author_email='cjones@gruntle.org',
          url='http://code.google.com/p/python-taglib/',
          description='Library to manipulate audio file metadata',
          license='BSD',
          version=__version__,
          py_modules=['taglib'],
          scripts=['scripts/tagdump'],

          # http://pypi.python.org/pypi?%3Aaction=list_classifiers
          classifiers=[
              'Development Status :: 4 - Beta',
              'Environment :: Console',
              'Intended Audience :: Developers',
              'License :: OSI Approved :: BSD License',
              'Natural Language :: English',
              'Operating System :: OS Independent',
              'Programming Language :: Python :: 2.6',
              'Topic :: Multimedia :: Sound/Audio',
              'Topic :: Software Development :: Libraries :: Python Modules'])

    return 0

if __name__ == '__main__':
    sys.exit(main())
