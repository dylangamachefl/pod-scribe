"""
Unit tests for Hybrid Retriever Service
Tests BM25, FAISS, and ensemble retrieval functionality.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile
import shutil

from services.hybrid_retriever import HybridRetrieverService, FAISSEmbeddingsWrapper
from langchain_core.documents import Document


class TestFAISSEmbeddingsWrapper(unittest.TestCase):
    """Test the FAISS embeddings wrapper."""
    
    def setUp(self):
        self.mock_embeddings_service = Mock()
        self.mock_embeddings_service.embed_text.return_value = [0.1] * 768
    
    def test_embed_query(self):
        """Test embedding a query string."""
        wrapper = FAISSEmbeddingsWrapper(self.mock_embeddings_service)
        result = wrapper.embed_query("test query")
        
        self.assertEqual(len(result), 768)
        self.mock_embeddings_service.embed_text.assert_called_once_with("test query")
    
    def test_embed_documents_with_cache(self):
        """Test embedding documents with precomputed cache."""
        docs = [
            Document(page_content="doc 1", metadata={}),
            Document(page_content="doc 2", metadata={})
        ]
        precomputed = [[0.1] * 768, [0.2] * 768]
        
        wrapper = FAISSEmbeddingsWrapper(
            self.mock_embeddings_service,
            precomputed_embeddings=precomputed,
            documents=docs
        )
        
        # Should use cached embeddings
        result = wrapper.embed_documents(["doc 1", "doc 2"])
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], [0.1] * 768)
        self.assertEqual(result[1], [0.2] * 768)
        # Should not call the service since we have cached values
        self.mock_embeddings_service.embed_text.assert_not_called()
    
    def test_embed_documents_without_cache(self):
        """Test embedding documents without cache."""
        wrapper = FAISSEmbeddingsWrapper(self.mock_embeddings_service)
        
        result = wrapper.embed_documents(["new doc 1", "new doc 2"])
        
        self.assertEqual(len(result), 2)
        self.assertEqual(self.mock_embeddings_service.embed_text.call_count, 2)


class TestHybridRetrieverService(unittest.TestCase):
    """Test the Hybrid Retriever Service."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_embeddings_service = Mock()
        self.mock_embeddings_service.embed_text.return_value = [0.1] * 768
        
        self.mock_qdrant_service = Mock()
        self.mock_qdrant_service.collection_name = "test_collection"
        
        # Create temp directory for index storage
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock INDEXES_PATH
        self.indexes_path_patcher = patch('services.hybrid_retriever.INDEXES_PATH', Path(self.temp_dir))
        self.indexes_path_patcher.start()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.indexes_path_patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test service initialization."""
        service = HybridRetrieverService(
            self.mock_embeddings_service,
            self.mock_qdrant_service
        )
        
        self.assertIsNone(service.bm25_retriever)
        self.assertIsNone(service.faiss_retriever)
        self.assertIsNone(service.ensemble_retriever)
        self.assertEqual(len(service.documents), 0)
    
    def test_build_indexes_empty_collection(self):
        """Test building indexes with empty collection."""
        # Mock empty Qdrant response
        self.mock_qdrant_service.client.scroll.return_value = ([], None)
        
        service = HybridRetrieverService(
            self.mock_embeddings_service,
            self.mock_qdrant_service
        )
        
        result = service.build_indexes()
        
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["documents_indexed"], 0)
    
    @patch('services.hybrid_retriever.BM25Retriever')
    @patch('services.hybrid_retriever.FAISS')
    def test_build_indexes_with_documents(self, mock_faiss, mock_bm25):
        """Test building indexes with documents."""
        # Mock Qdrant points
        mock_point = Mock()
        mock_point.id = "123"
        mock_point.vector = [0.1] * 768
        mock_point.payload = {
            "text": "Test content",
            "episode_title": "Test Episode",
            "podcast_name": "Test Podcast",
            "speaker": "Speaker 1",
            "timestamp": "00:01:00",
            "chunk_index": 0,
            "source_file": "test.txt"
        }
        
        self.mock_qdrant_service.client.scroll.return_value = ([mock_point], None)
        
        service = HybridRetrieverService(
            self.mock_embeddings_service,
            self.mock_qdrant_service
        )
        
        result = service.build_indexes()
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["documents_indexed"], 1)
        self.assertEqual(len(service.documents), 1)
        self.assertEqual(service.documents[0].page_content, "Test content")


if __name__ == '__main__':
    unittest.main()
