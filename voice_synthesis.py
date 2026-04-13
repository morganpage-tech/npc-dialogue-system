"""
Voice Synthesis System for NPC Dialogue System
Multi-provider TTS with ElevenLabs, OpenAI, and local fallback support
"""

import os
import json
import time
import hashlib
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

# Optional imports
try:
    import elevenlabs
    HAS_ELEVENLABS = True
except ImportError:
    HAS_ELEVENLABS = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False


class VoiceProvider(Enum):
    """Available TTS providers."""
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    GTTS = "gtts"           # Google TTS (free)
    PYTTSX3 = "pyttsx3"     # Local offline TTS
    EDGE_TTS = "edge_tts"   # Microsoft Edge TTS (free)
    COQUI = "coqui"         # Coqui TTS (local)


class VoiceEmotion(Enum):
    """Emotional tones for voice synthesis."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SURPRISED = "surprised"
    CALM = "calm"
    WHISPER = "whisper"


@dataclass
class VoiceConfig:
    """Configuration for a specific voice."""
    name: str                          # Display name
    provider: VoiceProvider            # TTS provider
    voice_id: str                      # Provider-specific voice ID
    language: str = "en"               # Language code
    speed: float = 1.0                 # Speech speed multiplier
    pitch: float = 1.0                 # Pitch adjustment
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    
    # Provider-specific settings
    model: str = ""                    # Model name (for ElevenLabs/OpenAI)
    style: str = ""                    # Speaking style
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "provider": self.provider.value,
            "voice_id": self.voice_id,
            "language": self.language,
            "speed": self.speed,
            "pitch": self.pitch,
            "emotion": self.emotion.value,
            "model": self.model,
            "style": self.style,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VoiceConfig':
        return cls(
            name=data["name"],
            provider=VoiceProvider(data["provider"]),
            voice_id=data["voice_id"],
            language=data.get("language", "en"),
            speed=data.get("speed", 1.0),
            pitch=data.get("pitch", 1.0),
            emotion=VoiceEmotion(data.get("emotion", "neutral")),
            model=data.get("model", ""),
            style=data.get("style", ""),
        )


@dataclass
class SynthesisResult:
    """Result of voice synthesis."""
    success: bool
    audio_path: Optional[str] = None
    audio_data: Optional[bytes] = None
    duration_seconds: float = 0.0
    provider: VoiceProvider = VoiceProvider.PYTTSX3
    voice_id: str = ""
    error: str = ""
    cached: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "audio_path": self.audio_path,
            "duration_seconds": self.duration_seconds,
            "provider": self.provider.value,
            "voice_id": self.voice_id,
            "error": self.error,
            "cached": self.cached,
        }


class VoiceSynthesizer(ABC):
    """Abstract base class for voice synthesizers."""
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        output_path: Optional[str] = None
    ) -> SynthesisResult:
        """Synthesize speech from text."""
        pass
    
    @abstractmethod
    def get_available_voices(self) -> List[Dict]:
        """Get list of available voices for this provider."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available."""
        pass


