"""
Performance Optimization Module for NPC Dialogue System

Features:
- Response caching (LRU + semantic similarity)
- Connection pooling for Ollama
- Batch request processing
- Response pre-generation for common queries
- Performance metrics and monitoring
- Async request handling

Usage:
    from performance import PerformanceManager, CachedNPCDialogue
    
    # Initialize with caching
    perf_manager = PerformanceManager()
    npc = CachedNPCDialogue("Blacksmith", "character_cards/blacksmith.json", 
                            cache_manager=perf_manager.cache)
"""

import json
import time
import hashlib
import asyncio
import threading
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# PERFORMANCE METRICS
# ============================================

@dataclass
class PerformanceMetrics:
    """Track performance metrics for the system."""
    
    # Size limit for history list (memory safeguard)
    max_history_size: int = 10000
    
    # Request counts
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    batch_requests: int = 0
    
    # Timing
    total_generation_time: float = 0.0
    total_cache_lookup_time: float = 0.0
    
    # Tokens
    total_tokens_generated: int = 0
    
    # Errors
    errors: int = 0
    timeouts: int = 0
    
    # History of individual request records for detailed analysis
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    def record_request(self, generation_time: float, tokens: int, from_cache: bool = False):
        """Record a request."""
        self.total_requests += 1
        if from_cache:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
            self.total_generation_time += generation_time
            self.total_tokens_generated += tokens
        
        # Append to history and enforce size limit
        self.history.append({
            "generation_time": generation_time,
            "tokens": tokens,
            "from_cache": from_cache,
            "timestamp": time.time(),
        })
        if len(self.history) > self.max_history_size:
            self.history = self.history[-self.max_history_size:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        avg_gen_time = (
            self.total_generation_time / self.cache_misses 
            if self.cache_misses > 0 else 0
        )
        cache_hit_rate = (
            self.cache_hits / self.total_requests * 100 
            if self.total_requests > 0 else 0
        )
        avg_tokens = (
            self.total_tokens_generated / self.cache_misses 
            if self.cache_misses > 0 else 0
        )
        
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "batch_requests": self.batch_requests,
            "avg_generation_time": f"{avg_gen_time:.2f}s",
            "total_generation_time": f"{self.total_generation_time:.1f}s",
            "total_tokens": self.total_tokens_generated,
            "avg_tokens_per_response": f"{avg_tokens:.0f}",
            "errors": self.errors,
            "timeouts": self.timeouts,
        }
    
    def reset(self):
        """Reset all metrics."""
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.batch_requests = 0
        self.total_generation_time = 0.0
        self.total_cache_lookup_time = 0.0
        self.total_tokens_generated = 0
        self.errors = 0
        self.timeouts = 0
        self.history.clear()


# ============================================
# RESPONSE CACHE
# ============================================

