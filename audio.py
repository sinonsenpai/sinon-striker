"""
Audio module — envelope-based sound generation and SoundManager.
Uses numpy + pygame.sndarray to generate all SFX and music in-memory.
"""

import numpy as np
import pygame


def generate_sound(envelope: list, volume=0.3):
    """
    Generate a sound from an envelope of (frequency, duration, wave_type) segments.
    frequency: float for fixed, or (start, end) tuple for sweep_up / sweep_down.
    wave_type: "sine", "square", "noise", "sweep_up", "sweep_down".
    Each segment is auto-faded (10% in/out) to avoid clicks.
    """
    sample_rate = 22050
    total_frames = 0
    for _, dur, _ in envelope:
        total_frames += int(sample_rate * dur)

    wave = np.zeros(total_frames, dtype=np.float64)
    cursor = 0

    for freq, dur, wave_type in envelope:
        seg_frames = int(sample_rate * dur)
        t = np.linspace(0, dur, seg_frames, endpoint=False)

        if wave_type == "sine":
            seg = np.sin(2 * np.pi * freq * t)
        elif wave_type == "square":
            seg = np.sign(np.sin(2 * np.pi * freq * t))
        elif wave_type == "noise":
            seg = np.random.uniform(-1, 1, seg_frames).astype(np.float64)
        elif wave_type == "sweep_up":
            f0, f1 = freq
            freqs = np.linspace(f0, f1, seg_frames)
            seg = np.sin(2 * np.pi * freqs * t)
        elif wave_type == "sweep_down":
            f0, f1 = freq
            freqs = np.linspace(f0, f1, seg_frames)
            seg = np.sin(2 * np.pi * freqs * t)
        else:
            seg = np.zeros(seg_frames)

        # 10% fade in / fade out to prevent clicks
        fade_len = max(1, int(seg_frames * 0.1))
        seg[:fade_len] *= np.linspace(0, 1, fade_len)
        seg[-fade_len:] *= np.linspace(1, 0, fade_len)

        wave[cursor:cursor + seg_frames] = seg
        cursor += seg_frames

    wave = (wave * volume * 32767 * 0.5).astype(np.int16)
    stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
    return pygame.sndarray.make_sound(stereo)


# ── Envelope definitions ───────────────────────────────────────────────

SOUND_ENVELOPES = {
    "attack": [
        ((400, 800), 0.08, "sweep_up"),
        (300, 0.05, "noise"),
    ],
    "enemy_hit": [
        ((200, 80), 0.15, "sweep_down"),
    ],
    "player_hit": [
        (150, 0.05, "square"),
        (100, 0.10, "noise"),
    ],
    "skill": [
        ((300, 900), 0.10, "sweep_up"),
        (800, 0.15, "sine"),
    ],
    "buff": [
        (400, 0.05, "sine"),
        (600, 0.05, "sine"),
        (800, 0.05, "sine"),
    ],
    "crit": [
        (800, 0.03, "square"),
        (200, 0.06, "noise"),
    ],
    "victory": [
        (659, 0.12, "sine"),
        (784, 0.12, "sine"),
        (988, 0.12, "sine"),
        (1319, 0.20, "sine"),
    ],
    "menu_select": [
        (600, 0.03, "sine"),
    ],
    "menu_confirm": [
        ((500, 700), 0.06, "sweep_up"),
    ],
    "item_use": [
        ((300, 600), 0.20, "sweep_up"),
    ],
    "loot_drop": [
        (500, 0.03, "sine"),
        (700, 0.03, "sine"),
    ],
    "enemy_turn": [
        (120, 0.06, "square"),
    ],
    "achievement_unlock": [
        (880, 0.08, "sine"),
        (1100, 0.08, "sine"),
        (1320, 0.15, "sine"),
    ],
    "boss_roar": [
        ((300, 80), 0.4, "sweep_down"),
    ],
    "floor_up": [
        (523, 0.06, "sine"),
        (659, 0.06, "sine"),
        (784, 0.10, "sine"),
    ],
    "rest_heal": [
        (400, 0.10, "sine"),
        (500, 0.15, "sine"),
    ],
    "shop_buy": [
        ((500, 800), 0.12, "sweep_up"),
    ],
    "shop_sell": [
        (600, 0.06, "sine"),
        (400, 0.06, "sine"),
    ],
    "menu_back": [
        ((500, 300), 0.08, "sweep_down"),
    ],
    "error": [
        (200, 0.10, "square"),
    ],
    "boss_defeated": [
        (659, 0.10, "sine"),
        (784, 0.10, "sine"),
        (988, 0.10, "sine"),
        (1319, 0.25, "sine"),
        (1760, 0.30, "sine"),
    ],
    "miss": [
        (200, 0.05, "square"),
        (150, 0.05, "square"),
    ],
    "level_up": [
        (784, 0.06, "sine"),
        (988, 0.06, "sine"),
        (1175, 0.12, "sine"),
    ],
}

