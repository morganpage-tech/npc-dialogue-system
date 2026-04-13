#!/usr/bin/env python3
"""
Voice Synthesis System Demo

Demonstrates multi-provider TTS with NPC voice profiles,
caching, and various voice configurations.
"""

import asyncio
import os
from voice_synthesis import (
    VoiceSystem,
    VoiceConfig,
    VoiceProvider,
    VoiceEmotion,
    SynthesisResult,
    synthesize_speech,
    DEFAULT_NPC_VOICES,
    setup_npc_voices,
)


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'-'*60}\n")


def demo_provider_availability():
    """Check which TTS providers are available."""
    print_separator("PROVIDER AVAILABILITY")
    
    system = VoiceSystem()
    providers = system.get_available_providers()
    
    for provider in providers:
        status = "✅ Available" if provider["available"] else "❌ Not available"
        print(f"{provider['provider'].upper():15} {status}")
        
        if provider["available"] and provider["voices"]:
            print(f"                Sample voices: {len(provider['voices'])} available")
    
    print()


def demo_available_voices():
    """List available voices from all providers."""
    print_separator("AVAILABLE VOICES")
    
    system = VoiceSystem()
    
    # Edge TTS voices (free)
    print("Edge TTS Voices (Free):")
    for voice in system.synthesizers[VoiceProvider.EDGE_TTS].get_available_voices():
        print(f"  - {voice['id']:25} ({voice['gender']}, {voice['language']})")
    
    print()
    
    # OpenAI voices
    print("OpenAI Voices:")
    for voice in system.synthesizers[VoiceProvider.OPENAI].get_available_voices():
        print(f"  - {voice['id']:15} ({voice['gender']}) - {voice['description']}")
    
    print()


async def demo_basic_synthesis():
    """Demonstrate basic speech synthesis."""
    print_separator("BASIC SYNTHESIS")
    
    system = VoiceSystem()
    
    # Synthesize with default settings
    text = "Greetings, traveler. Welcome to our village."
    
    print(f"Text: \"{text}\"")
    print(f"Provider: Edge TTS (default)")
    print()
    
    result = await system.synthesize(text)
    
    if result.success:
        print(f"✅ Success!")
        print(f"   Audio saved to: {result.audio_path}")
        print(f"   Provider: {result.provider.value}")
        print(f"   Cached: {result.cached}")
    else:
        print(f"❌ Failed: {result.error}")
    
    print()


async def demo_multi_provider():
    """Test synthesis with different providers."""
    print_separator("MULTI-PROVIDER SYNTHESIS")
    
    system = VoiceSystem()
    text = "The ancient forest holds many secrets."
    
    providers_to_test = [
        (VoiceProvider.EDGE_TTS, "en-US-JennyNeural"),
        (VoiceProvider.GTTS, "en"),
    ]
    
    for provider, voice_id in providers_to_test:
        synthesizer = system.synthesizers.get(provider)
        
        if synthesizer and synthesizer.is_available():
            print(f"Testing {provider.value.upper()}...")
            
            result = await system.synthesize(
                text=text,
                provider=provider,
                voice_config=VoiceConfig(
                    name="Test",
                    provider=provider,
                    voice_id=voice_id,
                )
            )
            
            if result.success:
                print(f"  ✅ Success: {result.audio_path}")
            else:
                print(f"  ❌ Failed: {result.error}")
        else:
            print(f"⏭️  {provider.value.upper()} not available")
        
        print()


