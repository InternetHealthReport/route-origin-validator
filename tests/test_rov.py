import pytest
import rov

@pytest.fixture(scope='session')
def default_rov():
    drov = rov.ROV(rov.DEFAULT_IRR_URLS, rov.DEFAULT_RPKI_URLS)
    drov.download_databases(False)
    drov.load_databases()
    
    return drov


@pytest.fixture(scope='session')
def archive_rov():
    year, month, day = '2018', '10', '02'
    rpki_dir = rov.DEFAULT_RPKI_DIR+'/2018/10/02/'
    rpki_url = []
    for url in rov.RPKI_ARCHIVE_URLS:
        rpki_url.append( url.format(year=int(year), month=int(month), day=int(day)) )

    arov = rov.ROV(rov.DEFAULT_IRR_URLS, rpki_urls=rpki_url, rpki_dir=rpki_dir)
    arov.download_databases(False)
    arov.load_databases()
    
    return arov


# RPKI statues
def test_rpki_notfound(default_rov):
    validation_results = default_rov.check('10.1.0.0/16', 15169)
    assert validation_results['rpki']['status'] == 'NotFound'
   
def test_rpki_invalid(default_rov):
    validation_results = default_rov.check('8.8.8.0/24', 123)
    assert validation_results['rpki']['status'] == 'Invalid'
    
def test_rpki_morespecific(default_rov):
    validation_results = default_rov.check('8.8.8.0/25', 15169)
    assert validation_results['rpki']['status'] == 'Invalid,more-specific'
    
def test_rpki_valid(default_rov):
    validation_results = default_rov.check('8.8.8.0/24', 15169)
    assert validation_results['rpki']['status'] == 'Valid'
    

# IRR statues
def test_irr_notfound(default_rov):
    validation_results = default_rov.check('10.1.0.0/16', 15169)
    assert validation_results['irr']['status'] == 'NotFound'
    
def test_irr_invalid(default_rov):
    validation_results = default_rov.check('8.8.8.0/24', 123)
    assert validation_results['irr']['status'] == 'Invalid'
    
def test_irr_morespecific(default_rov):
    validation_results = default_rov.check('8.8.8.0/25', 15169)
    assert validation_results['irr']['status'] == 'Invalid,more-specific'
    
def test_irr_valid(default_rov):
    validation_results = default_rov.check('8.8.8.0/24', 15169)
    assert validation_results['irr']['status'] == 'Valid'
    

# delegated statues
def test_delegated_prefix_reserved(default_rov):
    validation_results = default_rov.check('10.0.0.0/8', 15169)
    assert validation_results['delegated']['prefix']['status'] == 'reserved'
    
def test_delegated_prefix_assigned(default_rov):
    validation_results = default_rov.check('8.8.8.0/24', 15169)
    assert validation_results['delegated']['prefix']['status'] == 'assigned'
    
def test_delegated_asn_reserved(default_rov):
    validation_results = default_rov.check('8.8.8.0/24', 0)
    assert validation_results['delegated']['asn']['status'] == 'reserved'
    
def test_delegated_asn_assigned(default_rov):
    validation_results = default_rov.check('8.8.8.0/24', 15169)
    assert validation_results['delegated']['asn']['status'] == 'assigned'


# archive RPKI
def test_archive_notfound(archive_rov):
    validation_results = archive_rov.check('10.1.0.0/16', 15169)
    assert validation_results['rpki']['status'] == 'NotFound'
    
def test_archive_invalid(archive_rov):
    validation_results = archive_rov.check('1.1.1.0/24', 123)
    assert validation_results['rpki']['status'] == 'Invalid'
    
def test_archive_morespecific(archive_rov):
    validation_results = archive_rov.check('1.1.1.0/25', 13335)
    assert validation_results['rpki']['status'] == 'Invalid,more-specific'
    
def test_archive_valid(archive_rov):
    validation_results = archive_rov.check('1.1.1.0/24', 13335)
    assert validation_results['rpki']['status'] == 'Valid'
    
    
# Others 
def test_query(default_rov):
    res = default_rov.check('8.8.8.0/24', 15169)
    assert res["query"]["prefix"] == '8.8.8.0/24'
    assert res["query"]["asn"] == 15169
    
