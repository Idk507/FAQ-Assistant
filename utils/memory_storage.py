import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Tuple
import json
from datetime import datetime

class InMemoryVectorStore:
    """
    Simple in-memory vector store using cosine similarity for document retrieval.
    Avoids external databases as per requirements.
    """

    def __init__(self):
        self.documents = []
        self.embeddings = []
        self.metadata = []

    def add_documents(self, documents: List[str], embeddings: List[List[float]], metadata: List[Dict] = None):
        """
        Add documents with their embeddings to the store.

        Args:
            documents: List of document texts
            embeddings: List of embedding vectors
            metadata: Optional metadata for each document
        """
        self.documents.extend(documents)
        self.embeddings.extend(embeddings)

        if metadata:
            self.metadata.extend(metadata)
        else:
            self.metadata.extend([{}] * len(documents))

    def similarity_search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[str, Dict, float]]:
        """
        Perform similarity search using cosine similarity.

        Args:
            query_embedding: Embedding vector for the query
            top_k: Number of top similar documents to return

        Returns:
            List of tuples (document, metadata, similarity_score)
        """
        if not self.embeddings:
            return []

        # Convert to numpy arrays
        query_vector = np.array(query_embedding).reshape(1, -1)
        doc_vectors = np.array(self.embeddings)

        # Calculate cosine similarities
        similarities = cosine_similarity(query_vector, doc_vectors)[0]

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append((
                self.documents[idx],
                self.metadata[idx],
                float(similarities[idx])
            ))

        return results

    def clear(self):
        """Clear all documents and embeddings"""
        self.documents = []
        self.embeddings = []
        self.metadata = []


class RegulatoryKnowledgeBase:
    """
    Specialized knowledge base for regulatory information with FAQ storage.
    """

    def __init__(self):
        self.faqs = []
        self.regulatory_texts = []
        self.vector_store = InMemoryVectorStore()

    def add_regulatory_text(self, text: str, source: str = "", date: str = ""):
        """
        Add regulatory text to the knowledge base.

        Args:
            text: The regulatory text content
            source: Source of the regulatory information
            date: Date of the regulatory update
        """
        metadata = {
            "type": "regulatory_text",
            "source": source,
            "date": date or datetime.now().isoformat(),
            "timestamp": datetime.now().timestamp()
        }

        self.regulatory_texts.append({
            "content": text,
            "metadata": metadata
        })

    def add_faqs(self, faqs: List[Dict[str, Any]], regulatory_context: str = ""):
        """
        Add FAQs to the knowledge base.

        Args:
            faqs: List of FAQ dictionaries with 'question' and 'answer' keys
            regulatory_context: Context about the regulatory changes
        """
        for faq in faqs:
            faq_entry = {
                "question": faq.get("question", ""),
                "answer": faq.get("answer", ""),
                "regulatory_context": regulatory_context,
                "created_at": datetime.now().isoformat(),
                "validated": faq.get("validated", False)
            }
            self.faqs.append(faq_entry)

    def get_recent_faqs(self, limit: int = 10) -> List[Dict]:
        """Get most recent FAQs"""
        sorted_faqs = sorted(self.faqs, key=lambda x: x["created_at"], reverse=True)
        return sorted_faqs[:limit]

    def search_faqs(self, query: str, embedding_func=None, top_k: int = 5) -> List[Dict]:
        """
        Search FAQs using semantic similarity if embeddings are available,
        otherwise use simple text matching.

        Args:
            query: Search query
            embedding_func: Function to generate embeddings
            top_k: Number of results to return
        """
        if embedding_func and self.vector_store.embeddings:
            # Use semantic search
            query_embedding = embedding_func(query)
            results = self.vector_store.similarity_search(query_embedding, top_k)

            faq_results = []
            for doc, metadata, score in results:
                if metadata.get("type") == "faq":
                    faq_results.append({
                        "question": metadata.get("question", ""),
                        "answer": metadata.get("answer", ""),
                        "score": score,
                        "metadata": metadata
                    })
            return faq_results

        else:
            # Use simple text matching
            query_lower = query.lower()
            matching_faqs = []

            for faq in self.faqs:
                question_match = query_lower in faq["question"].lower()
                answer_match = query_lower in faq["answer"].lower()

                if question_match or answer_match:
                    score = 1.0 if question_match else 0.7
                    matching_faqs.append({
                        "question": faq["question"],
                        "answer": faq["answer"],
                        "score": score,
                        "metadata": faq
                    })

            # Sort by score and return top_k
            matching_faqs.sort(key=lambda x: x["score"], reverse=True)
            return matching_faqs[:top_k]

    def get_all_regulatory_texts(self) -> List[Dict]:
        """Get all regulatory texts"""
        return self.regulatory_texts

    def clear_all(self):
        """Clear all stored data"""
        self.faqs = []
        self.regulatory_texts = []
        self.vector_store.clear()
