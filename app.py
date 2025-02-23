from flask import Flask, request, jsonify
import threading
import os
from downloader import Downloader

app = Flask(__name__)

# Global variables
download_dir = os.getcwd()
downloader = Downloader(download_dir)
queue_lock = threading.Lock()
active_downloads = {}
download_history = []

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Social Media Downloader</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #1E272C; color: #ECEFF1; margin: 0; padding: 0; }
            header { background-color: #0288D1; padding: 10px; text-align: center; }
            .container { display: flex; justify-content: space-around; padding: 20px; }
            section { background-color: #2E3B41; padding: 20px; border-radius: 5px; width: 30%; }
            h2 { color: #81D4FA; }
            form label { margin-top: 10px; display: block; }
            textarea, select, button { width: 100%; margin-top: 5px; padding: 5px; }
            button { background-color: #0288D1; color: white; border: none; padding: 10px; cursor: pointer; }
            button:hover { background-color: #4FC3F7; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #ECEFF1; padding: 8px; text-align: left; }
            th { background-color: #0288D1; }
        </style>
    </head>
    <body>
        <header><h1>Social Media Downloader</h1></header>
        <div class="container">
            <section id="download-section">
                <h2>Download</h2>
                <form id="download-form">
                    <label for="urls">URLs (one per line):</label><br>
                    <textarea id="urls" name="urls" rows="5" cols="50"></textarea><br>
                    <label for="format">Format:</label>
                    <select id="format" name="format">
                        <option value="Video+Audio (MP4)">Video+Audio (MP4)</option>
                        <option value="Audio only (MP3)">Audio only (MP3)</option>
                    </select><br>
                    <label for="quality">Quality:</label>
                    <select id="quality" name="quality">
                        <option value="720p">720p</option>
                        <option value="480p">480p</option>
                        <option value="1080p">1080p</option>
                    </select><br>
                    <button type="submit">Download</button>
                </form>
            </section>
            <section id="queue-section">
                <h2>Queue</h2>
                <button id="clear-queue">Clear Queue</button>
                <table id="queue-table">
                    <thead><tr><th>URL</th><th>Status</th><th>Progress</th></tr></thead>
                    <tbody></tbody>
                </table>
            </section>
            <section id="history-section">
                <h2>History</h2>
                <table id="history-table">
                    <thead><tr><th>Time</th><th>URL</th></tr></thead>
                    <tbody></tbody>
                </table>
            </section>
        </div>
        <script>
            document.getElementById('download-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(this);
                fetch('/download', { method: 'POST', body: formData })
                    .then(response => response.json())
                    .then(data => alert(data.message))
                    .catch(error => alert('Error: ' + error));
            });

            document.getElementById('clear-queue').addEventListener('click', function() {
                fetch('/clear', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => alert(data.message))
                    .catch(error => alert('Error: ' + error));
            });

            function updateStatus() {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        const queueBody = document.querySelector('#queue-table tbody');
                        queueBody.innerHTML = '';
                        for (let id in data.downloads) {
                            const task = data.downloads[id];
                            queueBody.innerHTML += `<tr><td>${task.url}</td><td>${task.status}</td><td>${task.progress}</td></tr>`;
                        }
                        const historyBody = document.querySelector('#history-table tbody');
                        historyBody.innerHTML = '';
                        data.history.forEach(entry => {
                            historyBody.innerHTML += `<tr><td>${entry.time}</td><td>${entry.url}</td></tr>`;
                        });
                    });
            }
            setInterval(updateStatus, 1000);
            updateStatus();
        </script>
    </body>
    </html>
    """
    return html

@app.route('/download', methods=['POST'])
def download():
    urls = request.form.get('urls', '').strip().splitlines()
    format_type = request.form.get('format', 'Video+Audio (MP4)')
    quality = request.form.get('quality', '720p')

    with queue_lock:
        for url in urls:
            if url.strip():
                task_id = len(active_downloads) + 1
                active_downloads[task_id] = {
                    'url': url,
                    'status': 'Queued',
                    'progress': '0%',
                    'format': format_type,
                    'quality': quality
                }
                threading.Thread(target=downloader.download_video, args=(url, format_type, quality, task_id), daemon=True).start()
                download_history.append({'time': downloader.get_timestamp(), 'url': url})
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
    port = int(os.environ.get('PORT', 5000))  # Render assigns PORT
    app.run(debug=False, host='0.0.0.0', port=port)  # Bind to 0.0.0.0 for Render
