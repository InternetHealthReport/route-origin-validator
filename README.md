# route-origin-validator
Offline Internet route origin validation using RPKI and IRR databases

This python library is designed for validating a large number of routes in one shot. It downloads IRR/RPKI databases to avoid network overhead for each query.

## Installation

TODO

## Usage:

### Command line
```zsh
>> python3 src/rov.py 8.8.8.0/24 15169 
{'irr': 'Valid', 'rpki': 'Valid'}

>> python3 src/rov.py 8.8.8.0/25 15169
{'irr': 'Invalid,more-specific', 'rpki': 'Invalid,more-specific'}

>> python3 src/rov.py 1.0.0.0/16 15169
{'irr': 'NotFound', 'rpki': 'NotFound'}
```

### In python (recommended for large batches)
```python
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

# download databases if needed, set update to True if you need fresh databases
rov.download_databases(update=False)

# reade databases, this may take a bit of time
rov.load_databases()

# this should be super fast
for prefix, asn in routes:
    state = rov.check(prefix, asn)
    print(prefix,  state)

# prints this:
# 1.1.1.0/24 {'irr': 'NotFound', 'rpki': 'Valid'}
# 2.2.2.0/24 {'irr': 'NotFound', 'rpki': 'Invalid,more-specific'}
# 3.3.3.0/24 {'irr': 'NotFound', 'rpki': 'Valid'}
# 4.4.4.0/24 {'irr': 'Valid', 'rpki': 'NotFound'}
# 5.5.5.0/24 {'irr': 'NotFound', 'rpki': 'Invalid,more-specific'}

    
```
