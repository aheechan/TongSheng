"""Unit tests that need neither GPU nor model weights."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tongsheng.config import (AppConfig, normalize_language, other_language,
                              output_language_prompt_name, output_languages,
                              speaks_target, OUTPUT_LANGUAGE_CODES)  # noqa: E402
from tongsheng.text import detect_language, split_sentences  # noqa: E402
from tongsheng.tts.voices import VoiceProfile, VoiceStore  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = AppConfig()
        self.assertEqual(cfg.language, "zh")
        self.assertEqual(cfg.mode, "live")
        self.assertEqual(cfg.target_language, "en")
        self.assertEqual(cfg.tier().sample_rate, 24000)

    def test_language_switch_changes_target(self) -> None:
        cfg = AppConfig()
        cfg.ui.language = "en"
        cfg.normalize()
        self.assertEqual(cfg.target_language, "zh")
        self.assertEqual(cfg.tier("rec").sample_rate, 48000)

    def test_aliases(self) -> None:
        self.assertEqual(normalize_language("cn"), "zh")
        self.assertEqual(normalize_language("English"), "en")
        self.assertEqual(other_language("zh"), "en")

    def test_roundtrip(self) -> None:
        cfg = AppConfig()
        cfg.ui.mode = "rec"
        cfg.tts.speed = 1.07
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            cfg.save(path)
            loaded = AppConfig.load(path)
        self.assertEqual(loaded.mode, "rec")
        self.assertAlmostEqual(loaded.tts.speed, 1.07, places=3)
        self.assertEqual(loaded.tier().version, "v4")

    def test_tier_config_survives_yaml(self) -> None:
        cfg = AppConfig.load(ROOT / "config.example.yaml")
        self.assertEqual(cfg.tts.tiers["live"].sample_rate, 24000)
        self.assertEqual(cfg.tiers["rec"].version if hasattr(cfg, "tiers") else
                         cfg.tts.tiers["rec"].version, "v4")

    def test_output_language_catalog(self) -> None:
        self.assertEqual(len(OUTPUT_LANGUAGE_CODES), 15)
        self.assertIn("ja", OUTPUT_LANGUAGE_CODES)
        self.assertTrue(speaks_target("ja"))
        self.assertTrue(speaks_target("ko"))
        self.assertFalse(speaks_target("es"))
        self.assertEqual(output_language_prompt_name("ja"), "Japanese (日本語)")
        labels = output_languages("zh")
        self.assertEqual(len(labels), 15)
        self.assertIn("Español", labels[4][1])

    def test_explicit_output_language_wins(self) -> None:
        cfg = AppConfig()
        cfg.translate.target_language = "ja"
        cfg.normalize()
        self.assertEqual(cfg.target_language, "ja")
        cfg.translate.target_language = ""
        cfg.normalize()
        self.assertEqual(cfg.target_language, "en")

    def test_unknown_output_language_falls_back_to_auto(self) -> None:
        cfg = AppConfig()
        cfg.translate.target_language = "klingon"
        cfg.normalize()
        self.assertEqual(cfg.translate.target_language, "")
        self.assertEqual(cfg.target_language, "en")


class TextTests(unittest.TestCase):
    def test_detect(self) -> None:
        self.assertEqual(detect_language("你好，世界"), "zh")
        self.assertEqual(detect_language("Hello world, how are you?"), "en")

    def test_split_keeps_sentences(self) -> None:
        parts = split_sentences("今天很好。明天呢？后天再说吧！", max_chars=40)
        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[0].startswith("今天很好"))

    def test_split_long_english(self) -> None:
        text = "This is a long sentence that should be broken into smaller pieces for the speech synthesizer to handle well."
        parts = split_sentences(text, max_chars=30, lang="en")
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= 30 for p in parts))


class VoiceTests(unittest.TestCase):
    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = VoiceStore(Path(tmp))
            profile = VoiceProfile(id="demo-1", name="Demo", reference_text="hello")
            store.save(profile)
            loaded = store.get("demo-1")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.name, "Demo")
            self.assertEqual(loaded.reference_text, "hello")
            self.assertFalse(loaded.trained)
            self.assertTrue((Path(loaded.dir) / "profile.json").exists())

    def test_privatevoice_layout_is_understood(self) -> None:
        data = {
            "id": "x-1", "name": "X",
            "voice": {"mode": "finetune", "gpt_ckpt": "a.ckpt",
                      "sovits_ckpt": "b_l48.pth", "reference": "reference.wav",
                      "reference_text": "你好"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            profile = VoiceProfile.from_dict(data, tmp)
            self.assertEqual(profile.gpt_ckpt, "a.ckpt")
            self.assertEqual(profile.sovits_rec, "b_l48.pth")
            self.assertEqual(profile.reference_text, "你好")
            self.assertTrue(profile.trained)


class PromptTests(unittest.TestCase):
    def test_correction_json_parsing(self) -> None:
        from tongsheng.correct import apply_guard, parse_correction

        result = parse_correction('```json\n{"text": "你好世界", "risk": 0.1, "edits": []}\n```',
                                  "你好世界")
        self.assertEqual(result.text, "你好世界")
        self.assertFalse(result.parse_error)

    def test_guard_rejects_rewrites(self) -> None:
        from tongsheng.correct import CorrectionResult, apply_guard

        original = "今天天气很好"
        result = apply_guard(CorrectionResult(text="今天天气非常非常好并且适合出游"), original, 0.2)
        self.assertEqual(result.text, original)

    def test_translation_cleanup(self) -> None:
        from tongsheng.translate import clean_translation

        self.assertEqual(clean_translation("译文：Hello there."), "Hello there.")
        self.assertEqual(clean_translation('"Hi."'), "Hi.")


class HotkeyTests(unittest.TestCase):
    def test_parse(self) -> None:
        from tongsheng.hotkey import parse_combo

        combo = parse_combo("ctrl+alt")
        self.assertEqual(combo.modifiers, {"ctrl", "alt"})
        self.assertIsNone(combo.key)
        combo = parse_combo("ctrl+shift+space")
        self.assertEqual(combo.key, 0x20)
        with self.assertRaises(ValueError):
            parse_combo("nonsensekey")


class HistoryTests(unittest.TestCase):
    def test_jsonl_roundtrip(self) -> None:
        from tongsheng.service import TurnResult

        result = TurnResult(raw="a", translation="b")
        record = result.as_record()
        self.assertIn("ts", record)
        json.dumps(record, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