async def demo_npc_voices():
    """Demonstrate NPC voice profiles."""
    print_separator("NPC VOICE PROFILES")
    
    system = VoiceSystem()
    
    # Setup default NPC voices
    npc_archetypes = {
        "Greta the Blacksmith": "blacksmith",
        "Lydia the Merchant": "merchant",
        "Elder Theron": "elder",
        "Guard Captain Marcus": "guard",
        "Healer Sofia": "healer",
    }
    
    setup_npc_voices(system, npc_archetypes)
    
    # Show registered profiles
    print("Registered NPC Voices:")
    for npc_name, config in system.voice_profiles.items():
        print(f"  {npc_name}:")
        print(f"    Voice ID: {config.voice_id}")
        print(f"    Provider: {config.provider.value}")
        print(f"    Speed: {config.speed}")
    print()
    
    # Synthesize for each NPC
    texts = {
        "Greta the Blacksmith": "Need something forged? Bring me the materials and I'll make it right.",
        "Lydia the Merchant": "Welcome to my shop! I have the finest goods from across the realm.",
        "Elder Theron": "Ah, young one. The village has need of brave souls such as yourself.",
        "Guard Captain Marcus": "Halt! State your business in the village.",
        "Healer Sofia": "You look wounded. Let me tend to your injuries.",
    }
    
    print("Synthesizing NPC dialogue:")
    for npc_name, text in texts.items():
        print(f"\n[{npc_name}]")
        print(f'  "{text}"')
        
        result = await system.synthesize(text=text, npc_name=npc_name)
        
        if result.success:
            print(f"  ✅ {result.audio_path}")
        else:
            print(f"  ❌ {result.error}")


async def demo_voice_customization():
    """Demonstrate voice customization options."""
    print_separator("VOICE CUSTOMIZATION")
    
    system = VoiceSystem()
    text = "The dragon approaches from the north!"
    
    # Test different speeds
    print("Speed variations:")
    for speed in [0.75, 1.0, 1.25]:
        config = VoiceConfig(
            name=f"Speed {speed}",
            provider=VoiceProvider.EDGE_TTS,
            voice_id="en-US-JennyNeural",
            speed=speed,
        )
        
        result = await system.synthesize(text=text, voice_config=config)
        
        if result.success:
            print(f"  Speed {speed}: ✅ {result.audio_path}")
        else:
            print(f"  Speed {speed}: ❌ {result.error}")
    
    print()
    
    # Test different voices
    print("Voice variations:")
    voices = [
        ("en-US-JennyNeural", "Jenny (Female, US)"),
        ("en-US-GuyNeural", "Guy (Male, US)"),
        ("en-GB-SoniaNeural", "Sonia (Female, UK)"),
        ("en-GB-RyanNeural", "Ryan (Male, UK)"),
    ]
    
    for voice_id, description in voices:
        config = VoiceConfig(
            name=description,
            provider=VoiceProvider.EDGE_TTS,
            voice_id=voice_id,
        )
        
        result = await system.synthesize(text=text, voice_config=config)
        
        if result.success:
            print(f"  {description}: ✅")
        else:
            print(f"  {description}: ❌ {result.error}")


async def demo_caching():
    """Demonstrate audio caching."""
    print_separator("AUDIO CACHING")
    
    system = VoiceSystem()
    text = "This text will be cached for reuse."
    
    print("First synthesis (should generate new audio):")
    result1 = await system.synthesize(text=text)
    print(f"  Cached: {result1.cached}")
    print(f"  Path: {result1.audio_path}")
    
    print()
    print("Second synthesis (should use cache):")
    result2 = await system.synthesize(text=text)
    print(f"  Cached: {result2.cached}")
    print(f"  Path: {result2.audio_path}")
    
    print()
    print("Third synthesis with cache disabled:")
    result3 = await system.synthesize(text=text, use_cache=False)
    print(f"  Cached: {result3.cached}")
    print(f"  Path: {result3.audio_path}")


async def demo_quick_synthesis():
    """Demonstrate quick synthesis helper function."""
    print_separator("QUICK SYNTHESIS HELPER")
    
    text = "Quick synthesis test using the helper function."
    
    print(f"Text: \"{text}\"")
    print("Using: synthesize_speech() helper")
    
    result = await synthesize_speech(
        text=text,
        voice="en-GB-SoniaNeural",
        provider="edge_tts",
    )
    
    if result.success:
        print(f"✅ Success: {result.audio_path}")
    else:
        print(f"❌ Failed: {result.error}")


