"""
In-memory stand-in for simple_salesforce.Salesforce used by the guided-flow tests.

install() replaces simple_salesforce.Salesforce (and SalesforceLogin users of it)
so the app can be driven by streamlit.testing.v1.AppTest without network access.
Every login is recorded in LOGINS; every bulk/REST write in WRITES.
"""

import re
import uuid

import simple_salesforce

LOGINS = []   # (username, domain)
WRITES = []   # (object, operation, records)
QUERIES = []  # soql strings

BAD_PASSWORD = "bad-password"
# username -> 'auth' (wrong credentials) or 'network' (connection error) for the next logins
FAIL_MODE = {}


def _field(name, ftype='string', label=None, nillable=True, createable=True, updateable=True,
           unique=False, external_id=False, length=255, picklist=None, reference_to=None,
           defaulted=False):
    return {
        'name': name, 'label': label or name, 'type': ftype, 'nillable': nillable,
        'createable': createable, 'updateable': updateable, 'unique': unique,
        'externalId': external_id, 'length': length, 'defaultedOnCreate': defaulted,
        'calculated': False, 'autoNumber': False, 'idLookup': name == 'Id',
        'picklistValues': [{'value': v, 'label': v, 'active': True} for v in (picklist or [])],
        'referenceTo': reference_to or [], 'relationshipName': None,
        'precision': 18 if ftype in ('currency', 'double') else 0, 'scale': 2 if ftype == 'currency' else 0,
        'digits': 0, 'inlineHelpText': None, 'nameField': name == 'Name',
    }


DESCRIBES = {
    'Account': {
        'name': 'Account', 'label': 'Account', 'custom': False, 'createable': True, 'queryable': True,
        'recordTypeInfos': [{'name': 'Master', 'recordTypeId': '012000000000000AAA', 'available': True,
                             'defaultRecordTypeMapping': True, 'master': True, 'active': True}],
        'fields': [
            _field('Id', 'id', nillable=False, createable=False, updateable=False),
            _field('Name', 'string', 'Account Name', nillable=False),
            _field('AccountNumber', 'string', 'Account Number', length=40),
            _field('Phone', 'phone', 'Account Phone', length=40),
            _field('Industry', 'picklist', picklist=['Agriculture', 'Banking', 'Energy']),
            _field('AnnualRevenue', 'currency', 'Annual Revenue'),
            _field('External_Key__c', 'string', 'External Key', unique=True, external_id=True),
            _field('CreatedDate', 'datetime', 'Created Date', nillable=False, createable=False,
                   updateable=False, defaulted=True),
        ],
    },
    'Contact': {
        'name': 'Contact', 'label': 'Contact', 'custom': False, 'createable': True, 'queryable': True,
        'recordTypeInfos': [],
        'fields': [
            _field('Id', 'id', nillable=False, createable=False, updateable=False),
            _field('LastName', 'string', 'Last Name', nillable=False),
            _field('Email', 'email'),
            _field('AccountId', 'reference', 'Account ID', reference_to=['Account']),
        ],
    },
}

RECORDS = {
    'Account': [
        {'Id': '001000000000001AAA', 'Name': 'Acme', 'AccountNumber': 'A-1', 'Phone': '5551234567',
         'Industry': 'Energy', 'AnnualRevenue': 10.0, 'External_Key__c': 'K1'},
        {'Id': '001000000000002AAA', 'Name': 'Globex', 'AccountNumber': 'A-2', 'Phone': '5559876543',
         'Industry': 'Banking', 'AnnualRevenue': 20.0, 'External_Key__c': 'K2'},
    ],
    'Organization': [{'Id': '00D000000000001AAA', 'Name': 'Fake Org'}],
}


def _records_for(soql):
    match = re.search(r'\bFROM\s+(\w+)', soql, re.IGNORECASE)
    obj = match.group(1) if match else ''
    rows = RECORDS.get(obj, [])
    return [{'attributes': {'type': obj, 'url': f'/services/data/v59.0/sobjects/{obj}/{r["Id"]}'}, **r}
            for r in rows]


class _FakeSFType:
    def __init__(self, name):
        self.name = name

    def describe(self):
        if self.name not in DESCRIBES:
            raise Exception(f"sObject type '{self.name}' is not supported.")
        return DESCRIBES[self.name]

    def create(self, record):
        WRITES.append((self.name, 'create', [record]))
        return {'id': '001' + uuid.uuid4().hex[:15].upper(), 'success': True, 'errors': []}


class _FakeBulkType:
    def __init__(self, name):
        self.name = name

    def _write(self, operation, records):
        WRITES.append((self.name, operation, list(records)))
        return [{'success': True, 'created': operation != 'update', 'id': '001' + uuid.uuid4().hex[:15].upper(),
                 'errors': []} for _ in records]

    def insert(self, records, batch_size=None, **kwargs):
        return self._write('insert', records)

    def update(self, records, batch_size=None, **kwargs):
        return self._write('update', records)

    def upsert(self, records, external_id_field=None, batch_size=None, **kwargs):
        return self._write('upsert', records)

    def query(self, soql, **kwargs):
        QUERIES.append(soql)
        return [{k: v for k, v in r.items() if k != 'attributes'} for r in _records_for(soql)]


class _FakeBulk:
    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return _FakeBulkType(name)


class FakeSalesforce:
    def __init__(self, username=None, password=None, security_token=None, domain=None, **kwargs):
        mode = FAIL_MODE.get(username)
        if password == BAD_PASSWORD or mode == 'auth':
            raise simple_salesforce.exceptions.SalesforceAuthenticationFailed(
                'INVALID_LOGIN', 'Invalid username, password, security token; or user locked out.')
        if mode == 'network':
            import requests
            raise requests.exceptions.ConnectionError("HTTPSConnectionPool(host='login.salesforce.com'): "
                                                      "Max retries exceeded")
        LOGINS.append((username, domain))
        self.username = username
        self.sf_instance = 'fake.my.salesforce.com'
        self.session_id = uuid.uuid4().hex
        self.base_url = 'https://fake.my.salesforce.com/services/data/v59.0/'
        self.sf_version = '59.0'
        self.bulk = _FakeBulk()

    def query(self, soql, **kwargs):
        QUERIES.append(soql)
        records = _records_for(soql)
        return {'records': records, 'totalSize': len(records), 'done': True}

    def query_all(self, soql, **kwargs):
        return self.query(soql)

    def describe(self):
        return {'sobjects': [{'name': n, 'label': d['label'], 'custom': d['custom'], 'queryable': True,
                              'createable': True, 'updateable': True, 'deletable': True}
                             for n, d in DESCRIBES.items()]}

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return _FakeSFType(name)


def install():
    simple_salesforce.Salesforce = FakeSalesforce
    try:
        import simple_salesforce.api as api
        api.Salesforce = FakeSalesforce
    except Exception:
        pass


def reset():
    LOGINS.clear()
    WRITES.clear()
    QUERIES.clear()
    FAIL_MODE.clear()
