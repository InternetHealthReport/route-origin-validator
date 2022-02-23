# route-origin-validator
Offline Internet route origin validation using RPKI, IRR, and RIRs delegated databases

This python library is designed for validating a large number of routes in one shot. It downloads IRR, RPKI, and delegated databases to avoid network overhead for each query.

## Installation
 ```
pip install rov
```

## Usage:
Both the command line and python interfaces return status codes for each data
source.
For IRR and RPKI the possible status codes are:
- NotFound
- Invalid
- Invalid,more-specific
- Valid

For delegated we expect globally reachable resources to be 'assigned'. Resources that are 'reserved' and 'available' should be considered as bogons.

### Command line
The command line interface should be used only for a few queries, each query will reload all databases.
```zsh
>> rov 8.8.8.0/24 15169 
{
    "query": {
        "prefix": "8.8.8.0/24",
        "asn": 15169
    },
    "irr": {
        "status": "Valid",
        "prefix": "8.8.8.0/24",
        "descr": "Google",
        "source": "RADB"
    },
    "rpki": {
        "status": "Valid",
        "prefix": "8.8.8.0/24",
        "maxLength": 24,
        "ta": "arin"
    },
    "delegated": {
        "prefix": {
            "status": "assigned",
            "prefix": "8.0.0.0/9",
            "date": "19921201",
            "registry": "arin",
            "country": "US"
        },
        "asn": {
            "status": "assigned",
            "registry": "arin"
        }
    }
}

>> rov 10.1.0.0/16 15169
{
    "query": {
         "prefix": "10.1.0.0/16",
         "asn": "15169"
    },
    "irr": {
        "status": "NotFound"
    },
    "rpki": {
        "status": "NotFound"
    },
    "delegated": {
        "prefix": {
            "status": "reserved",
            "prefix": "10.0.0.0/8",
            "date": "19940301",
            "registry": "iana",
            "country": "ZZ"
        },
        "asn": {
            "status": "assigned",
            "registry": "arin"
        }
    }
}
```

Past RPKI data can also be queried.
Currently this only works for RPKI, so the results mix past and recent data. 
In the following example, the rpki results are for 2018/10/01 but other results 
correspond to the exectution date.
```zsh
>> rov 8.8.8.0/24 15169 --rpki_archive 2018/10/01
{
    "query": {
        "prefix": "8.8.8.0/24",
        "asn": 15169
    },
    "irr": {
        "status": "Valid",
        "prefix": "8.8.8.0/24",
        "descr": "Google",
        "source": "RADB"
    },
    "rpki": {
        "status": "NotFound"
    },
    "delegated": {
        "prefix": {
            "status": "assigned",
            "prefix": "8.0.0.0/9",
            "date": "19921201",
            "registry": "arin",
            "country": "US"
        },
        "asn": {
            "status": "assigned",
            "registry": "arin"
        }
    }
}
```

### In python 
For large batches use the python library as follows:

```python
import json
from rov import ROV

# list of routes we want to validate
routes = [
    ['1.1.1.0/24', 13335],
    ['2.2.2.0/24', 3215],
    ['3.3.3.0/24', 16509],
    ['4.4.4.0/24', 198949],
    ['5.5.5.0/24', 6805],
    ]
    

rov = ROV()

# optional: download latest databases if needed
rov.download_databases()

# read databases, this may take a minute or so
rov.load_databases()

# this should be super fast
for prefix, asn in routes:
    state = rov.check(prefix, asn)
    print(prefix)
    print(json.dumps(state, indent=4))

#1.1.1.0/24
#{
#    "query": {
#        "prefix": "1.1.1.0/24",
#        "asn": 13335
#    },
#    "irr": {
#        "status": "Valid",
#        "prefix": "1.1.1.0/24",
#        "descr": "APNIC Research and Development\n6 Cordelia St",
#        "source": "APNIC"
#    },
#    "rpki": {
#        "status": "Valid",
#        "prefix": "1.1.1.0/24",
#        "maxLength": 24,
#        "ta": "apnic"
#    },
#    "delegated": {
#        "prefix": {
#            "status": "assigned",
#            "prefix": "1.1.1.0/24",
#            "date": "20110811",
#            "registry": "apnic",
#            "country": "AU"
#        },
#        "asn": {
#            "status": "assigned",
#            "registry": "arin"
#        }
#    }
#}
#2.2.2.0/24
#{
#    "query": {
#        "prefix": "2.2.2.0/24",
#        "asn": 3215
#    },
#    "irr": {
#        "status": "Invalid,more-specific",
#        "prefix": "2.2.0.0/16",
#        "descr": "France Telecom Orange",
#        "source": "RIPE"
#    },
#    "rpki": {
#        "status": "Invalid,more-specific",
#        "prefix": "2.0.0.0/12",
#        "maxLength": 17,
#        "ta": "ripe"
#    },
#    "delegated": {
#        "prefix": {
#            "status": "assigned",
#            "prefix": "2.0.0.0/12",
#            "date": "20100712",
#            "registry": "ripencc",
#            "country": "FR"
#        },
#        "asn": {
#            "status": "assigned",
#            "registry": "ripencc"
#        }
#    }
#}
#3.3.3.0/24
#{
#    "query": {
#        "prefix": "3.3.3.0/24",
#        "asn": 16509
#    },
#    "irr": {
#        "status": "NotFound"
#    },
#    "rpki": {
#        "status": "Valid",
#        "prefix": "3.0.0.0/10",
#        "maxLength": 24,
#        "ta": "arin"
#    },
#    "delegated": {
#        "prefix": {
#            "status": "assigned",
#            "prefix": "3.0.0.0/9",
#            "date": "20171220",
#            "registry": "arin",
#            "country": "US"
#        },
#        "asn": {
#            "status": "assigned",
#            "registry": "arin"
#        }
#    }
#}
#4.4.4.0/24
#{
#    "query": {
#        "prefix": "4.4.4.0/24",
#        "asn": 198949
#    },
#    "irr": {
#        "status": "Valid",
#        "prefix": "4.4.4.0/24",
#        "descr": "dima_training",
#        "source": "RADB"
#    },
#    "rpki": {
#        "status": "NotFound"
#    },
#    "delegated": {
#        "prefix": {
#            "status": "assigned",
#            "prefix": "4.0.0.0/9",
#            "date": "19921201",
#            "registry": "arin",
#            "country": "US"
#        },
#        "asn": {
#            "status": "assigned",
#            "registry": "ripencc"
#        }
#    }
#}
#5.5.5.0/24
#{
#    "query": {
#        "prefix": "5.5.5.0/24",
#        "asn": 6805
#    },
#    "irr": {
#        "status": "Invalid,more-specific",
#        "prefix": "5.4.0.0/14",
#        "descr": "Telefonica Germany GmbH & Co. OHG",
#        "source": "RIPE"
#    },
#    "rpki": {
#        "status": "Invalid,more-specific",
#        "prefix": "5.4.0.0/14",
#        "maxLength": 14,
#        "ta": "ripe"
#    },
#    "delegated": {
#        "prefix": {
#            "status": "assigned",
#            "prefix": "5.4.0.0/14",
#            "date": "20120425",
#            "registry": "ripencc",
#            "country": "DE"
#        },
#        "asn": {
#            "status": "assigned",
#            "registry": "ripencc"
#        }
#    }
#}
```

## Acknowledgements

This project is supported by MANRS/ISOC, thanks!
