# All rights reserved.
#
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

from struct import Struct, error as StructError
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

__version__ = '2.1'
__author__ = 'Chris Jones <cjones@gruntle.org>'
__all__ = ['tagopen', 'InvalidMedia', 'ValidationError']

SAMPLESIZE = 1024
GAPLESS = u'iTunPGAP'
ANYITEM = -1
DEFAULT_ID3V2_VERSION = 2
DEFAULT_ID3V2_PADDING = 0
ENCODING = sys.getfilesystemencoding()

TYPES = {'_comment': 'DICT',
         '_image': 'IDICT',
         '_lyrics': 'DICT',
         '_unknown': 'DICT',
         'album': 'TEXT',
         'album_artist': 'TEXT',
         'artist': 'TEXT',
         'bpm': 'UINT16',
         'comment': 'TEXT',
         'compilation': 'BOOL',
         'composer': 'TEXT',
         'disk': 'UINT16X2',
         'encoder': 'TEXT',
         'gapless': 'BOOL',
         'genre': 'GENRE',
         'grouping': 'TEXT',
         'image': 'IMAGE',
         'lyrics': 'TEXT',
         'name': 'TEXT',
         'sort_album': 'TEXT',
         'sort_album_artist': 'TEXT',
         'sort_artist': 'TEXT',
         'sort_composer': 'TEXT',
         'sort_name': 'TEXT',
         'sort_video_show': 'TEXT',
         'track': 'UINT16X2',
         'video_description': 'TEXT',
         'video_episode': 'UINT32',
         'video_episode_id': 'TEXT',
         'video_season': 'UINT32',
         'video_show': 'TEXT',
         'volume': 'VOLUME',
         'year': 'UINT16'}

BOOLS = {False: ['no', 'off', '0', 'false', 'n', 'f', '\x00'],
         True: ['yes', 'on', '1', 'true', 'y', 't', '\x01']}