class ResponseCache:
    """
    LRU cache for NPC responses with optional semantic similarity matching.
    
    Features:
    - LRU eviction
    - TTL (time-to-live) expiration
    - Semantic similarity matching (optional)
    - Persistence to disk
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,  # 1 hour default
        similarity_threshold: float = 0.85,
        enable_similarity: bool = False
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.enable_similarity = enable_similarity
        
        # Cache storage: key -> (response, timestamp, metadata)
        self._cache: OrderedDict[str, Tuple[str, float, Dict]] = OrderedDict()
        
        # Similarity index for fuzzy matching
        self._similarity_index: Dict[str, str] = {}  # normalized_input -> cache_key
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Metrics
        self.metrics = PerformanceMetrics()
    
    def _generate_key(
        self, 
        npc_name: str, 
        user_input: str, 
        context_hash: str = ""
    ) -> str:
        """Generate a cache key."""
        normalized_input = user_input.lower().strip()
        combined = f"{npc_name}:{normalized_input}:{context_hash}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _normalize_input(self, text: str) -> str:
        """Normalize input for similarity matching."""
        # Simple normalization - remove extra whitespace, lowercase
        return ' '.join(text.lower().split())
    
    def _check_similarity(self, normalized_input: str) -> Optional[str]:
        """Check for similar inputs in cache."""
        if not self.enable_similarity:
            return None
        
        # Simple word-based similarity
        input_words = set(normalized_input.split())
        
        for cached_normalized, cache_key in self._similarity_index.items():
            cached_words = set(cached_normalized.split())
            
            # Jaccard similarity
            intersection = len(input_words & cached_words)
            union = len(input_words | cached_words)
            
            if union > 0:
                similarity = intersection / union
                if similarity >= self.similarity_threshold:
                    return cache_key
        
        return None
    
    def get(
        self, 
        npc_name: str, 
        user_input: str, 
        context_hash: str = ""
    ) -> Optional[Tuple[str, bool]]:
        """
        Get a cached response if available.
        
        Returns:
            Tuple of (response, is_similar_match) or None
        """
        start_time = time.time()
        
        with self._lock:
            key = self._generate_key(npc_name, user_input, context_hash)
            
            # Direct hit
            if key in self._cache:
                response, timestamp, metadata = self._cache[key]
                
                # Check TTL
                if time.time() - timestamp < self.ttl_seconds:
                    # Move to end (most recently used)
                    self._cache.move_to_end(key)
                    self.metrics.cache_hits += 1
                    self.metrics.total_cache_lookup_time += time.time() - start_time
                    return response, False
                else:
                    # Expired
                    del self._cache[key]
            
            # Similarity match
            normalized = self._normalize_input(user_input)
            similar_key = self._check_similarity(normalized)
            
            if similar_key and similar_key in self._cache:
                response, timestamp, metadata = self._cache[similar_key]
                
                if time.time() - timestamp < self.ttl_seconds:
                    self.metrics.cache_hits += 1
                    self.metrics.total_cache_lookup_time += time.time() - start_time
                    return response, True
            
            self.metrics.cache_misses += 1
            self.metrics.total_cache_lookup_time += time.time() - start_time
            return None
    
    def set(
        self, 
        npc_name: str, 
        user_input: str, 
        response: str, 
        context_hash: str = "",
        metadata: Dict = None
    ):
        """Cache a response."""
        with self._lock:
            key = self._generate_key(npc_name, user_input, context_hash)
            
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                # Clean up similarity index
                to_remove = [k for k, v in self._similarity_index.items() if v == oldest_key]
                for k in to_remove:
                    del self._similarity_index[k]
            
            # Store
            self._cache[key] = (response, time.time(), metadata or {})
            
            # Update similarity index
            normalized = self._normalize_input(user_input)
            self._similarity_index[normalized] = key
    
    def invalidate(self, npc_name: str = None):
        """Invalidate cache entries, optionally for a specific NPC."""
        with self._lock:
            if npc_name is None:
                self._cache.clear()
                self._similarity_index.clear()
            else:
                # Remove entries for specific NPC
                keys_to_remove = [
                    k for k, (r, t, m) in self._cache.items() 
                    if m.get('npc_name') == npc_name
                ]
                for key in keys_to_remove:
                    del self._cache[key]
                
                # Clean similarity index
                to_remove = [k for k, v in self._similarity_index.items() if v in keys_to_remove]
                for k in to_remove:
                    del self._similarity_index[k]
    
    def save(self, filepath: str):
        """Save cache to disk."""
        with self._lock:
            data = {
                "cache": [
                    {"key": k, "response": v[0], "timestamp": v[1], "metadata": v[2]}
                    for k, v in self._cache.items()
                ],
                "metrics": self.metrics.get_stats()
            }
            
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
    
    def load(self, filepath: str):
        """Load cache from disk."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with self._lock:
                for entry in data.get("cache", []):
                    # Only load non-expired entries
                    if time.time() - entry["timestamp"] < self.ttl_seconds:
                        self._cache[entry["key"]] = (
                            entry["response"],
                            entry["timestamp"],
                            entry.get("metadata", {})
                        )
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "similarity_index_size": len(self._similarity_index),
            **self.metrics.get_stats()
        }


