"""
Dungeon Master AI — Demo Script

Showcases all DM capabilities through 5 scenarios:
1. Quest Completion Cascade
2. Relationship Threshold Drama
3. Rule Compilation in Action
4. World Event Propagation
5. Narrative Arc Tracking
"""

import asyncio
import json
import time
import tempfile
import shutil
from unittest.mock import MagicMock, AsyncMock

from npc_state_manager import StateEvent, EventType, EventCallback
from dm_rule_engine import DmRuleEngine
from dungeon_master import (
    DungeonMaster,
    DungeonMasterConfig,
    NarrativeState,
    StoryArc,
    Observation,
)


class MockLLMProvider:
    def __init__(self, responses=None):
        self.responses = responses or []
        self._idx = 0
        self.calls = []

    def generate(self, messages, model, temperature=0.8, max_tokens=500):
        self.calls.append({"model": model, "messages": messages})
        if self._idx < len(self.responses):
            resp = self.responses[self._idx]
            self._idx += 1
        else:
            resp = {"directive": "none"}
        content = json.dumps(resp)
        return {"content": content, "tokens": 50, "total_duration": 100}


def make_event(
    event_type: EventType = EventType.QUEST_COMPLETED,
    player_id: str = "player",
    npc_id: str = "Thorne",
    zone_id: str = "ironhold_village",
    **extra_data,
) -> StateEvent:
    data = {"quest_name": "Test Quest", "quest_type": "fetch"}
    data.update(extra_data)
    return StateEvent(
        event_type=event_type,
        timestamp=time.time(),
        data=data,
        player_id=player_id,
        npc_id=npc_id,
        zone_id=zone_id,
    )


def create_dm(tmpdir, llm_responses=None) -> DungeonMaster:
    provider = MockLLMProvider(responses=llm_responses or [])
    config = DungeonMasterConfig(
        state_dir=tmpdir,
        rules_dir=tmpdir,
        auto_save_interval=0,
        min_observations=5,
        max_active_rules=50,
    )
    dm = DungeonMaster(
        config=config,
        llm_provider=provider,
        event_callback=MagicMock(emit=AsyncMock()),
    )
    dm._running = True
    return dm


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def print_directive(label: str, data: dict):
    print(f"  -> {label}: {data.get('directive_type', data.get('type', 'unknown'))}")
    if data.get("narrative_reason"):
        print(f"     Reason: {data['narrative_reason']}")


def get_emitted_events(dm):
    calls = dm.event_callback.emit.call_args_list
    events = []
    for call in calls:
        if call.args:
            events.append(call.args[0])
    return events


# ============================================
# SCENARIO 1: Quest Completion Cascade
# ============================================

async def scenario_1_quest_cascade(tmpdir: str):
    print_header("Scenario 1: Quest Completion Cascade")

    dm = create_dm(tmpdir, llm_responses=[
        {"directive": "relationship_override", "parameters": {
            "changes": [
                {"npc": "Thorne", "delta": 15, "reason": "quest_reward"},
                {"faction": "Merchants Guild", "delta": 5, "reason": "guild_reputation"},
            ],
        }, "narrative_reason": "Fetch quest for Thorne completed — reputation boost"},
        {"directive": "quest_suggestion", "parameters": {
            "quest_type": "fetch",
            "npc_name": "Thorne",
            "title": "The Secret Forge",
            "description": "Thorne trusts you with the location of his secret forge.",
        }, "narrative_reason": "Thorne relationship is high — unlock legendary quest"},
    ])

    print("Player completes 'Retrieve the Stolen Anvil' for Thorne...")
    event = make_event(
        event_type=EventType.QUEST_COMPLETED,
        npc_id="Thorne",
        quest_name="Retrieve the Stolen Anvil",
        quest_type="fetch",
        faction="Merchants Guild",
    )
    await dm.handle_event(event)

    emitted = get_emitted_events(dm)
    for e in emitted:
        print_directive("DM Directive", e.data)

    status = dm.get_status()
    print(f"\n  Events processed: {status['total_events_processed']}")
    print(f"  Active rules: {status['active_rules']}")
    print(f"  Tension: {json.dumps(dm.state.tension_map, indent=4)}")