async def demo_save_load_profiles():
    """Demonstrate saving and loading voice profiles."""
    print_separator("SAVE/LOAD PROFILES")
    
    system = VoiceSystem()
    
    # Register some voices
    system.register_voice("Test NPC 1", VoiceConfig(
        name="Test NPC 1",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-US-JennyNeural",
        speed=1.1,
    ))
    
    system.register_voice("Test NPC 2", VoiceConfig(
        name="Test NPC 2",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-GB-RyanNeural",
        speed=0.9,
    ))
    
    print(f"Registered {len(system.voice_profiles)} profiles")
    
    # Save
    system.save_profiles("test_voice_profiles.json")
    print("✅ Saved to test_voice_profiles.json")
    
    # Create new system and load
    system2 = VoiceSystem()
    system2.load_profiles("test_voice_profiles.json")
    print(f"✅ Loaded into new system: {len(system2.voice_profiles)} profiles")
    
    # Show loaded profiles
    for name, config in system2.voice_profiles.items():
        print(f"  {name}: {config.voice_id} (speed: {config.speed})")
    
    # Cleanup
    os.remove("test_voice_profiles.json")
    print("\n🧹 Cleaned up test file")


async def demo_emotional_voices():
    """Demonstrate emotional voice variations."""
    print_separator("EMOTIONAL VARIATIONS")
    
    system = VoiceSystem()
    
    emotions = [
        ("neutral", "The village is quiet today."),
        ("happy", "Wonderful news! The harvest was bountiful!"),
        ("sad", "The winter was harsh. Many did not survive."),
        ("calm", "Take your time. There is no rush."),
        ("whisper", "Be quiet. The guards are nearby."),
    ]
    
    for emotion, text in emotions:
        print(f"[{emotion.upper()}]")
        print(f'  "{text}"')
        
        config = VoiceConfig(
            name=f"Emotion: {emotion}",
            provider=VoiceProvider.EDGE_TTS,
            voice_id="en-US-JennyNeural",
            emotion=VoiceEmotion(emotion),
        )
        
        result = await system.synthesize(text=text, voice_config=config)
        
        if result.success:
            print(f"  ✅ Generated")
        else:
            print(f"  ❌ {result.error}")
        
        print()


async def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("  VOICE SYNTHESIS SYSTEM DEMO")
    print("  NPC Dialogue System v1.5.0")
    print("="*60)
    
    # Check providers
    demo_provider_availability()
    
    # Show available voices
    demo_available_voices()
    
    # Basic synthesis
    await demo_basic_synthesis()
    
    # Multi-provider
    await demo_multi_provider()
    
    # NPC voices
    await demo_npc_voices()
    
    # Customization
    await demo_voice_customization()
    
    # Caching
    await demo_caching()
    
    # Quick synthesis
    await demo_quick_synthesis()
    
    # Save/Load
    await demo_save_load_profiles()
    
    # Emotional voices
    await demo_emotional_voices()
    
    print_separator("DEMO COMPLETE")
    print("The Voice Synthesis System provides:")
    print("  - Multiple TTS providers (ElevenLabs, OpenAI, Edge TTS, gTTS, pyttsx3)")
    print("  - NPC voice profile management")
    print("  - Audio caching for repeated phrases")
    print("  - Voice customization (speed, pitch)")
    print("  - Emotional voice variations")
    print("  - Easy save/load of voice profiles")
    print()
    print("To enable premium providers:")
    print("  pip install elevenlabs")
    print("  pip install openai")
    print("  export ELEVENLABS_API_KEY=your_key")
    print("  export OPENAI_API_KEY=your_key")
    print()


if __name__ == "__main__":
    asyncio.run(main())