# ============================================
# CONNECTION POOL
# ============================================

class OllamaConnectionPool:
    """
    Connection pool for Ollama API requests.
    
    Features:
    - Connection reuse
    - Retry logic
    - Timeout configuration
    - Health checks
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        pool_size: int = 10,
        max_retries: int = 3,
        timeout: int = 120,
        backoff_factor: float = 0.5
    ):
        self.base_url = base_url
        self.pool_size = pool_size
        self.timeout = timeout
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        
        # Mount adapter with pool
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=pool_size,
            pool_maxsize=pool_size
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Health check
        self._healthy = self._check_health()
    
    def _check_health(self) -> bool:
        """Check if Ollama is healthy."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def is_healthy(self) -> bool:
        """Check connection health."""
        return self._healthy
    
    def post(self, endpoint: str, payload: Dict, timeout: int = None) -> requests.Response:
        """Make a POST request."""
        return self.session.post(
            f"{self.base_url}{endpoint}",
            json=payload,
            timeout=timeout or self.timeout
        )
    
    def get(self, endpoint: str, timeout: int = 5) -> requests.Response:
        """Make a GET request."""
        return self.session.get(
            f"{self.base_url}{endpoint}",
            timeout=timeout
        )
    
    def close(self):
        """Close all connections."""
        self.session.close()


# ============================================
# BATCH PROCESSOR
# ============================================