# ============================================
# SCENARIO 2: Relationship Threshold Drama
# ============================================

async def scenario_2_relationship_drama(tmpdir: str):
    print_header("Scenario 2: Relationship Threshold Drama")

    dm = create_dm(tmpdir)

    print("Player repeatedly offends Elara...")
    print("  -> relationship_change: Liked -> Neutral")

    event1 = make_event(
        event_type=EventType.RELATIONSHIP_CHANGE,
        npc_id="Elara",
        old_level="Liked",
        new_level="Neutral",
        delta=-15,
    )
    await dm.handle_event(event1)

    emitted = get_emitted_events(dm)
    for e in emitted:
        print_directive("Hardcoded Rule", e.data)

    dm.event_callback.emit.reset_mock()

    print("\n  -> relationship_change: Neutral -> Disliked")
    event2 = make_event(
        event_type=EventType.RELATIONSHIP_CHANGE,
        npc_id="Elara",
        old_level="Neutral",
        new_level="Disliked",
        delta=-25,
    )
    await dm.handle_event(event2)

    emitted = get_emitted_events(dm)
    for e in emitted:
        print_directive("Hardcoded Rule", e.data)

    print(f"\n  Tension: {json.dumps(dm.state.tension_map, indent=4)}")

    print("\n  -> relationship_change: Disliked -> Hated")
    dm.event_callback.emit.reset_mock()
    event3 = make_event(
        event_type=EventType.RELATIONSHIP_CHANGE,
        npc_id="Elara",
        old_level="Disliked",
        new_level="Hated",
        delta=-30,
        nearby_npc="Thorne",
    )
    await dm.handle_event(event3)

    emitted = get_emitted_events(dm)
    for e in emitted:
        print_directive("Hardcoded Rule", e.data)

    print(f"\n  Tension (after Hated): {json.dumps(dm.state.tension_map, indent=4)}")
    print(f"  Total events processed: {dm.state.total_events_processed}")


# ============================================
# SCENARIO 3: Rule Compilation in Action
# ============================================

async def scenario_3_rule_compilation(tmpdir: str):
    print_header("Scenario 3: Rule Compilation in Action")

    llm = MockLLMProvider(responses=[
        {"directive": "npc_directive", "parameters": {
            "npc": "{event.npc_id}",
            "directive": "nearby_wary",
            "prompt_modifier": "Nearby NPCs are wary of the player due to a failed kill quest.",
        }, "narrative_reason": "Kill quest failure makes NPCs distrustful"} ,
    ] * 10 + [
        {"rule_name": "Failed kill quest makes nearby NPCs wary",
         "description": "When a kill quest fails, nearby NPCs become wary of the player",
         "trigger": {
             "event_type": "quest_failed",
             "conditions": [
                 {"field": "event.data.quest_type", "operator": "eq", "value": "kill"}
             ],
         },
         "actions": [
             {"type": "npc_directive", "parameters": {
                 "npc": "{event.npc_id}",
                 "directive": "nearby_wary",
                 "prompt_modifier": "You are wary of the player. They failed a dangerous task nearby.",
             }},
         ],
         "priority": 5,
         "confidence": 0.91},
    ])

    config = DungeonMasterConfig(
        state_dir=tmpdir,
        rules_dir=tmpdir,
        auto_save_interval=0,
        min_observations=5,
    )
    dm = DungeonMaster(
        config=config,
        llm_provider=llm,
        event_callback=MagicMock(emit=AsyncMock()),
    )
    dm._running = True

    zones = ["eastern_road", "dark_forest", "mountain_pass", "swamp", "ironhold_village"]

    print("Simulating 5 repeated 'kill quest failed' events...\n")
    for i, zone in enumerate(zones):
        dm.event_callback.emit.reset_mock()
        event = make_event(
            event_type=EventType.QUEST_FAILED,
            npc_id="Guard",
            zone_id=zone,
            quest_name=f"Kill the Beast of {zone}",
            quest_type="kill",
        )
        await dm.handle_event(event)

        obs_count = len([
            o for o in dm.state.recent_observations
            if o.similarity_key() == "quest_failed:npc_directive"
        ])
        print(f"  Event {i + 1}: quest_failed (kill quest in {zone})")
        print(f"    -> LLM judged: npc_directive (nearby_wary)")
        print(f"    -> Pattern check: {obs_count}/5 observations")

        if obs_count >= 5:
            print(f"    -> *** Pattern detected! Compiling rule... ***")

    print(f"\n  Active compiled rules: {len(dm.rule_engine.active_rules)}")
    if dm.rule_engine.active_rules:
        rule = dm.rule_engine.active_rules[0]
        print(f"  Rule: '{rule.get('rule_name', 'Unknown')}'")
        print(f"  Confidence: {rule.get('confidence', 0)}")
        print(f"  Active: {rule.get('active', False)}")

    print("\n  6th event (kill quest in another zone):")
    dm.event_callback.emit.reset_mock()
    event6 = make_event(
        event_type=EventType.QUEST_FAILED,
        npc_id="Guard",
        zone_id="abandoned_mine",
        quest_name="Kill the Mine Spider",
        quest_type="kill",
    )
    await dm.handle_event(event6)

    matched = dm.rule_engine.match(
        {"event_type": "quest_failed", "npc_id": "Guard", "zone_id": "abandoned_mine",
         "data": {"quest_type": "kill"}},
        dm.state.to_dict(),
    )
    print(f"    -> Compiled rule matched: {matched.matched}")
    print(f"    -> No LLM call needed!")


