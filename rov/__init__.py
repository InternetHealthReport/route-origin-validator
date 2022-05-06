#!/usr/bin/env python3

import appdirs
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
import csv

import urllib
import urllib.request as request
from contextlib import closing

CACHE_DIR = appdirs.user_cache_dir('rov', 'IHR')

DEFAULT_IRR_DIR = CACHE_DIR+'/db/irr/'
IRR_FNAME = '*.gz'
DEFAULT_RPKI_DIR = CACHE_DIR+'/db/rpki/'
RPKI_FNAME = '*.*'
DEFAULT_DELEGATED_DIR = CACHE_DIR+'/db/delegated/'
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
RPKI_ARCHIVE_URLS = [ 
        'https://ftp.ripe.net/ripe/rpki/afrinic.tal/{year:04d}/{month:02d}/{day:02d}/roas.csv',
        'https://ftp.ripe.net/ripe/rpki/apnic.tal/{year:04d}/{month:02d}/{day:02d}/roas.csv',
        'https://ftp.ripe.net/ripe/rpki/arin.tal/{year:04d}/{month:02d}/{day:02d}/roas.csv',
        'https://ftp.ripe.net/ripe/rpki/lacnic.tal/{year:04d}/{month:02d}/{day:02d}/roas.csv',
        'https://ftp.ripe.net/ripe/rpki/ripencc.tal/{year:04d}/{month:02d}/{day:02d}/roas.csv',
        ]
DEFAULT_DELEGATED_URLS = [ 
        'https://www.nro.net/wp-content/uploads/delegated-stats/nro-extended-stats'
        ]

def guess_ta_name(url):
    rirs = ['afrinic', 'arin', 'lacnic', 'ripencc', 'apnic']

    for rir in rirs:
        if rir+'.tal' in url:
            return rir

    return 'unknown'


