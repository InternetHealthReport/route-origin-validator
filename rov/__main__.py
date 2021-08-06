#!/usr/bin/env python3

import argparse
import json

from rov import ROV
from rov import DEFAULT_RPKI_URLS
from rov import DEFAULT_RPKI_DIR
from rov import DEFAULT_IRR_URLS
from rov import RPKI_ARCHIVE_URLS

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
            nargs='+',
            help='URL to an IRR database dump (default to dumps from RADB)',
            default=DEFAULT_IRR_URLS)
    parser.add_argument(
            '--rpki_url',
            nargs='+',
            help='URL to a RPKI JSON endpoint (default=https://rpki.gin.ntt.net/api/export.json) \
                    Ignored if --rpki_archive is set.',
            default=DEFAULT_RPKI_URLS)
    parser.add_argument(
            '--rpki_archive',
            help='Load past RPKI data for the given date (format is year/mo/da). \
                    The given date should be greater than 2018/04/04.',
            )
    parser.add_argument(
            '--interactive',
            help='Open an interactive python shell with databases loaded in "rov".',
            action='store_true')
    args = parser.parse_args()


    rpki_url = args.rpki_url
    rpki_dir = DEFAULT_RPKI_DIR 
    # Compute RPKI archive URLs if the rpki_archive option is given
    if args.rpki_archive is not None:
        year, month, day = args.rpki_archive.split('/')
        rpki_dir += '/'+args.rpki_archive+'/'
        rpki_url = []
        for url in RPKI_ARCHIVE_URLS:
            rpki_url.append( url.format(year=int(year), month=int(month), day=int(day)) )

    # Main program
    rov = ROV(args.irr_url, rpki_url, rpki_dir=rpki_dir)

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