class ElevenLabsSynthesizer(VoiceSynthesizer):
    """ElevenLabs TTS provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"
    
    def is_available(self) -> bool:
        return HAS_ELEVENLABS and self.api_key is not None
    
    async def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        output_path: Optional[str] = None
    ) -> SynthesisResult:
        if not self.is_available():
            return SynthesisResult(
                success=False,
                error="ElevenLabs not available or API key not set",
                provider=VoiceProvider.ELEVENLABS
            )
        
        try:
            from elevenlabs import generate, save, set_api_key, voices
            
            set_api_key(self.api_key)
            
            # Generate audio
            audio = generate(
                text=text,
                voice=voice_config.voice_id,
                model=voice_config.model or "eleven_monolingual_v1",
                stream=False
            )
            
            # Save to file
            if output_path:
                save(audio, output_path)
            else:
                output_path = f"voice_output/elevenlabs_{int(time.time())}.mp3"
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                save(audio, output_path)
            
            return SynthesisResult(
                success=True,
                audio_path=output_path,
                audio_data=audio if isinstance(audio, bytes) else None,
                provider=VoiceProvider.ELEVENLABS,
                voice_id=voice_config.voice_id
            )
            
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e),
                provider=VoiceProvider.ELEVENLABS
            )
    
    def get_available_voices(self) -> List[Dict]:
        if not self.is_available():
            return []
        
        try:
            from elevenlabs import voices
            voice_list = voices()
            return [
                {
                    "id": v.voice_id,
                    "name": v.name,
                    "labels": v.labels if hasattr(v, 'labels') else {},
                    "provider": "elevenlabs"
                }
                for v in voice_list
            ]
        except:
            return []


class OpenAISynthesizer(VoiceSynthesizer):
    """OpenAI TTS provider."""
    
    # Available OpenAI voices
    OPENAI_VOICES = {
        "alloy": {"name": "Alloy", "gender": "neutral", "description": "Neutral, balanced"},
        "echo": {"name": "Echo", "gender": "male", "description": "Warm, conversational"},
        "fable": {"name": "Fable", "gender": "male", "description": "Storytelling, expressive"},
        "onyx": {"name": "Onyx", "gender": "male", "description": "Deep, authoritative"},
        "nova": {"name": "Nova", "gender": "female", "description": "Energetic, friendly"},
        "shimmer": {"name": "Shimmer", "gender": "female", "description": "Soft, warm"},
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
    
    def is_available(self) -> bool:
        return HAS_OPENAI and self.api_key is not None
    
    async def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        output_path: Optional[str] = None
    ) -> SynthesisResult:
        if not self.is_available():
            return SynthesisResult(
                success=False,
                error="OpenAI not available or API key not set",
                provider=VoiceProvider.OPENAI
            )
        
        try:
            import openai
            
            client = openai.OpenAI(api_key=self.api_key)
            
            # Generate speech
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice_config.voice_id,
                input=text,
                speed=voice_config.speed
            )
            
            # Save to file
            if not output_path:
                output_path = f"voice_output/openai_{int(time.time())}.mp3"
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            return SynthesisResult(
                success=True,
                audio_path=output_path,
                audio_data=response.content,
                provider=VoiceProvider.OPENAI,
                voice_id=voice_config.voice_id
            )
            
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e),
                provider=VoiceProvider.OPENAI
            )
    
    def get_available_voices(self) -> List[Dict]:
        return [
            {
                "id": voice_id,
                "name": data["name"],
                "gender": data["gender"],
                "description": data["description"],
                "provider": "openai"
            }
            for voice_id, data in self.OPENAI_VOICES.items()
        ]


class CoquiSynthesizer(VoiceSynthesizer):
    """Coqui TTS provider (local)."""
    
    def __init__(self, model_name: str = "tts_models/en/ljspeech/vits"):
        self.model_name = model_name
        self._tts = None
    
    def is_available(self) -> bool:
        try:
            from TTS.api import TTS
            return True
        except ImportError:
            return False
    
    def _get_tts(self):
        if self._tts is None:
            from TTS.api import TTS
            self._tts = TTS(model_name=self.model_name, progress_bar=False, gpu=False)
        return self._tts
    
    async def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        output_path: Optional[str] = None
    ) -> SynthesisResult:
        if not self.is_available():
            return SynthesisResult(
                success=False,
                error="Coqui TTS not installed. Install with: pip install TTS",
                provider=VoiceProvider.COQUI
            )
        
        try:
            tts = self._get_tts()
            
            if not output_path:
                output_path = f"voice_output/coqui_{int(time.time())}.wav"
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: tts.tts_to_file(text=text, file_path=output_path)
            )
            
            return SynthesisResult(
                success=True,
                audio_path=output_path,
                provider=VoiceProvider.COQUI,
                voice_id=self.model_name
            )
            
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e),
                provider=VoiceProvider.COQUI
            )
    
    def get_available_voices(self) -> List[Dict]:
        if not self.is_available():
            return []
        
        try:
            from TTS.api import TTS
            models = TTS.list_models()
            return [
                {"id": m, "name": m.split("/")[-1], "provider": "coqui"}
                for m in models if m.startswith("tts_models/")
            ]
        except:
            return []


class EdgeTTSSynthesizer(VoiceSynthesizer):
    """Microsoft Edge TTS provider (free)."""
    
    # Common Edge TTS voices
    EDGE_VOICES = {
        "en-US-JennyNeural": {"name": "Jenny", "language": "en-US", "gender": "female"},
        "en-US-GuyNeural": {"name": "Guy", "language": "en-US", "gender": "male"},
        "en-GB-SoniaNeural": {"name": "Sonia", "language": "en-GB", "gender": "female"},
        "en-GB-RyanNeural": {"name": "Ryan", "language": "en-GB", "gender": "male"},
        "en-AU-NatashaNeural": {"name": "Natasha", "language": "en-AU", "gender": "female"},
        "en-AU-WilliamNeural": {"name": "William", "language": "en-AU", "gender": "male"},
    }
    
    def __init__(self):
        self._communicate = None
    
    def is_available(self) -> bool:
        try:
            import edge_tts
            return True
        except ImportError:
            return False
    
    async def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        output_path: Optional[str] = None
    ) -> SynthesisResult:
        if not self.is_available():
            return SynthesisResult(
                success=False,
                error="edge-tts not installed. Install with: pip install edge-tts",
                provider=VoiceProvider.EDGE_TTS
            )
        
        try:
            import edge_tts
            
            if not output_path:
                output_path = f"voice_output/edge_{int(time.time())}.mp3"
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            communicate = edge_tts.Communicate(text, voice_config.voice_id)
            await communicate.save(output_path)
            
            return SynthesisResult(
                success=True,
                audio_path=output_path,
                provider=VoiceProvider.EDGE_TTS,
                voice_id=voice_config.voice_id
            )
            
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e),
                provider=VoiceProvider.EDGE_TTS
            )
    
    def get_available_voices(self) -> List[Dict]:
        return [
            {
                "id": voice_id,
                "name": data["name"],
                "language": data["language"],
                "gender": data["gender"],
                "provider": "edge_tts"
            }
            for voice_id, data in self.EDGE_VOICES.items()
        ]


class GTTSSynthesizer(VoiceSynthesizer):
    """Google TTS provider (free)."""
    
    def is_available(self) -> bool:
        return HAS_GTTS
    
    async def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        output_path: Optional[str] = None
    ) -> SynthesisResult:
        if not self.is_available():
            return SynthesisResult(
                success=False,
                error="gTTS not installed. Install with: pip install gTTS",
                provider=VoiceProvider.GTTS
            )
        
        try:
            from gtts import gTTS
            
            if not output_path:
                output_path = f"voice_output/gtts_{int(time.time())}.mp3"
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            tts = gTTS(text=text, lang=voice_config.language, slow=False)
            
            # Run in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: tts.save(output_path)
            )
            
            return SynthesisResult(
                success=True,
                audio_path=output_path,
                provider=VoiceProvider.GTTS,
                voice_id=voice_config.language
            )
            
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e),
                provider=VoiceProvider.GTTS
            )
    
    def get_available_voices(self) -> List[Dict]:
        # gTTS supports many languages
        return [
            {"id": "en", "name": "English", "provider": "gtts"},
            {"id": "es", "name": "Spanish", "provider": "gtts"},
            {"id": "fr", "name": "French", "provider": "gtts"},
            {"id": "de", "name": "German", "provider": "gtts"},
            {"id": "it", "name": "Italian", "provider": "gtts"},
            {"id": "ja", "name": "Japanese", "provider": "gtts"},
        ]


class Pyttsx3Synthesizer(VoiceSynthesizer):
    """pyttsx3 TTS provider (offline, local)."""
    
    def __init__(self):
        self._engine = None
    
    def is_available(self) -> bool:
        return HAS_PYTTSX3
    
    def _get_engine(self):
        if self._engine is None:
            import pyttsx3
            self._engine = pyttsx3.init()
        return self._engine
    
    async def synthesize(
        self,
        text: str,
        voice_config: VoiceConfig,
        output_path: Optional[str] = None
    ) -> SynthesisResult:
        if not self.is_available():
            return SynthesisResult(
                success=False,
                error="pyttsx3 not installed. Install with: pip install pyttsx3",
                provider=VoiceProvider.PYTTSX3
            )
        
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            # Configure voice
            voices = engine.getProperty('voices')
            if voice_config.voice_id and len(voices) > int(voice_config.voice_id):
                engine.setProperty('voice', voices[int(voice_config.voice_id)].id)
            
            engine.setProperty('rate', int(200 * voice_config.speed))
            engine.setProperty('pitch', voice_config.pitch)
            
            if not output_path:
                output_path = f"voice_output/pyttsx3_{int(time.time())}.wav"
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            # Save to file
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            
            return SynthesisResult(
                success=True,
                audio_path=output_path,
                provider=VoiceProvider.PYTTSX3,
                voice_id=voice_config.voice_id
            )
            
        except Exception as e:
            return SynthesisResult(
                success=False,
                error=str(e),
                provider=VoiceProvider.PYTTSX3
            )
    
    def get_available_voices(self) -> List[Dict]:
        if not self.is_available():
            return []
        
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            return [
                {
                    "id": str(i),
                    "name": v.name,
                    "languages": v.languages,
                    "provider": "pyttsx3"
                }
                for i, v in enumerate(voices)
            ]
        except:
            return []


class VoiceSystem:
    """
    Main voice synthesis system with multi-provider support,
    caching, and NPC voice profiles.
    """
    
    def __init__(
        self,
        cache_dir: str = "voice_cache",
        output_dir: str = "voice_output",
        default_provider: VoiceProvider = VoiceProvider.EDGE_TTS,
    ):
        """
        Initialize the voice system.
        
        Args:
            cache_dir: Directory for cached audio files
            output_dir: Directory for generated audio files
            default_provider: Default TTS provider to use
        """
        self.cache_dir = Path(cache_dir)
        self.output_dir = Path(output_dir)
        self.default_provider = default_provider
        
        # Initialize synthesizers
        self.synthesizers: Dict[VoiceProvider, VoiceSynthesizer] = {
            VoiceProvider.ELEVENLABS: ElevenLabsSynthesizer(),
            VoiceProvider.OPENAI: OpenAISynthesizer(),
            VoiceProvider.EDGE_TTS: EdgeTTSSynthesizer(),
            VoiceProvider.GTTS: GTTSSynthesizer(),
            VoiceProvider.PYTTSX3: Pyttsx3Synthesizer(),
            VoiceProvider.COQUI: CoquiSynthesizer(),
        }
        
        # NPC voice profiles
        self.voice_profiles: Dict[str, VoiceConfig] = {}
        
        # Create directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def register_voice(self, npc_name: str, voice_config: VoiceConfig):
        """Register a voice profile for an NPC."""
        self.voice_profiles[npc_name] = voice_config
    
    def get_voice(self, npc_name: str) -> Optional[VoiceConfig]:
        """Get voice profile for an NPC."""
        return self.voice_profiles.get(npc_name)
    
    def _get_cache_key(self, text: str, voice_config: VoiceConfig) -> str:
        """Generate cache key for text + voice combination."""
        content = f"{text}|{voice_config.voice_id}|{voice_config.speed}|{voice_config.provider.value}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_audio(self, cache_key: str) -> Optional[str]:
        """Check if audio is cached."""
        cache_path = self.cache_dir / f"{cache_key}.mp3"
        if cache_path.exists():
            return str(cache_path)
        
        # Also check for wav
        cache_path = self.cache_dir / f"{cache_key}.wav"
        if cache_path.exists():
            return str(cache_path)
        
        return None
    
    async def synthesize(
        self,
        text: str,
        npc_name: Optional[str] = None,
        voice_config: Optional[VoiceConfig] = None,
        provider: Optional[VoiceProvider] = None,
        use_cache: bool = True,
        output_path: Optional[str] = None,
    ) -> SynthesisResult:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            npc_name: NPC name to use registered voice profile
            voice_config: Voice configuration (overrides NPC profile)
            provider: Force specific provider (overrides default)
            use_cache: Whether to use cached audio
            output_path: Custom output path for audio file
            
        Returns:
            SynthesisResult with audio path and metadata
        """
        # Determine voice config
        if voice_config is None:
            if npc_name and npc_name in self.voice_profiles:
                voice_config = self.voice_profiles[npc_name]
            else:
                # Default voice
                voice_config = VoiceConfig(
                    name="Default",
                    provider=provider or self.default_provider,
                    voice_id=self._get_default_voice_id(provider or self.default_provider),
                )
        
        # Override provider if specified
        if provider:
            voice_config.provider = provider
        
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(text, voice_config)
            cached_path = self._get_cached_audio(cache_key)
            if cached_path:
                return SynthesisResult(
                    success=True,
                    audio_path=cached_path,
                    provider=voice_config.provider,
                    voice_id=voice_config.voice_id,
                    cached=True
                )
        
        # Get synthesizer
        synthesizer = self.synthesizers.get(voice_config.provider)
        if not synthesizer or not synthesizer.is_available():
            # Fallback to next available provider
            synthesizer = self._get_fallback_synthesizer()
            if not synthesizer:
                return SynthesisResult(
                    success=False,
                    error="No TTS providers available",
                    provider=voice_config.provider
                )
        
        # Set default output path
        if not output_path and use_cache:
            cache_key = self._get_cache_key(text, voice_config)
            ext = ".mp3" if voice_config.provider in [VoiceProvider.ELEVENLABS, VoiceProvider.OPENAI, VoiceProvider.EDGE_TTS, VoiceProvider.GTTS] else ".wav"
            output_path = str(self.cache_dir / f"{cache_key}{ext}")
        
        # Synthesize
        result = await synthesizer.synthesize(text, voice_config, output_path)
        
        # Update voice config in result
        if result.success:
            result.voice_id = voice_config.voice_id
        
        return result
    
    def _get_default_voice_id(self, provider: VoiceProvider) -> str:
        """Get default voice ID for a provider."""
        defaults = {
            VoiceProvider.ELEVENLABS: "21m00Tcm4TlvDq8ikWAM",  # Rachel
            VoiceProvider.OPENAI: "alloy",
            VoiceProvider.EDGE_TTS: "en-US-JennyNeural",
            VoiceProvider.GTTS: "en",
            VoiceProvider.PYTTSX3: "0",
            VoiceProvider.COQUI: "tts_models/en/ljspeech/vits",
        }
        return defaults.get(provider, "default")
    
    def _get_fallback_synthesizer(self) -> Optional[VoiceSynthesizer]:
        """Get first available synthesizer as fallback."""
        fallback_order = [
            VoiceProvider.EDGE_TTS,
            VoiceProvider.GTTS,
            VoiceProvider.PYTTSX3,
            VoiceProvider.OPENAI,
            VoiceProvider.ELEVENLABS,
        ]
        
        for provider in fallback_order:
            synthesizer = self.synthesizers.get(provider)
            if synthesizer and synthesizer.is_available():
                return synthesizer
        
        return None
    
    def get_available_providers(self) -> List[Dict]:
        """Get list of available providers."""
        providers = []
        for provider, synthesizer in self.synthesizers.items():
            providers.append({
                "provider": provider.value,
                "available": synthesizer.is_available(),
                "voices": synthesizer.get_available_voices()[:10]  # Limit for display
            })
        return providers
    
    def get_available_voices(self, provider: Optional[VoiceProvider] = None) -> List[Dict]:
        """Get available voices for a provider or all providers."""
        if provider:
            synthesizer = self.synthesizers.get(provider)
            if synthesizer:
                return synthesizer.get_available_voices()
            return []
        
        # Get voices from all providers
        all_voices = []
        for prov, synthesizer in self.synthesizers.items():
            if synthesizer.is_available():
                voices = synthesizer.get_available_voices()
                for voice in voices:
                    voice["provider"] = prov.value
                all_voices.extend(voices)
        
        return all_voices
    
    def save_profiles(self, filepath: str = "voice_profiles.json"):
        """Save voice profiles to file."""
        data = {
            name: config.to_dict()
            for name, config in self.voice_profiles.items()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_profiles(self, filepath: str = "voice_profiles.json"):
        """Load voice profiles from file."""
        if not os.path.exists(filepath):
            return
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.voice_profiles = {
            name: VoiceConfig.from_dict(config)
            for name, config in data.items()
        }


# Convenience function for quick synthesis
async def synthesize_speech(
    text: str,
    voice: str = "en-US-JennyNeural",
    provider: str = "edge_tts",
    output_path: Optional[str] = None,
) -> SynthesisResult:
    """
    Quick helper to synthesize speech.
    
    Args:
        text: Text to synthesize
        voice: Voice ID
        provider: Provider name (elevenlabs, openai, edge_tts, gtts, pyttsx3)
        output_path: Output file path
        
    Returns:
        SynthesisResult
    """
    system = VoiceSystem()
    
    voice_config = VoiceConfig(
        name="Quick Voice",
        provider=VoiceProvider(provider),
        voice_id=voice,
    )
    
    return await system.synthesize(text, voice_config=voice_config, output_path=output_path)


# Default NPC voice profiles for common archetypes
DEFAULT_NPC_VOICES = {
    "blacksmith": VoiceConfig(
        name="Blacksmith",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-US-GuyNeural",
        speed=0.9,
        pitch=0.8,
    ),
    "merchant": VoiceConfig(
        name="Merchant",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-GB-RyanNeural",
        speed=1.1,
    ),
    "wizard": VoiceConfig(
        name="Wizard",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-GB-RyanNeural",
        speed=0.85,
    ),
    "guard": VoiceConfig(
        name="Guard",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-US-GuyNeural",
        speed=1.0,
    ),
    "healer": VoiceConfig(
        name="Healer",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-US-JennyNeural",
        speed=0.95,
    ),
    "noble": VoiceConfig(
        name="Noble",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-GB-SoniaNeural",
        speed=0.9,
    ),
    "child": VoiceConfig(
        name="Child",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-AU-NatashaNeural",
        speed=1.2,
        pitch=1.3,
    ),
    "elder": VoiceConfig(
        name="Elder",
        provider=VoiceProvider.EDGE_TTS,
        voice_id="en-GB-RyanNeural",
        speed=0.75,
    ),
}


def setup_npc_voices(voice_system: VoiceSystem, npc_archetypes: Dict[str, str]):
    """
    Setup voice profiles for NPCs based on their archetypes.
    
    Args:
        voice_system: VoiceSystem instance
        npc_archetypes: Dict of npc_name -> archetype
    """
    for npc_name, archetype in npc_archetypes.items():
        if archetype in DEFAULT_NPC_VOICES:
            voice_system.register_voice(npc_name, DEFAULT_NPC_VOICES[archetype])
