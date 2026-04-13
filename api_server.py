"""
NPC Dialogue API Server
FastAPI REST API for Unity/game engine integration
"""

import os
import json
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from npc_dialogue import NPCDialogue, NPCManager
from relationship_tracking import RelationshipTracker
from quest_generator import QuestGenerator, QuestManager, QuestType, ObjectiveType
from voice_synthesis import VoiceSystem, VoiceConfig, VoiceProvider

# Initialize FastAPI app
app = FastAPI(
    title="NPC Dialogue System API",
    description="REST API for AI-powered NPC dialogue in games",
    version="1.2.0"
)

# Enable CORS for Unity/WebView access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
manager: Optional[NPCManager] = None
relationship_tracker: Optional[RelationshipTracker] = None
quest_manager: Optional[QuestManager] = None
voice_system: Optional[VoiceSystem] = None
CHARACTER_CARDS_DIR = Path("character_cards")


# Request/Response Models
class GenerateRequest(BaseModel):
    npc_name: str
    player_input: str
    player_id: str = "player"
    game_state: Optional[Dict[str, Any]] = None


class GenerateResponse(BaseModel):
    response: str
    npc_name: str
    tokens: int
    elapsed_time: float
    tokens_per_second: float


class LoadCharacterRequest(BaseModel):
    character_path: str
    player_id: str = "player"


class UpdateRelationshipRequest(BaseModel):
    npc_name: str
    player_id: str
    change: int
    reason: Optional[str] = None


class SetFactionRequest(BaseModel):
    npc_name: str
    faction: str


class SaveHistoryRequest(BaseModel):
    npc_name: str
    player_id: str
    directory: str = "conversation_history"


class LoadHistoryRequest(BaseModel):
    npc_name: str
    player_id: str
    directory: str = "conversation_history"


class CharacterInfo(BaseModel):
    name: str
    description: str
    personality: str
    speaking_style: str


class RelationshipInfo(BaseModel):
    npc_name: str
    player_id: str
    score: int
    level: str
    history_count: int


class StatusResponse(BaseModel):
    status: str
    version: str
    loaded_npcs: List[str]
    model: str
    ollama_connected: bool


# Startup/Shutdown
@app.on_event("startup")
async def startup_event():
    """Initialize the NPC system on server start."""
    global manager, relationship_tracker, quest_manager, voice_system
    
    # Initialize relationship tracker
    relationship_tracker = RelationshipTracker(save_path="relationship_data")
    
    # Initialize NPC manager
    manager = NPCManager(
        model="llama3.2:1b",
        relationship_tracker=relationship_tracker
    )
    
    # Initialize quest manager
    quest_generator = QuestGenerator(relationship_tracker=relationship_tracker)
    quest_manager = QuestManager(
        quest_generator=quest_generator,
        relationship_tracker=relationship_tracker,
        save_dir="saves"
    )
    
    # Initialize voice system
    voice_system = VoiceSystem(
        cache_dir="voice_cache",
        output_dir="voice_output",
        default_provider=VoiceProvider.EDGE_TTS
    )
    
    # Check Ollama connection
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        print(f"✅ Connected to Ollama")
    except:
        print(f"⚠️  Warning: Could not connect to Ollama. Make sure it's running.")


@app.on_event("shutdown")
async def shutdown_event():
    """Save data on server shutdown."""
    global relationship_tracker
    if relationship_tracker:
        relationship_tracker.save()
        print("💾 Saved relationship data")


