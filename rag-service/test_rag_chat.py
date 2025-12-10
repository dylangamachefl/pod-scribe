"""
Test RAG chat for PydanticAI episode
"""
import requests
import json

url = "http://localhost:8000/chat"
headers = {"Content-Type": "application/json"}
data = {
    "question": "hi",
    "episode_title": "PydanticAI: the AI Agent Framework Winner"
}

print("Testing RAG chat for PydanticAI episode...")
print(f"Endpoint: {url}")
print(f"Question: {data['question']}")
print(f"Episode: {data['episode_title']}\n")

try:
    response = requests.post(url, headers=headers, json=data, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Success!")
        print(f"   Chunks found: {len(result.get('sources', []))}")
        print(f"   Answer: {result.get('answer', 'No answer')[:200]}...")
    else:
        print(f"❌ Error: HTTP {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