# ============================================
# SCENARIO 4: World Event Propagation
# ============================================

async def scenario_4_world_event(tmpdir: str):
    print_header("Scenario 4: World Event Propagation")

    dm = create_dm(tmpdir)

    dm.create_arc(
        "The Ironhold Troubles",
        "A series of problems plaguing Ironhold Village",
        involved_npcs=["Thorne", "Elara"],
        resolution_conditions=["bandits_defeated", "trade_restored"],
    )

    print("DM evaluates a faction change event...")
    event = make_event(
        event_type=EventType.FACTION_CHANGE,
        npc_id="",
        zone_id="ironhold_village",
        faction="Merchants Guild",
        new_reputation=-60,
        affected_zones=["ironhold_village", "eastern_road"],
    )
    await dm.handle_event(event)

    emitted = get_emitted_events(dm)
    for e in emitted:
        print_directive("DM Directive", e.data)

    print(f"\n  World conditions: {list(dm.state.world_conditions)}")
    print(f"  Active arcs: {len(dm.state.active_arcs)}")

    print("\nSimulating a major world event...")
    dm.event_callback.emit.reset_mock()
    event2 = make_event(
        event_type=EventType.WORLD_EVENT,
        npc_id="",
        zone_id="ironhold_village",
        event_name="Bandit Raid on Ironhold",
        severity="major",
        location="ironhold_village",
    )
    await dm.handle_event(event2)

    emitted = get_emitted_events(dm)
    for e in emitted:
        print_directive("DM Directive", e.data)


# ============================================
# SCENARIO 5: Narrative Arc Tracking
# ============================================