# Health Check
@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get API server status."""
    ollama_connected = False
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        ollama_connected = response.status_code == 200
    except:
        pass
    
    return StatusResponse(
        status="running",
        version="1.2.0",
        loaded_npcs=list(manager.npcs.keys()) if manager else [],
        model=manager.model if manager else "unknown",
        ollama_connected=ollama_connected
    )


# Dialogue Generation
@app.post("/api/dialogue/generate", response_model=GenerateResponse)
async def generate_dialogue(request: GenerateRequest):
    """Generate an NPC response to player input."""
    if not manager:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    # Load NPC if not already loaded
    if request.npc_name not in manager.npcs:
        # Try to find character card
        char_path = CHARACTER_CARDS_DIR / f"{request.npc_name.lower()}.json"
        if not char_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Character '{request.npc_name}' not found"
            )
        
        try:
            manager.load_character(
                str(char_path),
                player_id=request.player_id
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load character: {str(e)}"
            )
    
    # Get the NPC
    npc = manager.npcs[request.npc_name]
    
    # Generate response
    import time
    start_time = time.time()
    
    try:
        response = npc.generate_response(
            request.player_input,
            game_state=request.game_state,
            show_thinking=False
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate response: {str(e)}"
        )
    
    elapsed = time.time() - start_time
    
    # Estimate tokens (rough approximation)
    tokens = len(response.split()) * 1.3  # Rough token estimate
    tps = tokens / elapsed if elapsed > 0 else 0
    
    return GenerateResponse(
        response=response,
        npc_name=request.npc_name,
        tokens=int(tokens),
        elapsed_time=round(elapsed, 2),
        tokens_per_second=round(tps, 1)
    )


@app.post("/api/dialogue/generate/stream")
async def generate_dialogue_stream(request: GenerateRequest):
    """Generate NPC response with streaming (SSE)."""
    if not manager:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    # Load NPC if not already loaded
    if request.npc_name not in manager.npcs:
        char_path = CHARACTER_CARDS_DIR / f"{request.npc_name.lower()}.json"
        if not char_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Character '{request.npc_name}' not found"
            )
        manager.load_character(str(char_path), player_id=request.player_id)
    
    npc = manager.npcs[request.npc_name]
    
    async def event_generator():
        """Generate SSE events for streaming response."""
        try:
            # Use Ollama's streaming API
            import requests as req
            
            messages = npc._format_messages(request.player_input, request.game_state)
            
            payload = {
                "model": npc.model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": npc.temperature,
                    "num_predict": npc.max_tokens,
                }
            }
            
            full_response = ""
            
            with req.post(
                "http://localhost:11434/api/chat",
                json=payload,
                stream=True,
                timeout=120
            ) as response:
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if 'message' in data:
                            token = data['message'].get('content', '')
                            if token:
                                full_response += token
                                yield f"data: {json.dumps({'token': token})}\n\n"
                        
                        if data.get('done', False):
                            # Update history
                            npc.history.append({"role": "user", "content": request.player_input})
                            npc.history.append({"role": "assistant", "content": full_response})
                            if len(npc.history) > npc.max_history:
                                npc.history = npc.history[-npc.max_history:]
                            
                            yield f"data: {json.dumps({'done': True, 'full_response': full_response})}\n\n"
                            break
                            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# Character Management
@app.get("/api/characters")
async def list_characters():
    """List all loaded characters and available character cards."""
    loaded = list(manager.npcs.keys()) if manager else []
    
    # Find available character cards
    available = []
    if CHARACTER_CARDS_DIR.exists():
        for card_file in CHARACTER_CARDS_DIR.glob("*.json"):
            try:
                with open(card_file, 'r') as f:
                    card = json.load(f)
                available.append({
                    "name": card.get("name", card_file.stem),
                    "file": str(card_file),
                    "description": card.get("description", "")[:100] + "..."
                })
            except:
                pass
    
    return {
        "loaded": loaded,
        "available": available
    }


@app.post("/api/characters/load")
async def load_character(request: LoadCharacterRequest):
    """Load a character from a file."""
    if not manager:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    # Resolve path
    char_path = Path(request.character_path)
    if not char_path.is_absolute():
        char_path = CHARACTER_CARDS_DIR / request.character_path
    
    if not char_path.exists():
        # Try adding .json extension
        char_path = Path(str(char_path) + ".json")
    
    if not char_path.exists():
        raise HTTPException(status_code=404, detail=f"Character file not found: {request.character_path}")
    
    try:
        npc = manager.load_character(
            str(char_path),
            player_id=request.player_id
        )
        return {
            "status": "loaded",
            "character_name": npc.character_name,
            "description": npc.character_card.get("description", "")[:100]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load character: {str(e)}")


@app.get("/api/characters/{npc_name}")
async def get_character_info(npc_name: str):
    """Get information about a loaded character."""
    if not manager or npc_name not in manager.npcs:
        raise HTTPException(status_code=404, detail=f"Character '{npc_name}' not loaded")
    
    npc = manager.npcs[npc_name]
    
    return CharacterInfo(
        name=npc.character_name,
        description=npc.character_card.get("description", ""),
        personality=npc.character_card.get("personality", ""),
        speaking_style=npc.character_card.get("speaking_style", "")
    )


@app.delete("/api/characters/{npc_name}")
async def unload_character(npc_name: str):
    """Unload a character from memory."""
    if not manager or npc_name not in manager.npcs:
        raise HTTPException(status_code=404, detail=f"Character '{npc_name}' not loaded")
    
    # Save history before unloading
    npc = manager.npcs[npc_name]
    npc.save_history()
    
    del manager.npcs[npc_name]
    
    if manager.active_npc == npc:
        manager.active_npc = None
    
    return {"status": "unloaded", "npc_name": npc_name}


# Relationships
@app.get("/api/relationships/{npc_name}/{player_id}", response_model=RelationshipInfo)
async def get_relationship(npc_name: str, player_id: str):
    """Get relationship between NPC and player."""
    if not relationship_tracker:
        raise HTTPException(status_code=503, detail="Relationship system not initialized")
    
    score = relationship_tracker.get_relationship(npc_name, player_id)
    level = relationship_tracker.get_level_name(npc_name, player_id)
    history = relationship_tracker.get_history(npc_name, player_id)
    
    return RelationshipInfo(
        npc_name=npc_name,
        player_id=player_id,
        score=score,
        level=level,
        history_count=len(history)
    )


@app.post("/api/relationships/update")
async def update_relationship(request: UpdateRelationshipRequest):
    """Update relationship between NPC and player."""
    if not relationship_tracker:
        raise HTTPException(status_code=503, detail="Relationship system not initialized")
    
    new_score = relationship_tracker.update(
        request.npc_name,
        request.player_id,
        request.change,
        request.reason
    )
    
    level = relationship_tracker.get_level_name(request.npc_name, request.player_id)
    
    return {
        "status": "updated",
        "npc_name": request.npc_name,
        "player_id": request.player_id,
        "new_score": new_score,
        "level": level
    }


@app.get("/api/relationships/player/{player_id}")
async def get_player_relationships(player_id: str):
    """Get all relationships for a player."""
    if not relationship_tracker:
        raise HTTPException(status_code=503, detail="Relationship system not initialized")
    
    return relationship_tracker.get_all_relationships(player_id)


@app.post("/api/factions/set")
async def set_npc_faction(request: SetFactionRequest):
    """Assign an NPC to a faction."""
    if not relationship_tracker:
        raise HTTPException(status_code=503, detail="Relationship system not initialized")
    
    relationship_tracker.set_faction(request.npc_name, request.faction)
    
    return {
        "status": "set",
        "npc_name": request.npc_name,
        "faction": request.faction
    }


@app.get("/api/factions/{faction}/reputation/{player_id}")
async def get_faction_reputation(faction: str, player_id: str):
    """Get average reputation with a faction."""
    if not relationship_tracker:
        raise HTTPException(status_code=503, detail="Relationship system not initialized")
    
    score = relationship_tracker.get_faction_reputation(player_id, faction)
    
    return {
        "faction": faction,
        "player_id": player_id,
        "average_reputation": score
    }


# Conversation History
@app.post("/api/history/save")
async def save_conversation_history(request: SaveHistoryRequest):
    """Save conversation history for an NPC-player pair."""
    if not manager or request.npc_name not in manager.npcs:
        raise HTTPException(status_code=404, detail=f"Character '{request.npc_name}' not loaded")
    
    npc = manager.npcs[request.npc_name]
    npc.save_history(request.directory)
    
    return {
        "status": "saved",
        "npc_name": request.npc_name,
        "player_id": request.player_id,
        "turns": len(npc.history) // 2
    }


@app.post("/api/history/load")
async def load_conversation_history(request: LoadHistoryRequest):
    """Load conversation history for an NPC-player pair."""
    if not manager or request.npc_name not in manager.npcs:
        raise HTTPException(status_code=404, detail=f"Character '{request.npc_name}' not loaded")
    
    npc = manager.npcs[request.npc_name]
    npc.load_history(request.directory)
    
    return {
        "status": "loaded",
        "npc_name": request.npc_name,
        "player_id": request.player_id,
        "turns": len(npc.history) // 2
    }


@app.delete("/api/history/{npc_name}/{player_id}")
async def clear_conversation_history(npc_name: str, player_id: str):
    """Clear conversation history for an NPC-player pair."""
    if not manager or npc_name not in manager.npcs:
        raise HTTPException(status_code=404, detail=f"Character '{npc_name}' not loaded")
    
    npc = manager.npcs[npc_name]
    npc.reset_history()
    
    return {
        "status": "cleared",
        "npc_name": npc_name,
        "player_id": player_id
    }


# Game State Integration
@app.post("/api/dialogue/generate-with-state")
async def generate_with_game_state(
    npc_name: str,
    player_input: str,
    player_id: str = "player",
    location: Optional[str] = None,
    time_of_day: Optional[str] = None,
    current_quest: Optional[str] = None,
    player_health: Optional[int] = None,
    player_gold: Optional[int] = None
):
    """Generate NPC response with structured game state."""
    game_state = {}
    
    if location:
        game_state["location"] = location
    if time_of_day:
        game_state["time"] = time_of_day
    if current_quest:
        game_state["current_quest"] = current_quest
    if player_health is not None:
        game_state["player_health"] = player_health
    if player_gold is not None:
        game_state["player_gold"] = player_gold
    
    request = GenerateRequest(
        npc_name=npc_name,
        player_input=player_input,
        player_id=player_id,
        game_state=game_state if game_state else None
    )
    
    return await generate_dialogue(request)


# Utility Endpoints
@app.post("/api/save-all")
async def save_all_data():
    """Save all conversation history and relationship data."""
    if manager:
        for npc in manager.npcs.values():
            npc.save_history()
    
    if relationship_tracker:
        relationship_tracker.save()
    
    return {"status": "saved", "message": "All data saved successfully"}


@app.post("/api/export/{player_id}")
async def export_player_data(player_id: str):
    """Export all player data for game save."""
    if not relationship_tracker:
        raise HTTPException(status_code=503, detail="Relationship system not initialized")
    
    return relationship_tracker.export_player_data(player_id)


@app.post("/api/import")
async def import_player_data(data: Dict[str, Any]):
    """Import player data from game save."""
    if not relationship_tracker:
        raise HTTPException(status_code=503, detail="Relationship system not initialized")
    
    try:
        relationship_tracker.import_player_data(data)
        return {"status": "imported", "player_id": data.get("player_id")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")


# ============================================
# QUEST SYSTEM ENDPOINTS
# ============================================

class GenerateQuestsRequest(BaseModel):
    npc_name: str
    npc_archetype: Optional[str] = None
    npc_location: Optional[str] = None
    player_level: int = 1
    count: int = 2


class QuestProgressRequest(BaseModel):
    objective_type: str
    target: str
    amount: int = 1


class QuestInfo(BaseModel):
    id: str
    name: str
    description: str
    quest_giver: str
    quest_type: str
    status: str
    difficulty: int
    progress: float
    objectives: List[Dict[str, Any]]
    time_remaining: Optional[int]


@app.get("/api/quests/npc/{npc_name}")
async def get_npc_quests(npc_name: str, player_level: int = 1):
    """Get available quests from an NPC."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    player_state = {"level": player_level}
    quests = quest_manager.get_available_quests(npc_name, player_state)
    
    return {
        "npc_name": npc_name,
        "quests": [q.to_dict() for q in quests]
    }


