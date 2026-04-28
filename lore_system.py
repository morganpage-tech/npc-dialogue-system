"""
Lore System - RAG (Retrieval Augmented Generation) for NPC knowledge
Enables NPCs to reference game world events, locations, history, and lore
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

logger = logging.getLogger(__name__)


class LoreEntry:
    """A single piece of lore/knowledge."""
    
    def __init__(
        self,
        id: str,
        title: str,
        content: str,
        category: str = "general",
        known_by: List[str] = None,
        importance: float = 0.5,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        self.id = id
        self.title = title
        self.content = content
        self.category = category
        self.known_by = known_by or ["everyone"]
        self.importance = importance
        self.tags = tags or []
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "known_by": self.known_by,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LoreEntry':
        entry = cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            category=data.get("category", "general"),
            known_by=data.get("known_by", ["everyone"]),
            importance=data.get("importance", 0.5),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {})
        )
        if "created_at" in data:
            entry.created_at = data["created_at"]
        return entry
    
    def get_search_text(self) -> str:
        """Get text for embedding/search."""
        parts = [self.title, self.content]
        if self.tags:
            parts.append(" ".join(self.tags))
        return " ".join(parts)


class LoreSystem:
    """
    RAG-based lore system for NPC knowledge.
    Uses ChromaDB for vector storage and semantic search.
    """
    
    CATEGORIES = [
        "history",
        "locations",
        "characters",
        "items",
        "factions",
        "events",
        "quests",
        "legends",
        "general"
    ]
    
    def __init__(
        self,
        persist_directory: str = "lore_database",
        embedding_model: str = "all-MiniLM-L6-v2",
        max_entries: int = 10000
    ):
        """
        Initialize the lore system.
        
        Args:
            persist_directory: Directory to store the vector database
            embedding_model: Sentence transformer model for embeddings
            max_entries: Maximum number of lore entries (memory safeguard)
        """
        self.persist_directory = Path(persist_directory)
        self.embedding_model_name = embedding_model
        self.max_entries = max_entries
        
        # Initialize embedding model
        self.embedding_model = None
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                self.embedding_model = SentenceTransformer(embedding_model)
                print(f"✅ Loaded embedding model: {embedding_model}")
            except Exception as e:
                print(f"⚠️  Failed to load embedding model: {e}")
        
        # Initialize ChromaDB
        self.client = None
        self.collection = None
        if HAS_CHROMADB:
            try:
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                self.client = chromadb.PersistentClient(
                    path=str(self.persist_directory),
                    settings=Settings(anonymized_telemetry=False)
                )
                self.collection = self.client.get_or_create_collection(
                    name="lore",
                    metadata={"description": "NPC knowledge base"}
                )
                print(f"✅ Connected to ChromaDB: {self.collection.count()} entries")
            except Exception as e:
                print(f"⚠️  Failed to initialize ChromaDB: {e}")
        
        # In-memory fallback storage
        self.lore_entries: Dict[str, LoreEntry] = {}
        self._load_from_disk()
    
    def _load_from_disk(self):
        """Load lore entries from JSON files."""
        lore_dir = Path("lore_templates")
        if not lore_dir.exists():
            return
        
        for json_file in lore_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if "entries" in data:
                    # Multiple entries in file
                    for entry_data in data["entries"]:
                        entry = LoreEntry.from_dict(entry_data)
                        self.lore_entries[entry.id] = entry
                else:
                    # Single entry
                    entry = LoreEntry.from_dict(data)
                    self.lore_entries[entry.id] = entry
                    
            except Exception as e:
                print(f"⚠️  Failed to load {json_file}: {e}")
        
        print(f"📚 Loaded {len(self.lore_entries)} lore entries from disk")
        
        # Index in ChromaDB if available
        if self.collection is not None and self.lore_entries:
            self._sync_to_chromadb()
    
    def _sync_to_chromadb(self):
        """Sync in-memory entries to ChromaDB."""
        if not self.collection:
            return
        
        existing_ids = set(
            meta.get("id") 
            for meta in self.collection.get()["metadatas"]
        )
        
        new_entries = [
            entry for entry in self.lore_entries.values()
            if entry.id not in existing_ids
        ]
        
        if new_entries:
            self._add_to_chromadb(new_entries)
    
    def _add_to_chromadb(self, entries: List[LoreEntry]):
        """Add entries to ChromaDB."""
        if not self.collection or not entries:
            return
        
        ids = [e.id for e in entries]
        documents = [e.get_search_text() for e in entries]
        metadatas = [
            {
                "title": e.title,
                "category": e.category,
                "known_by": json.dumps(e.known_by),
                "importance": e.importance,
                "tags": json.dumps(e.tags)
            }
            for e in entries
        ]
        
        # Generate embeddings
        embeddings = None
        if self.embedding_model:
            try:
                embeddings = self.embedding_model.encode(documents).tolist()
            except Exception as e:
                print(f"⚠️  Failed to generate embeddings: {e}")
        
        try:
            if embeddings:
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
            else:
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
            print(f"📝 Indexed {len(entries)} entries in ChromaDB")
        except Exception as e:
            print(f"⚠️  Failed to add to ChromaDB: {e}")
    
    def add_lore(
        self,
        id: str,
        title: str,
        content: str,
        category: str = "general",
        known_by: List[str] = None,
        importance: float = 0.5,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> LoreEntry:
        """
        Add a new lore entry.
        
        Args:
            id: Unique identifier
            title: Title of the lore
            content: The actual lore content
            category: Category (history, locations, characters, etc.)
            known_by: Who knows this lore (NPC names, factions, "everyone")
            importance: Importance score 0-1 (affects retrieval)
            tags: Search tags
            metadata: Additional metadata
            
        Returns:
            The created LoreEntry
        """
        entry = LoreEntry(
            id=id,
            title=title,
            content=content,
            category=category,
            known_by=known_by or ["everyone"],
            importance=importance,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Store in memory
        self.lore_entries[id] = entry
        
        # Warn if exceeding max_entries safeguard
        if len(self.lore_entries) > self.max_entries:
            logger.warning(
                "Lore entries (%d) exceeded max_entries limit (%d). "
                "Consider removing unused entries to prevent unbounded memory growth.",
                len(self.lore_entries), self.max_entries
            )
        
        # Add to ChromaDB
        self._add_to_chromadb([entry])
        
        return entry
    
    def add_lore_batch(self, entries: List[Dict]) -> List[LoreEntry]:
        """
        Add multiple lore entries at once.
        
        Args:
            entries: List of lore dictionaries
            
        Returns:
            List of created LoreEntry objects
        """
        lore_entries = []
        for data in entries:
            entry = LoreEntry(
                id=data["id"],
                title=data["title"],
                content=data["content"],
                category=data.get("category", "general"),
                known_by=data.get("known_by", ["everyone"]),
                importance=data.get("importance", 0.5),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {})
            )
            self.lore_entries[entry.id] = entry
            lore_entries.append(entry)
        
        # Warn if exceeding max_entries safeguard
        if len(self.lore_entries) > self.max_entries:
            logger.warning(
                "Lore entries (%d) exceeded max_entries limit (%d) after batch add. "
                "Consider removing unused entries to prevent unbounded memory growth.",
                len(self.lore_entries), self.max_entries
            )
        
        self._add_to_chromadb(lore_entries)
        return lore_entries
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None,
        known_by: Optional[str] = None,
        min_importance: float = 0.0
    ) -> List[Tuple[LoreEntry, float]]:
        """
        Search for relevant lore entries.
        
        Args:
            query: Search query
            n_results: Maximum number of results
            category: Filter by category
            known_by: Filter by who knows (NPC name or faction)
            min_importance: Minimum importance threshold
            
        Returns:
            List of (LoreEntry, relevance_score) tuples
        """
        results = []
        
        # Try ChromaDB search first
        if self.collection:
            try:
                # Build where filter
                where_filter = None
                if category or known_by:
                    conditions = []
                    if category:
                        conditions.append({"category": category})
                    if conditions:
                        where_filter = {"$and": conditions} if len(conditions) > 1 else conditions[0]
                
                # Generate query embedding
                query_embedding = None
                if self.embedding_model:
                    query_embedding = self.embedding_model.encode([query]).tolist()[0]
                
                # Search
                if query_embedding:
                    search_results = self.collection.query(
                        query_embeddings=[query_embedding],
                        n_results=n_results * 2,  # Get extra for filtering
                        where=where_filter,
                        include=["documents", "metadatas", "distances"]
                    )
                else:
                    search_results = self.collection.query(
                        query_texts=[query],
                        n_results=n_results * 2,
                        where=where_filter,
                        include=["documents", "metadatas", "distances"]
                    )
                
                # Process results
                if search_results["ids"][0]:
                    for i, doc_id in enumerate(search_results["ids"][0]):
                        if doc_id in self.lore_entries:
                            entry = self.lore_entries[doc_id]
                            
                            # Apply filters
                            if known_by and known_by not in entry.known_by and "everyone" not in entry.known_by:
                                continue
                            if entry.importance < min_importance:
                                continue
                            
                            # Convert distance to similarity score
                            distance = search_results["distances"][0][i]
                            similarity = 1 - distance if distance <= 1 else 1 / (1 + distance)
                            
                            results.append((entry, similarity))
                            
                            if len(results) >= n_results:
                                break
                
                if results:
                    return results
                    
            except Exception as e:
                print(f"⚠️  ChromaDB search failed: {e}")
        
        # Fallback to keyword search
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored_entries = []
        for entry in self.lore_entries.values():
            # Apply filters
            if category and entry.category != category:
                continue
            if known_by and known_by not in entry.known_by and "everyone" not in entry.known_by:
                continue
            if entry.importance < min_importance:
                continue
            
            # Score based on keyword matching
            text = entry.get_search_text().lower()
            score = 0.0
            
            # Exact title match
            if query_lower in entry.title.lower():
                score += 0.5
            
            # Word matches
            entry_words = set(text.split())
            word_overlap = len(query_words & entry_words)
            score += word_overlap * 0.1
            
            # Importance boost
            score += entry.importance * 0.2
            
            if score > 0:
                scored_entries.append((entry, score))
        
        # Sort by score
        scored_entries.sort(key=lambda x: x[1], reverse=True)
        return scored_entries[:n_results]
    
    def get_context_for_npc(
        self,
        npc_name: str,
        query: str,
        max_tokens: int = 500,
        categories: List[str] = None
    ) -> str:
        """
        Get relevant lore context for an NPC query.
        
        Args:
            npc_name: Name of the NPC
            query: Player's question or context
            max_tokens: Approximate max tokens for context
            categories: Categories to search (None = all)
            
        Returns:
            Formatted context string for prompt injection
        """
        # Search for relevant lore
        results = self.search(
            query=query,
            n_results=5,
            known_by=npc_name
        )
        
        if not results:
            return ""
        
        # Build context
        context_parts = ["RELEVANT KNOWLEDGE:"]
        current_length = 0
        
        for entry, score in results:
            # Check categories filter
            if categories and entry.category not in categories:
                continue
            
            # Format entry
            entry_text = f"\n[{entry.category.title()}] {entry.title}: {entry.content}"
            
            # Check length
            if current_length + len(entry_text) > max_tokens * 4:  # Rough char estimate
                break
            
            context_parts.append(entry_text)
            current_length += len(entry_text)
        
        if len(context_parts) == 1:
            return ""
        
        context_parts.append("\n(Use this knowledge if relevant to the conversation)")
        
        return "\n".join(context_parts)
    
    def get_entry(self, entry_id: str) -> Optional[LoreEntry]:
        """Get a specific lore entry by ID."""
        return self.lore_entries.get(entry_id)
    
    def get_entries_by_category(self, category: str) -> List[LoreEntry]:
        """Get all entries in a category."""
        return [e for e in self.lore_entries.values() if e.category == category]
    
    def get_entries_known_by(self, npc_name: str) -> List[LoreEntry]:
        """Get all entries known by an NPC."""
        return [
            e for e in self.lore_entries.values()
            if npc_name in e.known_by or "everyone" in e.known_by
        ]
    
    def update_entry(self, entry_id: str, **kwargs) -> Optional[LoreEntry]:
        """Update a lore entry."""
        if entry_id not in self.lore_entries:
            return None
        
        entry = self.lore_entries[entry_id]
        
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        # Re-index in ChromaDB
        if self.collection:
            try:
                self.collection.delete(ids=[entry_id])
                self._add_to_chromadb([entry])
            except Exception as e:
                print(f"⚠️  Failed to update ChromaDB: {e}")
        
        return entry
    
    def delete_entry(self, entry_id: str) -> bool:
        """Delete a lore entry."""
        if entry_id not in self.lore_entries:
            return False
        
        del self.lore_entries[entry_id]
        
        if self.collection:
            try:
                self.collection.delete(ids=[entry_id])
            except Exception as e:
                print(f"⚠️  Failed to delete from ChromaDB: {e}")
        
        return True
    
    def save_to_file(self, filepath: str = None):
        """Save lore entries to a JSON file."""
        if filepath is None:
            filepath = "lore_templates/exported_lore.json"
        
        data = {
            "entries": [e.to_dict() for e in self.lore_entries.values()],
            "exported_at": datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved {len(self.lore_entries)} lore entries to {filepath}")
    
    def load_from_file(self, filepath: str):
        """Load lore entries from a JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        entries = data.get("entries", [])
        
        for entry_data in entries:
            entry = LoreEntry.from_dict(entry_data)
            self.lore_entries[entry.id] = entry
        
        self._sync_to_chromadb()
        print(f"📚 Loaded {len(entries)} lore entries from {filepath}")
    
    def get_stats(self) -> Dict:
        """Get statistics about the lore database."""
        categories = {}
        known_counts = {}
        
        for entry in self.lore_entries.values():
            categories[entry.category] = categories.get(entry.category, 0) + 1
            for knower in entry.known_by:
                known_counts[knower] = known_counts.get(knower, 0) + 1
        
        return {
            "total_entries": len(self.lore_entries),
            "categories": categories,
            "known_by_counts": known_counts,
            "chromadb_count": self.collection.count() if self.collection else 0,
            "embedding_model": self.embedding_model_name if self.embedding_model else None
        }
    
    def clear_all(self):
        """Clear all lore entries."""
        self.lore_entries.clear()
        
        if self.collection:
            try:
                # Delete all documents
                all_ids = [m.get("id") for m in self.collection.get()["metadatas"]]
                if all_ids:
                    self.collection.delete(ids=all_ids)
            except Exception as e:
                print(f"⚠️  Failed to clear ChromaDB: {e}")
        
        print("🗑️  Cleared all lore entries")
