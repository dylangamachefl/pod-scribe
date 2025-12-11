import json

with open('shared/config/pending_episodes.json') as f:
    data = json.load(f)

selected = [e for e in data['episodes'] if e.get('selected', False)]

print(f'Total episodes: {len(data["episodes"])}')
print(f'Selected episodes: {len(selected)}')

if selected:
    print('\nFirst selected episode:')
    ep = selected[0]
    print(f'  ID: {ep.get("id", "N/A")}')
    print(f'  Title: {ep.get("episode_title", "N/A")}')
    print(f'  Audio URL: {ep.get("audio_url", "N/A")}')
    print(f'  Selected: {ep.get("selected", False)}')
else:
    print('\n❌ No episodes are selected!')