@app.post("/api/quests/generate")
async def generate_quests(request: GenerateQuestsRequest):
    """Generate new quests for an NPC."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    npc_data = {}
    if request.npc_archetype:
        npc_data["archetype"] = request.npc_archetype
    if request.npc_location:
        npc_data["location"] = request.npc_location
    
    player_state = {"level": request.player_level}
    
    quests = quest_manager.generate_quests_for_npc(
        npc_name=request.npc_name,
        npc_data=npc_data,
        player_state=player_state,
        count=request.count
    )
    
    return {
        "status": "generated",
        "npc_name": request.npc_name,
        "quests": [q.to_dict() for q in quests]
    }


@app.post("/api/quests/{quest_id}/accept")
async def accept_quest(quest_id: str):
    """Accept a quest."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    quest = quest_manager.accept_quest(quest_id)
    
    if not quest:
        raise HTTPException(status_code=404, detail=f"Quest '{quest_id}' not found or not available")
    
    return {
        "status": "accepted",
        "quest": quest.to_dict()
    }


@app.post("/api/quests/{quest_id}/abandon")
async def abandon_quest(quest_id: str):
    """Abandon an active quest."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    success = quest_manager.abandon_quest(quest_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Quest '{quest_id}' not found or not active")
    
    return {"status": "abandoned", "quest_id": quest_id}


@app.get("/api/quests/active")
async def get_active_quests():
    """Get all active quests for the player."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    quests = quest_manager.get_active_quests()
    
    return {
        "count": len(quests),
        "quests": [q.to_dict() for q in quests]
    }


