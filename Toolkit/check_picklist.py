import sys, json
sys.path.append('c:/DM_toolkit')
with open('c:/DM_toolkit/Services/linkedservices.json') as f:
    creds = json.load(f)
from simple_salesforce import Salesforce
c = creds['AkashDev']
sf = Salesforce(username=c['username'], password=c['password'], security_token=c['security_token'], domain=c.get('domain','login'))
desc = sf.Account.describe()
for field in desc['fields']:
    if field['name'] == 'Industry':
        values = field.get('picklistValues', [])
        print(f'Total picklist values: {len(values)}')
        print('Keys in each entry:', list(values[0].keys()) if values else 'none')
        print('First 5 entries:')
        for v in values[:5]:
            print(' ', v)
        print('...')
        print('Last 5 entries:')
        for v in values[-5:]:
            print(' ', v)
        break