class BatchProcessor:
    """
    Process multiple NPC requests in parallel.
    
    Features:
    - Parallel execution
    - Configurable concurrency
    - Error handling per request
    - Result aggregation
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        connection_pool: OllamaConnectionPool = None
    ):
        self.max_concurrent = max_concurrent
        self.connection_pool = connection_pool or OllamaConnectionPool()
        self.metrics = PerformanceMetrics()
    
    async def process_batch(
        self,
        requests: List[Dict[str, Any]],
        processor: Callable[[Dict], Any]
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of requests in parallel.
        
        Args:
            requests: List of request dictionaries
            processor: Async function to process each request
            
        Returns:
            List of results (order preserved)
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_one(request: Dict, index: int) -> Tuple[int, Any]:
            async with semaphore:
                try:
                    result = await processor(request)
                    return index, {"success": True, "result": result}
                except Exception as e:
                    self.metrics.errors += 1
                    return index, {"success": False, "error": str(e)}
        
        # Create tasks
        tasks = [
            process_one(req, i) 
            for i, req in enumerate(requests)
        ]
        
        # Run all tasks
        results = await asyncio.gather(*tasks)
        
        # Sort by index and extract results
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]
    
    def process_batch_sync(
        self,
        requests: List[Dict[str, Any]],
        processor: Callable[[Dict], Any]
    ) -> List[Dict[str, Any]]:
        """Synchronous version of batch processing."""
        return asyncio.run(self.process_batch(requests, processor))


# ============================================
# RESPONSE PRE-GENERATION
# ============================================

class ResponsePreGenerator:
    """
    Pre-generate responses for common queries.
    
    Features:
    - Background generation
    - Priority queue
    - Template-based generation
    """
    
    def __init__(
        self,
        connection_pool: OllamaConnectionPool = None,
        cache: ResponseCache = None
    ):
        self.connection_pool = connection_pool or OllamaConnectionPool()
        self.cache = cache or ResponseCache()
        
        # Common queries per NPC archetype
        self.common_queries = {
            "blacksmith": [
                "What can you make?",
                "Do you have any weapons for sale?",
                "Can you repair my armor?",
                "What materials do you need?",
                "Tell me about your craft."
            ],
            "merchant": [
                "What do you have for sale?",
                "Can I trade with you?",
                "What's the price of this?",
                "Do you have any rare items?",
                "Any news from your travels?"
            ],
            "wizard": [
                "Can you teach me magic?",
                "What spells do you know?",
                "Tell me about the arcane arts.",
                "Do you have any potions?",
                "What mysteries have you uncovered?"
            ],
            "guard": [
                "What's happening in town?",
                "Any danger nearby?",
                "Where is the nearest inn?",
                "Who rules this place?",
                "Have you seen anything suspicious?"
            ],
            "innkeeper": [
                "Do you have rooms available?",
                "What's on the menu?",
                "Any news around here?",
                "Who else is staying?",
                "What can you tell me about this area?"
            ]
        }
        
        # Queue for pre-generation
        self._queue: List[Tuple[str, str, int]] = []  # (npc_name, query, priority)
        self._running = False
    
    def add_common_queries(self, npc_name: str, npc_type: str = None):
        """Add common queries for an NPC to the pre-generation queue."""
        queries = self.common_queries.get(npc_type or npc_name.lower(), [])
        
        for priority, query in enumerate(queries):
            self._queue.append((npc_name, query, priority))
        
        # Sort by priority
        self._queue.sort(key=lambda x: x[2])
    
    def pregenerate_all(self, npc_name: str, model: str = "llama3.2:1b"):
        """Pre-generate all queued responses for an NPC."""
        npc_queries = [(n, q, p) for n, q, p in self._queue if n == npc_name]
        
        for _, query, _ in npc_queries:
            # Check if already cached
            cached = self.cache.get(npc_name, query)
            if cached:
                continue
            
            # Generate response (simplified - would need full NPC context)
            try:
                response = self.connection_pool.post(
                    "/api/generate",
                    {
                        "model": model,
                        "prompt": f"Respond briefly as {npc_name}: {query}",
                        "stream": False,
                        "options": {"num_predict": 100}
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    generated = result.get("response", "").strip()
                    
                    # Cache the response
                    self.cache.set(npc_name, query, generated)
                    logger.info(f"Pre-generated response for {npc_name}: {query[:30]}...")
            
            except Exception as e:
                logger.warning(f"Pre-generation failed for {npc_name}: {e}")


# ============================================
# PERFORMANCE MANAGER
# ============================================

class PerformanceManager:
    """
    Central manager for all performance optimizations.
    
    Combines:
    - Response caching
    - Connection pooling
    - Batch processing
    - Pre-generation
    - Metrics
    """
    
    def __init__(
        self,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        pool_size: int = 10,
        max_concurrent: int = 5,
        ollama_url: str = "http://localhost:11434"
    ):
        # Initialize components
        self.cache = ResponseCache(
            max_size=cache_size,
            ttl_seconds=cache_ttl,
            enable_similarity=True
        )
        
        self.connection_pool = OllamaConnectionPool(
            base_url=ollama_url,
            pool_size=pool_size
        )
        
        self.batch_processor = BatchProcessor(
            max_concurrent=max_concurrent,
            connection_pool=self.connection_pool
        )
        
        self.pre_generator = ResponsePreGenerator(
            connection_pool=self.connection_pool,
            cache=self.cache
        )
        
        # Global metrics
        self.metrics = PerformanceMetrics()
        
        # Cache persistence path
        self._cache_path = "cache/npc_responses.json"
    
    def get_cached_response(
        self,
        npc_name: str,
        user_input: str,
        context: Dict = None
    ) -> Optional[str]:
        """Get a cached response if available."""
        context_hash = hashlib.md5(json.dumps(context or {}).encode()).hexdigest()[:8]
        result = self.cache.get(npc_name, user_input, context_hash)
        return result[0] if result else None
    
    def cache_response(
        self,
        npc_name: str,
        user_input: str,
        response: str,
        context: Dict = None,
        metadata: Dict = None
    ):
        """Cache a response."""
        context_hash = hashlib.md5(json.dumps(context or {}).encode()).hexdigest()[:8]
        meta = {"npc_name": npc_name, **(metadata or {})}
        self.cache.set(npc_name, user_input, response, context_hash, meta)
    
    def record_request(
        self,
        generation_time: float,
        tokens: int,
        from_cache: bool = False
    ):
        """Record request metrics."""
        self.metrics.record_request(generation_time, tokens, from_cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        return {
            "performance": self.metrics.get_stats(),
            "cache": self.cache.get_stats(),
            "connection_pool": {
                "healthy": self.connection_pool.is_healthy(),
                "pool_size": self.connection_pool.pool_size
            }
        }
    
    def save_state(self, path: str = None):
        """Save cache state to disk."""
        self.cache.save(path or self._cache_path)
    
    def load_state(self, path: str = None):
        """Load cache state from disk."""
        self.cache.load(path or self._cache_path)
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics.reset()
        self.cache.metrics.reset()
    
    def optimize_for_npc(self, npc_name: str, npc_type: str = None):
        """Run optimizations for a specific NPC."""
        # Pre-generate common responses
        self.pre_generator.add_common_queries(npc_name, npc_type)
        self.pre_generator.pregenerate_all(npc_name)


# ============================================
# CACHED NPC DIALOGUE WRAPPER
# ============================================

class CachedNPCDialogue:
    """
    Wrapper for NPCDialogue that adds caching.
    
    Drop-in replacement for NPCDialogue with performance optimizations.
    """
    
    def __init__(
        self,
        character_name: str,
        character_card_path: str,
        cache_manager: PerformanceManager = None,
        model: str = "llama3.2:1b",
        **kwargs
    ):
        from npc_dialogue import NPCDialogue
        
        # Create underlying NPC
        self._npc = NPCDialogue(
            character_name=character_name,
            character_card_path=character_card_path,
            model=model,
            **kwargs
        )
        
        # Performance manager
        self.perf = cache_manager or PerformanceManager()
        
        # Expose NPC properties
        self.character_name = character_name
        self.model = model
    
    def generate_response(
        self,
        user_input: str,
        game_state: Dict = None,
        show_thinking: bool = False
    ) -> str:
        """Generate response with caching."""
        
        # Check cache first
        cached = self.perf.get_cached_response(
            self.character_name,
            user_input,
            game_state
        )
        
        if cached:
            if show_thinking:
                print(f"⚡ {self.character_name} (from cache)")
            self.perf.record_request(0, 0, from_cache=True)
            
            # Update NPC history
            self._npc.history.append({"role": "user", "content": user_input})
            self._npc.history.append({"role": "assistant", "content": cached})
            
            return cached
        
        # Generate new response
        start_time = time.time()
        response = self._npc.generate_response(user_input, game_state, show_thinking)
        elapsed = time.time() - start_time
        
        # Cache it
        self.perf.cache_response(
            self.character_name,
            user_input,
            response,
            game_state
        )
        
        # Record metrics
        # Estimate tokens (rough approximation)
        tokens = len(response.split()) * 1.3
        self.perf.record_request(elapsed, int(tokens), from_cache=False)
        
        return response
    
    def __getattr__(self, name):
        """Delegate to underlying NPC."""
        return getattr(self._npc, name)


# ============================================
# DEMO
# ============================================

def demo_performance():
    """Demo performance optimizations."""
    print("=" * 60)
    print("Performance Optimization Demo")
    print("=" * 60)
    
    # Initialize performance manager
    perf = PerformanceManager(
        cache_size=100,
        cache_ttl=3600,
        pool_size=5
    )
    
    print("\n1. Connection Pool Health:")
    print(f"   Healthy: {perf.connection_pool.is_healthy()}")
    
    print("\n2. Testing Cache:")
    
    # Simulate caching
    perf.cache_response("Blacksmith", "Hello!", "Well met, traveler!")
    
    cached = perf.get_cached_response("Blacksmith", "Hello!")
    print(f"   Cached response: {cached}")
    
    # Similar query
    similar = perf.get_cached_response("Blacksmith", "hello")
    print(f"   Similar query result: {similar}")
    
    print("\n3. Performance Stats:")
    stats = perf.get_stats()
    for key, value in stats["performance"].items():
        print(f"   {key}: {value}")
    
    print("\n4. Cache Stats:")
    cache_stats = stats["cache"]
    for key, value in cache_stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    demo_performance()
