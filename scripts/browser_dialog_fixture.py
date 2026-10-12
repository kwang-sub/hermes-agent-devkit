#!/usr/bin/env python3
"""Loopback-only fixture server for the managed dialog probe."""
import argparse
from http.server import ThreadingHTTPServer
from probe_managed_dialog import FixtureHandler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True,type=int)
    args=parser.parse_args()
    if not 1<=args.port<=65535: parser.error('port must be 1..65535')
    with ThreadingHTTPServer(('127.0.0.1',args.port),FixtureHandler) as server:
        server.serve_forever()


if __name__=='__main__': main()
