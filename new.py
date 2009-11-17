#!/usr/bin/env python

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
# CRC:    http://www.ross.net/crc/download/crc_v3.txt

from struct import error as StructError, Struct
from collections import MutableMapping
from math import log
import sys
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

ANYITEM = -1
LANG = 'eng'
GAPLESS = u'iTunPGAP'
ENCODING = 'utf-8'
IMAGE_SAMPLE_SIZE = 512
DEFAULT_ID3V2_VERSION = 2
DEFAULT_ID3V2_PADDING = 128
FAKEMP3 = '\xff\xf3\x14\xc4' * 7
BLOCKSIZE = 4096

DICT, IDICT, TEXT, UINT16, BOOL, UINT16X2, GENRE, IMAGE, UINT32, VOLUME = [
        2 ** i for i in xrange(10)]

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

TRUE = 'y', 'yes', 'true', 't', '1', '\x01', 'on'

ID3V2_OPTS = {2: (Struct('3s3s0s'), False,
                  {'COM': '_comment',
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
                   'ULT': '_lyrics'}),
              3: (Struct('4s4s2s'), False,
                  {'APIC': '_image',
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
                   'USLT': '_lyrics'}),
              4: (Struct('4s4s2s'), True,
                  {'APIC': '_image',
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
                   'USLT': '_lyrics'})}

ID3V2_TAGS = dict(x for y in ID3V2_OPTS.itervalues() for x in y[2].iteritems())
ID3V1_ATTRS = ['name', 'artist', 'album', 'year', 'comment', 'track', 'genre']

ID3V2_ENCS = {'\x00': ('latin-1', '\x00'),
              '\x01': ('utf-16', '\x00\x00'),
              '\x02': ('utf-16-be', '\x00\x00'),
              '\x03': ('utf-8', '\x00')}

MP3_SAMPLESIZE = 2502

