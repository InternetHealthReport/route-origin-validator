#!/usr/bin/env python3

import appdirs
import argparse
from collections import defaultdict
import glob
import gzip
import json
import os
import math
import portion
import radix
import shutil
import sys

import urllib.request as request
from contextlib import closing

CACHE_DIR = appdirs.user_cache_dir('rov', 'IHR')

IRR_DIR = CACHE_DIR+'/db/irr/'
IRR_FNAME = '*.gz'
RPKI_DIR = CACHE_DIR+'/db/rpki/'
RPKI_FNAME = '*.json'
DELEGATED_DIR = CACHE_DIR+'/db/delegated/'
DELEGATED_FNAME = '*-stats'

DEFAULT_IRR_URLS = [
        # RADB
        'ftp://ftp.radb.net/radb/dbase/altdb.db.gz',
        'ftp://ftp.radb.net/radb/dbase/aoltw.db.gz',
        #'ftp://ftp.radb.net/radb/dbase/arin-nonauth.db.gz',
        #'ftp://ftp.radb.net/radb/dbase/arin.db.gz',
        'ftp://ftp.radb.net/radb/dbase/bboi.db.gz',
        'ftp://ftp.radb.net/radb/dbase/bell.db.gz',
        'ftp://ftp.radb.net/radb/dbase/canarie.db.gz',
        'ftp://ftp.radb.net/radb/dbase/easynet.db.gz',
        'ftp://ftp.radb.net/radb/dbase/jpirr.db.gz',
        'ftp://ftp.radb.net/radb/dbase/level3.db.gz',
        'ftp://ftp.radb.net/radb/dbase/nestegg.db.gz',
        'ftp://ftp.radb.net/radb/dbase/nttcom.db.gz',
        'ftp://ftp.radb.net/radb/dbase/openface.db.gz',
        'ftp://ftp.radb.net/radb/dbase/ottix.db.gz',
        'ftp://ftp.radb.net/radb/dbase/panix.db.gz',
        'ftp://ftp.radb.net/radb/dbase/radb.db.gz',
        'ftp://ftp.radb.net/radb/dbase/reach.db.gz',
        'ftp://ftp.radb.net/radb/dbase/rgnet.db.gz',
        'ftp://ftp.radb.net/radb/dbase/risq.db.gz',
        'ftp://ftp.radb.net/radb/dbase/rogers.db.gz',
        'ftp://ftp.radb.net/radb/dbase/tc.db.gz',
        # RIRs
        'ftp://ftp.arin.net/pub/rr/arin-nonauth.db.gz',
        'ftp://ftp.arin.net/pub/rr/arin.db.gz',
        'ftp://ftp.afrinic.net/pub/dbase/afrinic.db.gz',
        'ftp://ftp.apnic.net/pub/apnic/whois/apnic.db.route.gz',
        'https://ftp.lacnic.net/lacnic/irr/lacnic.db.gz',
        'ftp://ftp.ripe.net/ripe/dbase/split/ripe-nonauth.db.route.gz',
        'ftp://ftp.ripe.net/ripe/dbase/split/ripe-nonauth.db.route6.gz',
        'ftp://ftp.ripe.net/ripe/dbase/split/ripe.db.route.gz',
        'ftp://ftp.ripe.net/ripe/dbase/split/ripe.db.route6.gz',
        ]
DEFAULT_RPKI_URLS = [ 
        'https://rpki.gin.ntt.net/api/export.json'
        ]
DEFAULT_DELEGATED_URLS = [ 
        'https://www.nro.net/wp-content/uploads/delegated-stats/nro-extended-stats'
        ]

