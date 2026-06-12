import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('status_post_complete.json', encoding='utf-16') as f:
    data = json.load(f)

print("MODULE:", data.get('module'))
print("STEP:", data.get('step'))
print("CONTENT:")
print(data.get('content'))
print("PROMPT SUGGESTIONS:")
print(json.dumps(data.get('prompt_suggestions'), indent=2))
print("DATA KEYS:", list(data.get('data', {}).keys()))
