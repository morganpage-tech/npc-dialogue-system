# Voice Synthesis System

Multi-provider text-to-speech for the NPC Dialogue System. Supports premium APIs (ElevenLabs, OpenAI) and free alternatives (Edge TTS, gTTS, pyttsx3).

---

## Quick Start

```python
from voice_synthesis import VoiceSystem

# Initialize
voice = VoiceSystem()

# Synthesize speech
result = await voice.synthesize("Greetings, traveler!")
print(result.audio_path)  # Path to generated audio file
```

---

## Providers

### Edge TTS (Recommended - Free)
Microsoft Edge's neural TTS. High quality, completely free.

```bash
pip install edge-tts
```

```python
# Default provider, no API key needed
voice = VoiceSystem(default_provider=VoiceProvider.EDGE_TTS)
```

**Available Voices:**
- `en-US-JennyNeural` - Female, US English
- `en-US-GuyNeural` - Male, US English
- `en-GB-SoniaNeural` - Female, British
- `en-GB-RyanNeural` - Male, British
- `en-AU-NatashaNeural` - Female, Australian
- `en-AU-WilliamNeural` - Male, Australian

### OpenAI TTS (Premium)
High-quality neural voices from OpenAI.

```bash
pip install openai
export OPENAI_API_KEY=your_key
```

**Available Voices:**
- `alloy` - Neutral, balanced
- `echo` - Male, conversational
- `fable` - Male, storytelling
- `onyx` - Male, deep/authoritative
- `nova` - Female, energetic
- `shimmer` - Female, soft/warm

### ElevenLabs (Premium)
Best quality, most expressive voices.

```bash
pip install elevenlabs
export ELEVENLABS_API_KEY=your_key
```

### gTTS (Free)
Google Text-to-Speech. Simple, free, requires internet.

```bash
pip install gTTS
```

### pyttsx3 (Offline)
Local offline TTS. Works without internet, lower quality.

```bash
pip install pyttsx3
```

### Coqui TTS (Local)
Open-source local TTS with many models.

```bash
pip install TTS
```

---

## NPC Voice Profiles

Register voices for your NPCs:

```python
from voice_synthesis import VoiceSystem, VoiceConfig, VoiceProvider

voice = VoiceSystem()

# Register a voice for an NPC
voice.register_voice("Greta the Blacksmith", VoiceConfig(
    name="Greta",
    provider=VoiceProvider.EDGE_TTS,
    voice_id="en-US-GuyNeural",
    speed=0.9,
    pitch=0.8,  # Deeper voice
))

# Synthesize using the NPC's voice
result = await voice.synthesize(
    text="Need something forged?",
    npc_name="Greta the Blacksmith"
)
```

### Default NPC Archetype Voices

Pre-configured voices for common NPC types:

```python
from voice_synthesis import setup_npc_voices, DEFAULT_NPC_VOICES

# Available archetypes:
# blacksmith, merchant, wizard, guard, healer, noble, child, elder

npc_archetypes = {
    "Greta": "blacksmith",
    "Lydia": "merchant",
    "Merlin": "wizard",
}

setup_npc_voices(voice, npc_archetypes)
```

---

## Voice Customization

### Speed and Pitch

```python
config = VoiceConfig(
    name="Custom Voice",
    provider=VoiceProvider.EDGE_TTS,
    voice_id="en-US-JennyNeural",
    speed=1.2,    # 20% faster
    pitch=1.1,    # Slightly higher pitch
)
```

### Emotional Tones

```python
from voice_synthesis import VoiceEmotion

config = VoiceConfig(
    name="Emotional Voice",
    provider=VoiceProvider.EDGE_TTS,
    voice_id="en-US-JennyNeural",
    emotion=VoiceEmotion.WHISPER,  # For sneaking
)
```

Available emotions: `NEUTRAL`, `HAPPY`, `SAD`, `ANGRY`, `FEARFUL`, `SURPRISED`, `CALM`, `WHISPER`

---

## Caching

Audio is automatically cached for repeated phrases:

```python
# First call generates and caches
result1 = await voice.synthesize("Hello there!")  # cached=False

# Subsequent calls use cache
result2 = await voice.synthesize("Hello there!")  # cached=True

# Disable caching for one-off phrases
result3 = await voice.synthesize("Hello there!", use_cache=False)
```

Cache location: `voice_cache/`

---

## API Endpoints

### POST /api/voice/synthesize
Synthesize speech from text.

