import os
import subprocess
import threading
import re
import traceback
import signal
from dotenv import load_dotenv
from models import db, DownloadTask

load_dotenv()

DOWNLOADS_DIR = os.getenv('DOWNLOADS_DIR', '/app/downloads')
LOGS_DIR = '/app/logs'
USE_GPU = os.getenv('USE_GPU', 'false').lower() == 'true'

def get_log_path(task_id):
    return os.path.join(LOGS_DIR, f"task_{task_id}.log")

# Global registry to track active processes for cancellation
# Key: task_id, Value: subprocess.Popen object
active_processes = {}

def shutdown_all_tasks():
    """Kills all active subprocesses immediately on app shutdown."""
    print(f"Shutting down {len(active_processes)} active tasks...")
    for task_id, process in list(active_processes.items()):
        try:
            process.kill()
            print(f"Killed task {task_id}")
        except Exception as e:
            print(f"Error killing task {task_id}: {e}")
    active_processes.clear()

def update_task_progress(task_id, status=None, progress=None, filename=None, error_log=None, encoder_type=None):
    from main import app
    with app.app_context():
        try:
            task = DownloadTask.query.get(task_id)
            if task:
                if status is not None: task.status = status
                if progress is not None: task.progress = progress
                if filename is not None: task.filename = filename
                if error_log is not None: task.error_log = error_log
                if encoder_type is not None: task.encoder_type = encoder_type
                db.session.commit()
        except Exception as e:
            print(f"Database error updating task {task_id}: {e}")

def cleanup_task_files(task_id):
    """Removes temporary files specifically associated with a given task."""
    try:
        from main import app
        from models import DownloadTask
        with app.app_context():
            task = DownloadTask.query.get(task_id)
            if not task or not task.filename:
                return

            # Get the base filename without extensions to match .part, .temp, etc.
            # yt-dlp often uses filename.part or filename.ytdl
            base_name = os.path.basename(task.filename)
            
            for file in os.listdir(DOWNLOADS_DIR):
                # Match if the file starts with the base name and has a temp extension
                # or if it's a known yt-dlp temp pattern containing the task filename
                if (file.startswith(base_name) or base_name in file) and \
                   (file.endswith(('.part', '.temp', '.ytdl'))):
                    os.remove(os.path.join(DOWNLOADS_DIR, file))
                
                # Specifically for compression tasks, we need to find the output file.
                # The task.filename in DB for compress tasks is the INPUT filename.
                if task.task_type == 'compress':
                    # An output file for compression always starts with 'compressed_'
                    # and should contain the base_name of the input file.
                    if file.startswith('compressed_') and base_name in file:
                        # IMPORTANT: We only want to delete it if it's actually the one
                        # associated with this task. We can't be 100% sure without 
                        # the full output path, but since the process was just killed,
                        # and we are in cleanup_task_files, this is the intended target.
                        os.remove(os.path.join(DOWNLOADS_DIR, file))



    except Exception as e:
        print(f"Error cleaning up files for task {task_id}: {e}")