class ROV(object):

    def __init__( self, irr_urls=DEFAULT_IRR_URLS, rpki_urls=DEFAULT_RPKI_URLS, 
            delegated_urls=DEFAULT_DELEGATED_URLS, irr_dir=DEFAULT_IRR_DIR, 
            rpki_dir=DEFAULT_RPKI_DIR, delegated_dir=DEFAULT_DELEGATED_DIR ):
        """Initialize ROV object with databases URLs"""

        self.urls = {}
        self.urls[irr_dir] = irr_urls
        self.urls[rpki_dir] = rpki_urls
        self.urls[delegated_dir] = delegated_urls

        self.irr_dir = irr_dir
        self.rpki_dir = rpki_dir
        self.delegated_dir = delegated_dir

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

    def load_delegated(self):
        """Parse the delegated data, load prefix data in a radix tree and ASN
        data in a IntervalDict"""

        intervals = defaultdict(list)
        for fname in glob.glob(self.delegated_dir+DELEGATED_FNAME):
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
                    elif rec['type'] == 'ipv4' or rec['type'] == 'ipv6':

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

                        # compute prefix length
                        if rec['type'] == 'ipv4':
                            prefix_len = int(32-math.log2(rec['value']))
                        elif rec['type'] == 'ipv6':
                            prefix_len = int(rec['value'])

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


    def load_rpki(self):
        """Parse the RPKI data and load it in a radix tree"""

        for fname in glob.glob(self.rpki_dir+RPKI_FNAME):
            sys.stderr.write(f'Loading: {fname}\n')
            with open(fname, 'r') as fd:
                if fname.endswith('.json'):
                    data = json.load(fd)
                elif fname.endswith('.csv'):
                    ta = guess_ta_name(fname)
                    data = {'roas': [] }
                    rows = csv.reader(fd, delimiter=',')

                    # skip the header
                    next(rows)

                    for row in rows:
                        # Assume the same format as the one in RIPE archive
                        # https://ftp.ripe.net/ripe/rpki/
                        maxLength = int(row[3]) if row[3] else int(row[2].rpartition('/')[2])
                        data['roas'].append( {
                            'uri': row[0],
                            'asn': row[1],
                            'prefix': row[2],
                            'maxLength': maxLength,
                            'startTime': row[4],
                            'endTime': row[5],
                            'ta': ta
                            } )

                else:
                    sys.stderr.write('Error: Unknown file format for RPKI data!')
                    return 


                for rec in data['roas']:
                    if( isinstance(rec['asn'], str) 
                            and rec['asn'].startswith('AS') ):
                        asn = int(rec['asn'][2:])
                    else:
                        asn = int(rec['asn'])

                    rnode = self.roas['rpki'].search_exact(rec['prefix'])
                    if rnode is None:
                        rnode = self.roas['rpki'].add(rec['prefix'])

                    if asn not in rnode.data:
                        rnode.data[asn] = []

                    roa_details = {
                            'maxLength': rec['maxLength'],
                            'ta': rec['ta']
                        }

                    if 'startTime' in rec:
                        roa_details['startTime'] = rec['startTime']
                        roa_details['endTime'] = rec['endTime']

                    if 'uri' in rec:
                        roa_details['uri'] = rec['uri']

                    rnode.data[asn].append( roa_details )

    def load_irr(self):
        """Parse the IRR data and load it in a radix tree"""

        for fname in glob.glob(self.irr_dir+IRR_FNAME):
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
                            try:
                                asn = int(rec['origin'][2:].partition('#')[0])
                            except ValueError:
                                sys.stderr.write(f'Error in {fname}, invalid ASN!\n{rec}\n')
                                continue

                            if rnode is None:
                                rnode = self.roas['irr'].add(rec['route'])

                            if asn not in rnode.data:
                                rnode.data[asn] = []

                            rnode.data[asn].append({
                                'descr':  rec.get('descr', '') ,
                                'source': rec.get('source', '') 
                                })

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

        origin_asn = int(origin_asn)
        prefix_in = prefix.strip()
        prefixlen = int(prefix_in.partition('/')[2])
        states = {}

        # include the query in the results
        states['query'] = {
                'prefix': prefix,
                'asn': origin_asn
                }

        # Check routing status
        for name, rtree in self.roas.items():
            # Default to NotFound 
            selected_roa = None
            status = {'status': 'NotFound'}

            rnodes = rtree.search_covering(prefix)
            if len(rnodes) > 0:
                # report invalid with the first roa of the most specific prefix
                rnode = rnodes[0]
                status = {'status': 'Invalid', 'prefix': rnode.prefix}
                key = next(iter(rnode.data.keys()))
                selected_roa = rnode.data[key][0]

            for rnode in rnodes:
                if origin_asn in rnode.data: # Matching ASN

                    for roa in rnode.data[origin_asn]:
                        status = {'status': 'Invalid,more-specific', 'prefix': rnode.prefix}
                        selected_roa = roa

                        # check prefix length
                        if( ('maxLength' in roa and roa['maxLength'] >= prefixlen) 
                            or (prefix_in == rnode.prefix)):

                                status = {'status': 'Valid', 'prefix': rnode.prefix}
                                selected_roa = roa

                                break

                    if status['status'] == 'Valid':
                        break

            # copy roa attributes in the status report
            if selected_roa is not None:
                for k,v in selected_roa.items():
                    status[k] = v

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

        Overwrite=True clears the cache before downloading new files.
        Set overwrite=False to download only missing databases."""

        # TODO implement automatic update based on dates

        for folder, urls in self.urls.items():

            # Clear the whole cache if overwrite
            if overwrite and os.path.exists(folder):
                shutil.rmtree(folder)

            # Create the folder if needed
            os.makedirs(folder, exist_ok=True)

            for url in urls:
                # Check if the file already exists
                fname = url.rpartition('/')[2]

                # all files from RIPE's RPKI archive have the same name
                # 'roas.csv', change it with the tal name
                if fname == 'roas.csv':
                    fname = guess_ta_name(url)+'.csv'

                if os.path.exists(folder+fname) and not overwrite:
                    continue

                sys.stderr.write(f'Downloading: {url}\n')
                try:
                    with closing(request.urlopen(url)) as r:
                        with open(folder+fname, 'wb') as f:
                            shutil.copyfileobj(r, f)
                except urllib.error.URLError:
                    sys.stderr.write(f'Error {url} is not available.\n')