```json
{
    "text": "Greetings, traveler!",
    "voice_id": "en-US-JennyNeural",
    "provider": "edge_tts",
    "speed": 1.0,
    "use_cache": true
}
```

### GET /api/voice/synthesize/{npc_name}?text=...
Synthesize using an NPC's registered voice.

### POST /api/voice/register
Register a voice profile for an NPC.

```json
{
    "npc_name": "Greta",
    "voice_id": "en-US-GuyNeural",
    "provider": "edge_tts",
    "speed": 0.9,
    "pitch": 0.8
}
```

### GET /api/voice/providers
List available providers and their status.

### GET /api/voice/voices
List available voices.

### GET /api/voice/profiles
Get all registered NPC voice profiles.

### POST /api/voice/profiles/save
Save voice profiles to file.

### POST /api/voice/profiles/load
Load voice profiles from file.

---

## Integration with Dialogue System

### Combined Dialogue + Voice

```python
from npc_dialogue import NPCManager
from voice_synthesis import VoiceSystem
import asyncio

async def voiced_dialogue():
    # Initialize systems
    dialogue = NPCManager(model="llama3.2:1b")
    voice = VoiceSystem()
    
    # Register NPC voice
    voice.register_voice("Greta", VoiceConfig(
        name="Greta",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-US-GuyNeural",
        speed=0.9,
    ))
    
    # Generate dialogue
    response = dialogue.generate("Greta", "What can you tell me about the village?")
    
    # Synthesize voice
    result = await voice.synthesize(
        text=response,
        npc_name="Greta"
    )
    
    return response, result.audio_path
```

### Unity Integration

```csharp
// Unity client
public class VoicePlayer : MonoBehaviour
{
    public async Task<AudioClip> SynthesizeVoice(string npcName, string text)
    {
        string url = $"http://localhost:8000/api/voice/synthesize/{npcName}?text={UnityWebRequest.EscapeURL(text)}";
        
        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            await request.SendWebRequest();
            
            var result = JsonUtility.FromJson<VoiceResult>(request.downloadHandler.text);
            
            // Load audio file
            using (UnityWebRequest audioRequest = UnityWebRequestMultimedia.GetAudioClip(
                $"http://localhost:8000/api/voice/audio/{Path.GetFileName(result.audio_path)}",
                AudioType.MPEG))
            {
                await audioRequest.SendWebRequest();
                return DownloadHandlerAudioClip.GetContent(audioRequest);
            }
        }
    }
}
```

---

## Cost Comparison

| Provider | Quality | Cost | Speed | Offline |
|----------|---------|------|-------|---------|
| ElevenLabs | ⭐⭐⭐⭐⭐ | $5-22/mo | Fast | No |
| OpenAI | ⭐⭐⭐⭐ | $15/1M chars | Fast | No |
| Edge TTS | ⭐⭐⭐⭐ | Free | Fast | No |
| gTTS | ⭐⭐ | Free | Slow | No |
| Coqui | ⭐⭐⭐ | Free | Slow | Yes |
| pyttsx3 | ⭐ | Free | Fast | Yes |

---

## Troubleshooting

### No audio generated
1. Check if any provider is available: `voice.get_available_providers()`
2. Install at least one: `pip install edge-tts`
3. Check error messages in `result.error`

### Slow synthesis
1. Use Edge TTS or OpenAI for fastest results
2. Enable caching for repeated phrases
3. Avoid pyttsx3 on headless servers

### API key errors (ElevenLabs/OpenAI)
```bash
# Set environment variables
export ELEVENLABS_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here
```

---

## File Structure

```
npc-dialogue-system/
├── voice_synthesis.py      # Core voice system
├── demo_voice.py           # Demo script
├── voice_cache/            # Cached audio files
├── voice_output/           # Generated audio files
└── voice_profiles.json     # Saved NPC voice profiles
```

---

## Advanced Usage

### Custom Output Path

```python
result = await voice.synthesize(
    text="Hello!",
    output_path="custom/path/greeting.mp3"
)
```

### Direct Audio Data

```python
result = await voice.synthesize("Hello!")
audio_bytes = result.audio_data  # Raw audio bytes
```

### List All Available Voices

```python
voices = voice.get_available_voices()
for v in voices:
    print(f"{v['id']}: {v['name']} ({v['provider']})")
```

---

## Notes

- Voice profiles persist across sessions with save/load
- Caching uses MD5 hash of text + voice config
- Fallback automatically finds an available provider
- Emotional variations work best with ElevenLabs

---

**Version:** 1.5.0  
**Author:** MorganPage (Rogues Studio)
