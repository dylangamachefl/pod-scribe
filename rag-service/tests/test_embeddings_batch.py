import sys
import os
from pprint import pprint

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.embeddings import get_embedding_service

def test_batch_embeddings():
    print("🚀 Initializing Embedding Service...")
    service = get_embedding_service()
    
    texts = [
        "This is a test sentence for embedding.",
        "Ollama is a great tool for local LLMs.",
        "Batch processing should be faster and more reliable.",
        "We are testing the new /api/embed endpoint.",
        "The timeout has been increased to 120 seconds."
    ]
    
    print(f"📊 Testing batch embedding with {len(texts)} texts...")
    try:
        embeddings = service.embed_batch(texts)
        
        print(f"✅ Successfully generated {len(embeddings)} embeddings")
        
        if len(embeddings) > 0:
            print(f"📏 Embedding dimension: {len(embeddings[0])}")
            if len(embeddings[0]) == 768:
                print("✅ Dimension matches expected (768 for nomic-embed-text)")
            else:
                print(f"⚠️ Unexpected dimension: {len(embeddings[0])}")
        
        assert len(embeddings) == len(texts), f"Expected {len(texts)} embeddings, got {len(embeddings)}"
        print("✨ Batch embedding test PASSED!")
        
    except Exception as e:
        print(f"❌ Batch embedding test FAILED: {e}")
        import traceback
        traceback.print_exc()

def test_single_embedding():
    print("\n🚀 Testing single embedding...")
    service = get_embedding_service()
    text = "Just a single sentence test."
    
    try:
        embedding = service.embed_text(text)
        print(f"✅ Successfully generated single embedding")
        print(f"📏 Embedding dimension: {len(embedding)}")
        assert len(embedding) > 0, "Embedding should not be empty"
        print("✨ Single embedding test PASSED!")
    except Exception as e:
        print(f"❌ Single embedding test FAILED: {e}")

if __name__ == "__main__":
    print("="*60)
    print("Ollama Embedding Service Verification")
    print("="*60)
    test_batch_embeddings()
    test_single_embedding()
    print("="*60)