def download_vod(url, video_id, task_id):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    cmd = [
        'yt-dlp',
        '--newline',
        '-o', f'{DOWNLOADS_DIR}/%(title)s [%(id)s].%(ext)s',
        url
    ]
    
    if USE_GPU:
        cmd.extend(['--postprocessor-args', 'ffmpeg:-c:v h264_qsv'])
    
    update_task_progress(task_id, 'downloading')
    
    cmd_str = " ".join(cmd)
    print(f"[Task {task_id}] Executing: {cmd_str}")
    
    try:
        with open(get_log_path(task_id), 'w') as log_file:
            log_file.write(f"Command: {cmd_str}\n")
            log_file.flush()
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                bufsize=1,
                universal_newlines=True,
                start_new_session=True
            )
            
            active_processes[task_id] = process
            
            progress_re = re.compile(r'\[download\]\s+(\d+\.?\d*)%')
            filename = None
        
            # Read output line by line
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                
                print(f"[Task {task_id}] {line.strip()}")
                log_file.write(line)
                log_file.flush()
                
                match = progress_re.search(line)
                if match:
                    progress = float(match.group(1))
                    update_task_progress(task_id, progress=progress)
                
                if '[download] Destination:' in line:
                    filename = line.split('Destination: ')[-1].strip()
                    update_task_progress(task_id, filename=filename)
        
            process.wait()
            
            # Even if returncode != 0, check if the file actually exists
            success = process.returncode == 0
            if not success and filename and os.path.exists(filename):
                success = True
                
            if success:
                update_task_progress(task_id, 'completed', progress=100.0)
                cleanup_task_files(task_id)
                
                # --- Task Chaining for Automation Pipeline ---
                from models import MonitoredChannel
                from main import app
                with app.app_context():
                    task = DownloadTask.query.get(task_id)
                    # Find the channel that triggered this download
                    channel = MonitoredChannel.query.filter(
                        MonitoredChannel.user_id == task.user_id,
                        MonitoredChannel.enabled == True
                    ).first() # Simplified for now; real logic should correlate video_id
                    
                    if channel and channel.auto_compress:
                        presets = channel.compression_presets.split(',') if channel.compression_presets else ['balanced']
                        for preset in presets:
                            preset = preset.strip()
                            if not preset: continue
                            
                            # Create a new compression task
                            new_task = DownloadTask(
                                user_id=channel.user_id, 
                                filename=filename, 
                                status='pending', 
                                task_type='compress'
                            )
                            db.session.add(new_task)
                            db.session.commit()
                            start_compress_async(filename, preset, new_task.id, channel.user_id, channel.target_codec)
                # ---------------------------------------------
            else:
                update_task_progress(task_id, 'error', error_log="yt-dlp process failed and no output file found.")
                cleanup_task_files(task_id)
        
    except Exception as e:
        print(f"Error downloading {video_id}: {e}")
        print(traceback.format_exc())
        update_task_progress(task_id, 'error')
        cleanup_task_files(task_id)
    finally:
        active_processes.pop(task_id, None)


