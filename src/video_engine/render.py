"""Minimal rendering utilities using MoviePy.

This module provides an MVP function to render a single photo to an MP4
video. The implementation is intentionally small and provides clear
error messages when dependencies are missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import os
import shutil
import subprocess
import sys
from functools import lru_cache
import tempfile
import time
import threading
import queue
from collections import deque

# Pillow compatibility for Image.ANTIALIAS removal in recent versions.
# Some MoviePy functions reference Image.ANTIALIAS; ensure it's defined.
try:
    import PIL.Image as PILImage

    if not hasattr(PILImage, "ANTIALIAS") and hasattr(PILImage, "Resampling"):
        PILImage.ANTIALIAS = PILImage.Resampling.LANCZOS
except Exception:
    pass


def render_single_photo(
    photo_path: Path,
    output_path: Path,
    duration: float = 60.0,
    fps: int = 30,
    bgm_path: Optional[Path] = None,
    fade_in: float = 1.0,
    fade_out: float = 1.0,
) -> None:
    """Render a single photo as an MP4 video, optionally with background music.

    Parameters
    - photo_path: Path to the source image file (must exist)
    - output_path: Path to write the MP4 file (parent directories will be created)
    - duration: duration of the output video in seconds (float)
    - fps: frames per second to write
    - bgm_path: optional Path to an audio file to use as background music
    - fade_in/fade_out: seconds for audio fade-in/out (will be clamped to <= duration/2)

    Raises
    - FileNotFoundError: if ``photo_path`` or ``bgm_path`` (when provided) does not exist
    - RuntimeError: if moviepy is not installed or rendering fails
    """
    if not photo_path.exists() or not photo_path.is_file():
        raise FileNotFoundError(f"Photo not found or not a file: {photo_path}")

    if bgm_path is not None and (not bgm_path.exists() or not bgm_path.is_file()):
        raise FileNotFoundError(f"BGM not found or not a file: {bgm_path}")

    try:
        # Import lazily to provide clear errors when dependency is missing
        # Support different MoviePy layouts across versions.
        try:
            from moviepy.editor import ImageClip, AudioFileClip
        except Exception:
            # Fallback paths for newer/older MoviePy versions
            from moviepy.video.VideoClip import ImageClip  # type: ignore
            from moviepy.audio.io.AudioFileClip import AudioFileClip  # type: ignore

        # Audio fx: try to import a convenient container; otherwise import specific functions
        # Audio fx: try to import a convenient container; otherwise import classes
        audio_loop = None
        audio_fadein = None
        audio_fadeout = None
        AudioLoopClass = None
        AudioFadeInClass = None
        AudioFadeOutClass = None
        try:
            import moviepy.audio.fx.all as afx
            audio_loop = getattr(afx, "audio_loop", None)
            audio_fadein = getattr(afx, "audio_fadein", None)
            audio_fadeout = getattr(afx, "audio_fadeout", None)
        except Exception:
            # Import fx classes for MoviePy versions that expose them as classes
            try:
                from moviepy.audio.fx.AudioLoop import AudioLoop as AudioLoopClass
            except Exception:
                AudioLoopClass = None
            try:
                from moviepy.audio.fx.AudioFadeIn import AudioFadeIn as AudioFadeInClass
            except Exception:
                AudioFadeInClass = None
            try:
                from moviepy.audio.fx.AudioFadeOut import AudioFadeOut as AudioFadeOutClass
            except Exception:
                AudioFadeOutClass = None
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "moviepy is required for rendering with audio; install the 'render' extras (e.g., pip install -e \".[render]\")"
        ) from exc

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Create clip and set duration using APIs compatible across MoviePy versions
        clip = ImageClip(str(photo_path))
        try:
            clip = clip.with_duration(float(duration))
        except Exception:
            # Fallback to attribute assignment
            clip.duration = float(duration)

        audio_clip = None
        if bgm_path is not None:
            audio = AudioFileClip(str(bgm_path))
            # Ensure audio is at least `duration` long by looping if necessary
            if audio.duration < duration:
                if audio_loop is not None:
                    audio = audio_loop(audio, duration=duration)
                elif AudioLoopClass is not None:
                    audio = audio.with_effects([AudioLoopClass(duration=duration)])
                else:
                    # naive concatenation fallback
                    n = int(duration / audio.duration) + 1
                    new_audio = audio
                    for _ in range(n - 1):
                        new_audio = new_audio + audio
                    audio = new_audio.subclip(0, float(duration))
            else:
                audio = audio.subclip(0, float(duration))

            # Clamp fades
            max_fade = float(duration) / 2.0
            fi = min(float(fade_in), max_fade)
            fo = min(float(fade_out), max_fade)

            if fi > 0:
                if audio_fadein is not None:
                    audio = audio_fadein(audio, fi)
                elif AudioFadeInClass is not None:
                    audio = audio.with_effects([AudioFadeInClass(fi)])
            if fo > 0:
                if audio_fadeout is not None:
                    audio = audio_fadeout(audio, fo)
                elif AudioFadeOutClass is not None:
                    audio = audio.with_effects([AudioFadeOutClass(fo)])

            audio_clip = audio
            # Set audio on clip, handling different MoviePy versions
            try:
                clip = clip.set_audio(audio_clip)
            except Exception:
                clip.audio = audio_clip

        # Write file: include audio codec only if audio is present
        # Prefer hardware encoder when available, with fallback to libx264.
        codec = _select_video_encoder()
        write_kwargs = dict(fps=int(fps), codec=codec or "libx264", ffmpeg_params=_compat_ffmpeg_params())
        if audio_clip is not None:
            write_kwargs.update(dict(audio=True, audio_codec="aac"))
        else:
            write_kwargs.update(dict(audio=False))

        _write_videofile_with_fallback(clip, output_path, write_kwargs)
    except Exception as exc:  # pragma: no cover - depends on runtime ffmpeg
        raise RuntimeError(f"Failed to render video: {exc}") from exc


def _close_clip_safe(c):
    try:
        c.close()
    except Exception:
        pass


def _write_videofile_with_fallback(clip, output_path: Path, write_kwargs: dict) -> None:
    """Write a video file, falling back to libx264 if hardware encoder fails silently."""
    # Some MoviePy versions have different write_videofile signatures; call with minimal kwargs.
    clip.write_videofile(str(output_path), **write_kwargs)

    try:
        if output_path.exists() and output_path.stat().st_size > 0:
            return
    except Exception:
        pass

    # If file is missing/empty and codec wasn't libx264, retry with libx264
    codec = write_kwargs.get("codec")
    if codec and codec != "libx264":
        fallback_kwargs = dict(write_kwargs)
        fallback_kwargs["codec"] = "libx264"
        clip.write_videofile(str(output_path), **fallback_kwargs)


def _compat_ffmpeg_params() -> list[str]:
    """Return ffmpeg params for broad playback compatibility."""
    return [
        "-pix_fmt", "yuv420p",
        "-profile:v", "main",
        "-level", "4.1",
        "-movflags", "+faststart",
    ]


@lru_cache(maxsize=1)
def _select_video_encoder() -> Optional[str]:
    """Pick a hardware video encoder if available, else None.

    Order prefers common hardware encoders by platform. Can be overridden by
    env var VIDEO_ENGINE_FFMPEG_CODEC (set empty to disable).
    
    Behavior:
    - VIDEO_ENGINE_FFMPEG_CODEC set (empty or value): Use that (or None)
    - VIDEO_ENGINE_ENABLE_HW=0: Disable hardware, use libx264
    - Otherwise: Auto-detect and use hardware encoder if available (default)
    """
    override = os.environ.get("VIDEO_ENGINE_FFMPEG_CODEC")
    if override is not None:
        return override.strip() or None

    disable_hw = os.environ.get("VIDEO_ENGINE_ENABLE_HW")
    if disable_hw == "0":
        return None  # Explicitly disabled

    # Default: Auto-detect hardware encoder
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None

    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
        )
        encoders_text = result.stdout or ""
    except Exception:
        return None

    encoders = encoders_text.splitlines()

    # Preferred encoder order by platform
    if os.name == "nt":
        candidates = ["h264_nvenc", "h264_qsv", "h264_amf"]
    elif sys.platform == "darwin":
        candidates = ["h264_videotoolbox", "h264_nvenc", "h264_qsv", "h264_amf"]
    else:
        candidates = ["h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"]

    for cand in candidates:
        for line in encoders:
            if cand in line:
                return cand
    return None


def _get_ffmpeg_encoding_preset() -> str:
    """Get ffmpeg encoding preset from environment or return default.
    
    Supports:
    - VIDEO_ENGINE_FFMPEG_PRESET: "ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "placebo"
    - Default: "fast" for CPU, automatic for hardware
    """
    preset = os.environ.get("VIDEO_ENGINE_FFMPEG_PRESET", "").strip()
    if preset:
        return preset
    return "fast"


def _get_ffmpeg_crf() -> int:
    """Get ffmpeg quality setting (CRF) from environment or return default.
    
    Range: 0-51 (0=lossless, 18=visually lossless, 23=default, 51=worst quality)
    Lower values = better quality but slower encoding
    
    Supports VIDEO_ENGINE_FFMPEG_CRF environment variable.
    Default: 28 (good quality with reasonable speed)
    """
    crf = os.environ.get("VIDEO_ENGINE_FFMPEG_CRF", "").strip()
    if crf and crf.isdigit():
        val = int(crf)
        if 0 <= val <= 51:
            return val
    return 28


def _get_filter_scale() -> float:
    """Return processing scale factor for filters (0.1-1.0). Default 1.0 for quality."""
    val = os.environ.get("VIDEO_ENGINE_FILTER_SCALE", "").strip()
    if val:
        try:
            f = float(val)
            if 0.1 <= f <= 1.0:
                return f
        except Exception:
            pass
    return 1.0


def _stage_media_path(path: Path, tmpdir: str, idx: int) -> Path:
    """Stage OneDrive media to a local temp path to avoid placeholder stalls."""
    if "OneDrive" in str(path) or "OneDrive" in str(path.resolve()):
        staged = Path(tmpdir) / f"staged_{idx:04d}{path.suffix.lower()}"
        if not staged.exists():
            print("[ffmpeg] Staging media to local cache...", flush=True)
            shutil.copy2(path, staged)
        return staged
    return path


def _build_video_input_opts() -> list[str]:
    return [
        "-hwaccel", "auto",
        "-thread_queue_size", "512",
        "-ignore_editlist", "1",
        "-fflags", "+genpts+igndts",
        "-probesize", "32k",
        "-analyzeduration", "0",
        "-fpsprobesize", "0",
        "-sn",
        "-dn",
    ]


def _build_base_cmd(vf: str, use_dur: float, fps: int) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-fflags", "+genpts",
        "-t", str(use_dur),
        "-r", str(int(fps)),
        "-fps_mode", "cfr",
        "-filter_complex_threads", "2",
        "-filter_complex", f"{vf}[v]",
        "-map", "[v]",
        "-pix_fmt", "yuv420p",
    ]


def _write_concat_list(paths: list[Path], list_path: Path) -> None:
    list_path.write_text("\n".join([f"file '{p.as_posix()}'" for p in paths]), encoding="utf-8")


def _build_audio_extract_cmd(staged_path: Path, use_dur: float, out_audio: Path) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-i", str(staged_path),
        "-t", str(use_dur),
        "-vn",
        "-map", "0:a:0",
        "-ac", "2",
        "-ar", "44100",
        "-af", "aresample=async=1:first_pts=0",
        "-c:a", "pcm_s16le",
        str(out_audio),
    ]


def _build_silence_audio_cmd(use_dur: float, out_audio: Path) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-t", str(use_dur),
        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-ac", "2",
        "-ar", "44100",
        "-c:a", "pcm_s16le",
        str(out_audio),
    ]


def _ensure_raster_photo(path: Path, tmpdir: str, idx: int) -> Path:
    """Convert HEIC/HEIF to PNG for ffmpeg if needed."""
    ext = path.suffix.lower()
    if ext not in (".heic", ".heif"):
        return path
    try:
        from PIL import Image
        out_path = Path(tmpdir) / f"photo_{idx:04d}.png"
        if not out_path.exists():
            with Image.open(path) as img:
                img.save(out_path, format="PNG")
        return out_path
    except Exception:
        return path


def _build_audio_concat_cmd(audio_list_path: Path, audio_concat: Path) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(audio_list_path),
        "-ac", "2",
        "-ar", "44100",
        "-c:a", "pcm_s16le",
        str(audio_concat),
    ]


def _build_bgm_mix_cmd(
    concat_out: Path,
    audio_concat: Path,
    bgm_path: Path,
    total_dur: float,
    afilter: str,
    output_path: Path,
) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-i", str(concat_out),
        "-i", str(audio_concat),
        "-stream_loop", "-1",
        "-i", str(bgm_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-q:a", "8",
        "-map", "0:v:0",
        "-map", "[out_audio]",
        "-t", str(total_dur),
        "-filter_complex", afilter,
        "-movflags", "+faststart",
        "-fflags", "+genpts",
        str(output_path),
    ]


def _build_mux_cmd(concat_out: Path, audio_concat: Path, total_dur: float, output_path: Path) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-i", str(concat_out),
        "-i", str(audio_concat),
        "-c:v", "copy",
        "-c:a", "aac",
        "-q:a", "8",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", str(total_dur),
        "-movflags", "+faststart",
        "-fflags", "+genpts",
        str(output_path),
    ]


def _get_ffmpeg_encoder_args(codec: Optional[str]) -> list[str]:
    """Get ffmpeg encoder-specific arguments based on codec type.
    
    Returns list of command-line arguments for the encoder.
    """
    if not codec:
        codec = "libx264"
    
    args = ["-c:v", codec]
    
    if "nvenc" in codec:
        # NVIDIA NVENC optimized settings
        args.extend(["-preset", "fast"])  # fast, medium, slow
        args.extend(["-rc", "vbr"])  # variable bitrate
        args.extend(["-cq", "23"])  # quality 0-51 (lower=better, 23=default)
    elif "qsv" in codec:
        # Intel QuickSync Video settings
        args.extend(["-preset", "fast"])  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, placebo
    elif "amf" in codec:
        # AMD VCE settings
        args.extend(["-quality", "balanced"])  # balanced, speed, quality
        args.extend(["-rc", "vbr"])
    elif "videotoolbox" in codec:
        # Apple VideoToolbox settings
        args.extend(["-b:v", "2000k"])  # bitrate
    elif codec == "libx264":
        # CPU-based x264 with fast preset
        preset = _get_ffmpeg_encoding_preset()
        args.extend(["-preset", preset])
        crf = _get_ffmpeg_crf()
        args.extend(["-crf", str(crf)])
    
    return args


def render_timeline(
    plans: list,
    output_path: Path,
    fps: int = 30,
    bgm_path: Optional[Path] = None,
    fade_in: float = 0.5,
    fade_out: float = 0.5,
    transition: float = 0.3,
    fade_max_ratio: float = 1.0,
    bg_blur: float = 6.0,
    bgm_volume: float = 60.0,
    preserve_videos: bool = False,
    resolution: tuple[int, int] | None = None,
) -> None:
    """Render a sequence of ClipPlans into a single MP4 file by concatenation.

    Plans should be an iterable of objects with (path, kind, duration) attributes.

    Parameters:
    - bg_blur: blur radius applied to the BACKGROUND layer for PHOTO clips only.
      Set to 0 to disable blur. Default preserves previous behavior (6).
    - bgm_volume: BGM volume as percentage (0-200), where 100 is equal to video audio.
      Default is 60 (60% of video audio level).

    preserve_videos: when True, use the original video file's duration for video clips
    instead of restricting them to the planned duration. Defaults to False.
    """
    if not plans:
        raise ValueError("plans must be non-empty")

    # Prefer ffmpeg filter path for performance
    if _ffmpeg_available():
        try:
            return _render_timeline_ffmpeg(
                plans,
                output_path,
                fps=fps,
                bgm_path=bgm_path,
                fade_in=fade_in,
                fade_out=fade_out,
                transition=transition,
                fade_max_ratio=fade_max_ratio,
                bg_blur=bg_blur,
                bgm_volume=bgm_volume,
                preserve_videos=preserve_videos,
                resolution=resolution,
            )
        except Exception as exc:
            print(f"[ffmpeg] render failed: {exc}", flush=True)
            raise

    # Prefer the convenient editor import
    try:
        from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip
    except Exception:
        # Fallback imports for different MoviePy structures
        from moviepy.video.VideoClip import ImageClip  # type: ignore
        from moviepy.video.io.VideoFileClip import VideoFileClip  # type: ignore
        from moviepy.video.compositing.concatenate import concatenate_videoclips  # type: ignore
        from moviepy.audio.io.AudioFileClip import AudioFileClip  # type: ignore

    # Determine target resolution
    # Default when not specified: 1280x720 (matches tests)
    default_W, default_H = 1280, 720
    if resolution is not None:
        try:
            target_W, target_H = int(resolution[0]), int(resolution[1])
        except Exception:
            target_W, target_H = default_W, default_H
    else:
        # If preserve_videos is requested without explicit resolution, derive canvas from videos
        if preserve_videos:
            max_w, max_h = 0, 0
            for p in plans:
                if getattr(p, "kind", None) == "video":
                    path = Path(p.path)
                    if path.exists() and path.is_file():
                        try:
                            vf_probe = VideoFileClip(str(path))
                            try:
                                vw, vh = vf_probe.size
                                if not vw or not vh:
                                    raise Exception("invalid size")
                            except Exception:
                                try:
                                    f = vf_probe.get_frame(0)
                                    vh, vw = f.shape[0], f.shape[1]
                                except Exception:
                                    vw, vh = 0, 0
                        except Exception:
                            vw, vh = 0, 0
                        finally:
                            try:
                                _close_clip_safe(vf_probe)
                            except Exception:
                                pass
                        max_w = max(max_w, int(vw or 0))
                        max_h = max(max_h, int(vh or 0))
            if max_w > 0 and max_h > 0:
                target_W, target_H = max_w, max_h
            else:
                target_W, target_H = default_W, default_H
        else:
            target_W, target_H = default_W, default_H

    # Optional video fx/crop function placeholders (defensive)
    video_fadein_func = None
    video_fadeout_func = None
    video_crop_func = None

    # Audio fx initializations (similar to render_single_photo)
    audio_loop = None
    audio_fadein = None
    audio_fadeout = None
    AudioLoopClass = None
    AudioFadeInClass = None
    AudioFadeOutClass = None
    try:
        import moviepy.audio.fx.all as afx
        audio_loop = getattr(afx, "audio_loop", None)
        audio_fadein = getattr(afx, "audio_fadein", None)
        audio_fadeout = getattr(afx, "audio_fadeout", None)
    except Exception:
        try:
            from moviepy.audio.fx.AudioLoop import AudioLoop as AudioLoopClass
        except Exception:
            AudioLoopClass = None
        try:
            from moviepy.audio.fx.AudioFadeIn import AudioFadeIn as AudioFadeInClass
        except Exception:
            AudioFadeInClass = None
        try:
            from moviepy.audio.fx.AudioFadeOut import AudioFadeOut as AudioFadeOutClass
        except Exception:
            AudioFadeOutClass = None

    # Minimal photo composition helper: blurred background + centered foreground
    def compose_photo_fill_frame(imgclip, W: int, H: int, blur_radius: int = 0):
        try:
            sw, sh = imgclip.size
            if not sw or not sh:
                raise Exception("invalid size")
        except Exception:
            try:
                frame = imgclip.get_frame(0)
                sh, sw = frame.shape[0], frame.shape[1]
            except Exception:
                sw, sh = (W, H)

        # Build blurred background via PIL if possible
        bg = None
        try:
            from PIL import Image, ImageFilter
            import numpy as np
            pil_img = None
            try:
                if hasattr(imgclip, 'filename') and getattr(imgclip, 'filename', None):
                    pil_img = Image.open(imgclip.filename).convert("RGB")
                else:
                    arr = imgclip.get_frame(0)
                    pil_img = Image.fromarray(arr)
            except Exception:
                pil_img = None
            if pil_img is not None:
                scale = max(W / pil_img.width, H / pil_img.height)
                newsize = (int(pil_img.width * scale), int(pil_img.height * scale))
                pil_img = pil_img.resize(newsize, Image.LANCZOS)
                if blur_radius and blur_radius > 0:
                    pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=int(blur_radius)))
                left = max(0, (pil_img.width - W) // 2)
                top = max(0, (pil_img.height - H) // 2)
                pil_img = pil_img.crop((left, top, left + W, top + H))
                bg = ImageClip(np.array(pil_img))
        except Exception:
            bg = None

        try:
            if bg is None:
                # Fallback: scale original to cover
                cover_scale = max(W / sw, H / sh)
                bg = imgclip.resize(cover_scale)
        except Exception:
            bg = imgclip

        try:
            bg = bg.set_duration(imgclip.duration)
        except Exception:
            pass

        # Foreground: contain scale (avoid upscale for portrait)
        try:
            contain = min(W / sw, H / sh)
            if sh > sw and contain > 1:
                fg = imgclip
            else:
                fg = imgclip.resize(contain)
        except Exception:
            fg = imgclip

        try:
            fg = fg.set_position(("center", "center"))
        except Exception:
            try:
                fg = fg.set_position("center")
            except Exception:
                pass

        try:
            fg = fg.set_duration(imgclip.duration)
        except Exception:
            pass

        try:
            comp = CompositeVideoClip([bg.set_position((0, 0)), fg], size=(W, H))
        except Exception:
            try:
                comp = CompositeVideoClip([bg, fg.set_position(("center", "center"))], size=(W, H))
            except Exception:
                comp = CompositeVideoClip([bg, fg])

        try:
            comp = comp.set_duration(imgclip.duration)
        except Exception:
            pass

        return comp

    # Minimal video composition helper: blurred background + centered foreground (contain)
    def compose_video_fill_frame(vclip, W: int, H: int, blur_radius: int = 0):
        try:
            sw, sh = vclip.size
            if not sw or not sh:
                raise Exception("invalid size")
        except Exception:
            try:
                frame = vclip.get_frame(0)
                sh, sw = frame.shape[0], frame.shape[1]
            except Exception:
                sw, sh = (W, H)

        # Build blurred background via first frame
        bg = None
        try:
            from PIL import Image, ImageFilter
            import numpy as np
            arr = None
            try:
                arr = vclip.get_frame(0)
            except Exception:
                arr = None
            if arr is not None:
                pil_img = Image.fromarray(arr)
                scale = max(W / pil_img.width, H / pil_img.height)
                newsize = (int(pil_img.width * scale), int(pil_img.height * scale))
                pil_img = pil_img.resize(newsize, Image.LANCZOS)
                if blur_radius and blur_radius > 0:
                    pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=int(blur_radius)))
                left = max(0, (pil_img.width - W) // 2)
                top = max(0, (pil_img.height - H) // 2)
                pil_img = pil_img.crop((left, top, left + W, top + H))
                bg = ImageClip(np.array(pil_img))
        except Exception:
            bg = None

        try:
            if bg is None:
                cover_scale = max(W / sw, H / sh)
                bg = vclip.resize(cover_scale)
        except Exception:
            bg = vclip

        try:
            bg = bg.set_duration(vclip.duration)
        except Exception:
            pass

        # Foreground: contain scale, keep full content visible; avoid upscaling
        try:
            contain = min(W / sw, H / sh)
            if contain > 1:
                fg = vclip
            else:
                fg = vclip.resize(contain)
        except Exception:
            fg = vclip

        try:
            fg = fg.set_position(("center", "center"))
        except Exception:
            try:
                fg = fg.set_position("center")
            except Exception:
                pass

        try:
            fg = fg.set_duration(vclip.duration)
        except Exception:
            pass

        try:
            comp = CompositeVideoClip([bg.set_position((0, 0)), fg], size=(W, H))
        except Exception:
            try:
                comp = CompositeVideoClip([bg, fg.set_position(("center", "center"))], size=(W, H))
            except Exception:
                comp = CompositeVideoClip([bg, fg])

        try:
            comp = comp.set_duration(vclip.duration)
        except Exception:
            pass

        return comp

    def normalize_video_to_frame(vclip, W: int, H: int, preserve_native: bool = False):
        """For VIDEOS: ensure the clip fills W x H using cover-scaling and center-cropping.

        If `preserve_native` is True, do not resize the video: center it on a
        canvas of size (W, H) so the video's frames remain unchanged.
        """
        if preserve_native:
            try:
                comp = CompositeVideoClip([vclip.set_position(("center", "center"))], size=(W, H))
                try:
                    comp = comp.set_duration(vclip.duration)
                except Exception:
                    pass
                return comp
            except Exception:
                return vclip

        # Try to get source size; if not available, try to read a frame
        try:
            sw, sh = vclip.size
            if not sw or not sh:
                raise Exception("invalid size")
        except Exception:
            try:
                frame = vclip.get_frame(0)
                sh, sw = frame.shape[0], frame.shape[1]
            except Exception:
                sw, sh = (W, H)

        # Compute scale to cover the target frame
        try:
            scale = max(W / sw, H / sh)
        except Exception:
            scale = 1.0

        r = vclip
        # Prefer scaling by factor when supported
        try:
            r = vclip.resize(scale)
        except Exception:
            try:
                r = vclip.resize((W, H))
            except Exception:
                # Fall back to original clip if resizing fails
                r = vclip

        # Center-crop to exact size if possible
        try:
            if hasattr(r, "crop"):
                try:
                    r = r.crop(width=W, height=H, x_center=r.w / 2, y_center=r.h / 2)
                except Exception:
                    r = r.crop(width=W, height=H)
            elif video_crop_func is not None:
                try:
                    r = video_crop_func(r, width=W, height=H, x_center=r.w / 2, y_center=r.h / 2)
                except Exception:
                    x1 = max(0, (r.w - W) / 2)
                    y1 = max(0, (r.h - H) / 2)
                    x2 = x1 + W
                    y2 = y1 + H
                    r = video_crop_func(r, x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2))
            else:
                r = r.resize((W, H))
        except Exception:
            try:
                r = r.resize((W, H))
            except Exception:
                pass

        try:
            r = r.set_duration(vclip.duration)
        except Exception:
            pass

        # Wrap in a CompositeVideoClip sized to the target frame to guarantee output
        try:
            comp = CompositeVideoClip([r.set_position(("center", "center"))], size=(W, H))
            try:
                comp = comp.set_duration(r.duration)
            except Exception:
                pass
            return comp
        except Exception:
            return r

    clips = []
    try:
        for p in plans:
            path = Path(p.path)
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(f"Clip not found: {path}")
            dur = float(p.duration)
            if p.kind == "photo":
                c = ImageClip(str(path))
                try:
                    c = c.with_duration(dur)
                except Exception:
                    c.duration = dur

                # Compose photo with blurred background and centered foreground
                filled = compose_photo_fill_frame(c, target_W, target_H, blur_radius=int(bg_blur) if bg_blur is not None else 0)

                # apply transition fades per-clip to composed clip
                if transition and transition > 0:
                    t = min(float(transition), float(filled.duration) / 2.0)
                    if t > 0:
                        applied = False
                        if video_fadein_func is not None:
                            try:
                                filled = video_fadein_func(filled, t)
                                applied = True
                            except Exception:
                                applied = False
                        if not applied and hasattr(filled, "fadein"):
                            try:
                                filled = filled.fadein(t)
                            except Exception:
                                pass
                        applied = False
                        if video_fadeout_func is not None:
                            try:
                                filled = video_fadeout_func(filled, t)
                                applied = True
                            except Exception:
                                applied = False
                        if not applied and hasattr(filled, "fadeout"):
                            try:
                                filled = filled.fadeout(t)
                            except Exception:
                                pass
                clips.append(filled)
            else:
                # video: fill the frame by cover-scaling and center-cropping (no blurred background)
                vf = VideoFileClip(str(path))
                try:
                    # Source duration may be None or 0; be defensive
                    src_dur = getattr(vf, "duration", None)
                    if preserve_videos and src_dur and float(src_dur) > 0:
                        use_dur = float(src_dur)
                    else:
                        use_dur = float(dur)
                        if src_dur and float(src_dur) > 0:
                            use_dur = min(float(src_dur), use_dur)

                    # Trim or set duration
                    try:
                        sub = vf.subclip(0, float(use_dur))
                    except Exception:
                        vf.duration = float(use_dur)
                        sub = vf

                    # Decide composition based on canvas and source orientation
                    # - If canvas is portrait OR source video is portrait: use photo-like contain + blurred background.
                    # - Otherwise (landscape canvas with landscape source): cover scale + center crop.
                    try:
                        sw, sh = sub.size
                        if not sw or not sh:
                            raise Exception("invalid size")
                    except Exception:
                        try:
                            frame0 = sub.get_frame(0)
                            sh, sw = frame0.shape[0], frame0.shape[1]
                        except Exception:
                            sw, sh = target_W, target_H

                    is_source_portrait = (sh > sw)
                    if target_H > target_W or is_source_portrait:
                        filled = compose_video_fill_frame(
                            sub,
                            target_W,
                            target_H,
                            blur_radius=int(bg_blur) if bg_blur is not None else 0,
                        )
                    else:
                        filled = normalize_video_to_frame(sub, target_W, target_H, preserve_native=False)

                    # apply transition fades per-clip to composed clip
                    if transition and transition > 0:
                        t = min(float(transition), float(filled.duration) / 2.0)
                        if t > 0:
                            applied = False
                            if video_fadein_func is not None:
                                try:
                                    filled = video_fadein_func(filled, t)
                                    applied = True
                                except Exception:
                                    applied = False
                            if not applied and hasattr(filled, "fadein"):
                                try:
                                    filled = filled.fadein(t)
                                except Exception:
                                    pass
                            applied = False
                            if video_fadeout_func is not None:
                                try:
                                    filled = video_fadeout_func(filled, t)
                                    applied = True
                                except Exception:
                                    applied = False
                            if not applied and hasattr(filled, "fadeout"):
                                try:
                                    filled = filled.fadeout(t)
                                except Exception:
                                    pass

                    clips.append(filled)
                except Exception:
                    # ensure we close vf on error to avoid leaks
                    _close_clip_safe(vf)
                    raise

        final = concatenate_videoclips(clips, method="compose")

        audio_clip = None
        if bgm_path is not None:
            audio = AudioFileClip(str(bgm_path))
            total_dur = final.duration
            if audio.duration < total_dur:
                if audio_loop is not None:
                    audio = audio_loop(audio, duration=total_dur)
                elif AudioLoopClass is not None:
                    audio = audio.with_effects([AudioLoopClass(duration=total_dur)])
                else:
                    n = int(total_dur / audio.duration) + 1
                    new_audio = audio
                    for _ in range(n - 1):
                        new_audio = new_audio + audio
                    audio = new_audio.subclip(0, float(total_dur))
            else:
                audio = audio.subclip(0, float(total_dur))

            max_fade = float(total_dur) / 2.0
            fi = min(float(fade_in), max_fade)
            fo = min(float(fade_out), max_fade)

            if fi > 0:
                if audio_fadein is not None:
                    audio = audio_fadein(audio, fi)
                elif AudioFadeInClass is not None:
                    audio = audio.with_effects([AudioFadeInClass(fi)])
            if fo > 0:
                if audio_fadeout is not None:
                    audio = audio_fadeout(audio, fo)
                elif AudioFadeOutClass is not None:
                    audio = audio.with_effects([AudioFadeOutClass(fo)])

            audio_clip = audio
            # set audio
            try:
                final = final.set_audio(audio_clip)
            except Exception:
                final.audio = audio_clip
        else:
            # No bgm requested: ensure final has no audio to avoid mixing original clip audio
            try:
                final = final.without_audio()
            except Exception:
                final.audio = None

        # Ensure output dir exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        codec = _select_video_encoder()
        write_kwargs = dict(fps=int(fps), codec=codec or "libx264", ffmpeg_params=_compat_ffmpeg_params())
        if audio_clip is not None:
            write_kwargs.update(dict(audio=True, audio_codec="aac"))
        else:
            write_kwargs.update(dict(audio=False))

        _write_videofile_with_fallback(final, output_path, write_kwargs)
    finally:
        # Close clips to avoid file locks
        for c in clips:
            _close_clip_safe(c)
        try:
            _close_clip_safe(final)
        except Exception:
            pass


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run_ffmpeg(cmd: list[str], progress_total_sec: float | None = None, progress_label: str | None = None) -> None:
    if progress_total_sec and progress_total_sec > 0:
        progress_cmd = cmd[:1] + ["-progress", "pipe:1", "-nostats"] + cmd[1:]
        proc = subprocess.Popen(progress_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        last_pct = -1
        last_output = time.time()
        start_time = time.time()
        q: queue.Queue[str] = queue.Queue()
        err_tail: deque[str] = deque(maxlen=200)

        def _reader():
            if not proc.stdout:
                return
            for line in proc.stdout:
                q.put(line)

        def _err_reader():
            if not proc.stderr:
                return
            for line in proc.stderr:
                err_tail.append(line)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        te = threading.Thread(target=_err_reader, daemon=True)
        te.start()
        try:
            while True:
                if proc.poll() is not None and q.empty():
                    break
                try:
                    line = q.get(timeout=0.5)
                except queue.Empty:
                    if time.time() - last_output >= 5:
                        prefix = f"[{progress_label}] " if progress_label else ""
                        elapsed = time.time() - start_time
                        print(f"{prefix}working... {elapsed:.1f}s", flush=True)
                        last_output = time.time()
                    continue

                line = line.strip()
                last_output = time.time()
                if line.startswith("out_time_ms="):
                    try:
                        out_ms = int(line.split("=", 1)[1])
                        pct = int(min(100, (out_ms / 1_000_000) / progress_total_sec * 100))
                        if pct != last_pct:
                            prefix = f"[{progress_label}] " if progress_label else ""
                            print(f"{prefix}progress: {pct}%", flush=True)
                            last_pct = pct
                    except Exception:
                        pass
        finally:
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                tail = "".join(err_tail)
                raise RuntimeError(f"ffmpeg failed: stdout={stdout!r}\nstderr_tail={tail!r}")
        return

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: stdout={proc.stdout!r}\nstderr={proc.stderr!r}")


def _ffprobe_size(path: Path) -> tuple[int, int] | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        w_s, h_s = proc.stdout.strip().split("x")
        return int(w_s), int(h_s)
    except Exception:
        return None


def _ffprobe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        return float(proc.stdout.strip())
    except Exception:
        return None




def _ffmpeg_filter_cover(W: int, H: int) -> str:
    return f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=fast_bilinear,crop={W}:{H}"


def _ffmpeg_filter_contain(W: int, H: int) -> str:
    return f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=fast_bilinear"


def _ffmpeg_filter_compose_with_blur(W: int, H: int, blur: int, no_upscale: bool = False) -> str:
    bg = _ffmpeg_filter_cover(W, H)
    if blur > 0:
        # Downscale before blur for speed, then scale back up
        bg = f"{bg},scale=iw*0.25:ih*0.25:flags=fast_bilinear,boxblur={blur}:1,scale={W}:{H}:flags=fast_bilinear"
    if no_upscale:
        fg = (
            f"scale=w='if(gt(iw\\,{W})\\,{W}\\,iw)':"
            f"h='if(gt(ih\\,{H})\\,{H}\\,ih)':"
            "force_original_aspect_ratio=decrease"
        )
    else:
        fg = _ffmpeg_filter_contain(W, H)
    return (
        f"[0:v]split=2[fgsrc][bgsrc];"
        f"[bgsrc]{bg}[bg];"
        f"[fgsrc]{fg}[fg];"
        f"[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2"
    )


def _ffmpeg_filter_with_fades(
    base: str,
    duration: float,
    transition: float,
    fade_max_ratio: float = 1.0,
    fade_in: bool = True,
    fade_out: bool = True,
) -> str:
    if transition and transition > 0 and duration > 0 and (fade_in or fade_out):
        cap = float(duration) * max(0.0, float(fade_max_ratio))
        t = min(float(transition), cap) if cap > 0 else float(transition)
        if t >= 0.01:
            parts = [base]
            if fade_in:
                parts.append(f"fade=t=in:st=0:d={t}")
            if fade_out:
                out_start = max(0.0, float(duration) - t)
                parts.append(f"fade=t=out:st={out_start}:d={t}")
            return ",".join(parts)
    return base


def _render_timeline_ffmpeg(
    plans: list,
    output_path: Path,
    fps: int = 30,
    bgm_path: Optional[Path] = None,
    fade_in: float = 0.5,
    fade_out: float = 0.5,
    transition: float = 0.3,
    fade_max_ratio: float = 1.0,
    bg_blur: float = 6.0,
    bgm_volume: float = 60.0,
    preserve_videos: bool = False,
    resolution: tuple[int, int] | None = None,
) -> None:
    # Determine target resolution (mirror MoviePy path behavior)
    default_W, default_H = 1280, 720
    if resolution is not None:
        try:
            target_W, target_H = int(resolution[0]), int(resolution[1])
        except Exception:
            target_W, target_H = default_W, default_H
    else:
        if preserve_videos:
            max_w, max_h = 0, 0
            for p in plans:
                if getattr(p, "kind", None) == "video":
                    size = _ffprobe_size(Path(p.path))
                    if size:
                        vw, vh = size
                        max_w = max(max_w, int(vw or 0))
                        max_h = max(max_h, int(vh or 0))
            if max_w > 0 and max_h > 0:
                target_W, target_H = max_w, max_h
            else:
                target_W, target_H = default_W, default_H
        else:
            target_W, target_H = default_W, default_H

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_dur = 0.0
    codec = _select_video_encoder() or "libx264"
    filter_scale = _get_filter_scale()
    video_blur_enabled = os.environ.get("VIDEO_ENGINE_VIDEO_BLUR", "").strip() == "1"
    proc_W = max(16, int(target_W * filter_scale))
    proc_H = max(16, int(target_H * filter_scale))
    if proc_W % 2 == 1:
        proc_W -= 1
    if proc_H % 2 == 1:
        proc_H -= 1
    with tempfile.TemporaryDirectory(prefix="ve_ffmpeg_") as tmpdir:
        clip_paths: list[Path] = []
        audio_paths: list[Path] = []

        for idx, p in enumerate(plans):
            print(f"[ffmpeg] Rendering clip {idx + 1}/{len(plans)}: {Path(p.path).name}", flush=True)
            path = Path(p.path)
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(f"Clip not found: {path}")

            # Stage OneDrive media to local temp cache to avoid network/placeholder stalls
            staged_path = _stage_media_path(path, tmpdir, idx)

            dur = float(p.duration)
            use_dur = dur

            src_w = src_h = None
            if getattr(p, "kind", None) == "video":
                # Skip per-clip ffprobe to avoid stalls on large/vfr MOV files
                pass
            else:
                try:
                    from PIL import Image
                    with Image.open(staged_path) as img:
                        src_w, src_h = img.size
                except Exception:
                    src_w, src_h = None, None

            total_dur += float(use_dur)

            is_source_portrait = bool(src_w and src_h and src_h > src_w)
            use_blur = int(bg_blur) if bg_blur is not None else 0
            blur_eff = use_blur

            kind = getattr(p, "kind", None)
            use_video_blur = bool(kind == "video" and video_blur_enabled)

            # Use compose_with_blur only for photos or when explicitly enabled for videos
            # Otherwise use cover filter for faster processing
            if (kind == "photo" or use_video_blur or target_H > target_W or is_source_portrait) and blur_eff > 0 and (kind != "video" or use_video_blur):
                no_upscale = False
                if kind == "video":
                    no_upscale = True
                elif is_source_portrait:
                    no_upscale = True
                base_filter = _ffmpeg_filter_compose_with_blur(proc_W, proc_H, blur_eff, no_upscale=no_upscale)
            else:
                base_filter = _ffmpeg_filter_cover(proc_W, proc_H)

            # Apply fades only at transitions (skip fade-in for first, fade-out for last)
            apply_fade_in = idx > 0
            apply_fade_out = idx < (len(plans) - 1)
            vf = _ffmpeg_filter_with_fades(
                base_filter,
                use_dur,
                transition,
                fade_max_ratio=fade_max_ratio,
                fade_in=apply_fade_in,
                fade_out=apply_fade_out,
            )
            if (proc_W, proc_H) != (target_W, target_H):
                vf = f"{vf},scale={target_W}:{target_H}:flags=fast_bilinear"

            out_clip = Path(tmpdir) / f"clip_{idx:04d}.mp4"
            
            # Build base command (video-only for speed)
            base_cmd = _build_base_cmd(vf, use_dur, fps)
            base_cmd.insert(base_cmd.index("-pix_fmt"), "-an")
            
            # Add encoder-specific arguments
            encoder_args = _get_ffmpeg_encoder_args(codec)
            
            # Add codec-independent options if not using hardware encoding
            if codec and "nvenc" not in codec and "qsv" not in codec and "amf" not in codec and "videotoolbox" not in codec:
                base_cmd.extend(["-profile:v", "main", "-level", "4.1"])
            
            base_cmd.extend(["-movflags", "+faststart", str(out_clip)])

            # kind already resolved above
            if kind == "photo":
                raster_path = _ensure_raster_photo(staged_path, tmpdir, idx)
                if raster_path.suffix.lower() in (".heic", ".heif") and _ffmpeg_supports_heif():
                    photo_input = ["-loop", "1", "-framerate", str(int(fps)), "-i", str(raster_path)]
                else:
                    photo_input = ["-loop", "1", "-framerate", str(int(fps)), "-i", str(raster_path)]
                cmd = [
                    "ffmpeg", "-y",
                    *photo_input,
                ] + base_cmd[1:]
            else:
                video_input_opts = _build_video_input_opts()
                cmd = [
                    "ffmpeg", "-y",
                    *video_input_opts,
                    "-i", str(staged_path),
                ] + base_cmd[1:]

            # Insert encoder args before pixel format
            insert_pos = cmd.index("-pix_fmt")
            for arg in reversed(encoder_args):
                cmd.insert(insert_pos, arg)

            _run_ffmpeg(cmd, progress_total_sec=use_dur, progress_label=f"clip {idx + 1}/{len(plans)}")
            clip_paths.append(out_clip)
            # Extract audio separately
            out_audio = Path(tmpdir) / f"audio_{idx:04d}.wav"
            if kind == "video":
                audio_cmd = _build_audio_extract_cmd(staged_path, use_dur, out_audio)
            else:
                audio_cmd = _build_silence_audio_cmd(use_dur, out_audio)
            _run_ffmpeg(audio_cmd, progress_total_sec=use_dur, progress_label=f"audio {idx + 1}/{len(plans)}")
            audio_paths.append(out_audio)

        # Concatenate clips
        print("[ffmpeg] Concatenating clips...", flush=True)
        list_path = Path(tmpdir) / "concat.txt"
        _write_concat_list(clip_paths, list_path)

        concat_out = Path(tmpdir) / "concat.mp4"
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-protocol_whitelist", "file,pipe",
            "-i", str(list_path),
            "-c", "copy",
            "-max_muxing_queue_size", "1024",
            "-fflags", "+genpts",
            str(concat_out),
        ]
        _run_ffmpeg(concat_cmd, progress_total_sec=total_dur, progress_label="concat")

        # Concatenate audio clips
        audio_list_path = Path(tmpdir) / "audio_concat.txt"
        _write_concat_list(audio_paths, audio_list_path)
        audio_concat = Path(tmpdir) / "audio_concat.wav"
        audio_concat_cmd = _build_audio_concat_cmd(audio_list_path, audio_concat)
        _run_ffmpeg(audio_concat_cmd, progress_total_sec=total_dur, progress_label="audio-concat")

        # Add BGM if requested
        if bgm_path is not None and bgm_path.exists() and bgm_path.is_file():
            print("[ffmpeg] Mixing BGM...", flush=True)
            max_fade = float(total_dur) / 2.0 if total_dur > 0 else 0.0
            fi = min(float(fade_in), max_fade)
            fo = min(float(fade_out), max_fade)
            
            # Build audio filter with volume control
            # bgm_volume is a percentage (0-200), where 100 = equal to video audio
            bgm_vol_factor = max(0.0, float(bgm_volume) / 100.0)
            
            af_parts = []
            # Video audio channel at full volume
            af_parts.append("[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume=1.0[video_audio]")
            # BGM audio with configured volume
            af_parts.append(f"[2:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={bgm_vol_factor}[bgm_audio]")
            # Mix both audio tracks without normalization attenuation
            af_parts.append("[video_audio][bgm_audio]amix=inputs=2:duration=longest:normalize=0[mixed_audio]")
            
            # Apply fades to mixed audio
            if fi > 0:
                af_parts.append(f"[mixed_audio]afade=t=in:st=0:d={fi}[faded_in]")
                fade_output = "faded_in"
            else:
                fade_output = "mixed_audio"
            
            if fo > 0:
                out_start = max(0.0, float(total_dur) - fo)
                af_parts.append(f"[{fade_output}]afade=t=out:st={out_start}:d={fo}[faded_out]")
                fade_output = "faded_out"

            # Prevent clipping
            af_parts.append(f"[{fade_output}]alimiter=limit=0.95[out_audio]")

            afilter = ";".join(af_parts)
            final_audio = "[out_audio]"

            audio_cmd = _build_bgm_mix_cmd(
                concat_out,
                audio_concat,
                bgm_path,
                total_dur,
                afilter,
                output_path,
            )
            _run_ffmpeg(audio_cmd, progress_total_sec=total_dur, progress_label="bgm")
        else:
            print("[ffmpeg] Writing output...", flush=True)
            mux_cmd = _build_mux_cmd(concat_out, audio_concat, total_dur, output_path)
            _run_ffmpeg(mux_cmd, progress_total_sec=total_dur, progress_label="mux")

