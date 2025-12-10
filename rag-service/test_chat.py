"""
Test the RAG chat feature with a sample question.
"""
import requests
import json

url = "http://localhost:8000/chat"
headers = {"Content-Type": "application/json"}
data = {
    "question": "What are the main strategies for speaking clearly and with confidence?",
    "episode_title": "How to Speak Clearly & With Confidence | Matt Abrahams"
}

print("Testing RAG chat feature...")
print(f"Question: {data['question']}")
print(f"Episode: {data['episode_title']}\n")

try:
    response = requests.post(url, headers=headers, json=data, timeout=60)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Chat Response:")
        print("=" * 80)
        print(result.get('answer'))
        print("=" * 80)
        print(f"\nProcessing time: {result.get('processing_time_ms', 0):.0f}ms")
        print(f"Number of sources: {len(result.get('sources', []))}")
    else:
        print(f"❌ Error: HTTP {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