ID3V2OPTS = {2: {'frame': Struct('3s3s0s'),
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
             3: {'frame': Struct('4s4s2s'),
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
                          'TSOC': 'sort_composer',
                          'TYER': 'year',
                          'USLT': '_lyrics'}},
             4: {'frame': Struct('4s4s2s'),
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

ID3V2TAGS = dict((tag, attr) for opts in ID3V2OPTS.itervalues()
                 for tag, attr in opts['tags'].iteritems())

ENCODINGS = {'\x00': ('latin-1', '\x00'),
             '\x01': ('utf-16', '\x00\x00'),
             '\x02': ('utf-16-be', '\x00\x00'),
             '\x03': ('utf-8', '\x00')}

BITRATES = [
    [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0],
    [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
    [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
    [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
    [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]]

SRATES = [[11025, 12000, 8000, 0], [0, 0, 0, 0],
          [22050, 24000, 16000, 0], [44100, 48000, 32000, 0]]

ID3V1FIELDS = ['name', 'artist', 'album', 'year', 'comment', 'track', 'genre']

ATOMS = {'moov': ('CONTAINER1', None),
         'moov.udta': ('CONTAINER1', None),
         'moov.udta.meta': ('CONTAINER2', None),
         'moov.udta.meta.ilst': ('CONTAINER1', None),
         'moov.udta.meta.ilst.aART': ('DATA', 'album_artist'),
         'moov.udta.meta.ilst.covr': ('DATA', 'image'),
         'moov.udta.meta.ilst.cpil': ('DATA', 'compilation'),
         'moov.udta.meta.ilst.desc': ('DATA', 'video_description'),
         'moov.udta.meta.ilst.disk': ('DATA', 'disk'),
         'moov.udta.meta.ilst.gnre': ('DATA', 'genre'),
         'moov.udta.meta.ilst.pgap': ('DATA', 'gapless'),
         'moov.udta.meta.ilst.soaa': ('DATA', 'sort_album_artist'),
         'moov.udta.meta.ilst.soal': ('DATA', 'sort_album'),
         'moov.udta.meta.ilst.soar': ('DATA', 'sort_artist'),
         'moov.udta.meta.ilst.soco': ('DATA', 'sort_composer'),
         'moov.udta.meta.ilst.sonm': ('DATA', 'sort_name'),
         'moov.udta.meta.ilst.sosn': ('DATA', 'sort_video_show'),
         'moov.udta.meta.ilst.tmpo': ('DATA', 'bpm'),
         'moov.udta.meta.ilst.trkn': ('DATA', 'track'),
         'moov.udta.meta.ilst.tven': ('DATA', 'video_episode_id'),
         'moov.udta.meta.ilst.tves': ('DATA', 'video_episode'),
         'moov.udta.meta.ilst.tvsh': ('DATA', 'video_show'),
         'moov.udta.meta.ilst.tvsn': ('DATA', 'video_season'),
         'moov.udta.meta.ilst.\xa9ART': ('DATA', 'artist'),
         'moov.udta.meta.ilst.\xa9alb': ('DATA', 'album'),
         'moov.udta.meta.ilst.\xa9cmt': ('DATA', 'comment'),
         'moov.udta.meta.ilst.\xa9day': ('DATA', 'year'),
         'moov.udta.meta.ilst.\xa9gen': ('DATA', 'genre'),
         'moov.udta.meta.ilst.\xa9grp': ('DATA', 'grouping'),
         'moov.udta.meta.ilst.\xa9lyr': ('DATA', 'lyrics'),
         'moov.udta.meta.ilst.\xa9nam': ('DATA', 'name'),
         'moov.udta.meta.ilst.\xa9too': ('DATA', 'encoder'),
         'moov.udta.meta.ilst.\xa9wrt': ('DATA', 'composer')}

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
              'vol': 'volume',
              'vol_adj': 'volume',
              'voladj': 'volume',
              'volume': 'volume',
              'volume_adj': 'volume',
              'volume_adjustment': 'volume',
              'volumeadj': 'volume',
              'volumeadjustment': 'volume',
              'year': 'year'}

IFFIDS = {'ANNO': 'comment',
          'AUTH': 'artist',
          'IART': 'artist',
          'ICMT': 'comment',
          'ICRD': 'year',
          'INAM': 'name',
          'NAME': 'name'}

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
          'JPop', 'Synthpop', None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None, None, None, None, None, None, None, None, None, None, None,
          None]

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


DecodeErrors = (IOError, OSError, EOFError, StructError,
                ValidationError, DecodeError)


class Container(MutableMapping):

    types = {}

    def __init__(self, *args, **kwargs):
        self.__dict__.update(dict(*args, **kwargs))

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
        val = self._validate(attr, val)
        super(Container, self).__setattr__(attr, val)

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
                if not attr.startswith('_') and self[attr])

    def __len__(self):
        return sum(1 for attr in self.__iter__())

    def __repr__(self):
        attrs = ', '.join('%s=%r' % item for item in self.iteritems())
        return '<%s object at 0x%x%s%s>' % (
                type(self).__name__, id(self), ': ' if attrs else '', attrs)

    @classmethod
    def _validate(cls, attr, val=None):
        try:
            val = cls.validate(val, cls.types[attr])
        except KeyError:
            pass
        except ValidationError, error:
            raise ValidationError('%s: %s' % (attr, error))
        return val

    @staticmethod
    def validate(val, type):
        return val


class Metadata(Container):

    types = TYPES

    @property
    def image_sample(self):
        if self.image:
            val = StringIO()
            self.image.save(val, self.image.format)
            val.seek(0, os.SEEK_SET)
            return val.read(512), self.image.format, self.image.size

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
                    type = 'TEXT'
                else:
                    val = self[attr]
                    type = self.types[attr]
                if not val:
                    continue
                if type == 'BOOL':
                    val = 'Yes'
                elif type in ('GENRE', 'TEXT'):
                    val = val.encode(encoding, 'ignore')
                elif type == 'IMAGE':
                    val = '%dx%d %s Image' % (val.size[0], val.size[1],
                                              val.format)
                elif type in ('UINT16', 'UINT32'):
                    val = str(val)
                elif type == 'UINT16X2':
                    val = ('%d/%d' % tuple(val)).replace('/0', '')
                elif type == 'VOLUME':
                    val = '%.1f' % val
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

    def __eq__(self, other):
        if not isinstance(other, Metadata):
            return NotImplemented
        try:
            self.compare(self, other)
        except ValidationError:
            return False
        return True

    def __ne__(self, other):
        val = self.__eq__(other)
        if val is NotImplemented:
            return val
        return not val

    @staticmethod
    def validate(val, type):
        raise ValidationError('metadata is read-only')

    @staticmethod
    def compare(src, dst):
        for attr, type in TYPES.iteritems():
            if attr.startswith('_'):
                continue
            if type == 'IMAGE':
                val1, val2 = src.image_sample, dst.image_sample
            else:
                val1, val2 = src[attr], dst[attr]
            if val1 != val2:
                raise ValidationError('%s: %r != %r' % (attr, val1, val2))


class Open(object):

    def __init__(self, file, mode='rb', close=True):
        self.file = file
        self.mode = mode
        self.close = close
        self.fp = None
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
            raise TypeError('file must be a path, descriptor, or open file')
        if self.external:
            self.pos = self.fp.tell()
        return self.fp

    def __exit__(self, *args):
        if self.external:
            self.fp.seek(self.pos, os.SEEK_SET)
        elif self.close:
            self.fp.close()


class Decoder(Metadata):

    format = None
    editable = False

    genre_re = re.compile(r'^\((\d+)\)$')

    uint32be = Struct('>L')
    int16be = Struct('>h')
    uint16be = Struct('>H')
    longbytes = Struct('4B')

    def __init__(self, file):
        if self.editable:
            close = False
            mode = 'rb+'
        else:
            close = True
            mode = 'rb'
        with Open(file, mode, close) as fp:
            self.fp = fp
            try:
                self.decode()
            except DecodeErrors, error:
                raise InvalidMedia(error)
        self.changed = False

    def decode(self):
        raise DecodeError('no decoder implemented')

    def save(self):
        raise EncodeError('encoder not implemented')

    def dump(self, file):
        raise EncodeError('encoder not implemented')

    def dumps(self):
        raise EncodeError('encoder not implemented')

    def __setattr__(self, attr, val):
        super(Decoder, self).__setattr__(attr, val)
        if attr in self.types:
            self.changed = True

    def __delattr__(self, attr):
        super(Decoder, self).__delattr__(attr)
        if attr in self.types:
            self.changed = True

    @classmethod
    def validate(cls, val, type):
        if val is not None:
            if type == 'GENRE':
                if isinstance(val, (int, long)):
                    if val < 0 or val > 0xff:
                        raise ValidationError('out of range')
                    val = GENRES[val]
                type = 'TEXT'
            elif type in ('UINT16', 'UINT32'):
                if isinstance(val, basestring):
                    try:
                        val = int(val)
                    except ValueError, error:
                        raise ValidationError(error)
                elif not isinstance(val, (int, long)):
                    raise ValidationError('must be a numeric value')
            if type in ('DICT', 'IDICT'):
                if not isinstance(val, dict):
                    raise ValidationError('must be a dictionary')
            elif type == 'BOOL':
                if isinstance(val, basestring):
                    if isinstance(val, unicode):
                        val = val.encode('ascii', 'ignore').strip()
                    val = val.lower().strip()
                    for result, vals in BOOLS.iteritems():
                        if val in vals:
                            val = result
                            break
                    else:
                        raise ValidationError('invalid boolean string')
                elif isinstance(val, (int, long)):
                    val = bool(val)
                elif not isinstance(val, bool):
                    raise ValidationError('invalid boolean')
            elif type == 'IMAGE':
                if not PIL:
                    raise ValidationError('must install PIL for image support')
                if not isinstance(val, ImageFile):
                    try:
                        with Open(val, 'rb') as fp:
                            val = Image.open(fp)
                            val.load()
                    except (IOError, TypeError), error:
                        raise ValidationError(error)
            elif type == 'VOLUME':
                if isinstance(val, basestring):
                    try:
                        val = float(val)
                    except ValueError, error:
                        raise ValidationError(error)
                elif isinstance(val, (int, long)):
                    val = float(val)
                elif not isinstance(val, float):
                    raise ValidationError('must be a float value')
                if val < -99.9:
                    val = -99.9
                if val > 100.0:
                    val = 100.0
            elif type == 'TEXT':
                if val:
                    if not isinstance(val, unicode):
                        if not isinstance(val, str):
                            val = str(val)
                        val = val.decode('ascii', 'ignore')
                    val = cls.unpad(val)
            elif type == 'UINT16':
                if val < 0 or val > 0xffff:
                    raise ValidationError('out of range of uint16')
            elif type == 'UINT32':
                if val < 0 or val > 0xffffffff:
                    raise ValidationError('out of range of uint32')
            elif type == 'UINT16X2':
                if isinstance(val, basestring):
                    val = [int(i) if i.isdigit() else 0 for i in val.split('/')]
                elif isinstance(val, (int, long)):
                    val = val, 0
                if isinstance(val, tuple):
                    val = list(val)
                elif not isinstance(val, list):
                    raise ValidationError('must be a sequence of start/end')
                if len(val) == 1:
                    val.append(0)
                elif len(val) != 2:
                    raise ValidationError('must be a sequence of start/end')
                if val[0] < 0:
                    val[0] = 0
                if val[1] < 0:
                    val[1] = 0
                if val[0] > 0xffff or val[1] > 0xffff:
                    raise ValidationError('must be in range of uint16')
                if val == [0, 0]:
                    val = None
            if type not in ('DICT', 'IDICT') and not val:
                val = None
        return val

    @staticmethod
    def unpad(val):
        val = list(val)
        while val and val[-1] in ' \x00':
            val.pop()
        return ''.join(val)


class MP3(Decoder):

    format = 'mp3'
    editable = True

    id3v1 = Struct('3s30s30s30s4s30sB')
    id3v2 = Struct('3s3B4s')

    tag_re = re.compile(r'^[A-Z0-9 ]{3,4}$')
    track_re = re.compile(r'^(.+)\x00 ([^\x00])$')

    fakemp3 = '\xff\xf2\x14\x00' * 13

    def __init__(self, file):
        self.hasid3v2 = False
        self.id3v2start = None
        self.id3v2end = None
        self.id3v2version = None

        self.hasmp3 = False
        self.mp3start = None

        self.hasid3v1 = False
        self.id3v1start = None
        self.id3v1end = None

        super(MP3, self).__init__(file)

    def get_gapless(self):
        return self.get_comment(GAPLESS)

    def set_gapless(self, val):
        self.set_comment(val, GAPLESS)

    def del_gapless(self):
        self.del_comment(GAPLESS)

    gapless = property(get_gapless, set_gapless, del_gapless)

    def get_comment(self, key=None, lang='eng'):
        if key != ANYITEM:
            key = lang, key
        return self.getdict('_comment', key)

    def set_comment(self, val, key=None, lang='eng'):
        if key == GAPLESS:
            val = self.validate(val, 'BOOL')
        else:
            val = self.validate(val, 'TEXT')
        self.setdict('_comment', (lang, key), val)

    def del_comment(self, key=None, lang='eng'):
        if key != ANYITEM:
            key = lang, key
        self.deldict('_comment', key)

    comment = property(get_comment, set_comment, del_comment)

    def get_lyrics(self, key=None, lang='eng'):
        if key != ANYITEM:
            key = lang, key
        return self.getdict('_lyrics', key)

    def set_lyrics(self, val, key=None, lang='eng'):
        if key == GAPLESS:
            val = self.validate(val, 'BOOL')
        else:
            val = self.validate(val, 'TEXT')
        self.setdict('_lyrics', (lang, key), val)

    def del_lyrics(self, key=None, lang='eng'):
        if key != ANYITEM:
            key = lang, key
        self.deldict('_lyrics', key)

    lyrics = property(get_lyrics, set_lyrics, del_lyrics)

    def get_image(self, key=ANYITEM):
        if key != ANYITEM:
            key = key,
        val = self.getdict('_image', key)
        if val:
            return val[0]

    def set_image(self, val, key=None, ptype=3):
        self.setdict('_image', (key,), (self.validate(val, 'IMAGE'), ptype))

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
            while True:
                head = self.fp.read(4)
                try:
                    yield head + self.fp.read(self.framelen(head) - 4)
                except DecodeErrors:
                    break

    def decode(self):
        try:
            self.decode_id3v1()
        except DecodeErrors:
            pass
        try:
            self.decode_id3v2()
        except DecodeErrors:
            pass
        try:
            if self.hasid3v2:
                pos = self.id3v2end
            else:
                pos = 0
            self.decode_mp3(pos)
        except DecodeErrors:
            pass
        if not self.hasid3v1 and not self.hasid3v2 and not self.hasmp3:
            raise DecodeError('no tags or mp3 data found')

    def decode_id3v2(self, pos=None):
        if pos is None:
            pos = 0
        try:
            self.fp.seek(pos, os.SEEK_SET)
            head = self.id3v2.unpack(self.fp.read(self.id3v2.size))
            if head[0] != 'ID3':
                raise DecodeError('no id3v2 tag')
            if head[1] not in ID3V2OPTS:
                raise DecodeError('unknown version: %d' % head[1])
            if head[2]:
                raise DecodeError('unknown revision: %d' % head[2])
            self.hasid3v2 = True
            self.id3v2start = pos
            self.id3v2version = head[1]
        except DecodeErrors:
            self.hasid3v2 = False
            self.id3v2start = None
            self.id3v2end = None
            self.id3v2version = None
            raise
        bytes_left = self.getint(head[4], syncsafe=True)
        self.id3v2end = self.fp.tell() + bytes_left
        frame = ID3V2OPTS[self.id3v2version]['frame']
        syncsafe = ID3V2OPTS[self.id3v2version]['syncsafe']
        while bytes_left > frame.size:
            try:
                tag, size, flags = frame.unpack(self.fp.read(frame.size))
                if not self.tag_re.search(tag):
                    break
                size = self.getint(size, syncsafe)
                val = self.fp.read(size)
                bytes_left -= (frame.size + size)
                if not val:
                    continue
                try:
                    attr = ID3V2TAGS[tag]
                except KeyError:
                    tags = self.getdict('_unknown', tag)
                    if not tags:
                        tags = []
                        self.setdict('_unknown', tag, tags)
                    tags.append(val)
                    continue
                type = self.types[attr]
                key = None
                if type in ('BOOL', 'GENRE', 'TEXT', 'UINT16', 'UINT16X2'):
                    val = self.getstr(val)
                if not val:
                    continue
                if type == 'DICT':
                    ebyte, val, encoding, term = self.splitenc(val)
                    lang = val[:3]
                    key, val = self.splitstr(val[3:], term, offset=1)
                    key = self.validate(self.getstr(ebyte + key), 'TEXT')
                    if key == GAPLESS:
                        val = self.validate(self.getstr(ebyte + val), 'BOOL')
                    else:
                        val = self.validate(self.getstr(ebyte + val), 'TEXT')
                    key = lang, key
                elif type == 'GENRE':
                    try:
                        val = int(self.genre_re.search(val).group(1))
                    except AttributeError:
                        pass
                elif type == 'IDICT':
                    ebyte, val, encoding, term = self.splitenc(val)
                    if tag == 'PIC':
                        val = val[3:]
                    else:
                        val = self.splitstr(val, offset=1)[1]
                    ptype = ord(val[0])
                    key, val = self.splitstr(val[1:], term, offset=1)
                    key = self.validate(self.getstr(ebyte + key), 'TEXT'),
                    val = self.validate(StringIO(val), 'IMAGE'), ptype
                elif type == 'VOLUME':
                    if tag == 'RVA2':
                        val = self.splitstr(val, offset=1)[1][1:3]
                        val = self.int16be.unpack(val)[0]
                        val = round(100 * (10 ** (val / 512.0 / 20) - 1), 1)
                    else:
                        pos, bits = ord(val[0]) & 1, ord(val[1])
                        val = self.getint(val[2:2 + int((bits + 7) / 8)])
                        val = round(float(val) / ((1 << bits) - 1) * 100, 1)
                        if not pos:
                            val *= -1
                if not val:
                    continue
                if key is None:
                    self[attr] = val
                else:
                    self.setdict(attr, key, val)
            except DecodeErrors:
                pass

    def decode_mp3(self, pos=None, samplesize=None):
        if pos is None:
            pos = self.fp.tell()
        if samplesize is None:
            samplesize = SAMPLESIZE
        try:
            self.mp3start = None
            self.fp.seek(pos, os.SEEK_SET)
            sample = self.fp.read(samplesize)
            size = self.uint32be.size
            i = 0
            while i < len(sample) - size + 1:
                i = sample.find('\xff', i)
                if i == -1:
                    break
                head = sample[i:i + size]
                try:
                    next = i + self.framelen(head)
                    self.framelen(sample[next:next + size])
                    self.mp3start = pos + i
                    self.hasmp3 = True
                    break
                except DecodeErrors:
                    i += 1
            if self.mp3start is None:
                raise DecodeError('no mp3 frames found')
            self.hasmp3 = True
        except DecodeErrors:
            self.hasmp3 = False
            self.mp3start = None
            raise

    def decode_id3v1(self):
        try:
            self.fp.seek(self.id3v1.size * -1, os.SEEK_END)
            self.id3v1start = self.fp.tell()
            tag = self.id3v1.unpack(self.fp.read(self.id3v1.size))
            if tag[0] != 'TAG':
                raise DecodeError('no id3v1 tag')
            self.hasid3v1 = True
            self.id3v1end = self.fp.tell()
        except DecodeErrors:
            self.hasid3v1 = False
            self.id3v1start = None
            self.id3v1end = None
            raise
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

    def save(self, version=None, unknown=False):
        if self.changed or (self.hasid3v2 and version != self.id3v2version):
            self.encode(self.fp, version=version, inplace=True, unknown=unknown)

    def dump(self, file=None, version=None, unknown=False, padding=None):
        if file is None:
            file = StringIO()
        with Open(file, 'wb') as fp:
            self.encode(fp, version, False, unknown, padding)
        if not fp.closed:
            return fp

    def dumps(self, version=None, unknown=False, padding=None):
        return self.dump(None, version, unknown, padding).getvalue()

    def encode(self, fp, version=None, inplace=False,
               unknown=False, padding=None):
        if version is None:
            version = self.id3v2version
        if version is None:
            version = DEFAULT_ID3V2_VERSION
        if version not in ID3V2OPTS:
            raise EncodeError('unknown version: %r' % version)
        if (unknown and self._unknown and
            self.hasid3v2 and version != self.id3v2version):
            raise EncodeError('cannot change id3v2 version and keep unknown')
        if padding is None:
            padding = DEFAULT_ID3V2_PADDING
        opts = ID3V2OPTS[version]
        frame, syncsafe, tags = opts['frame'], opts['syncsafe'], opts['tags']
        haveid3v1 = haveid3v2 = False
        for tag, attr in tags.iteritems():
            if self[attr]:
                haveid3v2 = True
                if attr in ID3V1FIELDS:
                    haveid3v1 = True
                    break
        id3v2pos = None
        if inplace:
            if haveid3v2:
                if self.hasid3v2:
                    id3v2pos = self.id3v2start
                else:
                    raise EncodeError("can't write new id3v2 tag")
            elif self.hasid3v2:
                id3v2pos = self.id3v2start
        elif haveid3v2:
            id3v2pos = fp.tell()
        if id3v2pos is not None:
            opts = ID3V2OPTS[version]
            sizes = opts['frame'].unpack('\x00' * frame.size)
            taglen, sizelen, flagslen = [len(i) for i in sizes]
            flags = '\x00' * flagslen
            fp.seek(id3v2pos, os.SEEK_SET)
            fp.write('\x00' * 10)
            if inplace:
                bytes_left = tagsize = self.id3v2end - self.id3v2start
                cache = []
            else:
                bytes_left = self.getint('\x7f\x7f\x7f\x7f', syncsafe=True)
                tagsize = 0
            bytes_left -= 10
            for tag, val in self.id3v2items(opts['tags'], unknown):
                if len(tag) != taglen:
                    raise EncodeError('unexpected tag size')
                size = self.getbytes(len(val), opts['syncsafe'])[sizelen * -1:]
                tag = frame.pack(tag, size, flags) + val
                size = len(tag)
                if size > bytes_left:
                    raise EncodeError('no room for id3v2 tag')
                bytes_left -= size
                if inplace:
                    cache.append(tag)
                else:
                    fp.write(tag)
                    tagsize += size
            if inplace:
                for tag in cache:
                    fp.write(tag)
                fp.write('\x00' * bytes_left)
            else:
                fp.write('\x00' * padding)
                tagsize += padding
            pos = fp.tell()
            fp.seek(id3v2pos, os.SEEK_SET)
            tagsize = self.getbytes(tagsize, syncsafe=True)
            fp.write(self.id3v2.pack('ID3', version, 0, 0, tagsize))
            fp.seek(pos, os.SEEK_SET)
            if inplace:
                self.id3v2version = version
        if self.hasmp3 and not inplace:
            for frame in self.mp3frames:
                fp.write(frame)
        id3v1pos = None
        if inplace:
            if self.hasid3v1:
                id3v1pos = self.id3v1.size * -1
            elif haveid3v1:
                id3v1pos = 0
        elif haveid3v1:
            id3v1pos = 0
        if id3v1pos is not None:
            tag = ['TAG', self.pad(self.name), self.pad(self.artist),
                   self.pad(self.album), self.pad(self.year, 4)]
            if self.track and self.track[0] and self.track[0] < 256:
                tag.append(self.pad(self.comment, 28) +
                           '\x00' + chr(self.track[0]))
            else:
                tag.append(self.pad(self.comment))
            if self.genre and self.genre in GENRES:
                tag.append(GENRES.index(self.genre))
            else:
                tag.append(255)
            fp.seek(id3v1pos, os.SEEK_END)
            fp.write(self.id3v1.pack(*tag))
            if inplace:
                self.hasid3v1 = True
                self.id3v1end = fp.tell()
                self.id3v1start = self.id3v1end - self.id3v1.size

    def id3v2items(self, tags, unknown=False):
        for tag, attr in tags.iteritems():
            val = self[attr]
            if not val:
                continue
            type = self.types[attr]
            if type == 'BOOL':
                val = u'1'
            elif type == 'DICT':
                for key, val in val.iteritems():
                    lang, key = key
                    if key == GAPLESS:
                        if not val:
                            continue
                        val = u'1'
                    key2 = self.mkstr(key)
                    val2 = self.mkstr(val, term=False)
                    if key2[0] == val2[0]:
                        key, val = key2, val2
                    elif key2[0] == '\x01':
                        key, val = key2, self.mkstr(val, utf16=True, term=False)
                    else:
                        key, val = self.mkstr(key, utf16=True), val2
                    yield tag, key[0] + lang + key[1:] + val[1:]
                continue
            elif type == 'GENRE':
                if val in GENRES:
                    val = u'(%d)' % GENRES.index(val)
            elif type == 'IDICT':
                for key, val in val.iteritems():
                    key = self.mkstr(key[0])
                    val, ptype = val
                    if tag == 'PIC':
                        if val.format == 'JPEG':
                            fmt = 'JPG'
                        else:
                            fmt = val.format[:3]
                    else:
                        fmt = 'image/%s\x00' % val.format.lower()
                    data = StringIO()
                    val.save(data, val.format)
                    val = key[0] + fmt + chr(ptype) + key[1:] + data.getvalue()
                    yield tag, val
                continue
            elif type == 'UINT16':
                val = unicode(val)
            elif type == 'UINT16X2':
                val = u'%d/%d' % tuple(val)
                val = val.replace('/0', '')
            elif type == 'VOLUME':
                if tag == 'RVA2':
                    val = int(round(log(val / 100.0 + 1, 10) * 20 * 512, 0))
                    val = '\x00\x01%s\x00' % self.int16be.pack(val)
                else:
                    if val < 0:
                        val = val * -1
                        dir = '\x00'
                    else:
                        dir = '\x03'
                    val = self.uint16be.pack(int(val / 100 * 0x10000 - 1))
                    val = dir + '\x10' + val * 2 + '\x00' * 4
            if isinstance(val, unicode):
                val = self.mkstr(val, term=False)
            yield tag, val
        if unknown and self._unknown:
            for tag, vals in self._unknown.iteritems():
                for val in vals:
                    yield tag, val

    @classmethod
    def getint(cls, bytes, syncsafe=False):
        val = '\x00' * (cls.uint32be.size - len(bytes)) + bytes
        val = cls.uint32be.unpack(val)[0]
        if syncsafe:
            val = (((val & 0x0000007f) >> 0) | ((val & 0x00007f00) >> 1) |
                   ((val & 0x007f0000) >> 2) | ((val & 0x7f000000) >> 3))
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
        ebyte, val, encoding, term = cls.splitenc(val)
        return cls.splitstr(val, term)[0].decode(encoding, 'ignore')

    @staticmethod
    def mkstr(val, utf16=False, term=True):
        if val is None:
            val = u''
        if not utf16:
            try:
                val = '\x00%s' % val.encode('latin-1')
                if term:
                    val += '\x00'
                return val
            except UnicodeEncodeError:
                pass
        val = '\x01\xff\xfe%s' % val.encode('utf-16-le')
        if term:
            val += '\x00\x00'
        return val

    @staticmethod
    def splitenc(val):
        try:
            ebyte = val[0]
            encoding, term = ENCODINGS[ebyte]
            return ebyte, val[1:], encoding, term
        except (KeyError, IndexError):
            return '', val, 'ascii', '\x00'

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
    def framelen(cls, head):
        head = cls.uint32be.unpack(head)[0]
        if head & 0xffe00000 != 0xffe00000:
            raise DecodeError('no frame sync')
        version = (head >> 0x13) & 0x03
        layer = (head >> 0x11) & 0x03
        version_idx = None
        if version == 3:
            if layer == 3:
                version_idx = 0
            elif layer == 2:
                version_idx = 1
            elif layer == 1:
                version_idx = 2
        elif version in (0, 2):
            if layer == 3:
                version_idx = 3
            elif layer in (1, 2):
                version_idx = 4
        if version_idx is None:
            raise DecodeError('invalid version/layer')
        bitrate = BITRATES[version_idx][(head >> 0x0c) & 0x0f] * 1000.0
        if not bitrate:
            raise DecodeError('invalid bitrate')
        srate = SRATES[version][(head >> 0x0a) & 0x03]
        if not srate:
            raise DecodeError('invalid sample rate')
        if layer == 3:
            return int((12 * bitrate / srate + ((head >> 0x09) & 0x01)) * 4)
        else:
            return int(144 * bitrate / srate + ((head >> 0x09) & 0x01))

    @staticmethod
    def pad(val, size=30):
        if val is None:
            val = ''
        elif isinstance(val, unicode):
            val = val.encode('ascii', 'ignore').strip()
        else:
            val = str(val)
        val = val[:size]
        return val + '\x00' * (size - len(val))


class IFF(MP3):

    format = 'iff'

    aiff = Struct('>4sL')
    riff = Struct('<4sL')

    def decode(self, pos=None, end=None, fmt=None):
        if pos is None:
            pos = 0
        if end is None:
            self.fp.seek(0, os.SEEK_END)
            end = self.fp.tell()
        try:
            self.decode_id3v1()
        except DecodeErrors:
            pass
        while pos < end:
            self.fp.seek(pos, os.SEEK_SET)
            if fmt is None:
                id = self.fp.read(4)
                if id in ('FORM', 'CAT ', 'LIST'):
                    fmt = self.aiff
                elif id == 'RIFF':
                    fmt = self.riff
                else:
                    raise DecodeError('not an iff file')
                self.fp.seek(pos, os.SEEK_SET)
            id, size = fmt.unpack(self.fp.read(fmt.size))
            pos += fmt.size
            if id in ('FORM', 'CAT ', 'LIST', 'RIFF'):
                self.decode(pos + 4, pos + size, fmt)
            elif id in IFFIDS:
                val = self.unpad(self.fp.read(size).decode('utf-8', 'ignore'))
                try:
                    self[IFFIDS[id]] = val
                except ValidationError:
                    pass
            elif id == 'data':
                try:
                    self.decode_mp3()
                except DecodeErrors:
                    pass
            elif id == 'ID3 ':
                try:
                    self.decode_id3v2(self.fp.tell())
                except DecodeErrors:
                    pass
            pos += size + size % 2


class M4A(Decoder):

    format = 'm4a'

    head = Struct('>L4s')
    uint16x2 = Struct('>2H')

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
            size, name = self.head.unpack(self.fp.read(self.head.size))
            path = base + [name]
            tag = '.'.join(path)
            if not ftyp:
                if tag != 'ftyp':
                    raise DecodeError('not an mpeg4 file')
                ftyp = True
            atom, attr = ATOMS.get(tag, (None, None))
            if atom == 'CONTAINER1':
                self.decode(pos + 8, pos + size, path, ftyp)
            elif atom == 'CONTAINER2':
                self.decode(pos + 12, pos + size, path, ftyp)
            elif atom == 'DATA':
                self.fp.seek(pos + 24)
                val = self.fp.read(size - 24)
                type = self.types[attr]
                if type in ('GENRE', 'TEXT'):
                    if name == 'gnre':
                        val = GENRES[self.uint16be.unpack(val)[0] - 1]
                    else:
                        val = val.decode('utf-8')
                elif type == 'IMAGE':
                    val = StringIO(val)
                elif type == 'UINT16':
                    if name == 'tmpo':
                        val = self.uint16be.unpack(val)[0]
                elif type == 'UINT16X2':
                    val = self.uint16x2.unpack(val[2:6])
                elif type == 'UINT32':
                    val = self.uint32be.unpack(val)[0]
                try:
                    self[attr] = val
                except ValidationError:
                    pass
            if not size:
                break
            pos += size


class Vorbis(Decoder):

    format = 'vorbis'

    uint32le = Struct('<L')

    def decode(self):
        self.encoder = self.getstr()
        for i in xrange(self.getint()):
            key, val = self.getstr().split('=', 1)
            try:
                attr = VORBISTAGS[key.lower()]
            except KeyError:
                continue
            if self.types[attr] == 'GENRE':
                if val.isdigit():
                    val = int(val)
                else:
                    try:
                        val = int(self.genre_re.search(val).group(1))
                    except AttributeError:
                        pass
            try:
                self[attr] = val
            except ValidationError:
                pass

    def getint(self):
        return self.uint32le.unpack(self.fp.read(self.uint32le.size))[0]

    def getstr(self):
        return self.fp.read(self.getint()).decode('utf-8', 'ignore')


class FLAC(Vorbis):

    format = 'flac'

    head = Struct('B3s')

    def decode(self):
        self.fp.seek(0, os.SEEK_SET)
        if self.fp.read(4) != 'fLaC':
            raise DecodeError('not a flac file')
        pos = 4
        self.fp.seek(0, os.SEEK_END)
        end = self.fp.tell()
        while pos < end:
            self.fp.seek(pos, os.SEEK_SET)
            head, size = self.head.unpack(self.fp.read(self.head.size))
            size = self.uint32be.unpack('\x00' + size)[0]
            if head & 127 == 4:
                super(FLAC, self).decode()
            if head & 128:
                break
            pos += size + self.head.size


class OGG(Vorbis):

    format = 'ogg'

    page = Struct('>4s2BQ3LB')

    def decode(self):
        self.fp.seek(0, os.SEEK_END)
        end = self.fp.tell()
        pos = 0
        while pos < end:
            self.fp.seek(pos, os.SEEK_SET)
            page = self.page.unpack(self.fp.read(self.page.size))
            if page[0] != 'OggS':
                raise DecodeError('not an ogg page')
            size = sum(ord(i) for i in self.fp.read(page[7]))
            if self.fp.read(7) == '\x03vorbis':
                super(OGG, self).decode()
            pos += size + page[7] + self.page.size


DECODERS = FLAC, OGG, M4A, IFF, MP3


def tagopen(file, readonly=True):
    for cls in DECODERS:
        try:
            tag = cls(file)
        except InvalidMedia:
            continue
        if readonly or not cls.editable:
            tag = Metadata(tag)
        return tag
    raise InvalidMedia('no suitable decoder found')
