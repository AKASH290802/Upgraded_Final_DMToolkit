import json
from simple_salesforce import Salesforce

# Load credentials from linkedservices.json
with open(r'C:\DM_toolkit\Services\linkedservices.json', 'r') as f:
    creds = json.load(f)

orgs = list(creds.keys())
print(f"Available orgs: {orgs}")

# Prompt user to select an org key (case-insensitive)
selected_org = input(f"Enter the org key to use from above: ").strip()
matched_org = None
for org in orgs:
    if selected_org.lower() == org.lower():
        matched_org = org
        break

if not matched_org:
    print(f"Invalid org key: {selected_org}")
    exit(1)

org_cred = creds[matched_org]

# Fetch client_id and client_secret if present
client_id = org_cred.get('client_id')
client_secret = org_cred.get('client_secret')

print(f'connected org: {matched_org}')
if client_id and client_secret:
    print(f"client_id: {client_id}")
    print(f"client_secret: {client_secret}")
else:
    print("client_id or client_secret not found in org credentials.")