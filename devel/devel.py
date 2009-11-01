class devel(object):

    fakemp3 = '\xff\xf2\x14\x00' * 7

    @staticmethod
    def getgenres():
        from BeautifulSoup import BeautifulSoup
        from urllib import urlopen
        url = 'http://www.multimediasoft.com/amp3dj/help/amp3dj_00003e.htm'
        soup = BeautifulSoup(urlopen(url))
        genres = [None for _ in xrange(256)]
        for div in soup.body('div', 's0'):
            val = div.renderContents().replace('\xc2\xa0', ' ')
            val = val.replace('&nbsp;', ' ').replace('&amp;', '&')
            try:
                i, genre = val.split('-', 1)
                i = int(i)
            except ValueError:
                continue
            genres[i] = genre.strip()
        return [genre for genre in genres if genre]

    @staticmethod
    def dumplist(val, name):
        lead = '%s = [' % name
        isize = pos = len(lead)
        indent = ' ' * isize
        lines = [[lead]]
        last = len(val) - 1
        max = 80
        for i, val in enumerate(val):
            val = repr(val)
            val += ']' if i == last else ', '
            size = len(val)
            if pos + size > max:
                lines.append([indent])
                pos = isize
            lines[-1].append(val)
            pos += size
        print '\n'.join(''.join(line).rstrip() for line in lines)

    @staticmethod
    def types(isize=0):
        indent = ' ' * isize
        nsize = isize + 4
        next = ' ' * nsize
        for i, type in enumerate(map(devel.raw, sorted(set(TYPES.values())))):
            print '%s%sif type == %r:' % (indent, 'el' if i else '', type)
            print '%s# XXX' % next
            print '%spass' % next
            if not i:
                print "%sprint ' ' * %d + '# %%r' %% (val,)" % (next, nsize)

    @staticmethod
    def walk(dir, ext=None):
        for basedir, subdirs, filenames in os.walk(dir):
            try:
                subdirs.remove('.svn')
            except ValueError:
                pass
            for filename in filenames:
                if not ext or (os.path.splitext(filename)[1] == ext):
                    yield os.path.join(basedir, filename)

    class raw(object):
        def __init__(self, x): self.x = x
        def __repr__(self): return self.x

    @classmethod
    def mkparser(cls):
        spec = cls.mkspec('AAAAAAAA AAAB2CCD EEEEFFGH IIJJKLMM')
        pos = sum(len(i) for i in spec)
        for fmt in spec:
            fsize = len(fmt)
            pos -= fsize
            mask = 2 ** fsize - 1
            if mask > 255:
                mask = mask << pos
                shift = 0
            else:
                shift = pos
            line = ['%s=' % fmt[0]]
            if shift and mask:
                line.append('(')
            line.append('val')
            if shift:
                line.append(' >> %s' % cls.mkhex(shift))
                if mask:
                    line.append(')')
            if mask:
                line.append(' & %s' % cls.mkhex(mask))
            line.append(',')
            print ''.join(line)

    @staticmethod
    def mkspec(fmt):
        spec = []
        last = None
        for ch in fmt.replace(' ', ''):
            if ch != last:
                last = ch
                spec.append([])
            spec[-1].append(ch)
        return [''.join(i) for i in spec]

    @staticmethod
    def mkhex(val):
        val = hex(val).replace('0x', '').replace('L', '')
        return '0x' + '0' * (len(val) % 2) + val

    @classmethod
    def dump(cls, obj, name=None, isize=0):
        from pprint import pformat
        if isinstance(obj, basestring) and name is None:
            name = obj
            obj = globals()[name]
        lead = '%s = ' % name
        lsize = len(lead)
        data = pformat(obj, width=80 - lsize - isize)
        indent = ' ' * isize
        ldent = ' ' * lsize
        for i, line in enumerate(data.splitlines()):
            new = [indent]
            if i:
                new.append(ldent)
            else:
                new.append(lead)
            new.append(line)
            print ''.join(new)

    @classmethod
    def mkbitrates(cls):
        fmt = '''bits    V1,L1   V1,L2   V1,L3   V2,L1   V2, L2 & L3
                 0000    free    free    free    free    free
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
        cls.dump(cls.mktable(fmt), 'MP3_BITRATES')

    @classmethod
    def mksrates(cls):
        fmt = '''bits    MPEG1   MPEG2   MPEG2.5
                 00      44100   22050   11025
                 01      48000   24000   12000
                 10      32000   16000   8000'''
        table = cls.mktable(fmt)
        cls.dump(table, 'MP3_SRATES')

    @classmethod
    def mktable(cls, fmt):
        table = [[int(i) if i.isdigit() else 0 for i in line.split()[1:]]
                 for line in fmt.splitlines()[1:]]
        return cls.rotate(table)

    @classmethod
    def rotate(cls, table):
        return [[line[i] for line in table] for i in xrange(len(table[0]))]

    @staticmethod
    def testuint16x2():
        '''
        track   track/total     /total
        str     int
        tuple   list
        '''
        vals = 1, 0, -1
        tests = []
        for track in vals:
            strack = str(track)
            tests += [track,
                      strack,
                      strack + '/',
                      (track,),
                      (strack,),
                      [track],
                      [strack]]
            for total in vals:
                stotal = str(total)
                tests += [(track, total),
                          (track, stotal),
                          (strack, total),
                          (strack, stotal),
                          [track, total],
                          [track, stotal],
                          [strack, total],
                          [strack, stotal],
                          strack + '/' + stotal,
                          '/' + stotal]

        clean = []
        for test in tests:
            if test not in clean:
                clean.append(test)
        ok = [None, [0, 1], [1, 0], [1, 1]]
        bad = {}
        okcount = 0
        total = len(clean)
        for test in clean:
            result = Decoder.validate(test, UINT16X2)
            if result in ok:
                okcount += 1
            else:
                t = type(result).__name__
                foo = bad.setdefault(t, [])
                foo.append((test, result))
        print 'fixed: %d/%d' % (okcount, total)
        print 'bad: %s' % ' '.join(bad.keys())

    @classmethod
    def testvalid(cls):
        types = sorted(set(TYPES.values()))
        for type in types:
            def t(val):
                new = Decoder.validate(val, type)
                print '%r -> %r' % (val, new)
            if type == BOOL:
                t(True)
                t(1)
                t(0)
                t('yes')
                t('no')
                t('\x01')
                t(False)
                t('')
            elif type == DICT:
                t({})
            elif type == GENRE:
                t(20)
                t(19)
                t('hugs')
                t(u'dongs   \x00')
                t(3.0)
            elif type == IDICT:
                t({})
            elif type == IMAGE:
                t('samples/cry.png')
                with open('samples/cry.png') as fp:
                    t(fp)
                fd = os.open('samples/cry.png', os.O_RDONLY)
                t(fd)
            elif type == TEXT:
                t(object())
                t(u'hi..')
                t(None)
                t('')
                t(u'')
                t(3)
                t(u'\u1234')
            elif type == UINT16:
                t(3)
                t(3.4)
                t('3')
                t('33')
                t('')
                t('0')
                t(0)
            elif type == UINT16X2:
                # XXX
                pass
            elif type == UINT32:
                t(3.9999999997)
            elif type == VOLUME:
                t(-200)
                t(105)
                t('3')
                t(-40.0)
                t('')

    @staticmethod
    def getmaxflen():
        flens = set()
        for version in xrange(4):
            for layer in xrange(4):
                for bitrate in xrange(16):
                    for srate in xrange(4):
                        for padding in xrange(2):
                            val = (0xffe00000 | (version << 0x13) |
                                   (layer << 0x11) | (bitrate << 0x0c) |
                                   (srate << 0x0a) | (padding << 0x09))
                            head = Struct('>L').pack(val)
                            try:
                                flen = MP3.mp3framelen(head)
                                flens.add(flen)
                            except Errors:
                                pass
        print max(flens) * 2

    @staticmethod
    def mkfakemp3():
        flens = {}
        for version in xrange(4):
            for layer in xrange(4):
                for bitrate in xrange(16):
                    for srate in xrange(4):
                        for padding in xrange(2):
                            val = (0xffe00000 | (version << 0x13) |
                                   (layer << 0x11) | (bitrate << 0x0c) |
                                   (srate << 0x0a) | (padding << 0x09))
                            head = Struct('>L').pack(val)
                            try:
                                flen = MP3.mp3framelen(head)
                                flens.setdefault(flen, []).append(head)
                            except Errors:
                                pass
        key = min(flens.keys())
        head = flens[key][0]
        #print MP3.decode_mp3frame(Struct(">L").unpack(head)[0])
        i = 0
        while True:
            data = head * i
            try:
                MP3(StringIO(data))
                break
            except InvalidMedia:
                pass
            i += 1
        print '    fakemp3 = %r * %d' % (head, i)

    @staticmethod
    def testmp3():
        for file in devel.walk('/exports/mp3', '.mp3'):
            try:
                src = MP3(file)
                dst = MP3(src.dump(None))
                Metadata.compare(src, dst)
            except Errors, error:
                print >> sys.stderr, '%s: %s' % (file, error)
