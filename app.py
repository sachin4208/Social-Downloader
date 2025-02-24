from flask import Flask, request, render_template_string, send_file
import yt_dlp
import os
import requests
from io import BytesIO

app = Flask(__name__)

# Directory for temporary downloads
download_dir = os.getenv('DOWNLOAD_DIR', os.getcwd())

@app.route('/', methods=['GET', 'POST'])
def index():
    video_info = None
    thumbnail_url = None
    qualities = []
    error = None

    if request.method == 'POST' and 'url' in request.form:
        url = request.form['url']
        try:
            # Fetch video info without downloading
            ydl_opts = {'quiet': True, 'simulate': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            # Extract details
            video_info = {
                'title': info.get('title', 'Unknown Title'),
                'url': url
            }
            thumbnail_url = info.get('thumbnail')
            # Get available video qualities (heights)
            qualities = sorted(set(fmt['height'] for fmt in info['formats'] 
                                 if fmt.get('vcodec') != 'none' and fmt.get('height')), 
                             reverse=True)
        except Exception as e:
            error = f"Error fetching details: {str(e)}"

    # HTML template with form, preview, and download options
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Simple Video Downloader</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f0f0f0; margin: 20px; }
            h1 { color: #333; }
            form, .section { margin: 20px 0; padding: 10px; background: white; border-radius: 5px; }
            input[type="text"], select, button { width: 100%; margin: 5px 0; padding: 5px; }
            button { background: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
            img { max-width: 300px; margin: 10px 0; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h1>Simple Video Downloader</h1>
        <form method="POST">
            <label>Paste Video URL:</label><br>
            <input type="text" name="url" placeholder="e.g., https://www.youtube.com/watch?v=..." required><br>
            <button type="submit">Get Details</button>
        </form>
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        {% if video_info %}
            <div class="section">
                <h2>{{ video_info.title }}</h2>
                {% if thumbnail_url %}
                    <img src="{{ thumbnail_url }}" alt="Thumbnail">
                {% endif %}
                <form method="POST" action="/download">
                    <input type="hidden" name="url" value="{{ video_info.url }}">
                    <label>Download Options:</label><br>
                    <select name="quality">
                        {% for q in qualities %}
                            <option value="{{ q }}">{{ q }}p</option>
                        {% endfor %}
                    </select><br>
                    <button type="submit" name="format" value="mp4">Download MP4</button>
                    <button type="submit" name="format" value="mp3">Download MP3</button>
                </form>
            </div>
        {% endif %}
    </body>
    </html>
    """
    return render_template_string(html, video_info=video_info, thumbnail_url=thumbnail_url, qualities=qualities, error=error)

@app.route('/download', methods=['POST'])
def download():
    url = request.form['url']
    format_type = request.form['format']
    quality = request.form['quality']

    ydl_opts = {
        'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]' if format_type == 'mp4' else 'bestaudio',
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'merge_output_format': 'mp4' if format_type == 'mp4' else None,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if format_type == 'mp3' else [],
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if format_type == 'mp3':
                # Adjust filename for MP3 extension after postprocessing
                base, _ = os.path.splitext(filename)
                filename = base + '.mp3'
        
        # Send file as attachment and remove it afterward
        with open(filename, 'rb') as f:
            file_data = BytesIO(f.read())
        os.remove(filename)
        return send_file(file_data, as_attachment=True, download_name=os.path.basename(filename))
    except Exception as e:
        return f"Error downloading: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Render assigns PORT
    app.run(host='0.0.0.0', port=port, debug=False)
