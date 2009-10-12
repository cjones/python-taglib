#!/usr/bin/env python

"""Test taglib's encode/decode integrity.

This tool will walk through all the files in a directory and attempt to
decode them, verifying the format is appropriate for the extension.  If
encoding is supported, it will encode the file, decode the saved
version, and compare the metadata in each to verify they are identical.
All errors are logged to the console and optionally to a logfile.
"""

from optparse import OptionParser
import logging as log
import time
import sys
import os

sys.dont_write_bytecode = True  # DOWN WITH PYC
from taglib import (tagopen, StringIO, DICT, IDICT, TYPES,
                    LIST, IMAGE, InvalidMedia, __version__)

# initialize root logger
log.basicConfig(level=log.INFO, format='%(levelname)s> %(message)s')

# some common extensions and their expected decoder type
exts = {'.m4a': 'm4a',
        '.m4r': 'm4a',
        '.mp4': 'm4a',
        '.mp3': 'mp3',
        '.mp2': 'mp3',
        '.flac': 'flac',
        '.aif': 'iff',
        '.aiff': 'iff',
        '.wav': 'iff',
        '.avi': 'iff',
        '.ogg': 'ogg'}

class Timer(object):

    """Context to time a job"""

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        """Start timer"""
        log.info('%s started' % self.name)
        self.start = time.time()
        return self

    def __exit__(self, *args):
        """Exit timer context"""
        elapsed = self.clock(time.time() - self.start)
        log.info('%s finished in %s' % (self.name, elapsed))

    @staticmethod
    def clock(seconds):
        """Convert seconds to human-readable time"""
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return ':'.join(str(val).zfill(2) for val in (hours, minutes, seconds))


class Meter(Timer):

    """Meter for enumerating items"""

    WIDTH = 72
    FREQ = 0.25
    FMT = '[%d/%d] Elapsed: %s - Remaining: %s'
    ANSI_HIDE_CURSOR = '\x1b[?25l'
    ANSI_SHOW_CURSOR = '\x1b[?25h'

    def __init__(self, name, items, freq=None, stream=None, width=None):
        if not hasattr(items, '__len__'):
            items = list(items)
        if freq is None:
            freq = self.FREQ
        if stream is None:
            stream = sys.stderr
        if width is None:
            width = self.WIDTH
        self.items = items
        self.size = len(items)
        self.freq = freq
        self.stream = stream
        self.width = width
        super(Meter, self).__init__(name)

    def __enter__(self):
        """Begin timer"""
        self.last = 0
        self.pos = 0
        self.writeline(self.ANSI_HIDE_CURSOR)
        return super(Meter, self).__enter__()

    def __exit__(self, *args):
        """Exit meter context"""
        self.writeline(self.ANSI_SHOW_CURSOR)
        return super(Meter, self).__exit__(*args)

    def update(self, pos=None):
        """Update status line"""
        if pos is None:
            pos = self.pos
        else:
            self.pos = pos
        now = time.time()
        if now - self.last >= self.freq:
            self.last = now
            done = now - self.start
            if pos:
                eta = self.clock(done / pos * (self.size - pos))
            else:
                eta = '--:--:--'
            self.writeline(self.FMT % (pos, self.size, self.clock(done), eta))

    def writeline(self, line):
        """Write statusline"""
        self.stream.write(line.ljust(self.width) + '\r')

    def log(self, level, message):
        """Log without messing up status line"""
        if level >= log.root.level:
            self.writeline('')
            log.log(level, message)
            self.update()

    def __iter__(self):
        """Iterating meter yields each item and updates status line"""
        for i, item in enumerate(self.items):
            self.update(i)
            yield item

    def __getattribute__(self, key):
        """Dynamically provide logging functions"""
        try:
            return super(Meter, self).__getattribute__(key)
        except AttributeError, error:
            tb = sys.exc_traceback
        try:
            return lambda message: self.log(getattr(log, key.upper()), message)
        except AttributeError:
            raise error, None, tb


def find(dir, skip_svn=True):
    """Yields full path to files in a directory"""
    log.info('scanning %s' % dir)
    for basedir, subdirs, filenames in os.walk(dir):
        if skip_svn and '.svn' in subdirs:
            subdirs.remove('.svn')
        for filename in filenames:
            yield os.path.join(basedir, filename)
    log.info('finished scanning')


def test(file):
    """Test decode/save/decode of file and return errors if any"""
    ext = os.path.splitext(file)[1].lower()
    expected = exts.get(ext)
    try:
        src = tagopen(file, readonly=False)
    except InvalidMedia:
        return ['could not decode']
    except Exception, error:
        return ['unexpected decode error: %s' % error]
    errors = []
    # actual mp3 files can be inside a RIFF container, so don't complain
    if src.format != expected and not (ext == '.mp3' and src.format == 'iff'):
        errors.append('unexpected format.  %s != %s' % (expected, src.format))
    # on the other hand, don't try to save unless it did find an mp3
    if src.close or (src.format == 'iff' and not src.has_mp3data):
        return errors
    try:
        dst = src.save(StringIO())
    except Exception, error:
        return errors + ['could not save: %s' % error]
    try:
        dst = tagopen(dst)
    except Exception, error:
        return errors + ['could not reopen: %s' % error]
    for attr, type in TYPES.iteritems():
        if type in (DICT, IDICT, LIST):
            continue
        if type == IMAGE:
            val1, val2 = src.image_sample, dst.image_sample
        else:
            val1, val2 = src[attr], dst[attr]
        if val1 != val2:
            errors.append('%s: %r != %r' % (attr, val1, val2))
    return errors


def main(args=None):
    optparse = OptionParser('%prog <dir>', version=__version__,
                            description=__doc__)
    group = optparse.add_option_group('Log options')
    group.add_option('-l', dest='logfile', metavar='<file>',
                     help='log messages to <file>')
    opts, args = optparse.parse_args(args)
    if len(args) != 1:
        optparse.print_help()
        return 1
    if opts.logfile:
        handler = log.FileHandler(opts.logfile)
        handler.setFormatter(log.root.handlers[0].formatter)
        log.root.addHandler(handler)
        log.info('opened logfile: %s' % opts.logfile)
    library = args[0]
    files_tested = files_broken = error_count = 0
    log.info('begin at %s' % time.ctime())
    try:
        with Meter('TestLibrary', find(library)) as meter:
            for file in meter:
                files_tested += 1
                errors = test(file)
                nerr = len(errors)
                if nerr:
                    files_broken += 1
                    error_count += nerr
                    message = '%d error%s parsing %s' % (
                            nerr, 's' if nerr > 1 else '', file)
                    meter.warn(message)
                    for i, error in enumerate(errors):
                        meter.error('error %d/%d: %s' % (i + 1, nerr, error))
    except KeyboardInterrupt:
        log.error('user cancelled test')
        return 2
    finally:
        log.info('Files tested: %d' % files_tested)
        log.info('Files broken: %d' % files_broken)
        log.info('Error count: %d' % error_count)
    return 0

if __name__ == '__main__':
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass
    sys.exit(main())
