import yt_dlp
import os
from datetime import datetime

class Downloader:
    def __init__(self, download_dir):
        self.download_dir = download_dir
        self.speed_limit = 500 * 1024  # 500 KB/s

    def get_timestamp(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def progress_hook(self, d, task_id, active_downloads):
        if d['status'] == 'downloading':
            progress = d.get('_percent_str', '0%')
            active_downloads[task_id]['status'] = 'Downloading'
            active_downloads[task_id]['progress'] = progress
        elif d['status'] == 'finished':
            active_downloads[task_id]['status'] = 'Completed'
            active_downloads[task_id]['progress'] = '100%'

    def download_video(self, url, format_type, quality, task_id):
        from app import active_downloads
        ydl_opts = {
            'format': f'bestvideo[height<={quality[:-1]}]+bestaudio' if format_type == 'Video+Audio (MP4)' else 'bestaudio',
            'outtmpl': os.path.join(self.download_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [lambda d: self.progress_hook(d, task_id, active_downloads)],
            'quiet': True,
            'merge_output_format': 'mp4' if format_type == 'Video+Audio (MP4)' else None,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if format_type == 'Audio only (MP3)' else [],
            'ratelimit': self.speed_limit
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            active_downloads[task_id]['status'] = 'Error'
            active_downloads[task_id]['progress'] = str(e)
