"""
Example usage and testing script for Hybrid Search
Demonstrates how to use the hybrid search functionality.
"""
import requests
import json


def test_hybrid_search_api():
    """Test hybrid search via the API."""
    base_url = "http://localhost:8000"
    
    # Test 1: Hybrid search without episode filter
    print("\n=== Test 1: Hybrid Search (Cross-Episode) ===")
    response = requests.post(
        f"{base_url}/chat",
        json={
            "question": "What did they discuss about artificial intelligence?",
            "use_hybrid_search": True,
            "bm25_weight": 0.5,
            "faiss_weight": 0.5
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer'][:200]}...")
        print(f"Retrieval Method: {result['retrieval_method']}")
        print(f"Number of sources: {len(result['sources'])}")
        print(f"Processing time: {result['processing_time_ms']:.2f}ms")
    else:
        print(f"Error: {response.status_code} - {response.text}")
    
    # Test 2: Hybrid search with episode filter
    print("\n=== Test 2: Hybrid Search (Episode-Scoped) ===")
    response = requests.post(
        f"{base_url}/chat",
        json={
            "question": "What were the main topics discussed?",
            "episode_title": "Your Episode Title Here",  # Replace with actual episode
            "use_hybrid_search": True,
            "bm25_weight": 0.5,
            "faiss_weight": 0.5
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer'][:200]}...")
        print(f"Retrieval Method: {result['retrieval_method']}")
        print(f"Number of sources: {len(result['sources'])}")
    else:
        print(f"Error: {response.status_code} - {response.text}")
    
    # Test 3: BM25-heavy search (favor keywords)
    print("\n=== Test 3: BM25-Heavy Search ===")
    response = requests.post(
        f"{base_url}/chat",
        json={
            "question": "machine learning neural networks deep learning",
            "use_hybrid_search": True,
            "bm25_weight": 0.7,
            "faiss_weight": 0.3
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer'][:200]}...")
        print("Sources (BM25-heavy retrieval):")
        for i, source in enumerate(result['sources'][:3], 1):
            print(f"  {i}. {source['episode_title']} - {source['speaker']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")
    
    # Test 4: FAISS-heavy search (favor semantics)
    print("\n=== Test 4: FAISS-Heavy Search ===")
    response = requests.post(
        f"{base_url}/chat",
        json={
            "question": "What are the implications of AI on society?",
            "use_hybrid_search": True,
            "bm25_weight": 0.3,
            "faiss_weight": 0.7
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer'][:200]}...")
        print("Sources (FAISS-heavy retrieval):")
        for i, source in enumerate(result['sources'][:3], 1):
            print(f"  {i}. {source['episode_title']} - {source['speaker']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")
    
    # Test 5: Full context mode (for comparison)
    print("\n=== Test 5: Full Context Mode (For Comparison) ===")
    response = requests.post(
        f"{base_url}/chat",
        json={
            "question": "What were the main topics discussed?",
            "episode_title": "Your Episode Title Here",  # Replace with actual episode
            "use_hybrid_search": False  # Explicitly disable hybrid search
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Answer: {result['answer'][:200]}...")
        print(f"Retrieval Method: {result['retrieval_method']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def check_service_health():
    """Check if the RAG service is running."""
    base_url = "http://localhost:8000"
    
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ RAG service is running")
            print(json.dumps(response.json(), indent=2))
            return True
        else:
            print(f"❌ Service returned status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to service: {str(e)}")
        print("Make sure the RAG service is running: uvicorn src.main:app --reload")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Hybrid Search Test Script")
    print("=" * 60)
    
    if check_service_health():
        print("\nRunning hybrid search tests...\n")
        test_hybrid_search_api()
    else:
        print("\nPlease start the RAG service first:")
        print("  cd rag-service")
        print("  uvicorn src.main:app --reload")
