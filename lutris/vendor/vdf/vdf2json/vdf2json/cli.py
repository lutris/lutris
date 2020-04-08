#!/usr/bin/env python

import argparse
import sys
import json
import vdf
import codecs
from collections import OrderedDict


def main():
    p = argparse.ArgumentParser(prog='vdf2json')

    p.add_argument('infile', nargs='?', type=argparse.FileType('r'),
                   default=sys.stdin, help="VDF")
    p.add_argument('outfile', nargs='?', type=argparse.FileType('w'),
                   default=sys.stdout, help="JSON (utf8)")
    p.add_argument('-p', '--pretty', help='pretty json output', action='store_true')
    p.add_argument('-ei', default='utf-8', type=str, metavar='encoding',
                   help='input encoding E.g.: utf8, utf-16le, etc')
    p.add_argument('-eo', default='utf-8', type=str, metavar='encoding',
                   help='output encoding E.g.: utf8, utf-16le, etc')

    args = p.parse_args()

    # unicode pain
    if args.infile is not sys.stdin:
        args.infile.close()
        args.infile = codecs.open(args.infile.name, 'r', encoding=args.ei)
    else:
        args.infile = codecs.getreader(args.ei)(sys.stdin)

    if args.outfile is not sys.stdout:
        args.outfile.close()
        args.outfile = codecs.open(args.outfile.name, 'w', encoding=args.eo)
    else:
        args.outfile = codecs.getwriter(args.eo)(sys.stdout)

    data = vdf.loads(args.infile.read(), mapper=OrderedDict)

    json.dump(data, args.outfile, indent=4 if args.pretty else 0, ensure_ascii=False)


if __name__ == '__main__':
    main()
