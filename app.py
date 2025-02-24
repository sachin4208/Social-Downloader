from flask import Flask, request, render_template, send_file
import yt_dlp
import os
from io import BytesIO
import logging
import tempfile

app = Flask(__name__, static_folder='static')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

download_dir = os.getenv('DOWNLOAD_DIR', os.getcwd())

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST' and 'action' in request.form:
        if request.form['action'] == 'fetch':
            url = request.form['link']
            cookies_file = request.files.get('cookies')
            cookies_path = None
            if cookies_file and cookies_file.filename.endswith('.txt'):
                cookies_path = os.path.join(tempfile.gettempdir(), f'cookies_{os.urandom(8).hex()}.txt')
                cookies_file.save(cookies_path)

            try:
                ydl_opts = {
                    'quiet': True,
                    'simulate': True,
                    'cookiefile': cookies_path,
                    'nocheckcertificate': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                
                qualities = sorted(
                    set(fmt['height'] for fmt in info['formats'] if fmt.get('vcodec') != 'none' and fmt.get('height')),
                    reverse=True
                ) if 'formats' in info else [144, 360, 480, 720, 1080]
                return render_template('index.html', title=info.get('title'), thumbnail=info.get('thumbnail'), qualities=qualities)
            except Exception as e:
                return render_template('index.html', error=str(e))
            finally:
                if cookies_path and os.path.exists(cookies_path):
                    os.remove(cookies_path)
        elif request.form['action'] == 'download':
            url = request.form['link']
            format_type = request.form['format']
            quality = request.form['quality']
            cookies_file = request.files.get('cookies')
            cookies_path = None
            if cookies_file and cookies_file.filename.endswith('.txt'):
                cookies_path = os.path.join(tempfile.gettempdir(), f'cookies_{os.urandom(8).hex()}.txt')
                cookies_file.save(cookies_path)

            ydl_opts = {
                'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]' if format_type.startswith('mp4') else 'bestaudio',
                'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'merge_output_format': 'mp4' if format_type.startswith('mp4') else None,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if format_type == 'mp3' else [],
                'nocheckcertificate': True,
                'cookiefile': cookies_path,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    if format_type == 'mp3':
                        base, _ = os.path.splitext(filename)
                        filename = base + '.mp3'
                
                with open(filename, 'rb') as f:
                    file_data = BytesIO(f.read())
                os.remove(filename)
                return send_file(file_data, as_attachment=True, download_name=os.path.basename(filename))
            except Exception as e:
                return render_template('index.html', error=f"Error downloading: {str(e)}")
            finally:
                if cookies_path and os.path.exists(cookies_path):
                    os.remove(cookies_path)
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
