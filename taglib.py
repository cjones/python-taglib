# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# - Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#
# - Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# References:
#
# Genres: http://www.multimediasoft.com/amp3dj/help/amp3dj_00003e.htm
# MP3:    http://www.mpgedit.org/mpgedit/mpeg_format/mpeghdr.htm
# ID3v1:  http://en.wikipedia.org/wiki/Id3#Layout
# ID3v2:  http://www.id3.org/Developer_Information
# RVA:    http://git.savannah.gnu.org/cgit/gnupod.git/tree/src/ext/FileMagic.pm
# IFF:    http://en.wikipedia.org/wiki/Interchange_File_Format
# RIFF:   http://www.midi.org/about-midi/rp29spec(rmid).pdf
# MP4:    http://atomicparsley.sourceforge.net/mpeg-4files.html
# Vorbis: http://www.xiph.org/vorbis/doc/v-comment.html
# FLAC:   http://flac.sourceforge.net/format.html#stream
# OGG:    http://en.wikipedia.org/wiki/Ogg#File_format

from __future__ import with_statement
import sys

if sys.hexversion < 0x02060200:
    print >> sys.stderr, 'Sorry, Python 2.6 is required'
    sys.exit(0)

from struct import error as StructError, Struct
from collections import MutableMapping
from math import log
import os
import re

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    from PIL import Image
    from PIL.ImageFile import ImageFile
    PIL = True
except ImportError:
    PIL = False

__version__ = '3.0'
__author__ = 'Chris Jones <cjones@gruntle.org>'
__all__ = ['tagopen', 'InvalidMedia', 'ValidationError']

DEFAULT_ID3V2_VERSION = 2
DEFAULT_ID3V2_PADDING = 128
MP3_SAMPLESIZE = 5762
ANYITEM = -1
GAPLESS = u'iTunPGAP'
ENCODING = sys.getfilesystemencoding()

(DICT, IDICT, TEXT, UINT16, BOOL, UINT16X2,
 GENRE, IMAGE, UINT32, VOLUME) = xrange(10)

TYPES = {'_comment': DICT,
         '_image': IDICT,
         '_lyrics': DICT,
         '_unknown': DICT,
         'album': TEXT,
         'album_artist': TEXT,
         'artist': TEXT,
         'bpm': UINT16,
         'comment': TEXT,
         'compilation': BOOL,
         'composer': TEXT,
         'disk': UINT16X2,
         'encoder': TEXT,
         'gapless': BOOL,
         'genre': GENRE,
         'grouping': TEXT,
         'image': IMAGE,
         'lyrics': TEXT,
         'name': TEXT,
         'sort_album': TEXT,
         'sort_album_artist': TEXT,
         'sort_artist': TEXT,
         'sort_composer': TEXT,
         'sort_name': TEXT,
         'sort_video_show': TEXT,
         'track': UINT16X2,
         'video_description': TEXT,
         'video_episode': UINT32,
         'video_episode_id': TEXT,
         'video_season': UINT32,
         'video_show': TEXT,
         'volume': VOLUME,
         'year': UINT16}

DISPLAY = [('Info',
            (('Filename', 'filename'),
             ('Name', 'name'),
             ('Artist', 'artist'),
             ('Album Artist', 'album_artist'),
             ('Album', 'album'),
             ('Grouping', 'grouping'),
             ('Composer', 'composer'),
             ('Comments', 'comment'),
             ('Genre', 'genre'),
             ('Year', 'year'),
             ('Track Number', 'track'),
             ('Disc Number', 'disk'),
             ('BPM', 'bpm'),
             ('Part of a compilation', 'compilation'))),
           ('Video',
            (('Show', 'video_show'),
             ('Episode ID', 'video_episode_id'),
             ('Description', 'video_description'),
             ('Season Number', 'video_season'),
             ('Episode Number', 'video_episode'))),
           ('Sorting',
            (('Sort Name', 'sort_name'),
             ('Sort Artist', 'sort_artist'),
             ('Sort Album Artist', 'sort_album_artist'),
             ('Sort Album', 'sort_album'),
             ('Sort Composer', 'sort_composer'),
             ('Sort Show', 'sort_video_show'))),
           ('Misc',
            (('Volume Adjustment', 'volume'),
             ('Part of a gapless album', 'gapless'),
             ('Artwork', 'image'),
             ('Encoder', 'encoder'),
             ('Lyrics', 'lyrics')))]

GENRES = ['Blues', 'Classic Rock', 'Country', 'Dance', 'Disco', 'Funk',
          'Grunge', 'Hip-Hop', 'Jazz', 'Metal', 'New Age', 'Oldies', 'Other',
          'Pop', 'R&B', 'Rap', 'Reggae', 'Rock', 'Techno', 'Industrial',
          'Alternative', 'Ska', 'Death Metal', 'Pranks', 'Soundtrack',
          'Euro-Techno', 'Ambient', 'Trip-Hop', 'Vocal', 'Jazz+Funk', 'Fusion',
          'Trance', 'Classical', 'Instrumental', 'Acid', 'House', 'Game',
          'Sound Clip', 'Gospel', 'Noise', 'Alternative Rock', 'Bass', 'Soul',
          'Punk', 'Space', 'Meditative', 'Instrumental Pop',
          'Instrumental Rock', 'Ethnic', 'Gothic', 'Darkwave',
          'Techno-Industrial', 'Electronic', 'Pop-Folk', 'Eurodance', 'Dream',
          'Southern Rock', 'Comedy', 'Cult', 'Gangsta', 'Top 40',
          'Christian Rap', 'Pop/Funk', 'Jungle', 'Native US', 'Cabaret',
          'New Wave', 'Psychadelic', 'Rave', 'Showtunes', 'Trailer', 'Lo-Fi',
          'Tribal', 'Acid Punk', 'Acid Jazz', 'Polka', 'Retro', 'Musical',
          'Rock & Roll', 'Hard Rock', 'Folk', 'Folk-Rock', 'National Folk',
          'Swing', 'Fast Fusion', 'Bebob', 'Latin', 'Revival', 'Celtic',
          'Bluegrass', 'Avantgarde', 'Gothic Rock', 'Progressive Rock',
          'Psychedelic Rock', 'Symphonic Rock', 'Slow Rock', 'Big Band',
          'Chorus', 'Easy Listening', 'Acoustic', 'Humour', 'Speech',
          'Chanson', 'Opera', 'Chamber Music', 'Sonata', 'Symphony',
          'Booty Bass', 'Primus', 'Porn Groove', 'Satire', 'Slow Jam', 'Club',
          'Tango', 'Samba', 'Folklore', 'Ballad', 'Power Ballad',
          'Rhythmic Soul', 'Freestyle', 'Duet', 'Punk Rock', 'Drum Solo',
          'Acapella', 'Euro-House', 'Dance Hall', 'Goa', 'Drum & Bass',
          'Club - House', 'Hardcore', 'Terror', 'Indie', 'BritPop',
          'Negerpunk', 'Polsk Punk', 'Beat', 'Christian Gangsta Rap',
          'Heavy Metal', 'Black Metal', 'Crossover', 'Contemporary Christian',
          'Christian Rock', 'Merengue', 'Salsa', 'Thrash Metal', 'Anime',
          'JPop', 'Synthpop']