SOUND_VOLUMES = {
    "attack": 0.25, "enemy_hit": 0.30, "player_hit": 0.35,
    "skill": 0.30, "buff": 0.20, "crit": 0.40,
    "victory": 0.30, "menu_select": 0.20, "menu_confirm": 0.25,
    "item_use": 0.20, "loot_drop": 0.20, "enemy_turn": 0.15,
    "achievement_unlock": 0.35, "boss_roar": 0.40, "floor_up": 0.25,
    "rest_heal": 0.20, "shop_buy": 0.20, "shop_sell": 0.20,
    "menu_back": 0.20, "error": 0.30, "boss_defeated": 0.35, "miss": 0.20, "level_up": 0.30,
}


def generate_battle_music(duration=4.0):
    """
    Looping battle theme — 4-beat bass pulse + Em pad chord with fade.
    Tempo ~120 BPM, 4/4 time.
    """
    sample_rate = 22050
    total_frames = int(sample_rate * duration)
    beat_len = duration / 4.0  # one beat at 120 BPM in 4/4
    wave = np.zeros(total_frames, dtype=np.float64)

    # Bass pulse: E2 (82Hz) on each beat, 0.15s per hit, square wave
    for beat in range(4):
        start = int(sample_rate * beat * beat_len)
        end = int(start + sample_rate * 0.15)
        seg_len = end - start
        t_seg = np.linspace(0, 0.15, seg_len, endpoint=False)
        seg = np.sign(np.sin(2 * np.pi * 82 * t_seg)) * 0.15
        # quick fade out on the bass hit
        fade_out = max(1, int(seg_len * 0.3))
        seg[-fade_out:] *= np.linspace(1, 0, fade_out)
        wave[start:end] = seg

    # Pad chord: Em (E3=165Hz, G3=196Hz, B3=247Hz) sine, fades in/out
    t = np.linspace(0, duration, total_frames, endpoint=False)
    pad = (np.sin(2 * np.pi * 165 * t) +
           np.sin(2 * np.pi * 196 * t) +
           np.sin(2 * np.pi * 247 * t)) * 0.06

    # Envelope: fade in over 1s, hold 2s, fade out over 1s
    env = np.ones(total_frames)
    fade_in = int(sample_rate * 1.0)
    fade_out_start = int(sample_rate * 3.0)
    env[:fade_in] = np.linspace(0, 1, fade_in)
    env[fade_out_start:] = np.linspace(1, 0, total_frames - fade_out_start)
    pad *= env

    wave = wave + pad
    wave = (wave * 32767 * 0.5).astype(np.int16)
    stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
    return pygame.sndarray.make_sound(stereo)


def generate_title_music(duration=6.0):
    """Ambient, mysterious — slow pads with shimmer."""
    sample_rate = 22050
    frames = int(sample_rate * duration)
    t = np.linspace(0, duration, frames, endpoint=False)

    # Deep pad: Em chord (E2, G2, B2) very soft
    pad = (np.sin(2 * np.pi * 82 * t) * 0.08 +
           np.sin(2 * np.pi * 98 * t) * 0.06 +
           np.sin(2 * np.pi * 123 * t) * 0.06)

    # Shimmer: high arpeggio that fades in/out slowly
    shimmer_env = np.clip((np.sin(2 * np.pi * 0.25 * t) + 1) * 0.5, 0, 1)
    shimmer = np.sin(2 * np.pi * 880 * t) * 0.04 * shimmer_env

    # Subtle pulse every 2 seconds
    pulse = (np.sign(np.sin(2 * np.pi * 0.5 * t)) + 1) * 0.5 * 0.02

    wave = pad + shimmer + pulse
    wave = (wave * 32767 * 0.4).astype(np.int16)
    stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
    return pygame.sndarray.make_sound(stereo)


