import appdirs
import argparse
from collections import defaultdict
import glob
import gzip
import os
import radix
import shutil
import sys
import urllib.request as request
from contextlib import closing
import json

CACHE_DIR = appdirs.user_cache_dir('rov', 'IHR')

IRR_DIR = CACHE_DIR+'/db/irr/'
IRR_FNAME = '*.gz'
RPKI_DIR = CACHE_DIR+'/db/rpki/'
RPKI_FNAME = '*.json'

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

class ROV(object):

    def __init__(self, irr_urls=DEFAULT_IRR_URLS, rpki_urls=DEFAULT_RPKI_URLS):
        """Initialize ROV object with databases URLs"""

        self.urls = {}
        self.urls[IRR_DIR] = irr_urls
        self.urls[RPKI_DIR] = rpki_urls

        self.roas = {'irr': radix.Radix(), 'rpki': radix.Radix()}

    def load_databases(self):
        """Load databases into memory"""

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
                        if 'route' in rec:
                            if 'origin' not in rec:
                                # we may be in a 'descr' empty line
                                rec[field] += '\n'+line
                                continue

                            try:
                                rnode = self.roas['irr'].search_exact(rec['route'])
                                if rnode is None:
                                    rnode = self.roas['irr'].add(rec['route'])
                                    rnode.data['asn'] = []

                                try:
                                    asn = int(rec['origin'][2:].partition('#')[0])
                                    rnode.data['asn'].append(asn)
                                    rnode.data['desc'] = rec.get('descr', '') 
                                except ValueError:
                                    sys.stderr.write(f'Error in {fname}, invalid ASN!\n{rec}\n')
                            except Exception:
                                import IPython
                                IPython.embed()

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

        return res


    def check(self, prefix: str, origin_asn: int):
        """Compute the state of the given prefix, origin ASN pair"""

        prefix_in = prefix.strip()
        prefixlen = int(prefix_in.partition('/')[2])
        states = {}

        for name, rtree in self.roas.items():
            # Default by NotFound or Invalid
            rnodes = rtree.search_covering(prefix)
            if len(rnodes) > 0:
                states[name] = 'Invalid'
            else:
                states[name] = 'NotFound'

            for rnode in rnodes:
                if origin_asn in rnode.data['asn']: # Matching ASN
                    states[name] = 'Invalid,more-specific'
                    
                    # check prefix length
                    if( ('maxLength' in rnode.data and rnode.data['maxLength'] >= prefixlen) 
                        or (prefix_in == rnode.prefix)):
                            states[name] = 'Valid'
                            break
                        
        return states


    def download_databases(self, overwrite=False):
        """Download databases in the data folder"""
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


if __name__ == "__main__":
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
    print(validation_results)

    if args.interactive:
        import IPython
        IPython.embed()
