"""Image motion filter generation."""

from __future__ import annotations

from config import RenderConfig
from models import CropType, MotionType, Scene, Shot


class MotionFilterFactory:
    """Build FFmpeg video filters for image motion."""

    def build(self, scene: Scene, config: RenderConfig) -> str:
        """Return a video filter chain for an image scene."""

        width = config.width
        height = config.height
        fps = config.fps
        duration = scene.duration or 1
        frames = max(1, int(round(duration * fps)))
        speed = self._resolve_speed(scene.motion_speed, config.motion_speed)

        if scene.motion is MotionType.STATIC:
            return (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1,format=yuv420p"
            )

        z_expr, x_expr, y_expr = self._expressions(scene.motion, speed, frames)
        pre_scale = f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,crop={width * 2}:{height * 2}"
        return (
            f"{pre_scale},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height}:fps={fps},"
            "setsar=1,format=yuv420p"
        )

    def build_for_shot(self, shot: Shot, config: RenderConfig) -> str:
        """Return a video filter chain for a V2 manifest shot."""

        width = config.width
        height = config.height
        fps = config.fps
        frames = max(1, int(round(shot.duration * fps)))
        speed = self._resolve_speed(shot.motion_speed, config.motion_speed)

        if shot.keyframes:
            base = self._keyframe_filter(shot, config, frames)
            return self._with_effects(base, shot)

        if shot.motion is MotionType.STATIC:
            base = (
                f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
                f"crop={width * 2}:{height * 2},"
                f"{self._crop_filter(shot)},"
                f"scale={width}:{height},setsar=1,format=yuv420p"
            )
            return self._with_effects(base, shot)

        z_expr, x_expr, y_expr = self._shot_expressions(shot, speed, frames)
        pre_scale = f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,crop={width * 2}:{height * 2}"
        base = (
            f"{pre_scale},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height}:fps={fps},"
            "setsar=1,format=yuv420p"
        )
        return self._with_effects(base, shot)

    @staticmethod
    def _keyframe_filter(shot: Shot, config: RenderConfig, frames: int) -> str:
        keys = sorted(shot.keyframes, key=lambda item: item.time)
        if len(keys) == 1:
            keys = [keys[0], type(keys[0])(time=shot.duration, scale=keys[0].scale, x=keys[0].x, y=keys[0].y, rotation=keys[0].rotation)]
        fps = config.fps

        def expression(attribute: str) -> str:
            fallback = str(getattr(keys[-1], attribute))
            result = fallback
            for left, right in reversed(list(zip(keys, keys[1:]))):
                start = round(left.time * fps)
                end = max(start + 1, round(right.time * fps))
                a, b = getattr(left, attribute), getattr(right, attribute)
                value = f"{a}+({b}-{a})*(on-{start})/{end-start}"
                result = f"if(between(on,{start},{end}),{value},{result})"
            return result

        zoom = expression("scale")
        x = expression("x")
        y = expression("y")
        pre_scale = f"scale={config.width * 2}:{config.height * 2}:force_original_aspect_ratio=increase,crop={config.width * 2}:{config.height * 2}"
        chain = (
            f"{pre_scale},zoompan=z='{zoom}':"
            f"x='clip(iw*({x})-iw/zoom/2,0,iw-iw/zoom)':"
            f"y='clip(ih*({y})-ih/zoom/2,0,ih-ih/zoom)':"
            f"d={frames}:s={config.width}x{config.height}:fps={fps}"
        )
        if any(key.rotation for key in keys):
            rotation = expression("rotation")
            chain += f",rotate='({rotation})*PI/180':ow=iw:oh=ih:c=black"
        return chain + ",setsar=1,format=yuv420p"

    @staticmethod
    def _with_effects(base: str, shot: Shot) -> str:
        filters = [base]
        for effect in shot.effects:
            if not effect.enabled:
                continue
            enable = f"enable='between(t,{effect.start:g},{effect.end:g})'"
            amount = effect.intensity
            mapping = {
                "blur": f"boxblur=luma_radius={max(1, round(amount * 12))}:luma_power=1:{enable}",
                "brightness": f"eq=brightness={amount * 0.6:g}:{enable}",
                "contrast": f"eq=contrast={1 + amount:g}:{enable}",
                "saturation": f"eq=saturation={1 + amount * 2:g}:{enable}",
                "grayscale": f"hue=s=0:{enable}",
                "vignette": f"vignette=PI/{max(2, round(8 - amount * 5))}:{enable}",
                "flash": f"eq=brightness={amount:g}:{enable}",
                "shake": f"rotate='{amount * 0.02:g}*sin(40*t)':ow=iw:oh=ih:c=black:{enable}",
                "film_grain": f"noise=alls={round(amount * 35)}:allf=t+u:{enable}",
                "chromatic_aberration": f"rgbashift=rh={round(amount * 10)}:bh={-round(amount * 10)}:{enable}",
            }
            if effect.type in mapping:
                filters.append(mapping[effect.type])
        return ",".join(filters)

    @staticmethod
    def _resolve_speed(scene_speed: float | None, default_speed: float) -> float:
        if scene_speed is None:
            return default_speed
        if scene_speed >= 0.1:
            return default_speed * scene_speed
        return scene_speed

    @staticmethod
    def _expressions(motion: MotionType, speed: float, frames: int) -> tuple[str, str, str]:
        frame_span = max(1, frames - 1)
        center_x = "iw/2-(iw/zoom/2)"
        center_y = "ih/2-(ih/zoom/2)"
        progress = f"on/{frame_span}"

        if motion is MotionType.ZOOM_IN:
            return f"min(1+on*{speed},1.25)", center_x, center_y
        if motion is MotionType.ZOOM_OUT:
            return f"max(1.0,1.25-on*{speed})", center_x, center_y
        if motion is MotionType.PAN_LEFT:
            return "1.15", f"(iw-iw/zoom)*(1-{progress})", center_y
        if motion is MotionType.PAN_RIGHT:
            return "1.15", f"(iw-iw/zoom)*{progress}", center_y
        if motion is MotionType.PAN_UP:
            return "1.15", center_x, f"(ih-ih/zoom)*(1-{progress})"
        if motion is MotionType.PAN_DOWN:
            return "1.15", center_x, f"(ih-ih/zoom)*{progress}"
        if motion is MotionType.ZOOM_LEFT:
            return f"min(1+on*{speed},1.25)", f"(iw-iw/zoom)*(1-{progress})", center_y
        if motion is MotionType.ZOOM_RIGHT:
            return f"min(1+on*{speed},1.25)", f"(iw-iw/zoom)*{progress}", center_y
        if motion is MotionType.ZOOM_UP:
            return f"min(1+on*{speed},1.25)", center_x, f"(ih-ih/zoom)*(1-{progress})"
        if motion is MotionType.ZOOM_DOWN:
            return f"min(1+on*{speed},1.25)", center_x, f"(ih-ih/zoom)*{progress}"

        return "1.0", center_x, center_y

    @staticmethod
    def _crop_filter(shot: Shot) -> str:
        if shot.crop is CropType.MEDIUM:
            return "crop=iw*0.85:ih*0.85"
        if shot.crop is CropType.CLOSE:
            return "crop=iw*0.65:ih*0.65"
        if shot.crop is CropType.FOCAL and shot.focal_point is not None:
            x, y = shot.focal_point
            return (
                "crop=iw*0.65:ih*0.65:"
                f"x='clip(iw*{x}-iw*0.65/2,0,iw-iw*0.65)':"
                f"y='clip(ih*{y}-ih*0.65/2,0,ih-ih*0.65)'"
            )
        return "crop=iw:ih"

    @classmethod
    def _shot_expressions(cls, shot: Shot, speed: float, frames: int) -> tuple[str, str, str]:
        if shot.motion is MotionType.CROP_PUSH:
            center_x = "iw/2-(iw/zoom/2)"
            center_y = "ih/2-(ih/zoom/2)"
            return f"min(1+on*{speed},1.35)", center_x, center_y
        if shot.motion is MotionType.FOCAL_ZOOM and shot.focal_point is not None:
            x, y = shot.focal_point
            return (
                f"min(1+on*{speed},1.35)",
                f"clip(iw*{x}-iw/zoom/2,0,iw-iw/zoom)",
                f"clip(ih*{y}-ih/zoom/2,0,ih-ih/zoom)",
            )
        return cls._expressions(shot.motion, speed, frames)
