"""V2 manifest timeline calculation."""

from __future__ import annotations

from models import Manifest, ManifestTimeline, TimelineShot


class ManifestTimelineBuilder:
    """Calculate shot timestamps for V2 manifests."""

    def build(self, manifest: Manifest) -> ManifestTimeline:
        shots: list[TimelineShot] = []
        cursor = 0.0
        for index, shot in enumerate(manifest.shots):
            start = cursor
            end = start + float(shot.duration)
            shots.append(
                TimelineShot(
                    index=index,
                    source=shot,
                    asset=manifest.assets[shot.asset_id],
                    start_time=start,
                    end_time=end,
                    duration=float(shot.duration),
                )
            )
            cursor = end
        return ManifestTimeline(shots=shots, total_duration=cursor)