@app.get("/api/quests/{quest_id}")
async def get_quest(quest_id: str):
    """Get details of a specific quest."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    quest = quest_manager.get_quest(quest_id)
    
    if not quest:
        raise HTTPException(status_code=404, detail=f"Quest '{quest_id}' not found")
    
    return quest.to_dict()


@app.post("/api/quests/{quest_id}/progress")
async def update_quest_progress(quest_id: str, request: QuestProgressRequest):
    """Update progress on a quest objective."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    try:
        obj_type = ObjectiveType(request.objective_type)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid objective type: {request.objective_type}"
        )
    
    # Update progress on all matching active quests
    updates = quest_manager.update_progress(obj_type, request.target, request.amount)
    
    if quest_id not in updates:
        raise HTTPException(
            status_code=404, 
            detail=f"Quest '{quest_id}' not found or objective doesn't match"
        )
    
    quest = quest_manager.get_quest(quest_id)
    
    return {
        "status": "updated",
        "quest_id": quest_id,
        "progress": updates[quest_id],
        "is_complete": quest.is_complete() if quest else False
    }


@app.post("/api/quests/{quest_id}/complete")
async def complete_quest(quest_id: str):
    """Complete a quest and claim rewards."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    rewards = quest_manager.complete_quest(quest_id)
    
    if not rewards:
        quest = quest_manager.get_quest(quest_id)
        if quest and not quest.is_complete():
            raise HTTPException(
                status_code=400, 
                detail="Quest objectives not complete"
            )
        raise HTTPException(status_code=404, detail=f"Quest '{quest_id}' not found or not active")
    
    return {
        "status": "completed",
        "quest_id": quest_id,
        "rewards": rewards
    }


@app.get("/api/quests/summary")
async def get_quest_summary():
    """Get summary of quest state."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    return quest_manager.get_summary()