MP3_BITRATES = [
        [32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
        [32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
        [32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
        [32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
        [8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]]

MP3_SRATES = [[11025, 12000, 8000, 0], None, [22050, 24000, 16000, 0],
              [44100, 48000, 32000, 0]]

IFF_IDS = {'ANNO': 'comment',
           'AUTH': 'artist',
           'IART': 'artist',
           'ICMT': 'comment',
           'ICRD': 'year',
           'INAM': 'name',
           'NAME': 'name'}

A_NODE, A_SKIP, A_DATA, A_DICT = [2 ** i for i in xrange(4)]

ATOM_UTF8 = 1
ATOM_UINT = 21
ATOM_UINT16 = 0
ATOM_PNG = 14
ATOM_JPG = 13

ATOMS = {'moov': (A_NODE, None),
         'moov.udta': (A_NODE, None),
         'moov.udta.meta': (A_NODE | A_SKIP, None),
         'moov.udta.meta.ilst': (A_NODE, None),
         'moov.udta.meta.ilst.----': (A_DICT, None),
         'moov.udta.meta.ilst.aART': (A_NODE | A_DATA, 'album_artist'),
         'moov.udta.meta.ilst.covr': (A_NODE | A_DATA, 'image'),
         'moov.udta.meta.ilst.cpil': (A_NODE | A_DATA, 'compilation'),
         'moov.udta.meta.ilst.desc': (A_NODE | A_DATA, 'video_description'),
         'moov.udta.meta.ilst.disk': (A_NODE | A_DATA, 'disk'),
         'moov.udta.meta.ilst.gnre': (A_NODE | A_DATA, 'genre'),
         'moov.udta.meta.ilst.pgap': (A_NODE | A_DATA, 'gapless'),
         'moov.udta.meta.ilst.soaa': (A_NODE | A_DATA, 'sort_album_artist'),
         'moov.udta.meta.ilst.soal': (A_NODE | A_DATA, 'sort_album'),
         'moov.udta.meta.ilst.soar': (A_NODE | A_DATA, 'sort_artist'),
         'moov.udta.meta.ilst.soco': (A_NODE | A_DATA, 'sort_composer'),
         'moov.udta.meta.ilst.sonm': (A_NODE | A_DATA, 'sort_name'),
         'moov.udta.meta.ilst.sosn': (A_NODE | A_DATA, 'sort_video_show'),
         'moov.udta.meta.ilst.tmpo': (A_NODE | A_DATA, 'bpm'),
         'moov.udta.meta.ilst.trkn': (A_NODE | A_DATA, 'track'),
         'moov.udta.meta.ilst.tven': (A_NODE | A_DATA, 'video_episode_id'),
         'moov.udta.meta.ilst.tves': (A_NODE | A_DATA, 'video_episode'),
         'moov.udta.meta.ilst.tvsh': (A_NODE | A_DATA, 'video_show'),
         'moov.udta.meta.ilst.tvsn': (A_NODE | A_DATA, 'video_season'),
         'moov.udta.meta.ilst.\xa9ART': (A_NODE | A_DATA, 'artist'),
         'moov.udta.meta.ilst.\xa9alb': (A_NODE | A_DATA, 'album'),
         'moov.udta.meta.ilst.\xa9cmt': (A_NODE | A_DATA, 'comment'),
         'moov.udta.meta.ilst.\xa9day': (A_NODE | A_DATA, 'year'),
         'moov.udta.meta.ilst.\xa9gen': (A_NODE | A_DATA, 'genre'),
         'moov.udta.meta.ilst.\xa9grp': (A_NODE | A_DATA, 'grouping'),
         'moov.udta.meta.ilst.\xa9lyr': (A_NODE | A_DATA, 'lyrics'),
         'moov.udta.meta.ilst.\xa9nam': (A_NODE | A_DATA, 'name'),
         'moov.udta.meta.ilst.\xa9too': (A_NODE | A_DATA, 'encoder'),
         'moov.udta.meta.ilst.\xa9wrt': (A_NODE | A_DATA, 'composer')}

VORBIS_TAGS = {'album': 'album',
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

    """Base error class"""


class ValidationError(TaglibError):

    """Raised on data validation error"""


class DecodeError(TaglibError):

    """Raised on decode failure"""


class EncodeError(TaglibError):

    """Error encoding"""


class InvalidMedia(DecodeError):

    """Raised when media is unreadable"""


DecodeErrors = ValidationError, DecodeError, StructError, IOError, OSError
EncodeErrors = EncodeError, StructError, IOError, OSError


class Container(MutableMapping):

    """Flexible container object"""

    types = {}

    def __init__(self, *args, **kwargs):
        self.__dict__.update(dict.fromkeys(self.types))
        self.__dict__.update(*args, **kwargs)
        self.reset()

    @property
    def modified(self):
        """True if public attributes have been modified"""
        return bool(self.__changed)

    @property
    def changed(self):
        """List of modified attributes"""
        return sorted(self.__changed)

    def reset(self):
        """Reset modified status"""
        self.__changed = set()

    def getrepr(self, attr):
        """Get string representation for attribute"""
        return repr(self[attr])

    def __getitem__(self, attr):
        """Map dictionary access to attributes"""
        return self.__getattribute__(attr)

    def __getattribute__(self, attr):
        """Safe attribute access"""
        try:
            return super(Container, self).__getattribute__(attr)
        except AttributeError:
            if attr not in self.types:
                raise

    def __setitem__(self, attr, val):
        """Map dictionary access to attributes"""
        self.__setattr__(attr, val)

    def __setattr__(self, attr, val):
        """Safe attribute access"""
        try:
            val = self.validate(val, self.types[attr])
            if val != self[attr]:
                self.__changed.add(attr)
        except KeyError:
            pass
        except ValidationError, error:
            error.args = '%s: %s' % (attr, error),
            raise
        super(Container, self).__setattr__(attr, val)

    def __delitem__(self, attr):
        """Map dictionary access to attrs"""
        self.__delattr__(attr)

    def __delattr__(self, attr):
        """Safe attribute access"""
        if attr in self.types:
            self.__setattr__(attr, None)
        else:
            super(Container, self).__delattr__(attr)

    def __iter__(self):
        """Yields public attributes"""
        return (attr for attr in sorted(self.types)
                if not attr.startswith('_') and self[attr] is not None)

    def __len__(self):
        """Length of public attributes"""
        return sum(1 for _ in self.__iter__())

    def __repr__(self):
        """String representation of public attributes"""
        attrs = ', '.join('%s=%s' % (attr, self.getrepr(attr)) for attr in self)
        return '<%s object at 0x%x%s%s>' % (
                type(self).__name__, id(self), ': ' if attrs else '', attrs)

    @classmethod
    def validate(cls, val, dtype=None):
        """Validate attribute data"""
        try:
            return cls.transform(val, dtype)
        except Exception, error:
            raise ValidationError, error, sys.exc_traceback

    @staticmethod
    def transform(val, dtype=None):
        """Transform data to type"""
        return dtype(val)


class Metadata(Container):

    """Media metadata"""

    types = TYPES

    @property
    def image_sample(self):
        """Sample of image"""
        image = self.image
        if image:
            val = StringIO()
            image.save(val, image.format)
            val.seek(0)
            return val.read(IMAGE_SAMPLE_SIZE), image.size, image.format

    @property
    def rounded_volume(self):
        """Rounded string volume"""
        if self.volume is not None:
            return '%.1f' % round(self.volume)
        return '0.0'

    def getrepr(self, attr, encoding=None):
        """Get string representation for attribute"""
        val = self[attr]
        try:
            dtype = self.types[attr]
        except KeyError:
            dtype is None
        if val is None or dtype is None:
            return repr(val)
        if dtype == BOOL:
            return 'Yes' if val else 'No'
        elif dtype in (GENRE, TEXT):
            if encoding is None:
                encoding = ENCODING
            return val.encode(encoding)
        elif dtype == IMAGE:
            return '%dx%d %s Image' % (val.size[0], val.size[1], val.format)
        elif dtype in (UINT16, UINT32):
            return str(val)
        elif dtype == UINT16X2:
            return '%d/%d' % tuple(val)
        elif dtype == VOLUME:
            return '%.1f' % val

    def __eq__(self, other):
        """Compare objects"""
        if not isinstance(other, Metadata):
            return NotImplemented
        try:
            self.compare(self, other)
        except ValidationError:
            return False
        return True

    def __ne__(self, other):
        """Test inequality"""
        val = self.__eq__(other)
        if val is NotImplemented:
            return val
        return not val

    @staticmethod
    def transform(val, dtype=None):
        """Transform data to type"""
        raise ValidationError('read-only')

    @classmethod
    def compare(cls, x, y):
        """Compare two metadata objects"""
        for attr, dtype in cls.types.iteritems():
            if dtype in (DICT, IDICT):
                continue
            if dtype == IMAGE:
                xval, yval = x.image_sample, y.image_sample
            elif dtype == VOLUME:
                xval, yval = x.rounded_volume, y.rounded_volume
            else:
                xval, yval = x[attr], y[attr]
            if xval != yval:
                raise ValidationError('%s: %r != %r' % (attr, xval, yval))


class AttrMap(object):

    """Fail back attribute access to another object"""

    attrmap = None

    def __getattribute__(self, attr):
        """Fail back attribute access to another object"""
        get = super(AttrMap, self).__getattribute__
        try:
            return get(attr)
        except AttributeError:
            if not self.attrmap:
                raise
            exc_type, exc_value, exc_traceback = sys.exc_info()
            try:
                return get(self.attrmap).__getattribute__(attr)
            except AttributeError:
                raise exc_type, exc_value, exc_traceback


class Open(AttrMap):

    """Flexible open container"""

    attrmap = 'fp'

    def __init__(self, file, mode='rb', context_close=False):
        if isinstance(file, basestring):
            self.fp = open(file, mode)
            self.external = False
        elif isinstance(file, (int, long)):
            self.fp = os.fdopen(file, mode)
            self.external = True
        elif hasattr(file, 'seek'):
            self.fp = file
            self.external = True
        else:
            raise TypeError('file must be a path, fd, or fileobj')
        self.context_close = context_close

    def __enter__(self):
        """Enter open context"""
        if self.external:
            self.pos = self.tell()
        return self

    def __exit__(self, *exc_info):
        """Exit open context"""
        if self.external:
            self.seek(self.pos)
        elif self.context_close:
            self.close()


class Decoder(AttrMap, Metadata):

    """Base decoder class"""

    attrmap = 'fp'
    format = None
    editable = False

    uint32be = Struct('>L')
    uint32le = Struct('<L')
    int16be = Struct('>h')
    uint16be = Struct('>H')
    longbytes = Struct('4B')

    def __init__(self, file):
        if not self.format:
            raise DecodeError('unable to use base decoder')
        super(Decoder, self).__init__()
        if self.editable:
            mode = 'rb+'
            context_close = False
        else:
            mode = 'rb'
            context_close = True
        with Open(file, mode, context_close) as fp:
            self.fp = fp
            try:
                self.decode()
            except DecodeErrors, error:
                raise InvalidMedia, error, sys.exc_traceback
        self.reset()

    def getdict(self, attr, key):
        """Get managed dict item"""
        d = self[attr]
        if d:
            if key == ANYITEM:
                key = sorted(d)[0]
            return d.get(key)

    def setdict(self, attr, key, val):
        """Set managed dict item"""
        if val is None:
            self.deldict(attr, key)
        else:
            d = self[attr]
            if not d:
                d = self[attr] = {}
            d[key] = val

    def deldict(self, attr, key):
        """Delete managed dict item"""
        d = self[attr]
        if d:
            if key == ANYITEM:
                key = sorted(d)[0]
            try:
                del d[key]
                if not d:
                    del self[attr]
            except KeyError:
                pass

    def decode(self):
        """Decode metadata"""
        raise DecodeError('not implemented')

    def dump(self, file=None, **kwargs):
        """Dump to file"""
        if not self.format:
            raise EncodeError('unable to use base decoder')
        if not self.editable:
            raise EncodeError('%s does not support encoding' % self.format)
        if file is None:
            file = StringIO()
        with Open(file, 'wb') as fp:
            self.encode(fp, inplace=False, **kwargs)
        if not fp.closed:
            return fp

    def dumps(self, **kwargs):
        """Dump to string"""
        return self.dump(**kwargs).getvalue()

    def save(self, **kwargs):
        """Save updated metadata"""
        self.encode(self.fp, inplace=True, **kwargs)

    def encode(self, fp, inplace=False, **kwargs):
        """Encode to open file"""
        raise EncodeError('not implemented')

    def seekend(self, pos=0):
        """Seek backwards from end of file"""
        self.seek(pos * -1, os.SEEK_END)

    def seekcur(self, pos):
        """Seek from current position"""
        self.seek(pos, os.SEEK_CUR)

    def unpack(self, struct):
        """Read and unpack based on structure"""
        val = struct.unpack(self.read(struct.size))
        if len(val) == 1:
            return val[0]
        return val

    @staticmethod
    def transform(val, dtype=None):
        """Transform data to type"""
        if val is None or dtype is None:
            return val
        if dtype in (DICT, IDICT):
            if not isinstance(val, dict):
                raise TypeError('must be a dictionary')
            return val
        if dtype == IMAGE:
            if not PIL:
                raise ValueError('PIL required')
            if not isinstance(val, ImageFile):
                val = Image.open(val)
                val.load()
            return val
        if dtype == GENRE:
            if isinstance(val, (int, long)):
                val = GENRES[val]
            dtype = TEXT
        if dtype == TEXT and not isinstance(val, basestring):
            val = str(val)
        if isinstance(val, str):
            val = val.decode('ascii', 'ignore')
        if isinstance(val, unicode):
            val = val.replace('\x00', '').strip()
            if not val:
                return
            if dtype == TEXT:
                return val
        if dtype == BOOL:
            if isinstance(val, basestring):
                return val.lower() in TRUE
            elif not isinstance(val, bool):
                val = bool(val)
            return val
        if dtype in (UINT16, UINT32):
            if not isinstance(val, (int, long)):
                val = int(val)
            if val < 0:
                val = 0
            elif dtype == UINT16 and val > 0xffff:
                val = 0xffff
            elif dtype == UINT32 and val > 0xffffffff:
                val = 0xffffffff
            if not val:
                return
            return val
        if dtype == VOLUME:
            if not isinstance(val, float):
                val = float(val)
            if val < -99.9:
                val = -99.9
            elif val > 100.0:
                val = 100.0
            return val
        if dtype == UINT16X2:
            if isinstance(val, tuple):
                val = list(val)
            elif isinstance(val, unicode):
                val = val.split('/')
            elif not isinstance(val, list):
                val = [val]
            if not val:
                return
            if len(val) == 1:
                val.append(0)
            elif len(val) != 2:
                raise ValueError('must have 1 or 2 items')
            for i, item in enumerate(val):
                if not isinstance(item, (int, long)):
                    item = int(item)
                if item < 0:
                    item = 0
                elif item > 0xffff:
                    item = 0xffff
                val[i] = item
            if val == [0, 0]:
                return
            return val

    @classmethod
    def getint(cls, bytes, struct=None):
        """Convert bytes to integer"""
        if struct is None:
            struct = cls.uint32be
        return struct.unpack('\x00' * (struct.size - len(bytes)) + bytes)[0]

    @staticmethod
    def copyfile(src, dst, blocksize=None):
        """Copy source file to destination"""
        if blocksize is None:
            blocksize = BLOCKSIZE
        while True:
            data = src.read(blocksize)
            if not data:
                break
            dst.write(data)


class MP3Head(Container):

    """Container object for mp3 frame head attributes"""

    types = {'srate_idx': int, 'layer': int, 'sync': bool, 'private': int,
             'mode_ext': int, 'padding': int, 'emphasis': int, 'version': int,
             'bitrate_idx': int, 'mode': int, 'valid': bool, 'copyright': bool,
             'protected': bool, 'original': bool}

    head = Decoder.uint32be

    def __init__(self, bytes):
        """Decode MP3 frame header"""
        super(MP3Head, self).__init__()
        val = self.head.unpack(bytes)[0]
        self.sync = val & 0xffe00000 == 0xffe00000
        self.version = val >> 19 & 0x03
        self.layer = 4 - (val >> 17 & 0x03)
        self.protected = val >> 16 & 0x01 == 0x00
        self.bitrate_idx = (val >> 12 & 0x0f) - 1
        self.srate_idx = val >> 10 & 0x03
        self.padding = val >> 9 & 0x01
        self.private = val >> 8 & 0x01
        self.mode = val >> 6 & 0x03
        self.mode_ext = val >> 4 & 0x03
        self.copyright = val >> 3 & 0x01 == 0x01
        self.original = val >> 2 & 0x01 == 0x01
        self.emphasis = val & 0x03

    @property
    def valid(self):
        """True if this is a valid mp3 header"""
        return (self.sync and self.version != 1 and self.layer != 4 and
                self.bitrate_idx not in (-1, 14) and self.srate_idx != 3)

    @property
    def valid_bitrates(self):
        """List of valid bitrates"""
        if self.version == 3:
            idx = self.layer - 1
        elif self.layer == 1:
            idx = 3
        else:
            idx = 4
        return MP3_BITRATES[idx]

    @property
    def bitrate(self):
        """This frame's bitrate"""
        return self.valid_bitrates[self.bitrate_idx]

    @property
    def valid_srates(self):
        """List of valid sample rates"""
        return MP3_SRATES[self.version]

    @property
    def srate(self):
        """Sample rate"""
        return self.valid_srates[self.srate_idx]

    @property
    def length(self):
        """Length of this frame"""
        if self.layer == 1:
            return (self.bitrate * 12000 / self.srate + self.padding) << 2
        else:
            srate = self.srate
            if self.version2 or self.version25:
                srate <<= 1
            return self.bitrate * 144000 / srate + self.padding

    @property
    def version2(self):
        """True if this is a version2 mp3"""
        return self.version & 0x02 == 0x00

    @property
    def version25(self):
        """True if this is a version2.5 mp3"""
        return self.version & 0x01 == 0x00

    @property
    def packed(self):
        """Packed header"""
        val = ((0xffe00000 if self.sync else 0) |
               (self.version << 19) |
               ((4 - self.layer) << 17) |
               ((0 if self.protected else 1) << 16) |
               ((self.bitrate_idx + 1) << 12) |
               (self.srate_idx << 10) |
               (self.padding << 9) |
               (self.private << 8) |
               (self.mode << 6) |
               (self.mode_ext << 4) |
               ((1 if self.copyright else 0) << 3) |
               ((1 if self.original else 0) << 2) |
               (self.emphasis))
        return self.head.pack(val)


class MP3(Decoder):

    """Decode ID3 tags on MP3"""

    format = 'mp3'
    editable = True

    id3v1 = Struct('3s30s30s30s4s30sB')
    id3v2head = Struct('3s3B4s')

    tag_re = re.compile(r'^[A-Z0-9 ]{3,4}$')
    genre_re = re.compile(r'^\((\d+)\)$')

    def __init__(self, *args, **kwargs):
        self.hasid3v1 = False
        self.id3v1start = 0
        self.id3v1end = 0
        self.hasid3v2 = False
        self.id3v2start = 0
        self.id3v2end = 0
        self.id3v2version = None
        self.hasmp3 = False
        self.mp3start = 0
        self.mp3end = 0
        super(MP3, self).__init__(*args, **kwargs)

    @property
    def id3v1size(self):
        """Size of id3v1 tag"""
        return self.id3v1end - self.id3v1start

    @property
    def id3v2size(self):
        """Size of id3v2 tag"""
        return self.id3v2end - self.id3v2start

    @property
    def mp3size(self):
        """Size of mp3 tag"""
        return self.mp3end - self.mp3start

    @property
    def mp3frames(self):
        """Yields each frame of MP3 data"""
        if self.hasmp3:
            self.seek(self.mp3start)
            size = 0
            while True:
                try:
                    head = MP3Head(self.read(MP3Head.head.size))
                    if not head.valid:
                        raise DecodeError('invalid header')
                    yield head, self.read(head.length - MP3Head.head.size)
                    size += head.length
                except DecodeErrors:
                    break
            self.mp3end = self.mp3start + size

    @property
    def mp3bitrate(self):
        """Average bitrate"""
        frames = 0
        bitrate = 0.0
        for head, data in self.mp3frames:
            frames += 1
            bitrate += head.bitrate
        return bitrate / frames

    def get_gapless(self):
        """Get gapless"""
        return self.get_comment(key=GAPLESS)

    def set_gapless(self, val):
        """Set gapless"""
        self.set_comment(val, key=GAPLESS)

    def del_gapless(self):
        """Delete gapless"""
        self.del_comment(key=GAPLESS)

    gapless = property(get_gapless, set_gapless, del_gapless)

    def get_comment(self, key=None, lang=None):
        """Get comment"""
        if key != ANYITEM:
            if lang is None:
                lang = LANG
            key = lang, key
        return self.getdict('_comment', key)

    def set_comment(self, val, key=None, lang=None):
        """Set comment"""
        if lang is None:
            lang = LANG
        self.setdict('_comment', (lang, self.validate(key, TEXT)),
                     self.validate(val, BOOL if key == GAPLESS else TEXT))

    def del_comment(self, key=None, lang=None):
        """Delete comment"""
        if key != ANYITEM:
            if lang is None:
                lang = LANG
            key = lang, key
        self.deldict('_comment', key)

    comment = property(get_comment, set_comment, del_comment)

    def get_lyrics(self, key=None, lang=None):
        """Get lyrics"""
        if key != ANYITEM:
            if lang is None:
                lang = LANG
            key = lang, key
        return self.getdict('_lyrics', key)

    def set_lyrics(self, val, key=None, lang=None):
        """Set lyrics"""
        if lang is None:
            lang = LANG
        self.setdict('_lyrics', (lang, self.validate(key, TEXT)),
                     self.validate(val, TEXT))

    def del_lyrics(self, key=None, lang=None):
        """Delete lyrics"""
        if key != ANYITEM:
            if lang is None:
                lang = LANG
            key = lang, key
        self.deldict('_lyrics', key)

    lyrics = property(get_lyrics, set_lyrics, del_lyrics)

    def get_image(self, key=ANYITEM):
        """Get image"""
        if key != ANYITEM:
            key = key,
        val = self.getdict('_image', key)
        if val:
            return val[0]

    def set_image(self, val, key=None, ptype=3):
        """Set image"""
        val = self.validate(val, IMAGE)
        if val:
            val = val, ptype
        self.setdict('_image', (self.validate(key, TEXT),), val)

    def del_image(self, key=ANYITEM):
        """Delete image"""
        if key != ANYITEM:
            key = key,
        self.deldict('_image', key)

    image = property(get_image, set_image, del_image)

    def decode(self):
        """Decode ID3 tags"""
        try:
            self.decode_id3v1()
        except DecodeErrors:
            pass
        try:
            self.decode_id3v2()
        except DecodeErrors:
            pass
        self.decode_mp3()

    def decode_id3v1(self):
        """Decode ID3v1 tag"""
        try:
            self.seekend(self.id3v1.size)
            id3v1 = self.unpack(self.id3v1)
            if id3v1[0] != 'TAG':
                raise DecodeError('no id3v1 tag')
            try:
                self.name, self.artist, self.album, self.year = id3v1[1:5]
            except ValidationError:
                pass
            if id3v1[5][28] == '\x00' and id3v1[5][29] != '\x00':
                self.comment = id3v1[5][:28]
                self.track = ord(id3v1[5][29])
            else:
                self.comment = id3v1[5]
            try:
                self.genre = id3v1[6]
            except ValidationError:
                pass
            self.hasid3v1 = True
            self.id3v1end = self.tell()
            self.id3v1start = self.id3v1end - self.id3v1.size
        except DecodeErrors:
            self.hasid3v1 = False
            self.id3v1start = 0
            self.id3v1end = 0
            raise

    def decode_id3v2(self, pos=None):
        """Decode ID3v2 tag"""
        if pos is None:
            pos = 0
        try:
            self.seek(pos)
            id3v2head = self.unpack(self.id3v2head)
            if id3v2head[0] != 'ID3':
                raise DecodeError('no id3v2 tag')
            try:
                frame, syncsafe = ID3V2_OPTS[id3v2head[1]][:2]
            except KeyError:
                raise DecodeError('unknown version: %d' % id3v2head[1])
            if id3v2head[2]:
                raise DecodeError('unknown revision: %d' % id3v2head[2])
            if id3v2head[3]:
                pass  #print >> sys.stderr, 'XXX: flags on id3v2 header'
            id3v2size = self.getint(id3v2head[4], syncsafe=True)
            self.hasid3v2 = True
            self.id3v2start = pos
            self.id3v2end = pos + id3v2size
            self.id3v2version = id3v2head[1]
            while id3v2size >= frame.size:
                tag, size, flags = self.unpack(frame)
                if not self.tag_re.search(tag):
                    break
                size = self.getint(size, syncsafe)
                if self.getint(flags):
                    pass  # print >> sys.stderr, 'XXX frame flags'
                val = self.read(size)
                id3v2size -= (size + frame.size)
                try:
                    attr = ID3V2_TAGS[tag]
                    dtype = TYPES[attr]
                except KeyError:
                    unknown = self['_unknown']
                    if not unknown:
                        unknown = self['_unknown'] = {}
                    unknown.setdefault(tag, []).append(val)
                    continue
                if dtype in (BOOL, GENRE, TEXT, UINT16, UINT16X2):
                    val = self.getstr(val)
                if not val:
                    continue
                if dtype == GENRE:
                    try:
                        val = int(self.genre_re.search(val).group(1))
                    except AttributeError:
                        pass
                elif dtype == DICT:
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
                elif dtype == IDICT:
                    ebyte, val, encoding, term = self.getenc(val)
                    if tag == 'PIC':
                        val = val[3:]
                    else:
                        val = self.splitstr(val, offset=1)[1]
                    ptype = ord(val[0])
                    key, val = self.splitstr(val[1:], term, offset=1)
                    key = self.getstr(ebyte + key)
                    val = StringIO(val)
                    try:
                        self.set_image(val, key, ptype)
                    except ValidationError:
                        pass
                    continue
                elif dtype == VOLUME:
                    if tag == 'RVA2':
                        val = self.splitstr(val, offset=1)[1][1:3]
                        val = self.int16be.unpack(val)[0] / 512.0
                        val = 100 * (10 ** (val / 20) - 1)
                    else:
                        incdec, bits, val = ord(val[0]), ord(val[1]), val[2:]
                        i = int((bits + 7) / 8)
                        rval = self.getint(val[:i])
                        if incdec & 0x01 == 0x00:
                            rval *= -1
                        lval = self.getint(val[i:i * 2])
                        if incdec & 0x02 == 0x00:
                            lval *= -1
                        val = (rval + lval) / 2.0 / ((1 << bits) - 1) * 100
                try:
                    self[attr] = val
                except ValidationError:
                    pass
        except DecodeErrors:
            self.hasid3v2 = False
            self.id3v2start = 0
            self.id3v2end = 0
            self.id3v2version = None
            raise

    def decode_mp3(self, pos=None, samplesize=None):
        """Decode ID3v1 tag"""
        if pos is None:
            pos = self.id3v2end
        if samplesize is None:
            samplesize = MP3_SAMPLESIZE
        try:
            self.seek(pos)
            sample = self.read(samplesize)
            i = 0
            while i < len(sample) - MP3Head.head.size:
                i = sample.find('\xff', i)
                if i == -1:
                    break
                try:
                    head = MP3Head(sample[i:i + MP3Head.head.size])
                    if not head.valid:
                        raise DecodeError('not a valid mp3 frame')
                    j = i + head.length
                    head = MP3Head(sample[j:j + MP3Head.head.size])
                    if not head.valid:
                        raise DecodeError('next frame is invalid')
                    self.hasmp3 = True
                    self.mp3start = self.mp3end = pos + i
                    return
                except DecodeErrors:
                    pass
                i += 1
            raise DecodeError('no mp3 frame found')
        except DecodeErrors:
            self.hasmp3 = False
            self.mp3start = 0
            self.mp3end = 0
            raise

    def encode(self, fp, inplace=False, version=None, unknown=False,
               padding=None, doid3v1=True, doid3v2=True, domp3=True,
               fakemp3=False):
        """Encode ID3 tags"""
        if doid3v2:
            if version is None:
                version = self.id3v2version
                if version is None:
                    version = DEFAULT_ID3V2_VERSION
            try:
                frame, syncsafe, tags = ID3V2_OPTS[version]
            except KeyError:
                raise EncodeError('unknown id3v2 version')
            for tag, attr in tags.iteritems():
                if self[attr]:
                    haveid3v2 = True
                    break
            else:
                haveid3v2 = False
            if inplace:
                if self.hasid3v2:
                    fp.seek(self.id3v2start)
                else:
                    doid3v2 = False
            elif not haveid3v2:
                doid3v2 = False
            if doid3v2:
                taglen, sizelen, flagslen = [
                        len(i) for i in frame.unpack('\x00' * frame.size)]
                sizeidx = sizelen * -1
                flags = '\x00' * flagslen
                id3v2 = []
                id3v2size = 0
                for tag, val in self.id3v2items(tags, unknown, inplace):
                    if len(tag) != taglen:
                        raise EncodeError('invalid tag size: %r' % tag)
                    size = self.getbytes(len(val), syncsafe)[sizeidx:]
                    frame = tag + size + flags + val
                    id3v2.append(frame)
                    id3v2size += len(frame)
                if inplace:
                    if id3v2size > self.id3v2size:
                        raise EncodeError('no room for id3v2 tag')
                    padding = self.id3v2size - id3v2size
                elif padding is None:
                    padding = DEFAULT_ID3V2_PADDING
                id3v2.append('\x00' * padding)
                id3v2size += padding
                fp.write(self.id3v2head.pack(
                    'ID3', version, 0, 0,
                    self.getbytes(id3v2size, syncsafe=True)))
                for frame in id3v2:
                    fp.write(frame)
                self.id3v2version = version
        if not inplace and domp3:
            if fakemp3:
                fp.write(FAKEMP3)
            else:
                for head, data in self.mp3frames:
                    fp.write(head.packed)
                    fp.write(data)
        if doid3v1:
            for attr in ID3V1_ATTRS:
                if self[attr]:
                    haveid3v1 = True
                    break
            else:
                haveid3v1 = False
            if inplace:
                if self.hasid3v1:
                    fp.seek(self.id3v1start)
                elif haveid3v1:
                    self.seekend()
                else:
                    doid3v1 = False
            elif not haveid3v1:
                doid3v1 = False
            if doid3v1:
                if self.track and self.track[0] and self.track[0] < 256:
                    comment = (self.pad(self.comment, 28) +
                               '\x00' + chr(self.track[0]))
                else:
                    comment = self.pad(self.comment)
                try:
                    genre = GENRES.index(self.genre)
                except ValueError:
                    genre = 255
                fp.write(self.id3v1.pack(
                    'TAG', self.pad(self.name), self.pad(self.artist),
                    self.pad(self.album), self.pad(self.year, 4), comment,
                    genre))

    def id3v2items(self, tags, unknown, inplace):
        """Docstring for id3v2items"""
        term = not inplace
        for tag, attr in tags.iteritems():
            val = self[attr]
            if not val:
                continue
            dtype = self.types[attr]
            if dtype == BOOL:
                val = u'1'
            elif dtype == DICT:
                for key, val in val.iteritems():
                    lang, key = key
                    if key == GAPLESS:
                        val = u'1' if val else u'0'
                    key2 = self.mkstr(key, term=True)
                    val2 = self.mkstr(val, term=term)
                    if key2[0] == val2[0]:
                        key, val = key2, val2
                    elif key2[0] == '\x01':
                        key = key2
                        val = self.mkstr(val, utf16=True, term=term)
                    else:
                        key = self.mkstr(key, utf16=True, term=True)
                        val = val2
                    yield tag, key[0] + lang + key[1:] + val[1:]
                continue
            elif dtype == GENRE:
                try:
                    val = u'(%d)' % GENRES.index(val)
                except ValueError:
                    pass
            elif dtype == IDICT:
                for key, val in val.iteritems():
                    key = self.mkstr(key[0], term=True)
                    image, ptype = val
                    if tag == 'PIC':
                        if image.format == 'JPEG':
                            format = 'JPG'
                        else:
                            format = image.format[:3]
                    else:
                        format = 'image/%s\x00' % image.format.lower()
                    val = StringIO()
                    image.save(val, image.format)
                    yield tag, (key[0] + format + chr(ptype) +
                                key[1:] + val.getvalue())
                continue
            elif dtype == UINT16:
                val = unicode(val)
            elif dtype == UINT16X2:
                val = (u'%d/%d' % tuple(val)).replace('/0', '')
            elif dtype == VOLUME:
                if tag == 'RVA2':
                    val = '\x00\x01%s\x00' % (
                            self.int16be.pack(
                                int(log(val / 100 + 1, 10) * 20 * 512)))
                else:
                    val = int(val * 655.35)
                    if val < 0:
                        val *= -1
                        incdec = '\x00'
                    else:
                        incdec = '\x03'
                    val = (incdec + '\x10' + self.uint16be.pack(val) * 2 +
                           '\x00\x00\x00\x00')
            if isinstance(val, unicode):
                val = self.mkstr(val, term=not inplace)
            if isinstance(val, str):
                yield tag, val
        if unknown and self._unknown:
            for tag, vals in self._unknown.iteritems():
                for val in vals:
                    yield tag, val

    @staticmethod
    def pad(val, size=30):
        """Pad value with null bytes"""
        if val is None:
            val = ''
        elif isinstance(val, unicode):
            val = val.encode('ascii', 'ignore')
        elif not isinstance(val, str):
            val = str(val)
        val = val.strip()[:size]
        return val + '\x00' * (size - len(val))

    @classmethod
    def getint(cls, bytes, syncsafe=False):
        """Convert bytes to integer"""
        val = super(MP3, cls).getint(bytes)
        if syncsafe:
            return (val & 0x7f | (val & 0x7f00) >> 1 |
                    (val & 0x7f0000) >> 2 | (val & 0x7f000000) >> 3 )
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
        """Decode id3v2 string"""
        ebyte, val, encoding, term = cls.getenc(val)
        return cls.splitstr(val, term)[0].decode(encoding, 'ignore')

    @classmethod
    def getenc(cls, val):
        """Get id3v2 encoding from string"""
        try:
            ebyte = val[0]
            encoding, term = ID3V2_ENCS[ebyte]
            return ebyte, val[1:], encoding, term
        except (IndexError, KeyError):
            return '', val, 'ascii', '\x00'

    @staticmethod
    def splitstr(val, term='\x00', offset=0):
        """Safely split string without breaking utf-16"""
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
    def mkstr(cls, val, utf16=False, term=False):
        """Encode id3v2 string"""
        if val is None:
            val = u''
        elif not isinstance(val, unicode):
            val = val.decode('ascii', 'ignore')
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


class IFF(MP3):

    """Decode RIFF/AIFF container"""

    format = 'iff'
    editable = True

    riff = Struct('<4sL')
    aiff = Struct('>4sL')

    containers = 'RIFF', 'FORM', 'LIST', 'CAT '

    def __init__(self, *args, **kwargs):
        self.struct = None
        self.chunks = None
        super(IFF, self).__init__(*args, **kwargs)

    def decode(self):
        """Decode RIFF/AIFF container"""
        try:
            self.decode_id3v1()
        except DecodeErrors:
            pass
        self.chunks = []
        self.struct = None
        self.walk(end=self.id3v1start if self.hasid3v1 else None)

    def walk(self, pos=None, end=None):
        """Walk IFF structure"""
        if pos is None:
            pos = 0
        if end is None:
            self.seekend()
            end = self.tell()
        while pos < end:
            self.seek(pos)
            if self.struct is None:
                name = self.read(4)
                if name == 'RIFF':
                    self.struct = self.riff
                elif name in ('FORM', 'LIST', 'CAT '):
                    self.struct = self.aiff
                else:
                    raise DecodeError('not an iff file')
                continue
            name, size = self.unpack(self.struct)
            if not size:
                break
            self.chunks.append((pos, name, size))
            pos += self.struct.size
            next = pos + size + size % 2
            if name in self.containers:
                self.chunks.append(self.read(4))
                self.walk(pos + 4, next)
            elif name == 'ID3 ':
                try:
                    self.decode_id3v2(pos)
                except DecodeErrors:
                    pass
            elif name == 'data':
                try:
                    self.decode_mp3(pos)
                except DecodeErrors:
                    pass
            else:
                attr = IFF_IDS.get(name)
                if attr:
                    val = self.read(size).decode('utf-8', 'ignore')
                    try:
                        self[attr] = val
                    except ValidationError:
                        pass
            pos = next

    def encode(self, fp, inplace=False, asmp3=False, **kwargs):
        """Encode IFF container"""
        if inplace:
            raise EncodeError('in-place save not supported for this format')
        if asmp3:
            if not self.hasmp3:
                raise EncodeError('no mp3 data')
            return super(IFF, self).encode(fp, **kwargs)
        chunks = list(self.chunks)
        while chunks:
            # XXX so broken
            pos, name, size = chunks.pop(0)
            fp.write(self.struct.pack(name, size))
            if name in self.containers:
                x = chunks.pop(0)
                print 'adding container id %s' % x
                fp.write(x)
                continue
            else:
                print 'writing %s' % name
                self.seek(pos)
                data = self.read(size)
                fp.write(data)
            if size % 2:
                fp.write('\x00')


class M4A(Decoder):

    """Decode metadata from MPEG4 atoms"""

    format = 'm4a'
    editable = False

    head = Struct('>L4s')

    def decode(self):
        """Decode metadata from MPEG4 atoms"""
        self.walk(next='ftyp')

    def walk(self, pos=None, end=None, base=None, next=None, data=False):
        """Walk atoms"""
        if pos is None:
            pos = 0
        if end is None:
            self.seekend()
            end = self.tell()
        if base is None:
            base = []
        while pos < end:
            self.seek(pos)
            size, name = self.unpack(self.head)
            path = base + [name]
            tag = '.'.join(path)
            if next:
                if tag != next:
                    raise DecodeError('%s != %s' % (next, tag))
                next = None
            if not size:
                break
            dstart = pos + self.head.size
            pos += size
            try:
                flags, attr = ATOMS[tag]
            except KeyError:
                flags, attr = 0, None
            if flags & A_SKIP:
                dstart += self.uint32be.size
            if flags & A_NODE:
                self.walk(dstart, pos, path, data=flags & A_DATA == A_DATA)
            if flags & A_DATA:
                try:
                    atype, val = self.data
                except AttributeError:
                    continue
                del self.data
                if atype == ATOM_UTF8:
                    val = val.decode('utf-8')
                elif atype == ATOM_UINT:
                    val = self.getint(val)
                elif atype == ATOM_UINT16:
                    val = [
                        self.uint16be.unpack(val[i:i + self.uint16be.size])[0]
                        for i in xrange(0, len(val), self.uint16be.size)]
                    if len(val) == 1:
                        val = val[0]
                    else:
                        val = val[1:3]
                elif atype in (ATOM_PNG, ATOM_JPG):
                    val = StringIO(val)
                else:
                    print >> sys.stderr, 'unsupported atom: %d' % atype
                    continue
                try:
                    self[attr] = val
                except ValidationError:
                    pass
            if data and name == 'data':
                self.seek(dstart)
                dtype = self.unpack(self.head)[0]
                dstart += self.head.size
                self.data = dtype, self.read(pos - dstart)


class devel(object):

    """Functions for development only"""

    LIBRARY = '/exports/mp3'

    class raw(object):
        """Wrapper to display string as-is"""
        def __init__(self, val):
            self.val = val
        def __repr__(self):
            return self.val

    @staticmethod
    def walk(walkdir, ext=None):
        """Yields all files in a directory, recursively"""
        for basedir, subdirs, filenames in os.walk(walkdir):
            try:
                subdirs.remove('.svn')
            except ValueError:
                pass
            for filename in filenames:
                if not ext or os.path.splitext(filename)[1] == ext:
                    yield os.path.join(basedir, filename)

    @classmethod
    def mkmp3parser(cls):
        """Make parser for MP3 header"""
        cls.mkparser('AAAAAAAA AAABBCCD EEEEFFGH IIJJKLMM')
        cls.mkparser('........ ...XY... ........ ........')

    @classmethod
    def mkparser(cls, fmt):
        """Create a parser for bit format"""
        fmt = fmt.replace(' ', '')
        spec = []
        last = None
        for byte in fmt:
            if byte != last:
                last = byte
                spec.append([])
            spec[-1].append(byte)
        pos = len(fmt)
        for fmt in spec:
            size = len(fmt)
            pos -= size
            if fmt[0] == '.':
                continue
            mask = 2 ** size - 1
            if mask > 0xff:
                shift = 0
                mask <<= pos
            else:
                shift = pos
            line = ['%s = val' % fmt[0]]
            if shift:
                line.append(' >> %d' % shift)
            if mask:
                line.append(' & 0x%s' % cls.mkhex(mask))
            print ''.join(line)

    @staticmethod
    def mkhex(val):
        """Make hex string"""
        val = '%x' % val
        return '0' * (len(val) % 2) + val

    @classmethod
    def mkmp3bitrates(cls):
        """Make MP3 bitrate table"""
        fmt = '''0000    free    free    free    free    free
                 0001    32      32      32      32      8
                 0010    64      48      40      48      16
                 0011    96      56      48      56      24
                 0100    128     64      56      64      32
                 0101    160     80      64      80      40
                 0110    192     96      80      96      48
                 0111    224     112     96      112     56
                 1000    256     128     112     128     64
                 1001    288     160     128     144     80
                 1010    320     192     160     160     96
                 1011    352     224     192     176     112
                 1100    384     256     224     192     128
                 1101    416     320     256     224     144
                 1110    448     384     320     256     160
                 1111    bad     bad     bad     bad     bad'''
        table = cls.mktable(fmt)
        from pprint import pprint
        pprint(table)

    @classmethod
    def mkmp3srates(cls):
        """Make MP3 srate table"""
        fmt = '''00      44100   22050   11025
                 01      48000   24000   12000
                 10      32000   16000   8000
                 11      reserv. reserv. reserv.'''
        table = cls.mktable(fmt)
        from pprint import pprint
        pprint(table)

    @classmethod
    def mktable(cls, fmt):
        """Make a table"""
        table = [[int(i) if i.isdigit() else 0 for i in line.split()[1:]]
                 for line in fmt.splitlines()]
        return cls.rotate(table)

    @staticmethod
    def rotate(table):
        """Rotate table"""
        return [[line[i] for line in table] for i in xrange(len(table[0]))]

    @classmethod
    def mp3files(cls):
        """MP3 files in my library"""
        for mp3file in devel.walk(cls.LIBRARY, ext='.mp3'):
            yield mp3file

    @staticmethod
    def types(isize=0):
        """Show types"""
        types = ['DICT', 'IDICT', 'TEXT', 'UINT16', 'BOOL', 'UINT16X2',
                 'GENRE', 'IMAGE', 'UINT32', 'VOLUME']
        indent = ' ' * isize
        nsize = isize + 4
        next = ' ' * nsize
        for i, dtype in enumerate(sorted(types)):
            print '%s%sif dtype == %s:' % (indent, 'el' if i else '', dtype)
            print '%s# XXX' % next
            print '%spass' % next
            if not i:
                print "%sprint ' ' * %d + '# %%r' %% (val,)" % (next, nsize)

    @classmethod
    def getgenres(cls):
        """Get list of genres"""
        from BeautifulSoup import BeautifulSoup
        from urllib import urlopen
        url = 'http://www.multimediasoft.com/amp3dj/help/amp3dj_00003e.htm'
        soup = BeautifulSoup(urlopen(url))
        genres = [None for _ in xrange(256)]
        for row in soup.body('div', 's0'):
            row = row.renderContents().decode('utf-8').strip()
            row = row.replace(u'\xa0', u' ')
            row = row.replace('&nbsp;', ' ')
            row = row.replace('&amp;', '&')
            row = row.strip()
            try:
                i, genre = row.split('-', 1)
                i = int(i)
                genre = genre.encode('ascii').strip()
            except ValueError:
                continue
            genres[i] = genre
        genres = filter(None, genres)
        cls.dumplist(genres, 'GENRES')

    @staticmethod
    def dumplist(val, name):
        """Format list"""
        lead = '%s = [' % name
        lines = [[lead]]
        isize = pos = len(lead)
        indent = ' ' * isize
        last = len(val) - 1
        max = 80
        for i, genre in enumerate(val):
            val = repr(genre)
            val += ']' if i == last else ', '
            size = len(val)
            if pos + size > max:
                lines.append([indent])
                pos = isize
            lines[-1].append(val)
            pos += size
        print '\n'.join(''.join(line).rstrip() for line in lines)


class Vorbis(Decoder):

    """Decode VorbisComment"""

    editable = True

    def decode(self, pos=None):
        """Decode VorbisComment"""
        if pos is None:
            pos = 0
        self.seek(pos)
        self.encoder = self.nextstr()
        for i in xrange(self.nextint()):
            tag, val = self.nextstr().split('=', 1)
            try:
                attr = VORBIS_TAGS[tag.lower()]
            except KeyError:
                continue
            try:
                self[attr] = val
            except ValidationError:
                pass

    def encode(self, fp=None, inplace=False):
        """Encode VorbisComment"""
        if fp is None:
            fp = StringIO()
        fp.write(self.mkstr(self.encoder))
        tags = []
        for attr, val in self.iteritems():
            dtype = self.types[attr]
            if dtype == BOOL:
                val = u'1' if val else u'0'
            elif dtype == IMAGE:
                continue
            elif dtype in (UINT16, UINT32):
                val = unicode(val)
            elif dtype == UINT16X2:
                val = u'%d/%d' % tuple(val)
            elif dtype == VOLUME:
                val = u'%.1f' % val
            if isinstance(val, unicode):
                val = val.encode('utf-8')
            tags.append((attr.upper(), val))
        fp.write(self.uint32le.pack(len(tags)))
        for tag, val in tags:
            fp.write(self.mkstr('%s=%s' % (tag, val)))
        return fp

    def nextint(self):
        """Get next integer"""
        return self.unpack(self.uint32le)

    def nextstr(self):
        """Next string"""
        return self.read(self.nextint()).decode('utf-8')

    def mkstr(self, val):
        """Encoded string"""
        if val is None:
            val = ''
        elif not isinstance(val, unicode):
            if not isinstance(val, str):
                val = str(val)
            val = val.decode('ascii', 'ignore')
        val = val.encode('utf-8')
        return self.uint32le.pack(len(val)) + val


class FLAC(Vorbis):

    """Decode VorbisComment on FLAC media"""

    format = 'flac'
    editable = True

    magic = Struct('4s')
    head = Struct('B3s')

    MAGIC = 'fLaC'

    def __init__(self, *args, **kwargs):
        self.blocks = None
        super(FLAC, self).__init__(*args, **kwargs)

    def decode(self, pos=None):
        """Decode VorbisComment on FLAC media"""
        if pos is None:
            pos = 0
        self.seek(pos)
        if self.unpack(self.magic) != self.MAGIC:
            raise DecodeError('not a FLAC file')
        pos += self.magic.size
        self.seekend()
        end = self.tell()
        self.blocks = []
        while pos < end:
            self.seek(pos)
            flags, size = self.unpack(self.head)
            pos += self.head.size
            size = self.getint(size)
            self.blocks.append((pos, size, flags))
            if flags & 0x7f == 0x04:
                super(FLAC, self).decode(pos)
            if flags & 0x80:
                break
            pos += size

    def encode(self, fp, inplace=False):
        """Encode FLAC"""
        if inplace:
            raise EncodeError('in-place save not supported for this format')
        fp.write(self.MAGIC)
        for pos, size, flags in self.blocks:
            if flags & 0x7f == 0x04:
                data = super(FLAC, self).encode().getvalue()
                newsize = len(data)
            else:
                self.seek(pos)
                data = self.read(size)
                newsize = size
            newsize = self.uint32be.pack(newsize)[1:]
            fp.write(self.head.pack(flags, newsize))
            fp.write(data)
        self.seek(pos + size)
        self.copyfile(self.fp, fp)


class CRC(object):

    """Table-driven checksum implementation"""

    def __init__(self, width=4, poly=0x04C11DB7, reverse=False, initial=0):
        self.initial = initial
        bits = width * 8
        topbit = 1 << (bits - 1)
        self.mask = 2 ** bits - 1
        shift = bits - 8
        self.table = []
        for i in xrange(256):
            if reverse:
                i = self.reflect(i, 8)
            r = i << shift
            for i in xrange(8):
                r = (r << 1) ^ poly if r & topbit else r << 1
            if reverse:
                r = self.reflect(r, bits)
            self.table.append(r & self.mask)

    def checksum(self, data, r=None):
        """Calculate checksum"""
        if r is None:
            r = self.initial
        for byte in data:
            r = ((r << 8) ^ self.table[(r >> 24) ^ ord(byte)]) & self.mask
        return r

    @staticmethod
    def reflect(val, bits):
        """Reverse bit order"""
        tmp = val
        for i in xrange(bits):
            if tmp & 1:
                val |= (1 << ((bits - 1) - i))
            else:
                val &= ~(1 << ((bits - 1) - i))
            tmp >>= 1
        return val


class OGG(Vorbis):

    """Decode Vorbis comment on OGG media"""

    format = 'ogg'
    editable = True

    head = Struct('<4sBBQLLLB')
    crc = CRC()

    def __init__(self, *args, **kwargs):
        self.pages = None
        super(OGG, self).__init__(*args, **kwargs)

    def decode(self, pos=None, end=None):
        """Decode Vorbis comment on OGG media"""
        if pos is None:
            pos = 0
        if end is None:
            self.seekend()
            end = self.tell()
        self.pages = []
        while pos < end:
            self.seek(pos)
            head = self.unpack(self.head)
            if head[0] != 'OggS' or head[1]:
                raise DecodeError('not an ogg page')
            pos += self.head.size + head[7]
            packets = [0]
            segments = [ord(i) for i in self.read(head[7])]
            last = len(segments) - 1
            start = pos
            for i, segment in enumerate(segments):
                packets[-1] += segment
                if i < last and segment != 255:
                    packets.append(0)
            for i, packet in enumerate(packets):
                if self.read(7) == '\x03vorbis':
                    super(OGG, self).decode(self.tell())
                    comment = True
                else:
                    comment = False
                packets[i] = packet, comment
                pos += packet
            self.pages.append((start, head, packets))

    def encode(self, fp, inplace=False):
        """Encode VorbisComment"""
        if inplace:
            raise EncodeError('in-place save not supported for this format')
        sizes = []
        for start, head, packets in self.pages:
            self.seek(start)
            page = []
            segments = []
            last = len(packets) - 1
            for idx, packet in enumerate(packets):
                packet, comment = packet
                if comment:
                    self.seekcur(packet)
                    data = '\x03vorbis%s\x01' % (
                            super(OGG, self).encode().getvalue())
                    packet = len(data)
                else:
                    data = self.read(packet)
                page.append(data)
                i, r = divmod(packet, 255)
                segments.append('\xff' * i)
                if r or idx != last:
                    segments.append(chr(r))
            segments = ''.join(segments)
            head = list(head)
            head[6] = 0
            head[7] = len(segments)
            headpos = fp.tell()
            tmp = self.head.pack(*head) + segments
            fp.write(tmp)
            r = self.crc.checksum(tmp)
            for data in page:
                fp.write(data)
                r = self.crc.checksum(data, r)
            head[6] = r
            pos = fp.tell()
            fp.seek(headpos)
            fp.write(self.head.pack(*head))
            fp.seek(pos)


DECODERS = FLAC, OGG, M4A, IFF, MP3


def getmeta(file):
    """Open file and return metadata"""
    for decoder in DECODERS:
        try:
            return Metadata(decoder(file))
        except InvalidMedia:
            pass
    raise InvalidMedia('no suitable decoder found')


SIFFS = ['isample.aiff', 'isample.wav', 'isample1.aif', 'isample1.wav',
         'isample2.aif', 'isample2.wav', 'sample.aiff', 'sample.wav',
         'sample1.aif', 'sample2.aif']


def main():
    src = IFF('src.aiff')
    with open('dst.aiff', 'wb') as fp:
        src.dump(fp)
    return 0

if __name__ == '__main__':
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass
    sys.exit(main())
