"""
Delete and recreate the Qdrant collection with correct dimensions.
"""
import requests

# Delete the old collection
print("Deleting old collection...")
try:
    response = requests.delete("http://localhost:6333/collections/podcast_transcripts")
    if response.status_code in [200, 404]:
        print("✅ Old collection deleted (or didn't exist)")
    else:
        print(f"⚠️ Delete response: {response.status_code}")
except Exception as e:
    print(f"⚠️ Error deleting: {e}")

# Create new collection with correct dimensions
print("\nCreating new collection with 768 dimensions...")
try:
    data = {
        "vectors": {
            "size": 768,
            "distance": "Cosine"
        }
    }
    response = requests.put("http://localhost:6333/collections/podcast_transcripts", json=data)
    if response.status_code == 200:
        print("✅ Collection created successfully")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"❌ Error: {e}")