class ROV(object):

    def __init__(self, irr_urls=DEFAULT_IRR_URLS, rpki_urls=DEFAULT_RPKI_URLS, 
            delegated_urls=DEFAULT_DELEGATED_URLS):
        """Initialize ROV object with databases URLs"""

        self.urls = {}
        self.urls[IRR_DIR] = irr_urls
        self.urls[RPKI_DIR] = rpki_urls
        self.urls[DELEGATED_DIR] = delegated_urls

        self.roas = {
                'irr': radix.Radix(), 
                'rpki': radix.Radix()
                }
        self.delegated = {
                'prefix': radix.Radix(),
                'asn': portion.IntervalDict()
                }

    def load_databases(self):
        """Load databases into memory. Also download databases if it is not 
        available locally."""

        # Make sure we have databases to load
        self.download_databases(overwrite=False)

        self.load_delegated()
        self.load_irr()
        self.load_rpki()

    def load_rpki(self):
        """Parse the RPKI data and load it in a radix tree"""

        for fname in glob.glob(RPKI_DIR+RPKI_FNAME):
            sys.stderr.write(f'Loading: {fname}\n')
            with open(fname, 'r') as fd:
                data = json.load(fd)

                for rec in data['roas']:
                    rnode = self.roas['rpki'].search_exact(rec['prefix'])
                    if rnode is None:
                        rnode = self.roas['rpki'].add(rec['prefix'])
                        rnode.data['asn'] = []

                    rnode.data['asn'].append(int(rec['asn'][2:]))
                    rnode.data['maxLength'] = rec['maxLength']
                    rnode.data['ta'] = rec['ta']

    def load_delegated(self):
        """Parse the delegated data, load prefix data in a radix tree and ASN
        data in a IntervalDict"""

        intervals = defaultdict(list)
        for fname in glob.glob(DELEGATED_DIR+DELEGATED_FNAME):
            sys.stderr.write(f'Loading: {fname}\n')
            # Read delegated-stats file. see documentation:
            # https://www.nro.net/wp-content/uploads/nro-extended-stats-readme5.txt
            fields_name = ['registry', 'cc', 'type', 'start', 'value', 'date', 'status']

            with open(fname, 'r') as fd:
                previous_rec = {f:'' for f in fields_name}
                start_interval = None

                for line in fd:
                    # skip comments
                    if line.strip().startswith('#'):
                        continue

                    # skip version and summary lines
                    fields_value = line.split('|')
                    if len(fields_value) < 8:
                        continue

                    # parse records
                    rec = dict( zip(fields_name, fields_value))
                    rec['value'] = int(rec['value'])

                    # ASN records
                    if rec['type'] == 'asn':
                        rec['start'] = int(rec['start'])
                        # first record
                        if start_interval is None:
                            start_interval = rec

                        else:
                            if( previous_rec['registry'] == rec['registry']
                                and previous_rec['status'] == rec['status']
                                and previous_rec['start']+previous_rec['value'] == rec['start']):

                                # continue reading the current interval
                                pass

                            else:
                                # store the previous interval and start a new one
                                key = '|'.join( [
                                            previous_rec['registry'],
                                            previous_rec['status']
                                            ])
                                interval = portion.closed( 
                                    start_interval['start'],
                                    previous_rec['start']+previous_rec['value']-1
                                    )
                                intervals[key].append(interval)

                                start_interval = rec

                        previous_rec = rec


                    # prefix records
                    elif rec['type'] == 'ipv4' or type == 'ipv6':

                        if previous_rec['type'] == 'asn':
                            # stored the last ASN interval
                            interval = portion.closed( 
                                start_interval['start'],
                                previous_rec['start']+previous_rec['value']-1
                                )
                            self.delegated['asn'][interval] = {
                                    'status': previous_rec['status'],
                                    'registry': previous_rec['registry']
                                    }
                            start_interval = None
                            previous_rec = {f:'' for f in fields_name}

                        prefix_len = int(32-math.log2(rec['value']))
                        prefix = f"{rec['start']}/{prefix_len}"
                        rnode = self.delegated['prefix'].search_exact(prefix)
                        if rnode is None:
                            rnode = self.delegated['prefix'].add(prefix)

                        rnode.data['status'] = rec['status']
                        rnode.data['prefix'] = prefix
                        rnode.data['date'] = rec['date']
                        rnode.data['registry'] = rec['registry']
                        rnode.data['country'] = rec['cc']


            # Fast way to populate IntervalDict
            for value, interval_list in intervals.items():

                registry, status = value.split('|')
                interval = portion.Interval(*interval_list)
                self.delegated['asn'][interval] = {
                    'status': status,
                    'registry': registry
                    }


    def load_irr(self):
        """Parse the IRR data and load it in a radix tree"""

        for fname in glob.glob(IRR_DIR+IRR_FNAME):
            sys.stderr.write(f'Loading: {fname}\n')
            with gzip.open(fname, 'rt', 
                    newline='\n', encoding='ISO-8859-1', errors='ignore') as fd:

                rec = {}
                field = ''
                for line in fd:
                    line = line.strip()

                    # Skip comments and remarks
                    if line.startswith('#') or line.startswith('%'):
                        continue

                    if line == '':
                        # Store the last record
                        if 'route' in rec:
                            if 'origin' not in rec:
                                # we may be in a 'descr' empty line
                                rec[field] += '\n'+line
                                continue

                            rnode = self.roas['irr'].search_exact(rec['route'])
                            if rnode is None:
                                rnode = self.roas['irr'].add(rec['route'])
                                rnode.data['asn'] = []

                            try:
                                asn = int(rec['origin'][2:].partition('#')[0])
                                rnode.data['asn'].append(asn)
                                rnode.data['descr'] = rec.get('descr', '') 
                                rnode.data['source'] = rec.get('source', '') 
                            except ValueError:
                                sys.stderr.write(f'Error in {fname}, invalid ASN!\n{rec}\n')

                        rec = {}
                        field = ''

                    else:
                        # New field
                        if ':' in line:
                            field, _, value = line.partition(":")
                            # Make same field name for IPv4 and IPv6
                            if field == 'route6':
                                field = 'route'
                            rec[field] = value.strip()
                        else:
                            # Multiline value
                            if field in rec and field in ['descr', 'addr']:
                                rec[field] += '\n'+line

    def lookup(self, prefix: int):
        """Search for entries for prefixes covering the given prefix.
        Return: dict will all matching entries"""

        res = defaultdict(dict)
        for name, rtree in self.roas.items():
            rnodes = rtree.search_covering(prefix)
            for rnode in rnodes:
                res[name][rnode.prefix] = rnode.data

        # Check status in delegated stats
        rnode = self.delegated['prefix'].search_best(prefix)
        if rnode is not None:
            res['delegated'] = rnode.data

        return res


    def check(self, prefix: str, origin_asn: int):
        """Compute the state of the given prefix, origin ASN pair"""

        # Check routing status
        prefix_in = prefix.strip()
        prefixlen = int(prefix_in.partition('/')[2])
        states = {}

        # include the query in the results
        states['query'] = {
                'prefix': prefix,
                'asn': origin_asn
                }

        for name, rtree in self.roas.items():
            # Default by NotFound or Invalid
            status = {'status': 'NotFound'}
            rnodes = rtree.search_covering(prefix)
            if len(rnodes) > 0:
                # report invalid with the most specific prefix
                rnode = rnodes[0]
                status = {'status': 'Invalid', 'prefix': rnode.prefix}
                for k,v in rnode.data.items():
                    status[k] = v

            for rnode in rnodes:
                if origin_asn in rnode.data['asn']: # Matching ASN
                    status = {'status': 'Invalid,more-specific', 'prefix': rnode.prefix}
                    for k,v in rnode.data.items():
                        status[k] = v

                    # check prefix length
                    if( ('maxLength' in rnode.data and rnode.data['maxLength'] >= prefixlen) 
                        or (prefix_in == rnode.prefix)):

                            status = {'status': 'Valid', 'prefix': rnode.prefix}
                            for k,v in rnode.data.items():
                                status[k] = v
                    
                            break

            states[name] = status
                        
        # Check status in delegated stats
        rnode = self.delegated['prefix'].search_best(prefix)
        prefix_data = {'status': 'NotFound'}
        if rnode is not None:
            prefix_data = rnode.data

        asn = self.delegated['asn'].get(int(origin_asn), {'status': 'NotFound'})

        states['delegated'] = {
                'prefix': prefix_data,
                'asn': asn
                }

        return states


    def download_databases(self, overwrite=True):
        """Download databases in the cache folder. 

        Set overwrite=False to download only missing databases."""

        # TODO implement automatic update based on 

        for folder, urls in self.urls.items():

            # Create the folder if needed
            os.makedirs(folder, exist_ok=True)

            for url in urls:
                # Check if the file already exists
                fname = url.rpartition('/')[2]
                if os.path.exists(folder+fname) and not overwrite:
                    continue

                sys.stderr.write(f'Downloading: {url}\n')
                with closing(request.urlopen(url)) as r:
                    with open(folder+fname, 'wb') as f:
                        shutil.copyfileobj(r, f)


# Command line application
def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Check the validity of the given prefix and origin ASN in \
                the RPKI and IRR database')
    parser.add_argument(
        'prefix', type=str, help='the prefix to validate')
    parser.add_argument(
        'ASN', type=int, help='the autonomous system number to validate')
    parser.add_argument(
            '--update', '-u', help='Fetch the latest databases', 
            action='store_true')
    parser.add_argument(
            '--irr_url', 
            help='URL to an IRR database dump (default to dumps from RADB)',
            default=DEFAULT_IRR_URLS)
    parser.add_argument(
            '--rpki_url',
            help='URL to a RPKI JSON endpoint (default=https://rpki.gin.ntt.net/api/export.json)',
            default=DEFAULT_RPKI_URLS)
    parser.add_argument(
            '--interactive',
            help='Open an interactive python shell with databases loaded in "rov".',
            action='store_true')
    args = parser.parse_args()


    # Main program
    rov = ROV(args.irr_url, args.rpki_url)

    # Download databases
    rov.download_databases(args.update)
    
    rov.load_databases()
    
    validation_results = rov.check(args.prefix, args.ASN)
    print(json.dumps(validation_results, indent=4))

    if args.interactive:
        import IPython
        IPython.embed()


if __name__ == "__main__":
    main()