def generate_hub_music(duration=5.0):
    """Warm, relaxed — major chord with gentle rhythm."""
    sample_rate = 22050
    frames = int(sample_rate * duration)
    t = np.linspace(0, duration, frames, endpoint=False)

    # Warm bass: C2 (65Hz) steady
    bass = np.sin(2 * np.pi * 65 * t) * 0.10

    # Major chord pad: C3, E3, G3 (happy, warm)
    chord = (np.sin(2 * np.pi * 131 * t) * 0.06 +
             np.sin(2 * np.pi * 165 * t) * 0.05 +
             np.sin(2 * np.pi * 196 * t) * 0.05)

    # Gentle rhythm: soft taps at 120 BPM
    beat = np.zeros(frames)
    beat_interval = int(sample_rate * 0.5)
    for i in range(int(duration / 0.5)):
        pos = i * beat_interval
        if pos < frames:
            beat_env = np.exp(-np.linspace(0, 5, int(sample_rate * 0.1)))
            end_pos = min(frames, pos + len(beat_env))
            beat[pos:end_pos] += beat_env[:end_pos - pos] * 0.03 * (0.7 if i % 2 == 0 else 0.4)

    wave = bass + chord + beat
    wave = (wave * 32767 * 0.4).astype(np.int16)
    stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
    return pygame.sndarray.make_sound(stereo)


class SoundManager:
    """Manages all game audio — pre-generates SFX and provides play methods."""

    def __init__(self):
        self.volume = 0.3
        self.music_volume = 0.25
        self._sounds = {}
        self._current_music = None

    def init(self):
        """Pre-generate all sound effects and music."""
        pygame.mixer.quit()
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)

        # Load persisted settings
        from save_manager import load_settings
        settings = load_settings()
        self.volume = settings.get("sfx_volume", 0.3)
        self.music_volume = settings.get("music_volume", 0.25)

        for name, env in SOUND_ENVELOPES.items():
            vol = SOUND_VOLUMES.get(name, 0.25)
            self._sounds[name] = generate_sound(env, vol)

        self._battle_music = generate_battle_music(4.0)
        self._battle_music.set_volume(self.music_volume)

        self._title_music = generate_title_music(6.0)
        self._title_music.set_volume(self.music_volume)

        self._hub_music = generate_hub_music(5.0)
        self._hub_music.set_volume(self.music_volume)

    def play(self, name: str):
        """Play a named sound effect at current volume."""
        snd = self._sounds.get(name)
        if snd:
            snd.set_volume(self.volume)
            snd.play()

    def _stop_all_music(self):
        """Stop all looping music tracks."""
        self._battle_music.stop()
        self._title_music.stop()
        self._hub_music.stop()

    def play_title_music(self):
        """Start the title screen ambient music."""
        if self._current_music != "title":
            self._stop_all_music()
            self._title_music.play(-1)
            self._current_music = "title"

    def play_hub_music(self):
        """Start the Haven's Rest hub music."""
        if self._current_music != "hub":
            self._stop_all_music()
            self._hub_music.play(-1)
            self._current_music = "hub"

    def start_battle_music(self):
        """Start the battle music, stopping any other music."""
        if self._current_music != "battle":
            self._stop_all_music()
            self._battle_music.play(-1)
            self._current_music = "battle"

    def stop_battle_music(self):
        """Stop the battle music."""
        self._battle_music.stop()
        if self._current_music == "battle":
            self._current_music = None

    def stop_music(self):
        """Stop all music."""
        self._stop_all_music()
        self._current_music = None

    def adjust_volume(self, delta: float):
        self.volume = max(0.0, min(1.0, self.volume + delta))

    def set_music_volume(self, vol: float):
        self.music_volume = max(0.0, min(1.0, vol))
        self._title_music.set_volume(self.music_volume)
        self._hub_music.set_volume(self.music_volume)
        self._battle_music.set_volume(self.music_volume)

    def get_music_volume(self) -> float:
        return self.music_volume
