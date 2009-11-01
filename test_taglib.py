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

from taglib import tagopen, ValidationError, InvalidMedia, __version__, MP3

# initialize root logger
log.basicConfig(level=log.INFO, format='%(levelname)s> %(message)s')

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


def test(file, version=None, fakemp3=False):
    """Test decode/save/decode of file and return errors if any"""
    ext = os.path.splitext(file)[1].lower()
    try:
        src = tagopen(file, readonly=False)
    except InvalidMedia:
        return ['could not decode']
    except Exception, error:
        return ['unexpected decode error: %s' % error]
    errors = []
    # actual mp3 files can be inside a RIFF container, so don't complain
    if not isinstance(src, MP3) or not src.hasmp3:
        return errors
    try:
        dst = src.dump(version=version, fakemp3=fakemp3)
    except Exception, error:
        return errors + ['could not save: %s' % error]
    try:
        dst = tagopen(dst)
    except Exception, error:
        return errors + ['could not reopen: %s' % error]
    try:
        MP3.compare(src, dst)
    except ValidationError, error:
        errors.append(error)
    return errors


def main(args=None):
    """Command-line interface"""
    optparse = OptionParser('%prog [opts] <dir>', version=__version__,
                            description=__doc__)
    optparse.add_option('-l', dest='logfile', metavar='<file>',
                        help='log messages to <file>')
    optparse.add_option('-V', dest='version', metavar='<2|3|4>', type='int',
                        help='force id3 version (default: same as source)')
    optparse.add_option('-s', dest='fakemp3', default=False,
                        action='store_true', help="skip mp3 copy for speed")
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
                errors = test(file, version=opts.version, fakemp3=opts.fakemp3)
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
