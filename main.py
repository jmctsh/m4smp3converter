from flask import Flask, request, render_template, send_from_directory
import os
import subprocess
import sys
import webbrowser
import threading
import tkinter as tk
from tkinter import messagebox
import logging
import shutil

# ---------------------------- Flask后端配置 ----------------------------
app = Flask(__name__)


# 动态获取EXE所在目录的绝对路径
def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


# 固定上传文件夹为EXE同级目录下的uploads
app.config['UPLOAD_FOLDER'] = os.path.join(get_exe_dir(), 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'m4s'}


# 动态获取资源路径（适配打包环境）
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)


def get_ffmpeg_path():
    return get_resource_path(os.path.join('static', 'ffmpeg.exe'))


# 清空上传文件夹
def clear_upload_folder():
    upload_folder = app.config['UPLOAD_FOLDER']
    if os.path.exists(upload_folder):
        shutil.rmtree(upload_folder)
    os.makedirs(upload_folder, exist_ok=True)


# 初始化时清空文件夹
clear_upload_folder()


# 文件类型检查
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# ---------------------------- Flask路由 ----------------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert():
    try:
        clear_upload_folder()  # 每次转换前清空旧文件

        if 'file' not in request.files:
            return "未选择文件", 400
        file = request.files['file']
        if file.filename == '':
            return "未选择文件", 400
        if not allowed_file(file.filename):
            return "仅支持.m4s文件", 400

        # 保存文件
        input_filename = file.filename
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        file.save(input_path)

        # 生成输出路径
        output_filename = f"{os.path.splitext(input_filename)[0]}.mp3"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        # 调用ffmpeg转换
        ffmpeg_path = get_ffmpeg_path()
        subprocess.run(
            [ffmpeg_path, '-i', input_path, '-vn', '-acodec', 'libmp3lame', '-q:a', '2', output_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT
        )

        # 返回文件（显式使用绝对路径）
        response = send_from_directory(
            app.config['UPLOAD_FOLDER'],
            output_filename,
            as_attachment=True,
            conditional=True
        )

        # 添加清理回调
        @response.call_on_close
        def cleanup():
            clear_upload_folder()

        return response

    except subprocess.CalledProcessError:
        clear_upload_folder()
        return "转换失败：FFmpeg错误", 500
    except Exception as e:
        clear_upload_folder()
        return f"系统错误：{str(e)}", 500


# ---------------------------- GUI控制窗口 ----------------------------
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("M4S转MP3工具")
        self.geometry("300x150")
        self.server_thread = None
        self.server_running = False

        # 控件
        self.btn_start = tk.Button(self, text="启动服务", command=self.start_server)
        self.btn_open = tk.Button(self, text="打开浏览器", command=self.open_browser, state=tk.DISABLED)
        self.btn_stop = tk.Button(self, text="停止服务", command=self.stop_server, state=tk.DISABLED)

        # 布局
        self.btn_start.pack(pady=10)
        self.btn_open.pack(pady=10)
        self.btn_stop.pack(pady=10)

    def start_server(self):
        def run_flask():
            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

        if not self.server_running:
            self.server_thread = threading.Thread(target=run_flask, daemon=True)
            self.server_thread.start()
            self.server_running = True
            self.btn_start.config(state=tk.DISABLED)
            self.btn_open.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.NORMAL)
            messagebox.showinfo("提示", "服务已启动！")

    def open_browser(self):
        webbrowser.open("http://127.0.0.1:5000")

    def stop_server(self):
        if self.server_running:
            # 清空上传文件夹
            upload_folder = app.config['UPLOAD_FOLDER']
            if os.path.exists(upload_folder):
                try:
                    shutil.rmtree(upload_folder)
                except Exception as e:
                    print(f"清理文件夹失败: {str(e)}")
            # 关闭程序
            self.quit()
            os._exit(0)


if __name__ == '__main__':
    # 隐藏Flask日志
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # 启动GUI
    gui = Application()
    gui.mainloop()

# 运行：python main.py
# 打包：pyinstaller main.py --name M4SConverter --add-data "templates;templates" --add-data "static;static" --onefile --noconsole
# 生成项目依赖：pip freeze > requirements.txt