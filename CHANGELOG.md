# Changelog

All notable changes to the NPC Dialogue System will be documented in this file.

## [1.1.0] - 2026-04-07

### Added - Relationship Tracking System

**Core Features:**
- Full relationship tracking with scores (-100 to +100)
- Six relationship levels: Hated, Disliked, Neutral, Liked, Loved, Adored
- Dynamic NPC personality based on relationship score
- Temperature adjustment for dialogue consistency
- Speaking style modifiers per relationship level

**Relationship Updates:**
- Quest completion relationship rewards
- Gift giving mechanics with diminishing returns
- Dialogue choice impact on relationships
- Faction support for group-wide relationships
- Time-based relationship decay (optional)

**Persistence:**
- Full save/load persistence for relationships
- Query system for relationship conditions
- Relationship summary and statistics

### New Files

| File | Lines | Description |
|------|-------|-------------|
| `relationship_tracking.py` | 500+ | Complete relationship tracking system |
| `test_relationships.py` | 600+ | 50 unit tests (100% passing) |
| `RELATIONSHIPS.md` | 450+ | Comprehensive documentation |
| `demo_relationships.py` | 300+ | Feature demonstration script |
| `test_demo_relationships.py` | 200+ | Simplified demo |

### Updated Files

- `npc_dialogue.py` - Integrated relationship tracking
- `README.md` - Added relationship examples
- `character_cards/*.json` - Added relationship fields

### Integration

- `RelationshipTracker` class for standalone use
- `NPCDialogue` integration via `relationship_tracker` parameter
- `NPCManager` support for shared relationship tracking
- Character cards support `gift_preferences` and `relationships` fields

### Tests

- 50 unit tests covering all relationship features
- Test categories: State, Levels, Scores, Temperature, Quests, Gifts, Dialogue, Factions, Persistence, Time Decay, Queries, Summary

---

## [1.0.0] - 2026-04-07

### Added
- Initial release of AI-powered NPC dialogue system
- Core dialogue engine with Ollama integration
- 3 example characters (Thorne - Blacksmith, Elara - Merchant, Zephyr - Wizard)
- Interactive CLI demo for testing conversations
- Conversation memory and persistence
- Character card system (SillyTavern JSON format)
- Complete documentation set
- Setup and testing scripts
- MIT License for commercial use

### Features
- 100% local LLM inference (no cloud costs)
- NPCs remember past conversations
- Multiple character support with seamless switching
- Game state context in dialogue
- Easy-to-use Python API
- Works on M1 MacBook Air (8GB/16GB RAM)

### Documentation
- README.md - Full system documentation
- QUICKSTART.md - 5-minute setup guide
- PROJECT_SUMMARY.md - Overview and roadmap
- INTEGRATION_GUIDE.md - Unity/Godot/Web integration
- 1,480 lines of comprehensive documentation
- Step-by-step setup instructions
- Game engine integration examples
- Performance optimization tips
- Troubleshooting guide

### Files
- npc_dialogue.py (327 lines) - Core dialogue engine
- main.py (228 lines) - CLI demo
- setup_check.py (145 lines) - Setup verification
- test_structure.py (113 lines) - System tests
- 4 documentation files
- 3 character cards
- Setup and configuration files

**Total: 12 files, 2,129 lines**
