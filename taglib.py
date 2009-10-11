# Copyright (c) 2009, Chris Jones
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
# IFF:    http://en.wikipedia.org/wiki/Interchange_File_Format
# RIFF:   http://www.midi.org/about-midi/rp29spec(rmid).pdf
# MP4:    http://atomicparsley.sourceforge.net/mpeg-4files.html
# Vorbis: http://www.xiph.org/vorbis/doc/v-comment.html
# FLAC:   http://flac.sourceforge.net/format.html#stream
# OGG:    http://en.wikipedia.org/wiki/Ogg#File_format

"""Library to read metadata on mp3/flac/mp4/wav/aif/ogg files"""

from collections import MutableMapping
from struct import error as StructError
from struct import pack, unpack
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
except ImportError:
    Image = None

__version__ = '2.4'
__author__ = 'Chris Jones <cjones@gruntle.org>'

__all__ = ['ANYITEM', 'BaseDecoder', 'DECODERS', 'DecodeError', 'EncodeError',
           'FLAC', 'FlexOpen', 'GENRES', 'IFF', 'InvalidMedia', 'M4A', 'MP3',
           'MetadataContainer', 'OGG', 'TaglibError', 'ValidationError',
           'VorbisComment', 'tagopen']

ANYITEM = -1  # use as key for managed dict items to get anything
MAXJUNK = 65536  # maximum junk tolerated when seeking an mp3 frame
BLOCKSIZE = 4096  # size of buffered I/O
RVA2FACTOR = 33153.0 / 3135  # multiplier for volume adjustment
GAPLESS = u'iTunPGAP'  # comment key for id3v2 comments
ENCODING = sys.getfilesystemencoding()  # default output encoding

# flags
(ATOM_CONTAINER1, ATOM_CONTAINER2, ATOM_DATA, BOOL, DICT, GENRE,
 IDICT, IMAGE, INT32, TEXT, UINT16, UINT16X2, UINT32) = xrange(13)

# map of attributes to data types
TYPES = {'_comment': DICT,
         '_image': IDICT,
         '_lyrics': DICT,
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
         'volume': INT32,
         'year': UINT16}

# attributes present in id3v1 tag
ID3V1FIELDS = ['name', 'artist', 'album', 'year', 'comment', 'track', 'genre']

# tags for id3v2.2
ID3V2TAGS = ['TSC', 'TSA', 'TST', 'COM', 'TSP', 'RVA', 'TEN', 'PIC', 'TCP',
             'TCO', 'TCM', 'TP2', 'TP1', 'TAL', 'TRK', 'TPA', 'TT3', 'TT2',
             'TT1', 'ULT', 'TYE', 'TBP', 'TS2']

# map of id3v2 tags to attributes
ID3TAGS = {'APIC': '_image',
           'COM': '_comment',
           'COM ': '_comment',
           'COMM': '_comment',
           'PIC': '_image',
           'PIC ': '_image',
           'RVA': 'volume',
           'RVA ': 'volume',
           'RVA2': 'volume',
           'RVAD': 'volume',
           'TAL': 'album',
           'TAL ': 'album',
           'TALB': 'album',
           'TBP': 'bpm',
           'TBP ': 'bpm',
           'TBPM': 'bpm',
           'TCM': 'composer',
           'TCM ': 'composer',
           'TCMP': 'compilation',
           'TCO': 'genre',
           'TCO ': 'genre',
           'TCOM': 'composer',
           'TCON': 'genre',
           'TCP': 'compilation',
           'TCP ': 'compilation',
           'TDRC': 'year',
           'TEN': 'encoder',
           'TEN ': 'encoder',
           'TENC': 'encoder',
           'TIT1': 'grouping',
           'TIT2': 'name',
           'TIT3': 'video_description',
           'TP1': 'artist',
           'TP1 ': 'artist',
           'TP2': 'album_artist',
           'TP2 ': 'album_artist',
           'TPA': 'disk',
           'TPA ': 'disk',
           'TPE1': 'artist',
           'TPE2': 'album_artist',
           'TPOS': 'disk',
           'TRCK': 'track',
           'TRK': 'track',
           'TRK ': 'track',
           'TS2': 'sort_album_artist',
           'TS2 ': 'sort_album_artist',
           'TSA': 'sort_album',
           'TSA ': 'sort_album',
           'TSC': 'sort_composer',
           'TSC ': 'sort_composer',
           'TSO2': 'sort_album_artist',
           'TSOA': 'sort_album',
           'TSOC': 'sort_composer',
           'TSOP': 'sort_artist',
           'TSOT': 'sort_name',
           'TSP': 'sort_artist',
           'TSP ': 'sort_artist',
           'TST': 'sort_name',
           'TST ': 'sort_name',
           'TT1': 'grouping',
           'TT1 ': 'grouping',
           'TT2': 'name',
           'TT2 ': 'name',
           'TT3': 'video_description',
           'TT3 ': 'video_description',
           'TYE': 'year',
           'TYE ': 'year',
           'TYER': 'year',
           'ULT': '_lyrics',
           'ULT ': '_lyrics',
           'USLT': '_lyrics'}