@app.post("/api/quests/save")
async def save_quest_data(player_id: str = "player"):
    """Save quest state to file."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    quest_manager.save(player_id)
    
    return {"status": "saved", "player_id": player_id}


@app.post("/api/quests/load")
async def load_quest_data(player_id: str = "player"):
    """Load quest state from file."""
    if not quest_manager:
        raise HTTPException(status_code=503, detail="Quest system not initialized")
    
    quest_manager.load(player_id)
    
    return {
        "status": "loaded",
        "player_id": player_id,
        "summary": quest_manager.get_summary()
    }


# ============================================
# VOICE SYNTHESIS ENDPOINTS
# ============================================

class SynthesizeRequest(BaseModel):
    text: str
    npc_name: Optional[str] = None
    voice_id: Optional[str] = None
    provider: Optional[str] = None
    speed: float = 1.0
    use_cache: bool = True


class RegisterVoiceRequest(BaseModel):
    npc_name: str
    voice_id: str
    provider: str = "edge_tts"
    speed: float = 1.0
    pitch: float = 1.0


@app.post("/api/voice/synthesize")
async def synthesize_voice(request: SynthesizeRequest):
    """Synthesize speech from text."""
    if not voice_system:
        raise HTTPException(status_code=503, detail="Voice system not initialized")
    
    # Build voice config
    voice_config = None
    if request.voice_id:
        provider = VoiceProvider(request.provider) if request.provider else None
        voice_config = VoiceConfig(
            name="Custom",
            provider=provider or voice_system.default_provider,
            voice_id=request.voice_id,
            speed=request.speed,
        )
    
    # Determine provider
    provider = None
    if request.provider:
        try:
            provider = VoiceProvider(request.provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")
    
    # Synthesize
    result = await voice_system.synthesize(
        text=request.text,
        npc_name=request.npc_name,
        voice_config=voice_config,
        provider=provider,
        use_cache=request.use_cache,
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    
    return {
        "success": result.success,
        "audio_path": result.audio_path,
        "duration_seconds": result.duration_seconds,
        "provider": result.provider.value,
        "voice_id": result.voice_id,
        "cached": result.cached,
    }


@app.get("/api/voice/synthesize/{npc_name}")
async def synthesize_npc_voice(npc_name: str, text: str):
    """Synthesize speech for a specific NPC using their registered voice."""
    if not voice_system:
        raise HTTPException(status_code=503, detail="Voice system not initialized")
    
    result = await voice_system.synthesize(
        text=text,
        npc_name=npc_name,
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    
    return {
        "success": result.success,
        "audio_path": result.audio_path,
        "duration_seconds": result.duration_seconds,
        "provider": result.provider.value,
        "voice_id": result.voice_id,
        "cached": result.cached,
    }


@app.post("/api/voice/register")
async def register_npc_voice(request: RegisterVoiceRequest):
    """Register a voice profile for an NPC."""
    if not voice_system:
        raise HTTPException(status_code=503, detail="Voice system not initialized")
    
    try:
        provider = VoiceProvider(request.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")
    
    voice_config = VoiceConfig(
        name=request.npc_name,
        provider=provider,
        voice_id=request.voice_id,
        speed=request.speed,
        pitch=request.pitch,
    )
    
    voice_system.register_voice(request.npc_name, voice_config)
    
    return {
        "status": "registered",
        "npc_name": request.npc_name,
        "voice_id": request.voice_id,
        "provider": request.provider,
    }


@app.get("/api/voice/profiles")
async def get_voice_profiles():
    """Get all registered voice profiles."""
    if not voice_system:
        raise HTTPException(status_code=503, detail="Voice system not initialized")
    
    return {
        "profiles": {
            name: config.to_dict()
            for name, config in voice_system.voice_profiles.items()
        }
    }


@app.get("/api/voice/providers")
async def get_voice_providers():
    """Get available TTS providers."""
    if not voice_system:
        raise HTTPException(status_code=503, detail="Voice system not initialized")
    
    return {
        "providers": voice_system.get_available_providers()
    }


@app.get("/api/voice/voices")
async def get_available_voices(provider: Optional[str] = None):
    """Get available voices."""
    if not voice_system:
        raise HTTPException(status_code=503, detail="Voice system not initialized")
    
    prov = VoiceProvider(provider) if provider else None
    voices = voice_system.get_available_voices(prov)
    
    return {
        "count": len(voices),
        "voices": voices
    }


@app.get("/api/voice/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve an audio file."""
    from fastapi.responses import FileResponse
    
    # Check cache directory
    cache_path = Path("voice_cache") / filename
    if cache_path.exists():
        return FileResponse(
            cache_path,
            media_type="audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
        )
    
    # Check output directory
    output_path = Path("voice_output") / filename
    if output_path.exists():
        return FileResponse(
            output_path,
            media_type="audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
        )
    
    raise HTTPException(status_code=404, detail=f"Audio file not found: {filename}")


@app.post("/api/voice/profiles/save")
async def save_voice_profiles():
    """Save voice profiles to file."""
    if not voice_system:
        raise HTTPException(status_code=503, detail="Voice system not initialized")
    
    voice_system.save_profiles("voice_profiles.json")
    
    return {"status": "saved"}


@app.post("/api/voice/profiles/load")
async def load_voice_profiles():
    """Load voice profiles from file."""
    if not voice_system:
        raise HTTPException(status_code=503, detail="Voice system not initialized")
    
    voice_system.load_profiles("voice_profiles.json")
    
    return {
        "status": "loaded",
        "profiles_count": len(voice_system.voice_profiles)
    }


# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