def compress_video(input_filename, preset, task_id, user_id, codec='H.264'):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    input_path = os.path.join(DOWNLOADS_DIR, input_filename)
    # Use os.path.basename to ensure we only have the filename, not the full path
    base_input_filename = os.path.basename(input_filename)
    output_filename = f"compressed_{codec}_{preset}_{base_input_filename}"
    output_path = os.path.join(DOWNLOADS_DIR, output_filename)
    
    # Get total duration for progress calculation
    total_duration = 0
    try:
        probe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', input_path
        ]
        duration_out = subprocess.check_output(probe_cmd, text=True).strip()
        total_duration = float(duration_out)
    except Exception as e:
        print(f"Error probing duration for {input_filename}: {e}")

    presets = {
        'fast': {
            'crf': '36', 
            'h264_sw': 'veryfast', 'h264_hw': 'veryfast',
            'h265_sw': 'veryfast', 'h265_hw': 'veryfast',
            'av1_sw': '8', 'av1_hw': 'veryfast'
        },
        'balanced': {
            'crf': '32', 
            'h264_sw': 'medium', 'h264_hw': 'balanced',
            'h265_sw': 'medium', 'h265_hw': 'balanced',
            'av1_sw': '6', 'av1_hw': 'fast'
        },
        'high': {
            'crf': '22', 
            'h264_sw': 'slow', 'h264_hw': 'quality',
            'h265_sw': 'slow', 'h265_hw': 'quality',
            'av1_sw': '4', 'av1_hw': 'quality'
        }
    }
    
    p = presets.get(preset, presets['balanced'])
    
    codec_map = {
        'H.264': {'hw': 'h264_vaapi', 'sw': 'libx264', 'prefix': 'h264'},
        'H.265': {'hw': 'hevc_vaapi', 'sw': 'libx265', 'prefix': 'h265'},
        'AV1': {'hw': 'av1_vaapi', 'sw': 'libsvtav1', 'prefix': 'av1'},
        'x264': {'hw': None, 'sw': 'libx264', 'prefix': 'h264'}
    }
    
    mapping = codec_map.get(codec, codec_map['H.264'])
    encoders = []
    if mapping['hw']:
        encoders.append(mapping['hw'])
    encoders.append(mapping['sw'])
    
    full_log = []
    last_error = ""
    
    # Create/Clear log file at the start of compression
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(get_log_path(task_id), 'w') as f:
        f.write(f"Compression Task {task_id} started\n")
    
    for encoder in encoders:

        prefix = mapping['prefix']
        is_hw = 'vaapi' in encoder
        preset_key = f"{prefix}_{'hw' if is_hw else 'sw'}"
        current_preset = p.get(preset_key, 'medium')
        
        cmd = [
            'ffmpeg',
            '-y',
            '-vaapi_device', '/dev/dri/renderD128',
            '-i', input_path,
        ]
        if is_hw:
            cmd.extend(['-vf', 'format=nv12,hwupload'])
        
        cmd.extend(['-c:v', encoder])
        
        if is_hw:
            cmd.extend(['-global_quality', p['crf']])
        else:
            cmd.extend(['-crf', p['crf']])

        cmd.extend([
            '-preset', current_preset,
            '-c:a', 'copy',
            output_path
        ])
        
        cmd_str = " ".join(cmd)
        print(f"[Task {task_id}] Executing: {cmd_str}")
        
        log_entry = f"Attempting encoding with {encoder}..."
        encoder_type = 'HW' if is_hw else 'SW'
        
        try:
            # Append to the same task log file across different encoder attempts
            with open(get_log_path(task_id), 'a') as log_file:
                log_file.write(f"\nCommand: {cmd_str}\n")
                log_file.write(f"{log_entry}\n")
                log_file.flush()

                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    start_new_session=True
                )
                active_processes[task_id] = process
                
                # Record the current encoder type in DB
                update_task_progress(task_id, encoder_type=encoder_type)
                
                # Regex to find time=00:00:00.00
                time_re = re.compile(r'time=(\d+):(\d+):(\d+.\d+)')
                
                for line in iter(process.stdout.readline, ''):
                    print(f"[Task {task_id}] {line.strip()}")
                    log_file.write(line)
                    log_file.flush()
                    
                    match = time_re.search(line)
                    if match and total_duration > 0:
                        h, m, s = map(float, match.groups())
                        current_seconds = h * 3600 + m * 60 + s
                        progress = min(100.0, (current_seconds / total_duration) * 100)
                        update_task_progress(task_id, progress=round(progress, 2))
                
                process.wait()
                
                if process.returncode == 0:
                    update_task_progress(task_id, 'completed', progress=100.0, filename=output_filename, error_log="Successfully encoded with " + encoder)
                    return
                else:
                    err_msg = f"Encoder {encoder} failed with return code {process.returncode}"
                    log_file.write(f"{err_msg}\n")
                    log_file.flush()
                    last_error = err_msg
                    continue
        except Exception as e:
            err_msg = f"Encoder {encoder} exception: {str(e)}"
            with open(get_log_path(task_id), 'a') as log_file:
                log_file.write(f"{err_msg}\n")
                log_file.flush()
            last_error = err_msg
            continue
        finally:
            active_processes.pop(task_id, None)

    update_task_progress(task_id, 'error', error_log=f"All encoders failed. Last error: {last_error}")


def start_download_async(url, video_id, task_id):
    thread = threading.Thread(target=download_vod, args=(url, video_id, task_id))
    thread.start()
    return thread

def start_compress_async(input_filename, preset, task_id, user_id, codec='H.264'):
    thread = threading.Thread(target=compress_video, args=(input_filename, preset, task_id, user_id, codec))
    thread.start()
    return thread

def cancel_task(task_id):
    """Kills the process associated with the task and all its children. 
    Returns True if the task was successfully cancelled or was already dead.
    """
    process = active_processes.get(task_id)
    
    # 1. Kill by process group if available
    if process:
        try:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except ProcessLookupError:
                process.terminate()
            except Exception:
                process.terminate()

            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:
                    process.kill()
            active_processes.pop(task_id, None)
        except Exception as e:
            print(f"Error canceling process group for task {task_id}: {e}")

    # 2. Deep Cleanup: Find any orphaned ffmpeg processes associated with this task
    # We look for ffmpeg processes that have the task's output file in their command line
    try:
        import psutil
        # Get the filename from DB to find the process
        from main import app
        from models import DownloadTask, db
        with app.app_context():
            task = DownloadTask.query.get(task_id)
            if task and task.filename:
                target_file = task.filename
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                            cmdline = proc.info['cmdline']
                            if cmdline and any(target_file in arg for arg in cmdline):
                                print(f"Killing orphaned ffmpeg process {proc.info['pid']} for task {task_id}")
                                proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
    except Exception as e:
        print(f"Deep cleanup failed for task {task_id}: {e}")
    
    # 3. File Cleanup: Remove temporary files associated with this task
    cleanup_task_files(task_id)
    
    return True
