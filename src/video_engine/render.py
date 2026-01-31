"""Minimal rendering utilities using MoviePy.

This module provides an MVP function to render a single photo to an MP4
video. The implementation is intentionally small and provides clear
error messages when dependencies are missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

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
    transition: float = 0.3,
    preserve_videos: bool = False,
) -> None:
    """Render a sequence of ClipPlans into a single MP4 file by concatenation.

    Plans should be an iterable of objects with (path, kind, duration) attributes.

    preserve_videos: when True, use the original video file's duration for video clips
    instead of restricting them to the planned duration. Defaults to False.
    """
    if not plans:
        raise ValueError("plans must be non-empty")

    try:
        # Prefer the convenient editor import
        try:
            from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip
        except Exception:
            # Fallback imports for different MoviePy structures
            from moviepy.video.VideoClip import ImageClip  # type: ignore
            from moviepy.video.io.VideoFileClip import VideoFileClip  # type: ignore
            from moviepy.video.compositing.concatenate import concatenate_videoclips  # type: ignore
            from moviepy.audio.io.AudioFileClip import AudioFileClip  # type: ignore
            try:
                from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip  # type: ignore
            except Exception:
                from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "moviepy is required for rendering; install the 'render' extras (e.g., pip install -e \".[render]\")"
        ) from exc

    # Reuse audio fx helpers (classes or functions)
    AudioLoopClass = None

    # Pillow compatibility: some Pillow versions removed Image.ANTIALIAS in favor of
    # Image.Resampling.*; attempt to provide a fallback name so MoviePy's resize
    # (which references Image.ANTIALIAS) continues to work across versions.
    try:
        import PIL.Image as PILImage

        if not hasattr(PILImage, "ANTIALIAS") and hasattr(PILImage, "Resampling"):
            PILImage.ANTIALIAS = PILImage.Resampling.LANCZOS
    except Exception:
        pass
    AudioFadeInClass = None
    AudioFadeOutClass = None
    audio_loop = None
    audio_fadein = None
    audio_fadeout = None
    # Video fade helpers
    video_fadein_func = None
    video_fadeout_func = None
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

    # Video fade and utility fallbacks
    try:
        import moviepy.video.fx.all as vfx
        video_fadein_func = getattr(vfx, "fadein", None)
        video_fadeout_func = getattr(vfx, "fadeout", None)
        video_crop_func = getattr(vfx, "crop", None)
        video_blur_func = getattr(vfx, "gaussian_blur", None) or getattr(vfx, "blur", None)
    except Exception:
        try:
            from moviepy.video.fx.fadein import fadein as video_fadein_func  # type: ignore
        except Exception:
            video_fadein_func = None
        try:
            from moviepy.video.fx.fadeout import fadeout as video_fadeout_func  # type: ignore
        except Exception:
            video_fadeout_func = None
        try:
            from moviepy.video.fx.crop import crop as video_crop_func  # type: ignore
        except Exception:
            video_crop_func = None
        try:
            from moviepy.video.fx.gaussian_blur import gaussian_blur as video_blur_func  # type: ignore
        except Exception:
            video_blur_func = None

    # Output size constants (width x height)
    OUT_W = 1280
    OUT_H = 720

    # Decide target frame size. If `preserve_videos` is True and there are
    # video clips present, use the maximum native video width/height as the
    # target canvas to avoid rescaling video frames. Otherwise fall back to
    # the default OUT_W/OUT_H.
    target_W = OUT_W
    target_H = OUT_H
    if preserve_videos:
        max_w = 0
        max_h = 0
        any_video = False
        for p in plans:
            if getattr(p, "kind", None) == "video":
                any_video = True
                try:
                    vf = VideoFileClip(str(p.path))
                    try:
                        sw, sh = getattr(vf, "size", (None, None))
                        if not sw or not sh:
                            frame = vf.get_frame(0)
                            sh, sw = frame.shape[0], frame.shape[1]
                    except Exception:
                        sw, sh = (0, 0)
                except Exception:
                    sw, sh = (0, 0)
                finally:
                    try:
                        _close_clip_safe(vf)
                    except Exception:
                        pass

                if sw and sh:
                    max_w = max(max_w, int(sw))
                    max_h = max(max_h, int(sh))

        if any_video and max_w > 0 and max_h > 0:
            target_W, target_H = max_w, max_h

    def ensure_frame_size(clip, W: int, H: int):
        """Ensure a clip is exactly W x H by cover-scaling and center-cropping (best-effort).
        Preserves duration."""
        try:
            sw, sh = clip.size
        except Exception:
            sw, sh = (W, H)

        # Cover scale
        try:
            scale = max(W / sw, H / sh)
            r = clip.resize(scale)
        except Exception:
            try:
                r = clip.resize((W, H))
            except Exception:
                r = clip

        # Center-crop if possible
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
            r = r.set_duration(clip.duration)
        except Exception:
            pass

        return r

    def compose_photo_fill_frame(imgclip, W: int, H: int, blur_radius: int = 6):
        """For PHOTOS: background cover-scaled (optional blur), foreground contain-scaled centered.

        For portrait images (height > width) we avoid upscaling the foreground: the
        background is cover-scaled and blurred, while the foreground is placed at
        its original size (or scaled down if larger than the canvas). The blur
        radius is increased slightly for portrait photos to emphasize the depth effect.
        """
        try:
            sw, sh = imgclip.size
        except Exception:
            sw, sh = (W, H)

        # Background: cover-scale to fill canvas
        bg = ensure_frame_size(imgclip, W, H)

        # For portrait images, increase blur radius a bit for better separation
        br = blur_radius * 2 if sh > sw else blur_radius

        # Blur background if available
        if video_blur_func is not None:
            try:
                try:
                    bg = video_blur_func(bg, br)
                except TypeError:
                    bg = bg.fx(video_blur_func, br)
            except Exception:
                pass

        # Foreground: contain scale but do not upscale for portrait images
        try:
            contain_scale = min(W / sw, H / sh)
            if sh > sw and contain_scale > 1:
                # Portrait and would be upscaled: keep original size (no upscale)
                fg = imgclip
            else:
                # Scale down or keep same size
                fg = imgclip.resize(contain_scale)
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
            # Debug: if a tmp_debug folder exists, write intermediate frames for diagnosis
            try:
                from pathlib import Path

                dbg = Path("tmp_debug")
                if dbg.exists():
                    try:
                        bg.save_frame(str(dbg / "dbg_bg.png"), t=0)
                    except Exception:
                        pass
                    try:
                        fg.save_frame(str(dbg / "dbg_fg.png"), t=0)
                    except Exception:
                        pass
            except Exception:
                pass

            comp = CompositeVideoClip([bg.set_position((0, 0)), fg], size=(W, H))
            # Debug: save composed frame if requested
            try:
                from pathlib import Path

                dbg = Path("tmp_debug")
                if dbg.exists():
                    try:
                        comp.save_frame(str(dbg / "dbg_comp.png"), t=0)
                    except Exception:
                        pass
            except Exception:
                pass
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
                filled = compose_photo_fill_frame(c, target_W, target_H)

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
                # video
                vf = VideoFileClip(str(path))
                try:
                    # Source duration may be None or 0; be defensive
                    src_dur = getattr(vf, "duration", None)
                    # If preserve_videos is True and the source has a duration, prefer it.
                    if preserve_videos and src_dur and float(src_dur) > 0:
                        use_dur = float(src_dur)
                    else:
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

                    # Normalize video to frame (no background/foreground overlay)
                    sub = normalize_video_to_frame(sub, target_W, target_H, preserve_native=preserve_videos)

                    # apply transition fades per-clip to normalized video
                    if transition and transition > 0:
                        t = min(float(transition), float(sub.duration) / 2.0)
                        if t > 0:
                            applied = False
                            if video_fadein_func is not None:
                                try:
                                    sub = video_fadein_func(sub, t)
                                    applied = True
                                except Exception:
                                    applied = False
                            if not applied and hasattr(sub, "fadein"):
                                try:
                                    sub = sub.fadein(t)
                                except Exception:
                                    pass
                            applied = False
                            if video_fadeout_func is not None:
                                try:
                                    sub = video_fadeout_func(sub, t)
                                    applied = True
                                except Exception:
                                    applied = False
                            if not applied and hasattr(sub, "fadeout"):
                                try:
                                    sub = sub.fadeout(t)
                                except Exception:
                                    pass

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

