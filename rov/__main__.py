#!/usr/bin/env python3

import argparse
import json

from rov import ROV
from rov import DEFAULT_RPKI_URLS
from rov import DEFAULT_IRR_URLS

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
