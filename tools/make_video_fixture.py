"""Build a tiny valid video with Blender's bundled encoder for importer tests."""
from pathlib import Path
import shutil
import bpy

root = Path(__file__).resolve().parents[1]
folder = root / 'artifacts/video-fixture'
folder.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.render.resolution_x = scene.render.resolution_y = 32
scene.render.resolution_percentage = 100
scene.render.fps = 12
scene.frame_start, scene.frame_end = 1, 2
if hasattr(scene.render.image_settings, 'media_type'):
    scene.render.image_settings.media_type = 'VIDEO'
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.filepath = str(folder / 'fixture')
bpy.ops.render.render(animation=True)
videos = sorted(folder.glob('*.mp4'))
if not videos:
    raise RuntimeError('Blender did not write the video fixture')
shutil.copyfile(videos[-1], root / 'tests/fixtures/video.mp4')
print('VIDEO_FIXTURE', (root / 'tests/fixtures/video.mp4').stat().st_size)
