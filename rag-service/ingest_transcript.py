"""
Simple script to ingest the Huberman Lab transcript into RAG service.
"""
import requests
import json

url = "http://localhost:8000/ingest"
headers = {"Content-Type": "application/json"}
data = {
    "file_path": "/app/shared/output/Learn/PydanticAI_ the AI Agent Framework Winner.txt"
}

print("Ingesting transcript into RAG service...")
print(f"Endpoint: {url}")
print(f"File: {data['file_path']}\n")

try:
    response = requests.post(url, headers=headers, json=data, timeout=120)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Success!")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message')}")
        print(f"   Chunks created: {result.get('chunks_created')}")
        print(f"   Episode: {result.get('episode_title')}")
        print(f"   Podcast: {result.get('podcast_name')}")
    else:
        print(f"❌ Error: HTTP {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