# bitrate matrix for mp3 header
BITRATES = [
    [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0],
    [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0],
    [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
    [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0],
    [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]]

# sample rate matrix for mp3 header
SRATES = [[11025, 12000, 8000, 0], 0,
          [22050, 24000, 16000, 0],
          [44100, 48000, 32000, 0]]

# encoding and terminator for id3v2 text strings
ENCODINGS = {'\x00': ('latin-1', '\x00'),
             '\x01': ('utf-16', '\x00\x00'),
             '\x02': ('utf-16-be', '\x00\x00'),
             '\x03': ('utf-8', '\x00')}

# map of type id's to attributes for IFF formats
IFFIDS = {'ANNO': 'comment',
          'AUTH': 'artist',
          'IART': 'artist',
          'ICMT': 'comment',
          'ICRD': 'year',
          'IGNR': 'genre',
          'INAM': 'name',
          'ISFT': 'encoder',
          'NAME': 'name'}

# map of mpeg4 atoms to atom type/attribute
ATOMS = {'moov': (ATOM_CONTAINER1, None),
         'moov.udta': (ATOM_CONTAINER1, None),
         'moov.udta.meta': (ATOM_CONTAINER2, None),
         'moov.udta.meta.ilst': (ATOM_CONTAINER1, None),
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

# pre-defined id3v1 genres according to winamp/mediasoft
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

# map of vorbis tags to attributes
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
              'volume adjustment': 'volume',
              'volume_adjustment': 'volume',
              'volumeadjustment': 'volume',
              'year': 'year'}

# fields to display on dump
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

    """Base taglib error"""


class ValidationError(TaglibError):

    """Raised when invalid attribute is set"""


class DecodeError(TaglibError):

    """Raised on decoding error"""


class EncodeError(TaglibError):

    """Raised on encoding error"""


class InvalidMedia(TaglibError):

    """Raised if media format is invalid"""


class MetadataContainer(MutableMapping):

    """Metadata container that maps attributes to dictionary keys"""

    types = {}

    def __init__(self, *args, **kwargs):
        """Accepts same arguments as dict()"""
        self.__dict__.update(dict(*args, **kwargs))

    def getdict(self, attr, key):
        """Get managed dict item"""
        dict = self[attr]
        if dict:
            if key == ANYITEM:
                key = sorted(dict)[0]
            return dict.get(key)

    def setdict(self, attr, key, val):
        """Set managed dict item"""
        if val is None:
            self.deldict(attr, key)
        else:
            dict = self[attr]
            if not dict:
                dict = self[attr] = {}
            dict[key] = val

    def deldict(self, attr, key):
        """Delete managed dict item"""
        dict = self[attr]
        if dict:
            if key == ANYITEM:
                key = sorted(dict)[0]
            try:
                del dict[key]
                if not dict:
                    self[attr] = None
            except KeyError:
                pass

    def __getattribute__(self, key):
        """Safe attribute access"""
        try:
            return super(MetadataContainer, self).__getattribute__(key)
        except AttributeError:
            if key not in self.types:
                raise

    def __setattr__(self, key, val):
        """Validate attributes on set"""
        if key in self.types:
            try:
                val = self.validate(val, self.types[key])
            except ValidationError, error:
                raise ValidationError('%s: %s' % (key, error))
        super(MetadataContainer, self).__setattr__(key, val)

    def __delattr__(self, key):
        """Safe attribute delete"""
        try:
            super(MetadataContainer, self).__delattr__(key)
        except AttributeError:
            if key not in self.types:
                raise

    def __getitem__(self, key):
        """Map dictionary access to attributes"""
        return self.__getattribute__(key)

    def __setitem__(self, key, val):
        """Map dictionary access to attributes"""
        self.__setattr__(key, val)

    def __delitem__(self, key):
        """Map dictionary access to attributes"""
        self.__delattr__(key)

    def __iter__(self):
        """Yields set metadata attributes"""
        for key in sorted(self.types):
            if not key.startswith('_') and self[key]:
                yield key

    def __len__(self):
        """Size of set metadata attributes"""
        return sum(1 for key in self.__iter__())

    def __repr__(self):
        """String representation showing set metadata attributes"""
        val = ', '.join('%s=%r' % item for item in self.iteritems())
        val = (': ' if val else '') + val
        return '<%s object at 0x%x%s>' % (type(self).__name__, id(self), val)

    @staticmethod
    def validate(val, type):
        """Validate attributes"""
        return val


class FlexOpen(object):

    """Flexible open context that accepts path, descriptor, or fileobj"""

    def __init__(self, file, mode='rb', close=True):
        """
        file    - a path, descriptor, or fileobj
        mode    - mode to open with (does not apply to fileobj's)
        close   - if a path is provided, whether to close when done
        """
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
            raise TypeError('file must be a path, descriptor, or fileobj')
        self.close = close

    def __enter__(self):
        """Enter open context"""
        if self.external:
            self.pos = self.fp.tell()
        return self.fp

    def __exit__(self, *args):
        """Exit open context"""
        if self.external:
            self.fp.seek(self.pos, os.SEEK_SET)
        elif self.close:
            self.fp.close()


class BaseDecoder(MetadataContainer):

    """Base decoder class"""

    types = TYPES
    format = None
    close = True

    def __init__(self, file, offset=0):
        """
        file    - path, descriptor, or fileobj
        offset  - position to start decoding
        """
        with FlexOpen(file, 'rb', self.close) as fp:
            try:
                self.decode(fp, offset)
            except SafeErrors, error:
                raise InvalidMedia(error)
            if not self.close:
                self.fp = fp

    @property
    def image_sample(self):
        """Returns first 512 bytes of image, its format, and size"""
        image = self.image
        if image:
            val = StringIO()
            image.save(val, image.format)
            return val.getvalue()[:512], image.format, image.size

    def decode(self, fp, offset=0):
        """Decode open file starting at offset"""
        raise DecodeError('not implemented')

    def dump(self, width=72, stream=None, filename=None, encoding=None):
        """Dump metadata to stream (default STDOUT)"""
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
                    type = TEXT
                else:
                    val = self[attr]
                    type = self.types[attr]
                if not val:
                    continue
                if type == BOOL:
                    val = 'Yes'
                elif type in (GENRE, TEXT):
                    val = val.encode(encoding, 'ignore')
                elif type == IMAGE:
                    val = '%dx%d %s Image' % (val.size[0], val.size[1],
                                              val.format)
                elif type in (INT32, UINT16, UINT32):
                    val = str(val)
                elif type == UINT16X2:
                    val = ('%d/%d' % val).replace('/0', '')
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
        """Test equality of metadata between two files"""
        if not isinstance(other, BaseDecoder):
            return NotImplemented
        for attr, type in TYPES.iteritems():
            if type in (DICT, IDICT):
                continue
            if type == IMAGE:
                val1, val2 = self.image_sample, other.image_sample
            else:
                val1, val2 = self[attr], other[attr]
            if val1 != val2:
                return False
        return True

    def __ne__(self, other):
        """Test inequality of metadata between two files"""
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    @staticmethod
    def getbufread(fp, size=None, blocksize=None):
        """Create callback to perform buffered I/O"""
        pos = fp.tell()
        if size is None:
            fp.seek(0, os.SEEK_END)
            size = fp.tell()
            fp.seek(pos, os.SEEK_SET)
        if blocksize is None:
            blocksize = BLOCKSIZE
        state = {'size': size, 'pos': pos, 'buf': []}
        bufsize = lambda: sum(len(item) for item in state['buf'])

        def read(size):
            if size > state['size']:
                size = state['size']
            while bufsize() < size:
                val = fp.read(blocksize)
                if not val:
                    break
                state['buf'].append(val)
            val = ''.join(state['buf'])
            val, state['buf'] = val[:size], [val[size:]]
            read = len(val)
            state['pos'] += read
            if read < size:
                state['size'] = 0
            else:
                state['size'] -= read
            return val

        read.state = state
        return read

    @staticmethod
    def validate(val, type):
        """Validate/transform attributes"""
        if val is not None:
            if type in (UINT16, INT32, UINT32):
                if isinstance(val, basestring):
                    try:
                        val = int(val)
                    except (ValueError, TypeError), error:
                        raise ValidationError(error)
                elif not isinstance(val, (int, long)):
                    raise ValidationError('must be an integer')
            elif type == GENRE:
                if isinstance(val, (int, long)):
                    try:
                        val = GENRES[val]
                    except IndexError, error:
                        raise ValidationError(error)
                    if not val:
                        raise ValidationError('unknown genre')
            if type in (TEXT, GENRE):
                if isinstance(val, str):
                    val = list(val)
                    while val and val[-1] in ' \x00':
                        val.pop()
                    val = ''.join(val).decode('ascii', 'ignore')
                elif not isinstance(val, unicode):
                    val = unicode(val)
                val = val.strip()
            elif type == UINT16:
                if val < 0 or val > 0xffff:
                    raise ValidationError('out of range of uint16')
            elif type == INT32:
                if val < -0x80000000 or val > 0x7fffffff:
                    raise ValidationError('out of range of int32')
            elif type == UINT16X2:
                if isinstance(val, basestring):
                    val = [int(item) if item.isdigit() else 0
                           for item in val.split('/')]
                elif isinstance(val, (int, long)):
                    val = val, 0
                if isinstance(val, list):
                    val = tuple(val)
                elif not isinstance(val, tuple):
                    raise ValidationError('must be 2 uint16s')
                if len(val) == 1:
                    val = val[0], 0
                elif len(val) != 2:
                    raise ValidationError('must be 2 uint16s')
                if val[0] == -1:
                    val = 0, val[1]
                if val[1] == -1:
                    val = val[0], 0
                if (not isinstance(val[0], (int, long)) or
                    not isinstance(val[1], (int, long)) or
                    val[0] < 0 or val[0] > 0xffff or
                    val[1] < 0 or val[1] > 0xffff):
                    raise ValidationError('must be 2 uint16s')
                if val == (0, 0):
                    val = None
            elif type == BOOL:
                if isinstance(val, basestring):
                    val = val.lower().strip()
                    if val in ('yes', 'y', 'true', 't', 'on', '1', '\x01'):
                        val = True
                    elif val in ('no', 'n', 'false', 'f', 'off', '0', '\x00'):
                        val = False
                    else:
                        raise ValidationError('must be boolean')
                elif isinstance(val, (int, long)):
                    val = bool(val)
                elif not isinstance(val, bool):
                    raise ValidationError('must be boolean')
            elif type == IMAGE:
                if Image is None:
                    raise ValidationError('PIL support required')
                if not isinstance(val, ImageFile):
                    try:
                        with FlexOpen(val, 'rb') as fp:
                            val = Image.open(fp)
                            val.load()
                    except (TypeError, IOError), error:
                        raise ValidationError(error)
            elif type in (DICT, IDICT):
                if not isinstance(val, dict):
                    raise ValidationError('must be a dictionary')
            elif type == UINT32:
                if val < 0 or val > 0xffffffff:
                    raise ValidationError('out of range of uint32')
            else:
                raise NotImplementedError(type)
            if not val and type not in (DICT, IDICT):
                val = None
        return val


class MP3(BaseDecoder):

    """Decodes ID3v1/ID3v2 tags on MP3 files"""

    format = 'mp3'
    close = False
    genre_re = re.compile(r'^\((\d+)\)$')
    ptype_re = re.compile(r'[\x00-\x14]')

    def get_image(self, key=ANYITEM):
        """Get named image (default: any)"""
        if key != ANYITEM:
            key = (key,)
        val = self.getdict('_image', key)
        if val:
            return val[0]

    def set_image(self, val, key=None, ptype=3):
        """Set named image"""
        val = self.validate(val, IMAGE)
        if val:
            val = val, ptype
        self.setdict('_image', (key,), val)

    def del_image(self, key=ANYITEM):
        """Delete named image"""
        if key != ANYITEM:
            key = (key,)
        self.deldict('_image', key)

    image = property(get_image, set_image, del_image)

    def get_comment(self, lang='eng', key=None):
        """Get named comment"""
        if key != ANYITEM:
            key = lang, key
        return self.getdict('_comment', key)

    def set_comment(self, val, lang='eng', key=None):
        """Set named comment"""
        if key == GAPLESS:
            val = self.validate(val, BOOL)
        else:
            val = self.validate(val, TEXT)
        self.setdict('_comment', (lang, key), val)

    def del_comment(self, lang='eng', key=None):
        """Delete named comment"""
        if key != ANYITEM:
            key = lang, key
        self.deldict('_comment', key)

    comment = property(get_comment, set_comment, del_comment)

    def get_gapless(self):
        """Get gapless playback setting"""
        return self.get_comment(key=GAPLESS)

    def set_gapless(self, val):
        """Set gapless playback setting"""
        self.set_comment(val, key=GAPLESS)

    def del_gapless(self):
        """Delete gapless playback setting"""
        self.del_comment(key=GAPLESS)

    gapless = property(get_gapless, set_gapless, del_gapless)

    def get_lyrics(self, lang='eng', key=None):
        """Get named lyrics"""
        if key != ANYITEM:
            key = lang, key
        return self.getdict('_lyrics', key)

    def set_lyrics(self, val, lang='eng', key=None):
        """Set named lyrics"""
        val = self.validate(val, TEXT)
        self.setdict('_lyrics', (lang, key), val)

    def del_lyrics(self, lang='eng', key=None):
        """Delete named lyrics"""
        if key != ANYITEM:
            key = lang, key
        self.deldict('_lyrics', key)

    lyrics = property(get_lyrics, set_lyrics, del_lyrics)

    def get_mp3data(self, blocksize=None):
        """Yields blocks of mp3data"""
        if not self.has_mp3data:
            raise ValueError('no mp3 data')
        if blocksize is None:
            blocksize = BLOCKSIZE
        pos = self.fp.tell()
        try:
            self.fp.seek(self.mp3start)
            bytes_left = self.mp3size
            while bytes_left:
                size = bytes_left if blocksize > bytes_left else blocksize
                val = self.fp.read(size)
                if not val:
                    break
                bytes_left -= len(val)
                yield val
        finally:
            self.fp.seek(pos, os.SEEK_SET)

    mp3data = property(get_mp3data)

    def decode(self, fp, offset=0):
        """Decodes ID3v1/ID3v2 tags on open MP3 file"""
        try:
            self.decode_id3v1(fp)
        except SafeErrors:
            pass
        mp3end = fp.tell()
        try:
            self.decode_id3v2(fp, offset)
        except SafeErrors:
            pass
        self.seekmp3(fp)
        self.has_mp3data = True
        self.mp3start = fp.tell()
        self.mp3size = mp3end - self.mp3start

    def decode_id3v1(self, fp):
        """Decode ID3v1 tag"""
        try:
            fp.seek(-128, os.SEEK_END)
            val = unpack('3s30s30s30s4s30sB', fp.read(128))
            if val[0] != 'TAG':
                raise DecodeError('no id3v1 tag')
            fp.seek(-128, os.SEEK_END)
        except SafeErrors:
            fp.seek(0, os.SEEK_END)
            raise
        try:
            self.name, self.artist, self.album, self.year = val[1:5]
        except ValidationError:
            pass
        if val[5][28] in ' \x00' and val[5][29] != '\x00':
            self.comment = val[5][:28]
            self.track = ord(val[5][29])
        else:
            self.comment = val[5]
        self.genre = val[6]

    def decode_id3v2(self, fp, offset=0):
        """Decode ID3v2 tag"""
        try:
            fp.seek(offset, os.SEEK_SET)
        except IOError:
            fp.seek(0, os.SEEK_SET)
            raise
        read = self.getbufread(fp, size=10)
        try:
            head, version, revision, flags, size = unpack('3s3B4s', read(10))
            if head != 'ID3':
                raise DecodeError('no id3v2 tag')
            if version == 2:
                taglen, sizelen, flagslen, syncsafe = 3, 3, 0, False
            elif version == 3:
                taglen, sizelen, flagslen, syncsafe = 4, 4, 2, False
            elif version == 4:
                taglen, sizelen, flagslen, syncsafe = 4, 4, 2, True
            else:
                raise DecodeError('unknown version: %d' % version)
            if revision:
                raise DecodeError('unknown revision: %d' % revision)
            if flags:
                raise DecodeError('unknown flags: %d' % flags)
        except SafeErrors:
            fp.seek(offset, os.SEEK_SET)
            raise
        read.state['size'] = self.getint(size, syncsafe=True)
        while read.state['size']:
            try:
                tag = read(taglen)
                size = self.getint(read(sizelen), syncsafe)
                flags = self.getint(read(flagslen))
                attr = ID3TAGS.get(tag)
                if not attr:
                    read(size)
                    raise DecodeError('unknown tag: %s' % tag)
                val = read(size)
                if not val:
                    raise DecodeError('empty value')
                type = self.types[attr]
                key = None
                if type in (BOOL, GENRE, TEXT, UINT16, UINT16X2):
                    val = self.getstr(val)
                if not val:
                    raise DecodeError('empty value')
                if type == DICT:
                    ebyte, lang = val[0], val[1:4]
                    key, val = self.split(val[4:], ENCODINGS[ebyte][1], 1)
                    key = lang, self.validate(self.getstr(ebyte + key), TEXT)
                    val = self.validate(self.getstr(ebyte + val), TEXT)
                    if key[1] == GAPLESS:
                        val = self.validate(val, BOOL)
                elif type == GENRE:
                    try:
                        val = int(self.genre_re.search(val).group(1))
                    except AttributeError:
                        pass
                elif type == IDICT:
                    ebyte, val = val[0], val[1:]
                    if len(self.ptype_re.split(val, 1)[0]) == 3:
                        val = val[3:]
                    else:
                        val = self.split(val, offset=1)[1]
                    ptype, val = ord(val[0]), val[1:]
                    key, val = self.split(val, ENCODINGS[ebyte][1], offset=1)
                    key = (self.validate(self.getstr(ebyte + key), TEXT),)
                    val = self.validate(StringIO(val), IMAGE), ptype
                elif type == INT32:
                    if tag == 'RVA':
                        pos, bits = ord(val[0]) & 1, ord(val[1])
                        i, r = divmod(bits, 8)
                        if r:
                            i += 1
                        val = self.getint(val[2:2 + i])
                        if not pos:
                            val *= -1
                    else:
                        val = self.split(val, offset=1)[1][1:3]
                        val = int(unpack('>h', val)[0] * RVA2FACTOR)
                if not val:
                    raise DecodeError('empty value')
                if key:
                    self.setdict(attr, key, val)
                else:
                    self[attr] = val
            except SafeErrors:
                pass
        fp.seek(read.state['pos'], os.SEEK_SET)

    def save(self, file):
        """Save mp3 with updated metadata to file"""
        if not self.has_mp3data:
            raise EncodeError('no mp3 data')
        with FlexOpen(file, 'wb') as fp:
            self.encode(fp)
        return fp

    def encode(self, fp):
        """Encode mp3/metadata to open file"""
        id3v1 = id3v2 = False
        for tag in ID3V2TAGS:
            attr = ID3TAGS[tag]
            if self[attr]:
                id3v2 = True
                if attr in ID3V1FIELDS:
                    id3v1 = True
                    break
        if id3v2:
            self.encode_id3v2(fp)
        for val in self.mp3data:
            fp.write(val)
        if id3v1:
            self.encode_id3v1(fp)

    def encode_id3v1(self, fp):
        """Encode ID3v1 tag to open file"""
        val = ['TAG', self.pad(self.name), self.pad(self.artist),
               self.pad(self.album), self.pad(self.year, 4)]
        if self.track and self.track[0] and self.track[0] < 256:
            val += [self.pad(self.comment, 28), '\x00', chr(self.track[0])]
        else:
            val.append(self.pad(self.comment))
        if self.genre and self.genre in GENRES:
            val.append(chr(GENRES.index(self.genre)))
        else:
            val.append('\xff')
        fp.write(''.join(val))

    def encode_id3v2(self, fp):
        """Encode ID3v2 tag to open file"""
        head = fp.tell()
        fp.write(pack('>3s3BL', 'ID3', 2, 0, 0, 0))
        size = 0
        for val in self.id3v2_tags:
            fp.write(val)
            size += len(val)
        pos = fp.tell()
        try:
            fp.seek(head + 6)
            size = unpack('4B', pack('>L', size))
            fp.write(pack('4B',
                          ((size[1] >> 5) & 0x07) | (size[0] << 3) & 0x7f,
                          ((size[2] >> 6) & 0x03) | (size[1] << 2) & 0x7f,
                          ((size[3] >> 7) & 0x01) | (size[2] << 1) & 0x7f,
                          ((size[3] >> 0) & 0x7f)))
        finally:
            fp.seek(pos, os.SEEK_SET)

    @property
    def id3v2_tags(self):
        """Yields encoded ID3v2 tags"""
        for tag, val in self.id3v2_items:
            yield tag + pack('>L', len(val))[1:] + val

    @property
    def id3v2_items(self):
        """Yields encoded ID3v2 tag/value pairs"""
        for tag in ID3V2TAGS:
            attr = ID3TAGS[tag]
            try:
                val = self[attr]
                if not val:
                    raise EncodeError('empty value')
                type = self.types[attr]
                if type == BOOL:
                    val = u'1'
                elif type == DICT:
                    for key, val in val.iteritems():
                        lang, key = key
                        if key == GAPLESS:
                            if val:
                                val = u'1'
                            else:
                                raise EncodeError('storing false')
                        key2, val2 = self.mkstr(key), self.mkstr(val)
                        if key2[0] == val2[0]:
                            key, val = key2, val2
                        elif key2[0] == '\x01':
                            key, val = key2, self.mkstr(val, utf16=True)
                        else:
                            key, val = self.mkstr(key, utf16=True), val2
                        yield tag, key[0] + lang + key[1:] + val[1:]
                    continue
                elif type == GENRE:
                    if val in GENRES:
                        val = u'(%d)' % GENRES.index(val)
                elif type == IDICT:
                    for key, val in val.iteritems():
                        key = self.mkstr(key[0])
                        val, ptype = val
                        fmt = 'JPG' if val.format == 'JPEG' else val.format[:3]
                        data = StringIO()
                        val.save(data, val.format)
                        yield tag, (key[0] + fmt + chr(ptype) +
                                    key[1:] + data.getvalue())
                    continue
                elif type == INT32:
                    if val < 0:
                        dir = '\x00'
                        val *= -1
                    else:
                        dir = '\x03'
                    val = list(pack('>L', val))
                    while val and val[0] == '\x00':
                        val.pop(0)
                    val = ''.join(val)
                    i = len(val)
                    val = dir + chr(i * 8) + val * 2 + '\x00' * i * 2
                elif type == UINT16:
                    val = unicode(val)
                elif type == UINT16X2:
                    val = (u'%d/%d' % val).replace('/0', '')
                if isinstance(val, unicode):
                    val = self.mkstr(val)
                yield tag, val
            except SafeErrors:
                pass

    @staticmethod
    def getint(val, syncsafe=False):
        """Convert bytes to integer"""
        val = unpack('>L', '\x00' * (4 - len(val)) + val)[0]
        if syncsafe:
            val = (((val & 0x0000007f) >> 0) | ((val & 0x00007f00) >> 1) |
                   ((val & 0x007f0000) >> 2) | ((val & 0x7f000000) >> 3))
        return val

    @classmethod
    def getstr(cls, val):
        """Decode ID3v2 text field"""
        encoding, term = ENCODINGS[val[0]]
        return cls.split(val[1:], term)[0].decode(encoding, 'ignore')

    @staticmethod
    def mkstr(val, utf16=False):
        """Encode ID3v2 text field"""
        if val is None:
            val = u''
        if not utf16:
            try:
                return '\x00%s\x00' % val.encode('latin-1')
            except UnicodeEncodeError:
                pass
        return '\x01\xff\xfe%s\x00\x00' % val.encode('utf-16-le')

    @staticmethod
    def split(val, term='\x00', offset=0):
        """Split string without breaking utf-16 encoding"""
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

    @staticmethod
    def pad(val, size=30):
        """Pad ID3v1 text field"""
        if val is None:
            val = ''
        elif isinstance(val, unicode):
            val = val.encode('ascii', 'ignore')
        elif not isinstance(val, unicode):
            val = str(val)
        val = val.strip()[:size]
        return val + '\x00' * (size - len(val))

    @classmethod
    def seekmp3(cls, fp, samplesize=None):
        """Seek to first valid MP3 frame"""
        if samplesize is None:
            samplesize = MAXJUNK
        pos = fp.tell()
        try:
            sample = fp.read(samplesize)
            i = 0
            while i < len(sample) - 3:
                i = sample.find('\xff', i)
                if i == -1:
                    raise DecodeError('no syncword found')
                try:
                    next = i + cls.head_check(sample[i:i + 4])
                    cls.head_check(sample[next:next + 4])
                    pos += i
                    break
                except SafeErrors:
                    pass
                i += 1
        finally:
            fp.seek(pos, os.SEEK_SET)

    @staticmethod
    def head_check(head):
        """Return frame length if 4-byte value is an MP3 header"""
        head = unpack('>L', head)[0]
        if head & 0xffe00000 != 0xffe00000:
            raise DecodeError('no syncword')
        version = (head >> 19) & 3
        layer = (head >> 17) & 3
        if version == 3 and layer == 3:
            bitrate_index = 0
        elif version == 3 and layer == 2:
            bitrate_index = 1
        elif version == 3 and layer == 1:
            bitrate_index = 2
        elif version in (0, 2) and layer == 3:
            bitrate_index = 3
        elif version in (0, 2) and layer in (2, 1):
            bitrate_index = 4
        else:
            raise DecodeError('invalid version/layer')
        bitrate = BITRATES[bitrate_index][(head >> 12) & 15] * 1000.0
        if not bitrate:
            raise DecodeError('invalid bitrate')
        srate = SRATES[version][(head >> 10) & 3]
        if not srate:
            raise DecodeError('invalid sample rate')
        padding = (head >> 9) & 1
        if layer == 3:
            return int((12 * bitrate / srate + padding) * 4)
        else:
            return int(144 * bitrate / srate + padding)


class IFF(MP3):

    """Decodes metadata on RIFF/AIFF files"""

    format = 'iff'

    def decode(self, fp, offset=0):
        """Decodes metadata on open RIFF/AIFF file"""
        self.has_mp3data = False
        try:
            self.decode_id3v1(fp)
        except SafeErrors:
            pass
        self.decode_iff(fp, offset, fp.tell())

    def decode_iff(self, fp, pos, end, fmt=None):
        """Walk IFF chunks and decode metadata"""
        while pos < end:
            fp.seek(pos, os.SEEK_SET)
            id = fp.read(4)
            if fmt is None:
                if id == 'RIFF':
                    fmt = '<L'
                elif id in ('FORM', 'LIST', 'CAT '):
                    fmt = '>L'
                else:
                    raise DecodeError('unknown format')
            size = unpack(fmt, fp.read(4))[0]
            pos += 8
            try:
                if id in ('RIFF', 'FORM', 'LIST', 'CAT '):
                    self.decode_iff(fp, pos + 4, pos + size, fmt)
                elif id in IFFIDS:
                    val = list(fp.read(size).decode('utf-8', 'ignore'))
                    while val and val[-1] == '\x00':
                        val.pop()
                    self[IFFIDS[id]] = ''.join(val)
                elif id == 'ID3 ':
                    self.decode_id3v2(fp, offset=pos)
                elif id == 'data':
                    self.seekmp3(fp)
                    self.mp3start = fp.tell()
                    self.mp3size = pos + size - self.mp3start
                    self.has_mp3data = True
            except SafeErrors:
                pass
            pos += size + size % 2


class M4A(BaseDecoder):

    """Decodes atom metadata on M4A/MP4 files"""

    format = 'm4a'

    def decode(self, fp, offset=0):
        """Decodes atom metadata on open M4A/MP4 file"""
        self.decode_atoms(fp, offset, next='ftyp')

    def decode_atoms(self, fp, pos=None, end=None, base=None, next=None):
        """Walk atom structure and decode metadata"""
        if pos is None:
            pos = fp.tell()
        if end is None:
            fp.seek(0, os.SEEK_END)
            end = fp.tell()
        if base is None:
            base = []
        while pos < end:
            fp.seek(pos, os.SEEK_SET)
            size, name = unpack('>L4s', fp.read(8))
            path = base + [name]
            tag = '.'.join(path)
            if next:
                if tag != next:
                    raise DecodeError('unexpected atom: %s' % tag)
                next = None
            try:
                if tag not in ATOMS:
                    raise DecodeError('unsupported atom: %s' % tag)
                atom, attr = ATOMS[tag]
                if atom == ATOM_CONTAINER1:
                    self.decode_atoms(fp, pos + 8, pos + size, path)
                elif atom == ATOM_CONTAINER2:
                    self.decode_atoms(fp, pos + 12, pos + size, path)
                elif atom == ATOM_DATA:
                    type = self.types[attr]
                    fp.seek(pos + 24, os.SEEK_SET)
                    val = fp.read(size - 24)
                    if type == GENRE:
                        if len(val) == 2 and val[0] in '\x00\x01':
                            val = unpack('>H', val)[0] - 1
                    elif type == IMAGE:
                        val = StringIO(val)
                    elif type == TEXT:
                        val = val.decode('utf-8')
                    elif type == UINT16:
                        if name == 'tmpo':
                            val = unpack('>H', val)[0]
                    elif type == UINT16X2:
                        val = unpack('>2H', val[2:6])
                    elif type == UINT32:
                        val = unpack('>L', val)[0]
                    self[attr] = val
            except SafeErrors:
                pass
            if not size:
                break
            pos += size


class VorbisComment(BaseDecoder):

    """Providers decoder for VorbisComment tag"""

    def decode_vorbis(self, fp, size):
        """Decode VorbisComment"""
        read = self.getbufread(fp, size)
        getint = lambda: unpack('<L', read(4))[0]
        getstr = lambda: read(getint()).decode('utf-8')
        self.encoder = getstr()
        for i in xrange(getint()):
            key, val = getstr().split('=', 1)
            attr = VORBISTAGS.get(key.lower())
            if attr:
                try:
                    self[attr] = val
                except ValidationError:
                    pass


class FLAC(VorbisComment):

    """Decodes VorbisComment on FLAC files"""

    format = 'flac'

    def decode(self, fp, offset=0):
        """Decodes VorbisComment on open FLAC file"""
        fp.seek(offset, os.SEEK_SET)
        if fp.read(4) != 'fLaC':
            raise DecodeError('no flac header found')
        pos = fp.tell()
        fp.seek(0, os.SEEK_END)
        end = fp.tell()
        while pos < end:
            fp.seek(pos, os.SEEK_SET)
            head, size = unpack('B3s', fp.read(4))
            size = unpack('>L', '\x00' + size)[0]
            if head & 127 == 4:
                self.decode_vorbis(fp, size)
            if head & 128:
                break
            pos = pos + 4 + size


class OGG(VorbisComment):

    """Decodes VorbisComment on OGG files"""

    format = 'ogg'

    def decode(self, fp, offset=0):
        """Decodes VorbisComment on open OGG file"""
        pos = offset
        fp.seek(0, os.SEEK_END)
        end = fp.tell()
        while pos < end:
            fp.seek(pos, os.SEEK_SET)
            head = unpack('>4s2BQ3LB', fp.read(27))
            if head[0] != 'OggS' or head[1]:
                raise DecodeError('invalid ogg page')
            last = head[7] - 1
            packets = [0]
            for i, segment in enumerate(fp.read(head[7])):
                segment = ord(segment)
                packets[-1] += segment
                if segment < 255 and i != last:
                    packets.append(0)
            for packet in packets:
                if fp.read(7) == '\x03vorbis':
                    self.decode_vorbis(fp, packet - 8)
            pos = pos + 27 + head[7] + sum(packets)
            if head[2] & 4:
                break


def tagopen(file, offset=0):
    """Open file and decode metadata starting at offset"""
    for cls in DECODERS:
        try:
            return cls(file, offset)
        except InvalidMedia:
            pass
    raise InvalidMedia('no suitable decoder found')


DECODERS = FLAC, M4A, OGG, IFF, MP3

SafeErrors = (IOError, OSError, EOFError, StructError,
              ValidationError, DecodeError, EncodeError)
