from flask import Flask, request, jsonify
import threading
import os
import yt_dlp

app = Flask(__name__)

# Global variables
download_dir = os.getenv('DOWNLOAD_DIR', os.getcwd())
queue_lock = threading.Lock()
active_downloads = {}
download_history = []

def download_video(url, format_type, quality, task_id):
    global active_downloads
    ydl_opts = {
        'format': f'bestvideo[height<={quality[:-1]}]+bestaudio' if format_type == 'Video+Audio (MP4)' else 'bestaudio',
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'merge_output_format': 'mp4' if format_type == 'Video+Audio (MP4)' else None,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if format_type == 'Audio only (MP3)' else [],
        'progress_hooks': [lambda d: progress_hook(d, task_id)],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        with queue_lock:
            active_downloads[task_id]['status'] = 'Completed'
            active_downloads[task_id]['progress'] = '100%'
    except Exception as e:
        with queue_lock:
            active_downloads[task_id]['status'] = 'Error'
            active_downloads[task_id]['progress'] = str(e)

def progress_hook(d, task_id):
    with queue_lock:
        if d['status'] == 'downloading':
            active_downloads[task_id]['status'] = 'Downloading'
            active_downloads[task_id]['progress'] = d.get('_percent_str', '0%')

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Social Media Downloader</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f0f0f0; margin: 20px; }
            h1 { color: #333; }
            form, .section { margin: 20px 0; padding: 10px; background: white; border-radius: 5px; }
            textarea, select, button { width: 100%; margin: 5px 0; padding: 5px; }
            button { background: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background: #007bff; color: white; }
        </style>
    </head>
    <body>
        <h1>Social Media Downloader</h1>
        <form id="download-form">
            <label>URLs (one per line):</label><br>
            <textarea name="urls" rows="5"></textarea><br>
            <label>Format:</label>
            <select name="format">
                <option value="Video+Audio (MP4)">Video+Audio (MP4)</option>
                <option value="Audio only (MP3)">Audio only (MP3)</option>
            </select><br>
            <label>Quality:</label>
            <select name="quality">
                <option value="720p">720p</option>
                <option value="480p">480p</option>
                <option value="1080p">1080p</option>
            </select><br>
            <button type="submit">Download</button>
        </form>
        <div class="section">
            <h2>Queue</h2>
            <button id="clear-queue">Clear Queue</button>
            <table id="queue-table">
                <tr><th>URL</th><th>Status</th><th>Progress</th></tr>
            </table>
        </div>
        <div class="section">
            <h2>History</h2>
            <table id="history-table">
                <tr><th>Time</th><th>URL</th></tr>
            </table>
        </div>
        <script>
            document.getElementById('download-form').addEventListener('submit', function(e) {
                e.preventDefault();
                fetch('/download', { method: 'POST', body: new FormData(this) })
                    .then(res => res.json())
                    .then(data => alert(data.message));
            });
            document.getElementById('clear-queue').addEventListener('click', function() {
                fetch('/clear', { method: 'POST' })
                    .then(res => res.json())
                    .then(data => alert(data.message));
            });
            function updateStatus() {
                fetch('/status')
                    .then(res => res.json())
                    .then(data => {
                        const queueTable = document.getElementById('queue-table');
                        queueTable.innerHTML = '<tr><th>URL</th><th>Status</th><th>Progress</th></tr>';
                        for (let id in data.downloads) {
                            const task = data.downloads[id];
                            queueTable.innerHTML += `<tr><td>${task.url}</td><td>${task.status}</td><td>${task.progress}</td></tr>`;
                        }
                        const historyTable = document.getElementById('history-table');
                        historyTable.innerHTML = '<tr><th>Time</th><th>URL</th></tr>';
                        data.history.forEach(entry => {
                            historyTable.innerHTML += `<tr><td>${entry.time}</td><td>${entry.url}</td></tr>`;
                        });
                    });
            }
            setInterval(updateStatus, 1000);
            updateStatus();
        </script>
    </body>
    </html>
    """

@app.route('/download', methods=['POST'])
def download():
    urls = request.form.get('urls', '').strip().splitlines()
    format_type = request.form.get('format', 'Video+Audio (MP4)')
    quality = request.form.get('quality', '720p')

    with queue_lock:
        for url in urls:
            if url.strip():
                task_id = len(active_downloads) + 1
                active_downloads[task_id] = {'url': url, 'status': 'Queued', 'progress': '0%'}
                download_history.append({'time': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'url': url})
                threading.Thread(target=download_video, args=(url, format_type, quality, task_id), daemon=True).start()
    return jsonify({'message': f'Added {len(urls)} URLs to queue'})

@app.route('/status', methods=['GET'])
def status():
    with queue_lock:
        return jsonify({'downloads': active_downloads, 'history': download_history})

@app.route('/clear', methods=['POST'])
def clear():
    with queue_lock:
        active_downloads.clear()
    return jsonify({'message': 'Queue cleared'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Heroku assigns PORT
    app.run(host='0.0.0.0', port=port, debug=False)