BOOLEANS = {True: ['true', 't', 'yes', 'y', 'on', '1', 1, '\x01'],
            False: ['false', 'f', 'no', 'n', 'off', '0', 0]}

ID3V1_ATTRS = ['name', 'artist', 'album', 'year', 'comment', 'track', 'genre']

ID3V2_OPTS = {2: {'head': Struct('3s 3s 0s'),
                  'syncsafe': False,
                  'tags': {'COM': '_comment',
                           'PIC': '_image',
                           'RVA': 'volume',
                           'TAL': 'album',
                           'TBP': 'bpm',
                           'TCM': 'composer',
                           'TCO': 'genre',
                           'TCP': 'compilation',
                           'TEN': 'encoder',
                           'TP1': 'artist',
                           'TP2': 'album_artist',
                           'TPA': 'disk',
                           'TRK': 'track',
                           'TS2': 'sort_album_artist',
                           'TSA': 'sort_album',
                           'TSC': 'sort_composer',
                           'TSP': 'sort_artist',
                           'TST': 'sort_name',
                           'TT1': 'grouping',
                           'TT2': 'name',
                           'TT3': 'video_description',
                           'TYE': 'year',
                           'ULT': '_lyrics'}},
              3: {'head': Struct('4s 4s 2s'),
                  'syncsafe': False,
                  'tags': {'APIC': '_image',
                           'COMM': '_comment',
                           'RVAD': 'volume',
                           'TALB': 'album',
                           'TBPM': 'bpm',
                           'TCMP': 'compilation',
                           'TCOM': 'composer',
                           'TCON': 'genre',
                           'TENC': 'encoder',
                           'TIT1': 'grouping',
                           'TIT2': 'name',
                           'TIT3': 'video_description',
                           'TPE1': 'artist',
                           'TPE2': 'album_artist',
                           'TPOS': 'disk',
                           'TRCK': 'track',
                           'TSO2': 'sort_album_artist',
                           'TSOA': 'sort_album',
                           'TSOC': 'sort_composer',
                           'TSOP': 'sort_artist',
                           'TSOT': 'sort_name',
                           'TYER': 'year',
                           'USLT': '_lyrics'}},
              4: {'head': Struct('4s 4s 2s'),
                  'syncsafe': True,
                  'tags': {'APIC': '_image',
                           'COMM': '_comment',
                           'RVA2': 'volume',
                           'TALB': 'album',
                           'TBPM': 'bpm',
                           'TCMP': 'compilation',
                           'TCOM': 'composer',
                           'TCON': 'genre',
                           'TDRC': 'year',
                           'TENC': 'encoder',
                           'TIT1': 'grouping',
                           'TIT2': 'name',
                           'TIT3': 'video_description',
                           'TPE1': 'artist',
                           'TPE2': 'album_artist',
                           'TPOS': 'disk',
                           'TRCK': 'track',
                           'TSO2': 'sort_album_artist',
                           'TSOA': 'sort_album',
                           'TSOC': 'sort_composer',
                           'TSOP': 'sort_artist',
                           'TSOT': 'sort_name',
                           'USLT': '_lyrics'}}}

ID3V2_TAGS = dict((tag, attr) for opts in ID3V2_OPTS.itervalues()
                  for tag, attr in opts['tags'].iteritems())

ID3V2_ENCODINGS = {'\x00': ('latin-1', '\x00'),
                   '\x01': ('utf-16', '\x00\x00'),
                   '\x02': ('utf-16-be', '\x00\x00'),
                   '\x03': ('utf-8', '\x00')}

