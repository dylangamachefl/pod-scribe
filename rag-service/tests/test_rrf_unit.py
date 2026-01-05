
import unittest
from unittest.mock import MagicMock
from src.services.hybrid_retriever import HybridRetrieverService
from langchain_core.documents import Document

class TestRRFMerging(unittest.TestCase):
    def setUp(self):
        self.embeddings_service = MagicMock()
        self.qdrant_service = MagicMock()
        self.service = HybridRetrieverService(self.embeddings_service, self.qdrant_service)

    def test_rrf_merging_logic(self):
        # Mock results
        bm25_results = [
            Document(page_content="Text A", metadata={"episode_title": "Ep 1", "podcast_name": "Pod 1"}),
            Document(page_content="Text B", metadata={"episode_title": "Ep 1", "podcast_name": "Pod 1"}),
        ]
        qdrant_results = [
            {"text": "Text B", "episode_title": "Ep 1", "podcast_name": "Pod 1"},
            {"text": "Text C", "episode_title": "Ep 1", "podcast_name": "Pod 1"},
        ]
        
        # Text B is in both, should have highest score
        # Text A is rank 0 in BM25
        # Text B is rank 1 in BM25, rank 0 in Qdrant
        # Text C is rank 1 in Qdrant
        
        merged = self.service._merge_results_rrf(bm25_results, qdrant_results, k=3, rrf_k=60)
        
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]["text"], "Text B") # Highest score because it's in both
        self.assertIn("bm25", merged[0]["sources"])
        self.assertIn("qdrant", merged[0]["sources"])
        
        # Verify scores
        # Score B = 1/(60+1+1) + 1/(60+0+1) = 1/62 + 1/61
        # Score A = 1/(61)
        # Score C = 1/(62)
        
        self.assertGreater(merged[0]["score"], merged[1]["score"])

if __name__ == "__main__":
    unittest.main()
