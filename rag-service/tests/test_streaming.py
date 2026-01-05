
import requests
import json

def test_streaming_chat():
    url = "http://localhost:8000/chat/stream"
    payload = {
        "question": "What is this podcast about?",
        "episode_title": "Your Episode Title Here", # Adjust if needed
        "conversation_history": []
    }
    
    print(f"Testing streaming chat at {url}...")
    try:
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()
        
        print("\n--- Response Stream ---")
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("METADATA:"):
                    metadata = json.loads(decoded_line.replace("METADATA:", ""))
                    print(f"Metadata received: {len(metadata.get('sources', []))} sources")
                else:
                    print(decoded_line, end="", flush=True)
        print("\n-----------------------")
        print("\n✅ Streaming test complete!")
        
    except Exception as e:
        print(f"❌ Error during streaming test: {e}")

if __name__ == "__main__":
    test_streaming_chat()
