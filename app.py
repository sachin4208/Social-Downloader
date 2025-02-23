import os
from flask import Flask, render_template, request, jsonify, session
from flask_bootstrap import Bootstrap5
from celery import Celery
import yt_dlp
from datetime import datetime
from config import Config
from models import db, History, Setting

app = Flask(__name__)
app.config.from_object(Config)
Bootstrap5(app)
db.init_app(app)

# Celery Setup
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Initialize Database
with app.app_context():
    db.create_all()
    # Set default settings if not present
    defaults = {
        'download_dir': app.config['DOWNLOAD_DIR'],
        'proxy': '',
        'theme': 'dark',
        'auto_download': 'False',
        'notify_sound': 'True',
        'speed_limit': '500'  # KB/s
    }
    for key, value in defaults.items():
        if not Setting.query.filter_by(key=key).first():
            db.session.add(Setting(key=key, value=value))
    db.session.commit()

def get_setting(key):
    setting = Setting.query.filter_by(key=key).first()
    return setting.value if setting else defaults.get(key)

def set_setting(key, value):
    setting = Setting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        db.session.add(Setting(key=key, value=value))
    db.session.commit()

# Celery Task
@celery.task(bind=True)
def download_video(self, url, ydl_opts):
    def progress_hook(d):
        if d['status'] == 'downloading':
            self.update_state(state='PROGRESS', meta={
                'percentage': d.get('_percent_str', '0%'),
                'speed': d.get('_speed_str', 'N/A'),
                'url': url
            })
        elif d['status'] == 'finished':
            with app.app_context():
                db.session.add(History(url=url, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                db.session.commit()

    ydl_opts['progress_hooks'] = [progress_hook]
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# Routes
@app.route('/', methods=['GET', 'POST'])
def download():
    if request.method == 'POST':
        if 'fetch' in request.form:
            url = request.form['url'].strip()
            ydl_opts = {'quiet': True, 'simulate': True}
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    formats = ['Video+Audio (MP4)', 'Audio only (MP3)']
                    qualities = sorted(set(f.get('height') for f in info['formats'] if f.get('vcodec') != 'none' and f.get('height')))
                    thumbnail = info.get('thumbnail', '')
                    return jsonify({
                        'formats': formats,
                        'qualities': [f'{q}p' for q in qualities],
                        'thumbnail': thumbnail
                    })
            except Exception as e:
                return jsonify({'error': str(e)}), 400
        elif 'download' in request.form:
            urls = request.form['url'].strip().splitlines()
            format_type = request.form['format']
            quality = request.form['quality'].replace('p', '')
            download_dir = get_setting('download_dir')
            proxy = get_setting('proxy') or None
            speed_limit = int(get_setting('speed_limit')) * 1024
            ydl_opts = {
                'format': f'bestvideo[height<={quality}]+bestaudio' if format_type == 'Video+Audio (MP4)' else 'bestaudio',
                'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4' if format_type == 'Video+Audio (MP4)' else None,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}] if format_type == "Audio only (MP3)" else [],
                'writesubtitles': True,
                'ratelimit': speed_limit,
                'proxy': proxy,
                'quiet': True
            }
            tasks = [download_video.delay(url.strip(), ydl_opts).id for url in urls if url.strip()]
            return jsonify({'task_ids': tasks})
    return render_template('download.html', theme=get_setting('theme'))

@app.route('/queue')
def queue():
    return render_template('queue.html', theme=get_setting('theme'))

@app.route('/history')
def history():
    search = request.args.get('search', '')
    entries = History.query.filter(History.url.contains(search) | History.timestamp.contains(search)).all()
    return render_template('history.html', history=entries, theme=get_setting('theme'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        set_setting('download_dir', request.form['download_dir'])
        set_setting('proxy', request.form['proxy'])
        set_setting('speed_limit', request.form['speed_limit'])
        set_setting('auto_download', request.form.get('auto_download', 'False'))
        set_setting('notify_sound', request.form.get('notify_sound', 'False'))
        return jsonify({'success': True})
    return render_template('settings.html', 
                          download_dir=get_setting('download_dir'),
                          proxy=get_setting('proxy'),
                          speed_limit=get_setting('speed_limit'),
                          auto_download=get_setting('auto_download') == 'True',
                          notify_sound=get_setting('notify_sound') == 'True',
                          theme=get_setting('theme'))

@app.route('/task_status/<task_id>')
def task_status(task_id):
    task = download_video.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {'state': 'Pending', 'percentage': '0%', 'speed': 'N/A', 'url': 'Unknown'}
    elif task.state == 'PROGRESS':
        response = {'state': 'Downloading', **task.info}
    elif task.state == 'SUCCESS':
        response = {'state': 'Completed', 'percentage': '100%', 'speed': 'N/A', 'url': task.info.get('url', 'Unknown')}
    else:
        response = {'state': 'Error', 'percentage': '0%', 'speed': 'N/A', 'url': 'Unknown'}
    return jsonify(response)

@app.route('/cancel_task/<task_id>')
def cancel_task(task_id):
    task = download_video.AsyncResult(task_id)
    task.revoke(terminate=True)
    return jsonify({'success': True})

@app.route('/toggle_theme', methods=['POST'])
def toggle_theme():
    current = get_setting('theme')
    new_theme = 'light' if current == 'dark' else 'dark'
    set_setting('theme', new_theme)
    return jsonify({'theme': new_theme})

if __name__ == '__main__':
    app.run(debug=True)