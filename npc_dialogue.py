"""
NPC Dialogue System - Core Logic
Local LLM-powered character conversations for games
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
import requests
from relationship_tracking import RelationshipTracker, RelationshipLevel


class NPCDialogue:
    """
    An AI-powered NPC that can have conversations with players.
    Uses local LLM (via Ollama) for dialogue generation.
    """
    
    def __init__(
        self,
        character_name: str,
        character_card_path: str,
        model: str = "llama3.2:1b",
        player_id: str = "player",
        max_history: int = 20,
        temperature: float = 0.8,
        max_tokens: int = 500,
        relationship_tracker: Optional[RelationshipTracker] = None,
    ):
        """
        Initialize an NPC with a character card and model settings.
        
        Args:
            character_name: Name of the NPC
            character_card_path: Path to JSON character card
            model: Ollama model name (e.g., "llama3.2:1b")
            player_id: Unique identifier for the player
            max_history: Number of conversation turns to remember
            temperature: Randomness (0.0-1.0, higher = more creative)
            max_tokens: Maximum response length
            relationship_tracker: Optional RelationshipTracker instance
        """
        self.character_name = character_name
        self.model = model
        self.player_id = player_id
        self.max_history = max_history
        self.base_temperature = temperature  # Store base temperature
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Load character card
        self.character_card = self._load_character_card(character_card_path)
        
        # Conversation history
        self.history: List[Dict[str, str]] = []
        
        # Relationship tracking
        self.relationship_tracker = relationship_tracker
        if self.relationship_tracker:
            # Adjust temperature based on current relationship
            self.temperature = self.relationship_tracker.get_temperature_adjustment(
                character_name, self.base_temperature
            )
        
        # Ollama API endpoint
        self.api_url = "http://localhost:11434/api/chat"
        
        # Verify Ollama is running
        self._check_ollama_connection()
    
    def _load_character_card(self, path: str) -> Dict:
        """Load character definition from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _check_ollama_connection(self):
        """Verify Ollama is running and model is available."""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [m['name'] for m in response.json().get('models', [])]
            
            if self.model not in models:
                print(f"⚠️  Warning: Model '{self.model}' not found in Ollama.")
                print(f"   Run: ollama pull {self.model}")
                available = ", ".join(models[:5]) + ("..." if len(models) > 5 else "")
                print(f"   Available: {available}")
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                "Ollama is not running! Start it with: ollama serve\n"
                "Or install: curl -fsSL https://ollama.com/install.sh | sh"
            )
    
    def _build_system_prompt(self, game_state: Optional[Dict] = None) -> str:
        """Build the system prompt with character personality and context."""
        
        # Base character info
        prompt = f"""You are {self.character_name}. 

CHARACTER DESCRIPTION:
{self.character_card.get('description', '')}

PERSONALITY:
{self.character_card.get('personality', '')}

IMPORTANT:
- Stay fully in character at all times
- {self.character_card.get('speaking_style', 'Speak naturally')}
- Don't break the fourth wall
- Be engaging but concise (2-4 sentences typical)
- Remember previous conversations with this player
"""

        # Add relationship context if tracker is available
        if self.relationship_tracker:
            rel_level = self.relationship_tracker.get_level(self.character_name)
            rel_modifier = self.relationship_tracker.get_speaking_style_modifier(self.character_name)
            
            if rel_modifier:
                prompt += f"\nYOUR RELATIONSHIP WITH THIS PLAYER:\n{rel_modifier}\n"
            
            prompt += f"\nCurrent relationship level: {rel_level.name}\n"
        
        # Add any game state context
        if game_state:
            prompt += f"\nCURRENT SITUATION:\n{self._format_game_state(game_state)}\n"
        
        return prompt
    
    def _format_game_state(self, game_state: Dict) -> str:
        """Format game state for context."""
        formatted = []
        for key, value in game_state.items():
            formatted.append(f"- {key}: {value}")
        return "\n".join(formatted)
    
    def _format_messages(
        self,
        user_input: str,
        game_state: Optional[Dict] = None
    ) -> List[Dict]:
        """Format messages for Ollama API."""
        
        messages = [
            {"role": "system", "content": self._build_system_prompt(game_state)},
        ]
        
        # Add conversation history
        messages.extend(self.history)
        
        # Add current user input
        messages.append({"role": "user", "content": user_input})
        
        return messages
    
    def generate_response(
        self,
        user_input: str,
        game_state: Optional[Dict] = None,
        show_thinking: bool = False
    ) -> str:
        """
        Generate an NPC response to player input.
        
        Args:
            user_input: What the player said/asked
            game_state: Current game context (location, quests, etc.)
            show_thinking: Print generation info
            
        Returns:
            NPC's response as text
        """
        if show_thinking:
            print(f"🤖 {self.character_name} is thinking...", end="", flush=True)
        
        start_time = time.time()
        
        # Prepare request
        payload = {
            "model": self.model,
            "messages": self._format_messages(user_input, game_state),
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        
        # Generate response
        try:
            response = requests.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            # Extract the message
            npc_response = result['message']['content'].strip()
            
            # Update history
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": npc_response})
            
            # Trim history if too long
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
            
            elapsed = time.time() - start_time

            if show_thinking:
                # Try to get token count from response (Ollama returns eval_count)
                tokens = result.get('eval_count', 0)
                tps = tokens / elapsed if elapsed > 0 else 0
                print(f" ✓ ({tokens} tokens, {elapsed:.1f}s, {tps:.1f} tok/s)")

            return npc_response
            
        except requests.exceptions.RequestException as e:
            return f"[Error: Failed to generate response - {e}]"
    
    def save_history(self, directory: str = "conversation_history"):
        """Save conversation history to disk."""
        os.makedirs(directory, exist_ok=True)
        
        filename = os.path.join(
            directory,
            f"{self.character_name}_{self.player_id}.json"
        )
        
        data = {
            "character_name": self.character_name,
            "player_id": self.player_id,
            "model": self.model,
            "timestamp": time.time(),
            "history": self.history,
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_history(self, directory: str = "conversation_history"):
        """Load conversation history from disk."""
        filename = os.path.join(
            directory,
            f"{self.character_name}_{self.player_id}.json"
        )
        
        if not os.path.exists(filename):
            return
        
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.history = data.get('history', [])
        
        print(f"📜 Loaded {len(self.history) // 2} past conversations")
    
    def reset_history(self):
        """Clear conversation history."""
        self.history = []
        print(f"🗑️  Conversation history cleared")
    
    def get_stats(self) -> Dict:
        """Get statistics about current conversation."""
        turns = len(self.history) // 2
        npc_words = sum(
            len(msg['content'].split())
            for msg in self.history
            if msg['role'] == 'assistant'
        )
        
        return {
            "character": self.character_name,
            "model": self.model,
            "turns": turns,
            "npc_words": npc_words,
            "history_size": len(self.history),
        }
    
    def print_character_info(self):
        """Display character card information."""
        print(f"\n{'='*60}")
        print(f"CHARACTER: {self.character_name}")
        print(f"{'='*60}")
        print(f"\n📖 Description:")
        print(f"   {self.character_card.get('description', 'N/A')}")
        print(f"\n🎭 Personality:")
        print(f"   {self.character_card.get('personality', 'N/A')}")
        print(f"\n💬 Speaking Style:")
        print(f"   {self.character_card.get('speaking_style', 'Natural')}")
        print(f"\n📝 First Message:")
        print(f"   {self.character_card.get('first_mes', 'N/A')}")
        
        # Show relationship info if available
        if self.relationship_tracker:
            rel_level = self.relationship_tracker.get_level(self.character_name)
            rel_score = self.relationship_tracker.get_relationship(self.character_name).score
            print(f"\n💖 Relationship: {rel_level.name} ({rel_score:+.1f})")
        
        print(f"\n{'='*60}\n")
    
    def get_relationship_level(self) -> Optional[str]:
        """Get current relationship level with the player."""
        if not self.relationship_tracker:
            return None
        return self.relationship_tracker.get_level(self.character_name).name
    
    def get_relationship_score(self) -> Optional[float]:
        """Get current relationship score with the player."""
        if not self.relationship_tracker:
            return None
        return self.relationship_tracker.get_relationship(self.character_name).score
    
    def update_from_quest(self, quest_id: str, success: bool = True, reward: float = 15.0) -> Optional[float]:
        """
        Update relationship after quest completion.
        
        Args:
            quest_id: Unique quest identifier
            success: Whether quest was completed successfully
            reward: Score change on success (penalty on failure)
            
        Returns:
            New relationship score, or None if no tracker
        """
        if not self.relationship_tracker:
            return None
        return self.relationship_tracker.update_from_quest(
            self.character_name, quest_id, success, reward
        )
    
    def update_from_gift(self, item_name: str, value: float = 5.0) -> Optional[float]:
        """
        Update relationship after giving a gift.
        
        Args:
            item_name: Name of the gifted item
            value: Relationship value of the item
            
        Returns:
            New relationship score, or None if no tracker
        """
        if not self.relationship_tracker:
            return None
        return self.relationship_tracker.update_from_gift(
            self.character_name, item_name, value
        )
    
    def update_from_dialogue(self, dialogue_type: str, sentiment: float = 0.0) -> Optional[float]:
        """
        Update relationship from dialogue choice.
        
        Args:
            dialogue_type: Type of dialogue ('friendly', 'hostile', 'neutral', 'flirt', 'insult')
            sentiment: Custom sentiment value (-1.0 to 1.0)
            
        Returns:
            New relationship score, or None if no tracker
        """
        if not self.relationship_tracker:
            return None
        return self.relationship_tracker.update_from_dialogue(
            self.character_name, dialogue_type, sentiment
        )
    
    def refresh_temperature(self):
        """Refresh temperature based on current relationship score."""
        if self.relationship_tracker:
            self.temperature = self.relationship_tracker.get_temperature_adjustment(
                self.character_name, self.base_temperature
            )



class NPCManager:
    """
    Manage multiple NPCs in a game world.
    Handles loading characters and maintaining separate conversations.
    """
    
    def __init__(self, model: str = "llama3.2:1b", relationship_tracker: Optional[RelationshipTracker] = None):
        self.model = model
        self.relationship_tracker = relationship_tracker
        self.npcs: Dict[str, NPCDialogue] = {}
        self.active_npc: Optional[NPCDialogue] = None
    
    def load_character(
        self,
        character_path: str,
        player_id: str = "player",
        **kwargs
    ) -> NPCDialogue:
        """Load a character from a JSON file."""
        with open(character_path, 'r', encoding='utf-8') as f:
            card = json.load(f)
        
        character_name = card.get('name', 'Unknown')
        
        npc = NPCDialogue(
            character_name=character_name,
            character_card_path=character_path,
            model=self.model,
            player_id=player_id,
            relationship_tracker=self.relationship_tracker,
            **kwargs
        )
        
        self.npcs[character_name] = npc
        return npc
    
    def set_active(self, character_name: str):
        """Set the currently active NPC for conversation."""
        if character_name not in self.npcs:
            raise ValueError(f"NPC '{character_name}' not loaded")
        self.active_npc = self.npcs[character_name]
    
    def get_active(self) -> Optional[NPCDialogue]:
        """Get the currently active NPC."""
        return self.active_npc
    
    def list_characters(self) -> List[str]:
        """List all loaded character names."""
        return list(self.npcs.keys())
    
    def save_all_histories(self, directory: str = "conversation_history"):
        """Save all conversation histories."""
        for npc in self.npcs.values():
            npc.save_history(directory)
    
    def load_all_histories(self, directory: str = "conversation_history"):
        """Load all conversation histories."""
        for npc in self.npcs.values():
            npc.load_history(directory)
    
    def save_relationships(self, filepath: Optional[str] = None):
        """Save relationship data for all NPCs."""
        if not self.relationship_tracker:
            print("⚠️  No relationship tracker configured")
            return
        self.relationship_tracker.save(filepath)
    
    def load_relationships(self, filepath: Optional[str] = None):
        """Load relationship data for all NPCs."""
        if not self.relationship_tracker:
            print("⚠️  No relationship tracker configured")
            return
        self.relationship_tracker.load(filepath)
        # Refresh temperatures for all NPCs based on loaded relationships
        for npc in self.npcs.values():
            npc.refresh_temperature()
    
    def print_relationship_summary(self):
        """Print relationship summary for all NPCs."""
        if not self.relationship_tracker:
            print("⚠️  No relationship tracker configured")
            return
        self.relationship_tracker.print_summary()
    
    def get_relationship_tracker(self) -> Optional[RelationshipTracker]:
        """Get the relationship tracker instance."""
        return self.relationship_tracker

