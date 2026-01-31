"""Minimal rendering utilities using MoviePy.

This module provides an MVP function to render a single photo to an MP4
video. The implementation is intentionally small and provides clear
error messages when dependencies are missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


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
        write_kwargs = dict(fps=int(fps), codec="libx264")
        if audio_clip is not None:
            write_kwargs.update(dict(audio=True, audio_codec="aac"))
        else:
            write_kwargs.update(dict(audio=False))

        # Some MoviePy versions have different write_videofile signatures; call with minimal kwargs.
        clip.write_videofile(str(output_path), **write_kwargs)
    except Exception as exc:  # pragma: no cover - depends on runtime ffmpeg
        raise RuntimeError(f"Failed to render video: {exc}") from exc


def _close_clip_safe(c):
    try:
        c.close()
    except Exception:
        pass


def render_timeline(
    plans: list,
    output_path: Path,
    fps: int = 30,
    bgm_path: Optional[Path] = None,
    fade_in: float = 0.5,
    fade_out: float = 0.5,
) -> None:
    """Render a sequence of ClipPlans into a single MP4 file by concatenation.

    Plans should be an iterable of objects with (path, kind, duration) attributes.
    """
    if not plans:
        raise ValueError("plans must be non-empty")

    try:
        # Prefer the convenient editor import
        try:
            from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip
        except Exception:
            # Fallback imports for different MoviePy structures
            from moviepy.video.VideoClip import ImageClip  # type: ignore
            from moviepy.video.io.VideoFileClip import VideoFileClip  # type: ignore
            from moviepy.video.compositing.concatenate import concatenate_videoclips  # type: ignore
            from moviepy.audio.io.AudioFileClip import AudioFileClip  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "moviepy is required for rendering; install the 'render' extras (e.g., pip install -e \".[render]\")"
        ) from exc

    # Reuse audio fx helpers (classes or functions)
    AudioLoopClass = None
    AudioFadeInClass = None
    AudioFadeOutClass = None
    audio_loop = None
    audio_fadein = None
    audio_fadeout = None
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
                clips.append(c)
            else:
                # video
                vf = VideoFileClip(str(path))
                try:
                    # Source duration may be None or 0; be defensive
                    src_dur = getattr(vf, "duration", None)
                    use_dur = float(dur)
                    if src_dur and float(src_dur) > 0:
                        use_dur = min(float(src_dur), use_dur)

                    # Trim to available duration. If source is shorter than target, we keep the short clip
                    try:
                        sub = vf.subclip(0, float(use_dur))
                    except Exception:
                        # fallback to setting duration attribute and use vf
                        vf.duration = float(use_dur)
                        sub = vf

                    clips.append(sub)
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

        write_kwargs = dict(fps=int(fps), codec="libx264")
        if audio_clip is not None:
            write_kwargs.update(dict(audio=True, audio_codec="aac"))
        else:
            write_kwargs.update(dict(audio=False))

        final.write_videofile(str(output_path), **write_kwargs)
    finally:
        # Close clips to avoid file locks
        for c in clips:
            _close_clip_safe(c)
        try:
            _close_clip_safe(final)
        except Exception:
            pass

