
import os
from qdrant_client import QdrantClient

def inspect_qdrant():
    client = QdrantClient(url="http://localhost:6333")
    collection_name = "podcast_transcripts"
    
    print(f"Inspecting collection: {collection_name}")
    
    # Get collection info
    info = client.get_collection(collection_name)
    print(f"Point count: {info.points_count}")
    
    # Scroll points to see metadata
    points, next_page = client.scroll(
        collection_name=collection_name,
        limit=10,
        with_payload=True,
        with_vectors=False
    )
    
    print("\nSample Metadata (First 10 points):")
    for p in points:
        payload = p.payload
        print(f"- Episode: {payload.get('episode_title')}")
        print(f"  Podcast: {payload.get('podcast_name')}")
        print(f"  Speaker: {payload.get('speaker')}")
        print("-" * 20)

    # Check for specific episode
    target_title = "The Productivity System I Taught to 6,642 Googlers"
    print(f"\nSearching for exact title: '{target_title}'")
    
    from qdrant_client.http.models import Filter, FieldCondition, MatchValue
    
    points, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="episode_title", match=MatchValue(value=target_title))
            ]
        ),
        limit=5
    )
    
    print(f"Found {len(points)} points with exact match.")
    
    # Try fuzzy/substring check if not found
    if len(points) == 0:
        print("No exact match found. Listing all unique titles in Qdrant...")
        titles = set()
        offset = None
        while True:
            scroll_pts, offset = client.scroll(collection_name=collection_name, limit=100, offset=offset)
            for p in scroll_pts:
                titles.add(p.payload.get("episode_title"))
            if not offset:
                break
        
        print(f"Unique titles found ({len(titles)}):")
        for t in sorted(list(titles)):
            print(f"- '{t}'")

if __name__ == "__main__":
    inspect_qdrant()
