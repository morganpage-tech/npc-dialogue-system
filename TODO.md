# NPC Dialogue System - Development Roadmap

This file tracks remaining features from the GitHub Issues roadmap. Each feature should be tackled one by one in order of priority.

---

## Current Status

**Completed:**
- ✅ v1.0.0 - Initial release with core dialogue system
- ✅ v1.1.0 - Relationship tracking system (Issue #2)

**Remaining:**
- 🔲 Issue #1 - Unity C# Integration (High Priority)
- 🔲 Issue #3 - Lore/Knowledge Base with RAG (Medium Priority)
- 🔲 Issue #4 - Streaming Responses (Medium Priority)

---

## Issue #1: Unity C# Integration Wrapper

**Priority:** HIGH
**GitHub Issue:** [#1](https://github.com/morganpage-tech/npc-dialogue-system/issues/1)
**Status:** 🔲 Not Started

### Goal
Make the NPC Dialogue System accessible to Unity developers, opening up the system to thousands more potential users.

### Requirements
- [ ] Create a C# client library for Unity
- [ ] Build a lightweight HTTP API server (FastAPI/Flask)
- [ ] Unity-specific features:
  - [ ] Async dialogue generation
  - [ ] Character loading/unloading
  - [ ] Relationship tracking integration
  - [ ] Conversation history management
- [ ] Unity example scene with demo characters
- [ ] Unity package (.unitypackage) for easy installation
- [ ] Documentation for Unity integration

### Implementation Plan
1. Create `api_server.py` - FastAPI server exposing NPC system as REST API
2. Create `unity_client/` directory with C# scripts:
   - `NPCDialogueClient.cs` - Main client class
   - `NPCCharacter.cs` - Character model
   - `NPCManager.cs` - Multi-NPC management
   - `RelationshipTracker.cs` - Unity-side relationship tracking
3. Create Unity example scene
4. Write `UNITY_INTEGRATION.md` documentation
5. Create `.unitypackage` for distribution
6. Update README with Unity setup instructions

### Files to Create
```
api_server.py                    # FastAPI REST server
unity_client/
  ├── NPCDialogueClient.cs       # Main client
  ├── NPCCharacter.cs            # Character model
  ├── NPCManager.cs              # Manager class
  ├── RelationshipTracker.cs     # Relationship tracking
  └── Editor/
      └── NPCDialogueWindow.cs   # Unity editor window
unity_example/
  ├── Scenes/
  │   └── DemoScene.unity
  └── Scripts/
      └── DemoController.cs
UNITY_INTEGRATION.md             # Unity documentation
```

### API Endpoints Needed
```
POST /api/dialogue/generate      # Generate NPC response
GET  /api/characters             # List loaded characters
POST /api/characters/load        # Load a character
GET  /api/relationships/{npc}    # Get relationship score
POST /api/relationships/update   # Update relationship
POST /api/history/save           # Save conversation history
POST /api/history/load           # Load conversation history
```

---

## Issue #3: Lore/Knowledge Base with RAG

**Priority:** MEDIUM
**GitHub Issue:** [#3](https://github.com/morganpage-tech/npc-dialogue-system/issues/3)
**Status:** 🔲 Not Started

### Goal
Enable NPCs to reference game world events, locations, history, and lore for richer, more contextual dialogue.

### Requirements
- [ ] Integrate vector database (ChromaDB or FAISS)
- [ ] Create lore document ingestion system
- [ ] Implement RAG (Retrieval Augmented Generation) pipeline
- [ ] NPC-aware context retrieval (each NPC knows different things)
- [ ] Support for structured lore (JSON, Markdown, plain text)
- [ ] Lore categories (history, locations, characters, items, factions)
- [ ] Query relevance scoring
- [ ] Documentation and examples

### Implementation Plan
1. Choose and integrate vector database (ChromaDB recommended)
2. Create `lore_system.py` with:
   - Lore ingestion from various formats
   - Vector embedding generation
   - Semantic search functionality
3. Create lore template system
4. Integrate with NPCDialogue for automatic context injection
5. Add character-specific knowledge restrictions
6. Create example lore files
7. Write `LORE_SYSTEM.md` documentation

### Files to Create
```
lore_system.py                   # Core RAG implementation
lore_ingestion.py                # Document processing
lore_templates/
  ├── world_history.json         # Example lore
  ├── locations.json
  ├── characters.json
  └── factions.json
LORE_SYSTEM.md                   # Documentation
```

### Lore Format Example
```json
{
  "category": "history",
  "entries": [
    {
      "id": "great_war",
      "title": "The Great War",
      "content": "100 years ago, the kingdoms fought...",
      "known_by": ["historians", "elders"],
      "importance": 0.9
    }
  ]
}
```

---

## Issue #4: Streaming Responses

**Priority:** MEDIUM
**GitHub Issue:** [#4](https://github.com/morganpage-tech/npc-dialogue-system/issues/4)
**Status:** 🔲 Not Started

### Goal
Enable word-by-word dialogue display for more immersive, responsive conversations.

### Requirements
- [ ] Implement streaming response generation
- [ ] SSE (Server-Sent Events) or WebSocket support
- [ ] Unity coroutine integration for streaming
- [ ] CLI streaming display
- [ ] Cancellable generation
- [ ] Token-by-token callback support
- [ ] Update API server for streaming endpoints

### Implementation Plan
1. Add streaming support to `npc_dialogue.py`:
   - Modify `generate_response()` for streaming
   - Add `generate_response_stream()` generator method
   - Token callback support
2. Update `api_server.py` with streaming endpoints
3. Add WebSocket or SSE support
4. Update Unity client for streaming
5. Add CLI streaming demo
6. Write documentation

### Files to Modify
```
npc_dialogue.py                  # Add streaming methods
api_server.py                    # Add streaming endpoints
unity_client/NPCDialogueClient.cs # Add streaming support
demo_streaming.py                # New streaming demo
```

### Streaming API
```python
# Python usage
for token in npc.generate_response_stream("Hello!"):
    print(token, end="", flush=True)

# Unity usage (C#)
client.GenerateResponseStream("Hello!", (token) => {
    dialogueText.text += token;
});
```

---

## Development Workflow

When starting a new session:

1. **Check this TODO.md** for current status
2. **Pick the next item** (start with Issue #1)
3. **Create a feature branch:**
   ```bash
   git checkout -b feature/issue-1-unity-integration
   ```
4. **Implement the feature** following the implementation plan
5. **Write/update tests**
6. **Update documentation**
7. **Commit and push:**
   ```bash
   git add -A
   git commit -m "feat: Add Unity C# integration (Issue #1)"
   git push origin feature/issue-1-unity-integration
   ```
8. **Close the GitHub issue** with a summary comment
9. **Update this TODO.md** with completion status
10. **Move to next issue**

---

## Quick Reference

**Repository:** https://github.com/morganpage-tech/npc-dialogue-system

**Key Files:**
- `npc_dialogue.py` - Core dialogue system
- `relationship_tracking.py` - Relationship tracking
- `character_cards/` - NPC definitions
- `RELATIONSHIPS.md` - Relationship system docs

**Testing:**
```bash
python3 test_relationships.py  # Run unit tests
python3 test_demo_relationships.py  # Run demo
```

**Current Version:** v1.1.0

**Next Version:** v1.2.0 (Unity Integration)

---

## Notes

- Each issue should be tackled in a fresh session to maintain clean context
- Update this file at the start and end of each session
- Keep commit messages descriptive and reference issue numbers
- All features should include tests and documentation
