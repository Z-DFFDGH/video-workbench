from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from video_workbench.media_tools import (
    MediaCommandError,
    build_ffmpeg_command,
    conversion_request,
    parse_timecode,
    resize_request,
    trim_request,
    validate_dimensions,
    validate_volume_db,
    volume_request,
)


class MediaToolCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.output = self.root / "output"
        self.output.mkdir()

    def create_media(self, name: str) -> Path:
        path = self.root / name
        path.write_bytes(b"media")
        return path

    def assert_audio_codec(self, command: list[str], expected: str) -> None:
        self.assertIn("-c:a", command)
        self.assertEqual(command[command.index("-c:a") + 1], expected)

    def test_audio_conversion_commands_cover_required_pairs(self) -> None:
        cases = (
            ("source.mp3", ".wav", "pcm_s16le"),
            ("source.wav", ".mp3", "libmp3lame"),
            ("source.mp3", ".aac", "aac"),
            ("source.aac", ".mp3", "libmp3lame"),
            ("source.wav", ".aac", "aac"),
            ("source.aac", ".wav", "pcm_s16le"),
            ("source.mp3", ".flac", "flac"),
            ("source.flac", ".mp3", "libmp3lame"),
        )

        for source_name, target, codec in cases:
            with self.subTest(source=source_name, target=target):
                source = self.create_media(source_name)
                request = conversion_request(source, self.output, target)
                output = self.output / f"converted{target}"
                command = build_ffmpeg_command(request, output)

                self.assertIn("-vn", command)
                self.assert_audio_codec(command, codec)
                self.assertEqual(command[-1], str(output.resolve()))

    def test_video_conversion_commands_cover_all_targets(self) -> None:
        sources = ("source.mp4", "source.mov", "source.mkv", "source.webm")
        targets = (".mp4", ".mov", ".mkv", ".webm")

        for source_name in sources:
            for target in targets:
                if Path(source_name).suffix.lower() == target:
                    continue
                with self.subTest(source=source_name, target=target):
                    source = self.create_media(source_name)
                    request = conversion_request(source, self.output, target)
                    command = build_ffmpeg_command(
                        request,
                        self.output / f"converted{target}",
                    )
                    if target == ".webm":
                        self.assertIn("libvpx-vp9", command)
                        self.assertIn("libopus", command)
                    else:
                        self.assertIn("libx264", command)
                        self.assertIn("aac", command)

    def test_extract_audio_targets(self) -> None:
        source = self.create_media("clip.mp4")
        cases = (
            (".mp3", "libmp3lame"),
            (".wav", "pcm_s16le"),
            (".aac", "aac"),
        )

        for target, codec in cases:
            with self.subTest(target=target):
                request = conversion_request(source, self.output, target)
                command = build_ffmpeg_command(
                    request,
                    self.output / f"audio{target}",
                )
                self.assertIn("-vn", command)
                self.assert_audio_codec(command, codec)

    def test_trim_command_contains_start_and_duration(self) -> None:
        source = self.create_media("clip.mp4")
        request = trim_request(source, self.output, "00:03", "00:08.5")
        command = build_ffmpeg_command(request, self.output / "clip_trimmed.mp4")

        self.assertEqual(command[command.index("-ss") + 1], "3")
        self.assertEqual(command[command.index("-t") + 1], "5.5")
        self.assertIn("libx264", command)

    def test_resize_command_uses_scale_pad_and_even_dimensions(self) -> None:
        source = self.create_media("clip.mp4")
        request = resize_request(source, self.output, 1080, 1920)
        command = build_ffmpeg_command(request, self.output / "clip_resized.mp4")
        filter_value = command[command.index("-vf") + 1]

        self.assertIn("scale=1080:1920:force_original_aspect_ratio=decrease", filter_value)
        self.assertIn("pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black", filter_value)
        self.assertIn("setsar=1", filter_value)

    def test_volume_command_uses_db_filter(self) -> None:
        source = self.create_media("voice.wav")
        request = volume_request(source, self.output, -3)
        command = build_ffmpeg_command(request, self.output / "voice_volume.wav")

        self.assertIn("-af", command)
        self.assertEqual(command[command.index("-af") + 1], "volume=-3dB")

    def test_timecode_and_dimension_validation(self) -> None:
        self.assertEqual(parse_timecode("01:02:03.5"), 3723.5)
        self.assertEqual(validate_dimensions(1080, 1920), (1080, 1920))
        self.assertEqual(validate_volume_db(6), 6.0)

        for value in ("", "-1", "00:70", "12:xx"):
            with self.subTest(value=value):
                with self.assertRaises(MediaCommandError):
                    parse_timecode(value)
        with self.assertRaises(MediaCommandError):
            validate_dimensions(1081, 1920)
        with self.assertRaises(MediaCommandError):
            validate_volume_db(61)

    def test_invalid_trim_and_audio_to_video_requests_are_rejected(self) -> None:
        video = self.create_media("clip.mp4")
        audio = self.create_media("voice.mp3")

        with self.assertRaises(MediaCommandError):
            trim_request(video, self.output, "00:08", "00:03")
        with self.assertRaises(MediaCommandError):
            conversion_request(audio, self.output, ".mp4")
        with self.assertRaises(MediaCommandError):
            conversion_request(video, self.output, ".mp4")


if __name__ == "__main__":
    unittest.main()