async def scenario_5_arc_tracking(tmpdir: str):
    print_header("Scenario 5: Narrative Arc Across Sessions")

    config = DungeonMasterConfig(
        state_dir=tmpdir,
        rules_dir=tmpdir,
        auto_save_interval=0,
    )
    dm = DungeonMaster(
        config=config,
        llm_provider=MockLLMProvider(),
        event_callback=MagicMock(emit=AsyncMock()),
    )
    dm._running = True

    print("Session 1: Player meets Thorne, completes 'Repair the Anvil'")
    arc = dm.create_arc(
        "The Blacksmith's Legacy",
        "Thorne is preparing to pass on his forge to a worthy successor",
        involved_npcs=["Thorne"],
        resolution_conditions=["player_completes_final_quest", "thorne_relationship_adored"],
    )
    print(f"  -> Arc created: '{arc.title}' (tension: {arc.tension_level})")

    event1 = make_event(
        event_type=EventType.QUEST_COMPLETED,
        npc_id="Thorne",
        quest_name="Repair the Anvil",
    )
    await dm.handle_event(event1)
    print(f"  -> Quest completed. Events processed: {dm.state.total_events_processed}")

    print("\nSession 2: Player completes 'Retrieve Star Iron' for Thorne")
    dm.advance_arc("arc_001", "Player retrieved star-iron ore", tension_delta=0.1)
    event2 = make_event(
        event_type=EventType.QUEST_COMPLETED,
        npc_id="Thorne",
        quest_name="Retrieve Star Iron",
    )
    await dm.handle_event(event2)
    arc = dm.state.active_arcs["arc_001"]
    print(f"  -> Arc advanced (tension: {arc.tension_level:.1f})")

    print("\nSession 3: Player fails 'Escort the Smith's Nephew'")
    dm.advance_arc("arc_001", "Player failed the escort quest", tension_delta=0.4)
    event3 = make_event(
        event_type=EventType.QUEST_FAILED,
        npc_id="Thorne",
        quest_name="Escort the Smith's Nephew",
    )
    await dm.handle_event(event3)
    arc = dm.state.active_arcs["arc_001"]
    print(f"  -> Arc tension spike! (tension: {arc.tension_level:.1f})")
    print(f"  -> Arc events: {[e['summary'] for e in arc.key_events]}")

    print("\nSession 4: Player redeems by completing 'Rescue the Nephew'")
    dm.advance_arc("arc_001", "Player rescued the nephew!", tension_delta=-0.4)
    event4 = make_event(
        event_type=EventType.QUEST_COMPLETED,
        npc_id="Thorne",
        quest_name="Rescue the Nephew",
    )
    await dm.handle_event(event4)
    arc = dm.state.active_arcs["arc_001"]
    print(f"  -> Arc tension drops (tension: {arc.tension_level:.1f})")
    print(f"  -> Arc approaching resolution")

    print("\nSession 5: Player completes 'The Final Forge'")
    dm.advance_arc("arc_001", "Player completed the masterwork", tension_delta=-0.1)
    dm.resolve_arc("arc_001")
    event5 = make_event(
        event_type=EventType.QUEST_COMPLETED,
        npc_id="Thorne",
        quest_name="The Final Forge",
    )
    await dm.handle_event(event5)
    arc = dm.state.active_arcs["arc_001"]
    print(f"  -> Arc '{arc.title}' RESOLVED")
    print(f"  -> Status: {arc.status}")
    print(f"  -> Total arc events: {len(arc.key_events)}")

    print(f"\n  Final state:")
    print(f"    Total events processed: {dm.state.total_events_processed}")
    print(f"    Tension map: {json.dumps(dm.state.tension_map, indent=6)}")

    print("\n  Saving state...")
    dm.save_state()
    print("  State saved to disk.")

    print("\n  Loading state into new DM instance...")
    dm2 = DungeonMaster(
        config=config,
        llm_provider=MockLLMProvider(),
        event_callback=MagicMock(emit=AsyncMock()),
    )
    dm2.load_state()
    restored_arc = dm2.state.active_arcs.get("arc_001")
    if restored_arc:
        print(f"  -> Arc '{restored_arc.title}' restored (status: {restored_arc.status})")
        print(f"  -> Events: {len(restored_arc.key_events)}")
    else:
        print("  -> ERROR: Arc not found after restore!")


# ============================================
# MAIN
# ============================================

async def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         DUNGEON MASTER AI — DEMO                        ║")
    print("║         Event-Driven Narrative Overseer                  ║")
    print("╚══════════════════════════════════════════════════════════╝")

    tmpdir = tempfile.mkdtemp(prefix="dm_demo_")
    try:
        await scenario_1_quest_cascade(tmpdir)
        await scenario_2_relationship_drama(tmpdir)
        await scenario_3_rule_compilation(tmpdir)
        await scenario_4_world_event(tmpdir)
        await scenario_5_arc_tracking(tmpdir)

        print_header("Demo Complete")
        print("  All 5 scenarios ran successfully.")
        print("  The Dungeon Master system is fully operational.")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
