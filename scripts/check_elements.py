import json
with open("test.json") as f:
    data = json.load(f)
elements = data["sanitized_dom"]["elements"]
for e in elements:
    print(f"  {e['element_id']}: role={e.get('role')} enabled={e.get('enabled', 'MISSING')}")