MP3_BITRATES = [
    [32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0],
    [32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
    [32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
    [32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
    [8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]]

MP3_SRATES = [[11025, 12000, 8000], None,
              [22050, 24000, 16000], [44100, 48000, 32000]]

IFFIDS = {'ANNO': 'comment',
          'AUTH': 'artist',
          'IART': 'artist',
          'ICMT': 'comment',
          'ICRD': 'year',
          'INAM': 'name',
          'NAME': 'name'}

ATOM_NODE1, ATOM_NODE2, ATOM_DATA = xrange(3)

ATOMS = {'moov': (ATOM_NODE1, None),
         'moov.udta': (ATOM_NODE1, None),
         'moov.udta.meta': (ATOM_NODE2, None),
         'moov.udta.meta.ilst': (ATOM_NODE1, None),
         'moov.udta.meta.ilst.aART': (ATOM_DATA, 'album_artist'),
         'moov.udta.meta.ilst.covr': (ATOM_DATA, 'image'),
         'moov.udta.meta.ilst.cpil': (ATOM_DATA, 'compilation'),
         'moov.udta.meta.ilst.desc': (ATOM_DATA, 'video_description'),
         'moov.udta.meta.ilst.disk': (ATOM_DATA, 'disk'),
         'moov.udta.meta.ilst.gnre': (ATOM_DATA, 'genre'),
         'moov.udta.meta.ilst.pgap': (ATOM_DATA, 'gapless'),
         'moov.udta.meta.ilst.soaa': (ATOM_DATA, 'sort_album_artist'),
         'moov.udta.meta.ilst.soal': (ATOM_DATA, 'sort_album'),
         'moov.udta.meta.ilst.soar': (ATOM_DATA, 'sort_artist'),
         'moov.udta.meta.ilst.soco': (ATOM_DATA, 'sort_composer'),
         'moov.udta.meta.ilst.sonm': (ATOM_DATA, 'sort_name'),
         'moov.udta.meta.ilst.sosn': (ATOM_DATA, 'sort_video_show'),
         'moov.udta.meta.ilst.tmpo': (ATOM_DATA, 'bpm'),
         'moov.udta.meta.ilst.trkn': (ATOM_DATA, 'track'),
         'moov.udta.meta.ilst.tven': (ATOM_DATA, 'video_episode_id'),
         'moov.udta.meta.ilst.tves': (ATOM_DATA, 'video_episode'),
         'moov.udta.meta.ilst.tvsh': (ATOM_DATA, 'video_show'),
         'moov.udta.meta.ilst.tvsn': (ATOM_DATA, 'video_season'),
         'moov.udta.meta.ilst.\xa9ART': (ATOM_DATA, 'artist'),
         'moov.udta.meta.ilst.\xa9alb': (ATOM_DATA, 'album'),
         'moov.udta.meta.ilst.\xa9cmt': (ATOM_DATA, 'comment'),
         'moov.udta.meta.ilst.\xa9day': (ATOM_DATA, 'year'),
         'moov.udta.meta.ilst.\xa9gen': (ATOM_DATA, 'genre'),
         'moov.udta.meta.ilst.\xa9grp': (ATOM_DATA, 'grouping'),
         'moov.udta.meta.ilst.\xa9lyr': (ATOM_DATA, 'lyrics'),
         'moov.udta.meta.ilst.\xa9nam': (ATOM_DATA, 'name'),
         'moov.udta.meta.ilst.\xa9too': (ATOM_DATA, 'encoder'),
         'moov.udta.meta.ilst.\xa9wrt': (ATOM_DATA, 'composer')}

VORBISTAGS = {'album': 'album',
              'album artist': 'album_artist',
              'album_artist': 'album_artist',
              'albumartist': 'album_artist',
              'artist': 'artist',
              'beats per minute': 'bpm',
              'beats_per_minute': 'bpm',
              'beatsperminute': 'bpm',
              'bpm': 'bpm',
              'comment': 'comment',
              'comments': 'comment',
              'compilation': 'compilation',
              'composer': 'composer',
              'date': 'year',
              'disc': 'disk',
              'disc number': 'disk',
              'disc_number': 'disk',
              'discnumber': 'disk',
              'disk': 'disk',
              'disk number': 'disk',
              'disk_number': 'disk',
              'disknumber': 'disk',
              'encoder': 'encoder',
              'gapless': 'gapless',
              'gapless playback': 'gapless',
              'gapless_playback': 'gapless',
              'gaplessplayback': 'gapless',
              'genre': 'genre',
              'grouping': 'grouping',
              'lyrics': 'lyrics',
              'name': 'name',
              'sort album': 'sort_album',
              'sort album artist': 'sort_album_artist',
              'sort artist': 'sort_artist',
              'sort composer': 'sort_composer',
              'sort name': 'sort_name',
              'sort video show': 'sort_video_show',
              'sort_album': 'sort_album',
              'sort_album_artist': 'sort_album_artist',
              'sort_artist': 'sort_artist',
              'sort_composer': 'sort_composer',
              'sort_name': 'sort_name',
              'sort_video_show': 'sort_video_show',
              'sortalbum': 'sort_album',
              'sortalbumartist': 'sort_album_artist',
              'sortartist': 'sort_artist',
              'sortcomposer': 'sort_composer',
              'sortname': 'sort_name',
              'sortvideoshow': 'sort_video_show',
              'tempo': 'bpm',
              'title': 'name',
              'track': 'track',
              'track number': 'track',
              'track_number': 'track',
              'tracknumber': 'track',
              'video description': 'video_description',
              'video episode': 'video_episode',
              'video episode id': 'video_episode_id',
              'video season': 'video_season',
              'video show': 'video_show',
              'video_description': 'video_description',
              'video_episode': 'video_episode',
              'video_episode_id': 'video_episode_id',
              'video_season': 'video_season',
              'video_show': 'video_show',
              'videodescription': 'video_description',
              'videoepisode': 'video_episode',
              'videoepisodeid': 'video_episode_id',
              'videoseason': 'video_season',
              'videoshow': 'video_show',
              'volume': 'volume',
              'year': 'year'}

class TaglibError(Exception):

    pass


class ValidationError(TaglibError):

    pass


class DecodeError(TaglibError):

    pass


class EncodeError(TaglibError):

    pass


class InvalidMedia(TaglibError):

    pass


class Container(MutableMapping):

    types = {}

    def __init__(self, *args, **kwargs):
        self.__dict__.update(*args, **kwargs)

    def getdisplay(self, attr):
        return repr(self[attr])

    def __getitem__(self, key):
        return self.__getattribute__(key)

    def __getattribute__(self, attr):
        try:
            return super(Container, self).__getattribute__(attr)
        except AttributeError:
            if attr not in self.types:
                raise

    def __setitem__(self, key, val):
        self.__setattr__(key, val)

    def __setattr__(self, attr, val):
        super(Container, self).__setattr__(attr, self._validate(attr, val))

    def __delitem__(self, key):
        self.__delattr__(key)

    def __delattr__(self, attr):
        self._validate(attr)
        try:
            super(Container, self).__delattr__(attr)
        except AttributeError:
            if attr not in self.types:
                raise

    def __iter__(self):
        return (attr for attr in sorted(self.types)
                if not attr.startswith('_') and self[attr] is not None)

    def __len__(self):
        return sum(1 for _ in self.__iter__())

    def __repr__(self):
        attrs = ', '.join('%s=%s' % (i, self.getdisplay(i)) for i in self)
        return '<%s object at 0x%x%s%s>' % (
                type(self).__name__, id(self), ': ' if attrs else '', attrs)

    @classmethod
    def _validate(cls, attr, val=None):
        try:
            return cls.validate(val, cls.types[attr])
        except KeyError:
            return val
        except ValidationError, error:
            error.args = '%s: %s' % (attr, error),
            raise

    @staticmethod
    def validate(val, type):
        if val is not None and type is not None and not isinstance(val, type):
            try:
                val = type(val)
            except Exception, error:
                raise ValidationError(error)
        return val


class Metadata(Container):

    types = TYPES

    @property
    def image_sample(self):
        if self.image:
            val = StringIO()
            self.image.save(val, self.image.format)
            val.seek(0, os.SEEK_SET)
            return val.read(512), self.image.size, self.image.format

    @property
    def rounded_volume(self):
        if self.volume:
            return '.%1f' % round(self.volume, 1)

    def display(self, width=72, stream=None, filename=None, encoding=None):
        if stream is None:
            stream = sys.stdout
        if filename is None:
            try:
                filename = os.path.basename(self.fp.name)
            except AttributeError:
                pass
        if encoding is None:
            encoding = ENCODING
        hr = '-' * width
        hasdata = False
        for section, fields in DISPLAY:
            lines = []
            size = 0
            for name, attr in fields:
                if attr == 'filename':
                    val = filename
                else:
                    val = self.getdisplay(attr)
                if not val:
                    continue
                if len(name) > size:
                    size = len(name)
                lines.append((name, val))
            if not lines:
                continue
            print >> stream, hr
            print >> stream, section.center(width)
            print >> stream, hr
            for name, val in lines:
                print >> stream, '%s: %s' % (name.rjust(size), val)
            hasdata = True
        if hasdata:
            print >> stream, hr
        else:
            print >> stream, 'No metadata to display'

    def getdisplay(self, attr, encoding=None):
        if encoding is None:
            encoding = ENCODING
        val = self[attr]
        if val is None:
            return
        type = self.types.get(attr)
        if type == BOOL:
            return 'yes' if val else 'no'
        elif type in (GENRE, TEXT):
            return val.encode(encoding, 'ignore')
        elif type == IMAGE:
            return '%dx%d %s Image' % (val.size[0], val.size[1], val.format)
        elif type in (UINT16, UINT32):
            return str(val)
        elif type == UINT16X2:
            return '%d/%d' % tuple(val)
        elif type == VOLUME:
            return '%.1f' % val
        else:
            return repr(val)

    def __eq__(self, other):
        if not isinstance(other, Metadata):
            return NotImplemented
        try:
            self.compare(self, other)
        except ValidationError:
            return False
        return True

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    @staticmethod
    def validate(val, type):
        raise ValidationError('read-only')

    @classmethod
    def compare(cls, x, y):
        for attr, type in cls.types.iteritems():
            if type in (DICT, IDICT):
                continue
            if type == IMAGE:
                xval, yval = x.image_sample, y.image_sample
            elif type == VOLUME:
                xval, yval = x.rounded_volume, y.rounded_volume
            else:
                xval, yval = x[attr], y[attr]
            if xval != yval:
                raise ValidationError('%s: %r != %r' % (attr, xval, yval))


class Open(object):

    def __init__(self, file, mode='rb', close=True):
        self.file = file
        self.mode = mode
        self.close = close
        self.fp = None
        self.external = None
        self.pos = None

    def __enter__(self):
        if isinstance(self.file, basestring):
            self.fp = open(self.file, self.mode)
            self.external = False
        elif isinstance(self.file, (int, long)):
            self.fp = os.fdopen(self.file, self.mode)
            self.external = True
        elif hasattr(self.file, 'seek'):
            self.fp = self.file
            self.external = True
        else:
            raise TypeError('file must be a path, descriptor, fileobj')
        if self.external:
            self.pos = self.fp.tell()
        return self.fp

    def __exit__(self, *exc_info):
        if self.external:
            self.fp.seek(self.pos, os.SEEK_SET)
        elif self.close:
            self.fp.close()


class Decoder(Metadata):

    format = None
    editable = False

    uint32be = Struct('> L')
    int16be = Struct('> h')
    uint16be = Struct('> H')
    uint32le = Struct('< L')

    def __init__(self, file):
        if self.editable:
            mode = 'rb+'
            close = False
        else:
            mode = 'rb'
            close = True
        with Open(file, mode, close) as fp:
            self.fp = fp
            try:
                self.decode()
            except Errors, error:
                raise InvalidMedia, error, sys.exc_traceback
        self.modified = False

    def save(self, *args, **kwargs):
        if not self.editable:
            raise EncodeError('encoding not formatted for %s' % self.format)
        if self.fp.closed:
            raise EncodeError('original file has closed')
        kwargs['inplace'] = True
        self.encode(self.fp, *args, **kwargs)

    def dump(self, file=None, *args, **kwargs):
        if file is None:
            file = StringIO()
        with Open(file, 'wb') as fp:
            kwargs['inplace'] = False
            self.encode(fp, *args, **kwargs)
        if not fp.closed:
            return fp

    def dumps(self, *args, **kwargs):
        return self.dump(None, *args, **kwargs).getvalue()

    def unpack(self, struct):
        val = struct.unpack(self.fp.read(struct.size))
        if len(val) == 1:
            return val[0]
        return val

    def __setattr__(self, attr, val):
        super(Decoder, self).__setattr__(attr, val)
        if attr in self.types:
            self.modified = True

    def __delattr__(self, attr):
        super(Decoder, self).__delattr__(attr)
        if attr in self.types:
            self.modified = True

    @staticmethod
    def decode():
        raise NotImplementedError

    @staticmethod
    def encode(fp, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def validate(cls, val, type):
        if val is None:
            return
        if type in (DICT, IDICT) and not isinstance(val, dict):
            raise ValidationError('must be a dictionary')
        elif type == GENRE:
            if isinstance(val, (int, long)):
                try:
                    val = GENRES[val]
                except IndexError, error:
                    raise ValidationError(error)
            type = TEXT
        if type == TEXT and not isinstance(val, basestring):
            val = str(val)
        if type in (TEXT, UINT16, BOOL, UINT16X2, GENRE, UINT32, VOLUME):
            if isinstance(val, str):
                val = val.decode('ascii', 'ignore')
            if isinstance(val, unicode):
                val = val.replace('\x00', '').strip()
                if not val:
                    return
                if type in (UINT16, UINT32):
                    try:
                        val = int(val)
                    except ValueError, error:
                        raise ValidationError(error)
                elif type == VOLUME:
                    try:
                        val = float(val)
                    except ValueError, error:
                        raise ValidationError(error)
                elif type == BOOL:
                    val = val.lower()
        if type == BOOL:
            for bool, vals in BOOLEANS.iteritems():
                if val in vals:
                    val =  bool
                    break
            else:
                raise ValidationError('invalid boolean')
        elif type == IMAGE:
            if not PIL:
                raise ValidationError('PIL required for image support')
            if not isinstance(val, ImageFile):
                try:
                    with Open(val, 'rb') as fp:
                        val = Image.open(fp)
                        val.load()
                except (TypeError, IOError), error:
                    raise ValidationError(error)
        elif type in (UINT16, UINT32):
            if isinstance(val, float):
                val = int(val)
            elif not isinstance(val, (int, long)):
                raise ValidationError('must be an integer')
        elif type == VOLUME:
            if isinstance(val, int):
                val = float(val)
            elif not isinstance(val, float):
                raise ValidatinError('must be a float')
            if val < -99.9:
                val = -99.9
            elif val > 100.0:
                val = 100.0
        if type == UINT16 and (val < 0 or val > 0xffff):
            raise ValidationError('out of range of uint16')
        elif type == UINT16X2:
            if isinstance(val, (int, long)):
                val = val, 0
            elif isinstance(val, unicode):
                val = val.split('/')
            if isinstance(val, tuple):
                val = list(val)
            elif not isinstance(val, list):
                raise ValidationError('invalid type for uint16x2')
            if not val:
                val = [0, 0]
            elif len(val) == 1:
                val.append(0)
            elif len(val) != 2:
                raise ValidationError('needs one or two members')
            for i, item in enumerate(val):
                if isinstance(item, basestring):
                    try:
                        item = int(item)
                    except ValueError:
                        item = 0
                elif not isinstance(item, (int, long)):
                    raise ValidationError('each member must be a number')
                if item < 0:
                    item = 0
                elif item > 0xffff:
                    raise ValidationError('member out of range of uint16')
                val[i] = item
            if val == [0, 0]:
                val = None
        elif type == UINT32 and (val < 0 or val > 0xffffffff):
            raise ValidationError('out of range of uint32')
        if not val and type not in (DICT, IDICT):
            val = None
        return val


class MP3Frame(Container):

    types = {'bitrate': int, 'copyright': bool, 'emphasis': int, 'ext': int,
             'layer': int, 'mode': int, 'original': bool, 'padding': int,
             'private': bool, 'protected': bool, 'srate': int, 'sync': bool,
             'v2': bool, 'version': int}


class MP3(Decoder):

    format = 'mp3'
    editable = True

    id3v1 = Struct('3s 30s 30s 30s 4s 30s B')
    id3v2head = Struct('3s B B B 4s')
    longbytes = Struct('4B')

    tag_re = re.compile(r'^[A-Z0-9 ]{3,4}$')
    genre_re = re.compile(r'^\((\d+)\)$')
    track_re = re.compile(r'^(.+)\x00 ([^\x00])$')

    fakemp3 = '\xff\xf2\x14\x00' * 7

    def __init__(self, *args, **kwargs):
        self.hasid3v1 = False
        self.id3v1start = None
        self.id3v1end = None
        self.hasid3v2 = False
        self.id3v2start = None
        self.id3v2end = None
        self.id3v2version = None
        self.hasmp3 = False
        self.mp3start = None
        self.mp3end = None
        super(MP3, self).__init__(*args, **kwargs)

    def get_gapless(self):
        return self.get_comment(key=GAPLESS)

    def set_gapless(self, val):
        self.set_comment(val, key=GAPLESS)

    def del_gapless(self):
        self.del_comment(key=GAPLESS)

    gapless = property(get_gapless, set_gapless, del_gapless)

    def get_comment(self, key=None, lang='eng'):
        if key != ANYITEM:
            key = lang, key
        return self.getdict('_comment', key)

    def set_comment(self, val, key=None, lang='eng'):
        self.setdict('_comment', (lang, self.validate(key, TEXT)),
                     self.validate(val, BOOL if key == GAPLESS else TEXT))

    def del_comment(self, key=None, lang='eng'):
        if key != ANYITEM:
            key = lang, key
        return self.deldict('_comment', key)

    comment = property(get_comment, set_comment, del_comment)

    def get_lyrics(self, key=None, lang='eng'):
        if key != ANYITEM:
            key = lang, key
        return self.getdict('_lyrics', key)

    def set_lyrics(self, val, key=None, lang='eng'):
        self.setdict('_lyrics', (lang, self.validate(key, TEXT)),
                     self.validate(val, TEXT))

    def del_lyrics(self, key=None, lang='eng'):
        if key != ANYITEM:
            key = lang, key
        return self.deldict('_lyrics', key)

    lyrics = property(get_lyrics, set_lyrics, del_lyrics)

    def get_image(self, key=ANYITEM):
        if key != ANYITEM:
            key = key,
        image = self.getdict('_image', key)
        if image:
            return image[0]

    def set_image(self, val, key=None, ptype=3):
        self.setdict('_image', (self.validate(key, TEXT),),
                     (self.validate(val, IMAGE), ptype))

    def del_image(self, key=ANYITEM):
        if key != ANYITEM:
            key = key,
        self.deldict('_image', key)

    image = property(get_image, set_image, del_image)

    def getdict(self, attr, key):
        dict = self[attr]
        if dict:
            if key == ANYITEM:
                key = sorted(dict)[0]
            return dict.get(key)

    def setdict(self, attr, key, val):
        if val is None:
            self.deldict(attr, key)
        else:
            dict = self[attr]
            if not dict:
                dict = self[attr] = {}
            dict[key] = val

    def deldict(self, attr, key):
        dict = self[attr]
        if dict:
            if key == ANYITEM:
                key = sorted(dict)[0]
            try:
                del dict[key]
                if not dict:
                    del self[attr]
            except KeyError:
                pass

    @property
    def mp3frames(self):
        if self.hasmp3:
            self.fp.seek(self.mp3start, os.SEEK_SET)
            hsize = self.uint32be.size
            size = 0
            while True:
                head = self.fp.read(hsize)
                try:
                    flen = self.mp3framelen(head)
                    frame = head + self.fp.read(flen - hsize)
                    size += len(frame)
                    yield frame
                except Errors:
                    break
            self.mp3end = self.mp3start + size

    def decode(self):
        try:
            self.decode_id3v1()
        except Errors:
            pass
        try:
            self.decode_id3v2()
        except Errors:
            pass
        self.decode_mp3()

    def decode_id3v1(self):
        try:
            self.fp.seek(self.id3v1.size * -1, os.SEEK_END)
            tag = self.unpack(self.id3v1)
            if tag[0] != 'TAG':
                raise DecodeError('no id3v1 tag')
            self.hasid3v1 = True
            self.id3v1end = self.fp.tell()
            self.id3v1start = self.id3v1end - self.id3v1.size
            try:
                self.name, self.artist, self.album, self.year = tag[1:5]
            except ValidationError:
                pass
            if tag[5][28] == '\x00' and tag[5][29] != '\x00':
                self.comment = tag[5][:28]
                self.track = ord(tag[5][29])
            else:
                try:
                    comment, track = self.track_re.search(tag[5]).groups()
                    self.comment = comment
                    self.track = ord(track)
                except AttributeError:
                    self.comment = tag[5]
            self.genre = tag[6]
        except Errors:
            self.hasid3v1 = False
            self.id3v1start = None
            self.id3v1end = None
            raise

    def decode_id3v2(self, pos=None):
        if pos is None:
            pos = 0
        try:
            self.fp.seek(pos, os.SEEK_SET)
            head = self.unpack(self.id3v2head)
            if head[0] != 'ID3':
                raise DecodeError('no id3v2 tag')
            try:
                opts = ID3V2_OPTS[head[1]]
            except KeyError:
                raise DecodeError('unknown version: %d' % head[1])
            self.hasid3v2 = True
            self.id3v2start = pos
            tagsize = self.getint(head[4], syncsafe=True)
            self.id3v2end = pos + self.id3v2head.size + tagsize
            self.id3v2version = head[1]
            while tagsize >= opts['head'].size:
                tag, size, flags = self.unpack(opts['head'])
                if not self.tag_re.search(tag):
                    break
                size = self.getint(size, opts['syncsafe'])
                tagsize -= (opts['head'].size + size)
                val = self.fp.read(size)
                try:
                    attr = ID3V2_TAGS[tag]
                except KeyError:
                    tags = self.__dict__.setdefault('_unknown', {})
                    tags.setdefault(tag, []).append(val)
                    continue
                type = self.types[attr]
                if type in (BOOL, GENRE, TEXT, UINT16, UINT16X2, UINT32):
                    val = self.getstr(val)
                    if not val:
                        continue
                if type == DICT:
                    ebyte, val, encoding, term = self.getenc(val)
                    lang = val[:3]
                    key, val = self.splitstr(val[3:], term, offset=1)
                    try:
                        getattr(self, 'set' + attr)(
                                self.getstr(ebyte + val),
                                self.getstr(ebyte + key), lang)
                    except ValidationError:
                        pass
                    continue
                elif type == GENRE:
                    try:
                        val = int(self.genre_re.search(val).group(1))
                    except AttributeError:
                        pass
                elif type == IDICT:
                    ebyte, val, encoding, term = self.getenc(val)
                    if tag == 'PIC':
                        val = val[3:]
                    else:
                        val = self.splitstr(val, offset=1)[1]
                    ptype = ord(val[0])
                    key, val = self.splitstr(val[1:], term, offset=1)
                    try:
                        self.set_image(StringIO(val),
                                       self.getstr(ebyte + key), ptype)
                    except ValidationError:
                        pass
                    continue
                elif type == VOLUME:
                    if tag == 'RVA2':
                        val = self.splitstr(val, offset=1)[1][1:3]
                        val = self.int16be.unpack(val)[0] / 512.0
                        val = 100 * (10 ** (val / 20) - 1)
                    else:
                        incdec, bits = ord(val[0]), ord(val[1])
                        i = int ((bits + 7) / 8)
                        j = i + 2
                        radj = self.getint(val[2:j])
                        ladj = self.getint(val[j:j + i])
                        if not incdec & 1:
                            radj *= -1
                        if not incdec & 2:
                            ladj *= -1
                        val = (ladj + radj) / 2.0 / ((1 << bits) - 1) * 100
                try:
                    self[attr] = val
                except ValidationError:
                    pass
        except Errors:
            self.hasid3v2 = False
            self.id3v2start = None
            self.id3v2end = None
            self.id3v2version = None
            raise

    def decode_mp3(self, pos=None, samplesize=None):
        if pos is None:
            pos = self.id3v2end
            if pos is None:
                pos = 0
        if samplesize is None:
            samplesize = MP3_SAMPLESIZE
        try:
            self.fp.seek(pos, os.SEEK_SET)
            sample = self.fp.read(samplesize)
            i = 0
            while True:
                i = sample.find('\xff', i)
                if i == -1:
                    raise DecodeError('no mp3 frame found')
                try:
                    j = i + self.mp3framelen(sample[i:i + self.uint32be.size])
                    self.mp3framelen(sample[j:j + self.uint32be.size])
                    self.hasmp3 = True
                    self.mp3start = pos + i
                    self.mp3end = None
                    break
                except Errors:
                    pass
                i += 1
        except Errors:
            self.hasmp3 = False
            self.mp3start = None
            self.mp3end = None
            raise

    def encode(self, fp, inplace=False, version=None, unknown=False,
               padding=None, doid3v1=True, doid3v2=True, domp3=True,
               fakemp3=False):
        if inplace and not self.hasid3v2:
            doid3v2 = False
        if doid3v2:
            self.encode_id3v2(fp, inplace, version, unknown, padding, doid3v2)
        if domp3 and not inplace:
            if fakemp3:
                fp.write(self.fakemp3)
            elif self.hasmp3:
                for frame in self.mp3frames:
                    fp.write(frame)
        if doid3v1:
            self.encode_id3v1(fp, inplace)

    def encode_id3v1(self, fp, inplace):
        for attr in ID3V1_ATTRS:
            if self[attr]:
                haveid3v1 = True
                break
        else:
            haveid3v1 = False

        id3v1pos = None
        if inplace:
            if self.hasid3v1:
                id3v1pos = self.id3v1.size * -1
            elif haveid3v1:
                id3v1pos = 0
        elif haveid3v1:
            id3v1pos = 0
        if id3v1pos is None:
            return
        elif inplace:
            fp.seek(id3v1pos, os.SEEK_END)

        if self.track and self.track[0] and self.track[0] < 256:
            comment = self.pad(self.comment, 28) + '\x00' + chr(self.track[0])
        else:
            comment = self.pad(self.comment)
        try:
            genre = GENRES.index(self.genre)
        except ValueError:
            genre = 255
        tag = self.id3v1.pack('TAG', self.pad(self.name),
                              self.pad(self.artist), self.pad(self.album),
                              self.pad(self.year, 4), comment, genre)
        fp.write(tag)

    def encode_id3v2(self, fp, inplace, version, unknown, padding, doid3v2):
        if version is None:
            version = self.id3v2version
            if version is None:
                version = DEFAULT_ID3V2_VERSION
        try:
            opts = ID3V2_OPTS[version]
        except KeyError:
            raise EncodeError('unknown version: %d' % version)
        if not self._unknown:
            unknown = False
        if unknown and version != self.id3v2version:
            raise EncodeError("can't change version and keep unknown")
        head = opts['head'].unpack('\x00' * opts['head'].size)
        ssize = len(head[1]) * -1
        flags = head[2]
        frames = []
        for tag, val in self.id3v2frames(opts, unknown):
            size = self.getbytes(len(val), opts['syncsafe'])[ssize:]
            frames += [tag, size, flags, val]
        data = ''.join(frames)
        size = len(data)
        if inplace:
            padding = (self.id3v2end - self.id3v2start -
                       size - self.id3v2head.size)
            if padding < 0:
                raise EncodeError('no room for id3v2 tag')
            fp.seek(self.id3v2start, os.SEEK_SET)
        else:
            if not size:
                return
            if padding is None:
                padding = DEFAULT_ID3V2_PADDING
        size += padding
        fp.write(self.id3v2head.pack('ID3', version, 0, 0,
                                     self.getbytes(size, syncsafe=True)))
        fp.write(data)
        fp.write('\x00' * padding)

    def id3v2frames(self, opts, unknown=False):
        for tag, attr in opts['tags'].iteritems():
            val = self[attr]
            if not val:
                continue
            type = self.types[attr]
            if type == BOOL:
                val = u'1'
            elif type == DICT:
                for key, val in val.iteritems():
                    lang, key = key
                    key2, val2 = self.mkstr(key), self.mkstr(val, term=False)
                    if key2[0] == val2[0]:
                        key, val = key2, val2
                    elif key2[0] == '\x01':
                        key, val = key2, self.mkstr(val, utf16=True, term=False)
                    else:
                        key, val = self.mkstr(key, utf16=True), val2
                    yield tag, key[0] + lang + key[1:] + val[1:]
                continue
            elif type == GENRE:
                try:
                    val = u'(%d)' % GENRES.index(val)
                except ValueError:
                    pass
            elif type == IDICT:
                for key, val in val.iteritems():
                    key = self.mkstr(key[0])
                    image, ptype = val
                    if tag == 'PIC':
                        if image.format == 'JPEG':
                            fmt = 'JPG'
                        else:
                            fmt = image.format[:3]
                    else:
                        fmt = 'image/%s\x00' % image.format.lower()
                    val = StringIO()
                    image.save(val, image.format)
                    yield tag, (key[0] + fmt + chr(ptype) +
                                key[1:] + val.getvalue())
                continue
            elif type == UINT16:
                val = unicode(val)
            elif type == UINT16X2:
                val = u'%d/%d' % tuple(val)
            elif type == VOLUME:
                if tag == 'RVA2':
                    val = self.int16be.pack(
                            int(log(val / 100 + 1, 10) * 0x2800))
                    val = '\x00\x01%s%s\x00' % (val, val)
                else:
                    if val < 0:
                        incdec = '\x00'
                        val *= -1
                    else:
                        incdec = '\x03'
                    val = '%s\x10%s\x00\x00\x00\x00' % (
                            incdec,
                            self.uint16be.pack(int(val / 100 * 0xffff)) * 2)
            if isinstance(val, unicode):
                val = self.mkstr(val, term=False)
            if isinstance(val, str):
                yield tag, val

    @staticmethod
    def pad(val, size=30):
        if val is None:
            val = ''
        elif isinstance(val, unicode):
            val = val.encode('ascii', 'ignore').strip()
        elif not isinstance(val, str):
            val = str(val)
        val = val[:size]
        return val + '\x00' * (size - len(val))

    @staticmethod
    def splitstr(val, term='\x00', offset=0):
        end = len(val)
        tsize = len(term)
        i = 0
        while i < end:
            j = val.find(term, i)
            if j == i:
                break
            if j == -1:
                i = end
            else:
                i = j + j % tsize
        i += offset * tsize
        return val[:i], val[i:]

    @classmethod
    def getint(cls, bytes, syncsafe=False):
        val = cls.uint32be.unpack(
                '\x00' * (cls.uint32be.size - len(bytes)) + bytes)[0]
        if syncsafe:
            return (((val & 0x0000007f) >> 0) | ((val & 0x00007f00) >> 1) |
                    ((val & 0x007f0000) >> 2) | ((val & 0x7f000000) >> 3) )
        return val

    @classmethod
    def getbytes(cls, val, syncsafe=False):
        bytes = cls.uint32be.pack(val)
        if syncsafe:
            vals = cls.longbytes.unpack(bytes)
            bytes = cls.longbytes.pack(
                    ((vals[1] >> 5) & 0x07) | (vals[0] << 3) & 0x7f,
                    ((vals[2] >> 6) & 0x03) | (vals[1] << 2) & 0x7f,
                    ((vals[3] >> 7) & 0x01) | (vals[2] << 1) & 0x7f,
                    ((vals[3] >> 0) & 0x7f))
        return bytes

    @classmethod
    def getstr(cls, val):
        ebyte, val, encoding, term = cls.getenc(val)
        return cls.splitstr(val, term)[0].decode(encoding, 'ignore')

    @staticmethod
    def mkstr(val, utf16=False, term=True):
        if val is None:
            val = u''
        elif isinstance(val, bool):
            val = u'1' if val else u'0'
        if not utf16:
            try:
                val = '\x00' + val.encode('latin-1')
                if term:
                    val += '\x00'
                return val
            except UnicodeEncodeError:
                pass
        val = '\x01\xff\xfe' + val.encode('utf-16-le')
        if term:
            val += '\x00\x00'
        return val

    @staticmethod
    def getenc(val):
        try:
            ebyte = val[0]
            encoding, term = ID3V2_ENCODINGS[ebyte]
            return ebyte, val[1:], encoding, term
        except (IndexError, KeyError):
            return '', val, 'ascii', '\x00'

    @classmethod
    def mp3framelen(cls, bytes):
        frame = cls.decode_mp3frame(cls.uint32be.unpack(bytes)[0])
        if (not frame.sync or frame.version == 1 or frame.layer == 4 or
            frame.bitrate in (-1, 14) or frame.srate == 3):
            raise DecodeError('invalid frame')
        bitrate = MP3_BITRATES[
                (3 if frame.layer == 1 else 4) if frame.v2
                else (frame.layer - 1)][frame.bitrate]
        srate = MP3_SRATES[frame.version][frame.srate]
        if frame.layer == 1:
            return (bitrate * 12000 / srate + frame.padding) << 2
        else:
            if frame.layer == 3 and frame.version in (0, 2):
                srate = srate << 1
            return bitrate * 144000 / srate + frame.padding

    @classmethod
    def decode_mp3frame(cls, val):
        frame = MP3Frame()
        frame.sync = val & 0xffe00000 == 0xffe00000
        frame.version = (val >> 0x13) & 0x03
        frame.v2 = not (frame.version & 0x01)
        frame.layer = 4 - ((val >> 0x11) & 0x03)
        frame.protected = not (val >> 0x10) & 0x01
        frame.bitrate = ((val >> 0x0c) & 0x0f) - 1
        frame.srate = (val >> 0x0a) & 0x03
        frame.padding = (val >> 0x09) & 0x01
        frame.private = bool((val >> 0x08) & 0x01)
        frame.mode = (val >> 0x06) & 0x03
        frame.ext = (val >> 0x04) & 0x03
        frame.copyright = bool((val >> 0x03) & 0x01)
        frame.original = bool((val >> 0x02) & 0x01)
        frame.emphasis = val & 0x03
        return frame


class IFF(MP3):

    format = 'iff'
    editable = True

    riff = Struct('< 4s L')
    aiff = Struct('> 4s L')

    def decode(self, pos=None, end=None, fmt=None):
        try:
            self.decode_id3v1()
        except Errors:
            pass
        if pos is None:
            pos = 0
        if end is None:
            self.fp.seek(0, os.SEEK_END)
            end = self.fp.tell()
        while pos < end:
            self.fp.seek(pos, os.SEEK_SET)
            if fmt is None:
                id = self.fp.read(4)
                if id == 'RIFF':
                    fmt = self.riff
                elif id in ('FORM', 'LIST', 'CAT '):
                    fmt = self.aiff
                else:
                    raise DecodeError('not an IFF file')
                continue
            id, size = self.unpack(fmt)
            pos += fmt.size
            if id in ('RIFF', 'FORM', 'LIST', 'CAT '):
                self.decode(pos + 4, pos + size, fmt)
            elif id in IFFIDS:
                try:
                    self[IFFIDS[id]] = self.fp.read(size)
                except ValidationError:
                    pass
            elif id == 'ID3 ':
                try:
                    self.decode_id3v2(pos)
                except Errors:
                    pass
            elif id == 'data':
                try:
                    self.decode_mp3(pos)
                except Errors:
                    pass
            pos += size + size % 2


class M4A(Decoder):

    format = 'm4a'
    editable = False

    head = Struct('> L 4s')
    uint16bex2 = Struct('> 2H')

    def decode(self, pos=None, end=None, base=None, ftyp=False):
        if pos is None:
            pos = self.fp.tell()
        if end is None:
            self.fp.seek(0, os.SEEK_END)
            end = self.fp.tell()
        if base is None:
            base = []
        while pos < end:
            self.fp.seek(pos, os.SEEK_SET)
            size, id = self.unpack(self.head)
            path = base + [id]
            tag = '.'.join(path)
            if not ftyp:
                if tag != 'ftyp':
                    raise DecodeError('not an mpeg4')
                ftyp = True
            atom, attr = ATOMS.get(tag, (None, None))
            if atom == ATOM_NODE1:
                self.decode(pos + 8, pos + size, path, ftyp)
            elif atom == ATOM_NODE2:
                self.decode(pos + 12, pos + size, path, ftyp)
            elif atom == ATOM_DATA:
                self.fp.seek(pos + 24)
                val = self.fp.read(size - 24)
                type = self.types[attr]
                if type == BOOL:
                    val = ord(val)
                elif type == GENRE:
                    if tag == 'moov.udta.meta.ilst.gnre':
                        val = self.uint16be.unpack(val)[0] - 1
                    else:
                        val = val.decode('utf-8', 'ignore')
                elif type == IMAGE:
                    val = StringIO(val)
                elif type == TEXT:
                    val = val.decode('utf-8', 'ignore')
                elif type == UINT16:
                    if tag == 'moov.udta.meta.ilst.tmpo':
                        val = self.uint16be.unpack(val)[0]
                elif type == UINT16X2:
                    val = self.uint16bex2.unpack(val[2:6])
                elif type == UINT32:
                    val = self.uint32be.unpack(val)[0]
                try:
                    self[attr] = val
                except ValidationError:
                    pass
            if not size:
                break
            pos += size


class Vorbis(Decoder):

    def decode(self):
        self.encoder = self.getstr()
        for i in xrange(self.getint()):
            tag, val = self.getstr().split('=', 1)
            try:
                attr = VORBISTAGS[tag.lower().strip()]
            except KeyError:
                continue
            try:
                self[attr] = val
            except ValidationError:
                pass

    def getint(self):
        return self.unpack(self.uint32le)

    def getstr(self):
        return self.fp.read(self.getint()).decode('utf-8', 'ignore')


class FLAC(Vorbis):

    format = 'flac'

    head = Struct('B 3s')

    def decode(self):
        self.fp.seek(0, os.SEEK_SET)
        if self.fp.read(4) != 'fLaC':
            raise DecodeError('not a flac file')
        pos = 4
        self.fp.seek(0, os.SEEK_END)
        end = self.fp.tell()
        while pos < end:
            self.fp.seek(pos, os.SEEK_SET)
            head, size = self.unpack(self.head)
            pos += self.head.size
            size = self.uint32be.unpack('\x00' + size)[0]
            if head & 127 == 4:
                super(FLAC, self).decode()
            if head & 128:
                break
            pos += size


class OGG(Vorbis):

    format = 'ogg'

    page = Struct('> 4s 2B Q 3L B')

    def decode(self):
        self.fp.seek(0, os.SEEK_END)
        end = self.fp.tell()
        pos = 0
        while pos < end:
            self.fp.seek(pos, os.SEEK_SET)
            page = self.unpack(self.page)
            if page[0] != 'OggS':
                raise DecodeError('not an ogg page')
            size = sum(ord(i) for i in self.fp.read(page[7]))
            if self.fp.read(7) == '\x03vorbis':
                super(OGG, self).decode()
            pos += self.page.size + page[7] + size


def tagopen(file, readonly=False):
    if readonly is None:
        readonly = DEFAULT_READONLY
    for cls in Decoders:
        try:
            tag = cls(file)
        except InvalidMedia:
            continue
        if readonly:
            return Metadata(tag)
        return tag
    raise InvalidMedia('no suitable decoder found')


Errors = TaglibError, StructError, IOError, OSError, EOFError
Decoders = FLAC, M4A, OGG, IFF, MP3
