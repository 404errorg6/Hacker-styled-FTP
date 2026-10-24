import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote
import cgi
import socket


class HackerHTTPHandler(SimpleHTTPRequestHandler):
    ICONS = {
        'folder': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ff41" stroke-width="1.5"><path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z"></path><path d="M12 11v6"></path><path d="M9 14l3 3 3-3"></path></svg>',
        'file': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ff41" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><line x1="10" y1="9" x2="8" y2="9"></line></svg>',
        'image': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ff41" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
        'video': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ff41" stroke-width="1.5"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>',
        'archive': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ff41" stroke-width="1.5"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line><line x1="12" y1="12" x2="12" y2="15"></line></svg>'
    }

    def do_GET(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            self.list_directory_with_upload(path)
        else:
            try:
                super().do_GET()
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                # Client cancelled download
                pass

    def do_POST(self):
        r, info = self.deal_post_data()
        self.send_response(200 if r else 400)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        response = f"""
        <html>
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                background-color: black;
                color: #00FF00;
                font-family: monospace;
                padding: 1em;
            }}
            a, button {{
                color: #00FF00;
                text-decoration: none;
                font-family: monospace;
                background: black;
                border: 1px solid #00FF00;
                padding: 0.3em 1em;
                cursor: pointer;
                transition: background-color 0.2s, color 0.2s;
            }}
            button:hover {{
                background-color: #00FF00;
                color: black;
            }}
        </style>
        </head>
        <body>
        <h2>{info}</h2>
        <form action="{self.path}" method="get">
            <button type="submit">Back to directory</button>
        </form>
        </body>
        </html>
        """
        try:
            self.wfile.write(response.encode('utf-8'))
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Client disconnected before response completed (e.g., during page reload)
            pass


    def deal_post_data(self):
        content_type = self.headers.get('Content-Type', '')
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': content_type,
            }
        )

        if 'file' not in form:
            return False, "No file field found in POST data."

        files = form['file']
        if not isinstance(files, list):
            files = [files]

        saved_files = []
        base_upload_dir = self.translate_path(self.path)
        if not os.path.isdir(base_upload_dir):
            base_upload_dir = os.path.dirname(base_upload_dir)

        for item in files:
            if not getattr(item, 'filename', None):
                continue
            rel_path = item.filename.replace('\\', '/')  # normalize Windows paths
            # Fix path traversal: remove any .. segments and ensure relative path
            secure_path = os.path.normpath(rel_path).lstrip(os.sep)
            # Additional check: ensure no .. components remain
            if '..' in secure_path.split(os.sep):
                return False, f"Invalid filename '{secure_path}': path traversal not allowed."
            dest_path = os.path.join(base_upload_dir, secure_path)

            # Ensure destination is within base_upload_dir
            dest_path = os.path.abspath(dest_path)
            base_upload_dir_abs = os.path.abspath(base_upload_dir)
            if not dest_path.startswith(base_upload_dir_abs):
                return False, f"Invalid path '{secure_path}': outside upload directory."

            dest_dir = os.path.dirname(dest_path)
            os.makedirs(dest_dir, exist_ok=True)  # create subdirectories

            try:
                # Read in chunks to handle large files
                chunk_size = 8192  # 8KB chunks
                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = item.file.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                saved_files.append(secure_path)
            except Exception as e:
                return False, f"Failed to save file '{secure_path}': {e}"

        if saved_files:
            return True, f"Uploaded files:<br>" + "<br>".join(saved_files)
        else:
            return False, "No valid files uploaded."

    def get_filename(self, fields):
        return "uploaded_file"

    def list_directory_with_upload(self, path):
        try:
            entries = os.listdir(path)
        except OSError:
            self.send_error(404, "Cannot list directory")
            return None

        entries.sort(key=lambda a: (not os.path.isdir(os.path.join(path, a)), a.lower()))
        displaypath = unquote(self.path)

        r = []
        r.append('<!DOCTYPE html><html><head>')
        r.append('<meta charset="utf-8">')
        r.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
        r.append('''
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                background-color: #0a0a0a;
                color: #00ff41;
                font-family: 'Courier New', 'Consolas', monospace;
                padding: 0;
                min-height: 100vh;
                line-height: 1.6;
                display: flex;
                flex-direction: column;
                height: 100vh;
                overflow: hidden;
            }

            .app-container {
                display: flex;
                flex-direction: column;
                height: 100vh;
                padding: 20px;
                gap: 15px;
            }

            .header-section {
                flex-shrink: 0;
            }

            .content-section {
                flex: 1;
                overflow-y: auto;
                overflow-x: hidden;
                padding-right: 5px;
                scroll-behavior: smooth;
            }

            .content-section::-webkit-scrollbar {
                width: 8px;
            }

            .content-section::-webkit-scrollbar-track {
                background: #0a0a0a;
            }

            .content-section::-webkit-scrollbar-thumb {
                background: #00ff41;
                border-radius: 4px;
                transition: background 0.3s ease;
            }

            .content-section::-webkit-scrollbar-thumb:hover {
                background: #00cc33;
            }

            table {
                animation: fadeIn 0.5s ease-in;
            }

            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            tr {
                animation: slideIn 0.3s ease-out;
            }

            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateX(-20px);
                }
                to {
                    opacity: 1;
                    transform: translateX(0);
                }
            }

            .footer-section {
                flex-shrink: 0;
            }

            h2 {
                font-size: 1.5em;
                margin-bottom: 10px;
                text-shadow: 0 0 10px #00ff41;
                letter-spacing: 2px;
            }

            h2::after {
                content: '_';
                animation: blink 1s infinite;
            }

            @keyframes blink {
                0%, 50% { opacity: 1; }
                51%, 100% { opacity: 0; }
            }

            hr {
                border: none;
                border-top: 1px solid #00ff41;
                margin: 15px 0;
                box-shadow: 0 0 5px #00ff41;
            }

            .header-section {
                margin-bottom: 0;
            }

            .footer-section {
                margin-top: 15px;
            }

            .header-bar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding: 15px;
                border: 1px solid #00ff41;
                background: linear-gradient(135deg, #0d1a0d 0%, #0a0a0a 100%);
                box-shadow: 0 0 15px rgba(0, 255, 65, 0.2);
            }

            .transfers-toggle {
                background: transparent;
                border: 1px solid #00ff41;
                color: #00ff41;
                font-family: 'Courier New', 'Consolas', monospace;
                font-size: 0.9em;
                padding: 8px 16px;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
                letter-spacing: 1px;
                position: relative;
                overflow: hidden;
            }

            .transfers-toggle:hover {
                background: #00ff41;
                color: #0a0a0a;
                box-shadow: 0 0 20px #00ff41;
                transform: translateY(-2px);
            }

            .transfers-toggle:active {
                transform: translateY(0) scale(0.95);
            }

            .transfers-toggle.active {
                background: #00ff41;
                color: #0a0a0a;
                box-shadow: 0 0 20px #00ff41;
            }

            .transfers-toggle::after {
                content: '';
                position: absolute;
                top: 50%;
                left: 50%;
                width: 0;
                height: 0;
                border-radius: 50%;
                background: rgba(0, 255, 65, 0.3);
                transform: translate(-50%, -50%);
                transition: width 0.3s, height 0.3s;
            }

            .transfers-toggle:active::after {
                width: 200px;
                height: 200px;
            }

            .progress-container {
                width: 100%;
                max-width: 600px;
                margin: 0 auto 15px auto;
                padding: 20px;
                border: 1px solid #00ff41;
                background: #0d1a0d;
                display: none;
                box-shadow: 0 0 15px rgba(0, 255, 65, 0.2);
            }

            .progress-container.show {
                display: block;
            }

            .transfer-info {
                margin-bottom: 15px;
            }

            .transfer-filename {
                font-weight: bold;
                margin-bottom: 8px;
                word-break: break-all;
                font-size: 1.1em;
                color: #00ff41;
            }

            .transfer-size {
                font-size: 0.9em;
                color: #00cc33;
            }

            .progress-bar {
                width: 100%;
                height: 25px;
                background-color: #0a0a0a;
                border: 1px solid #00ff41;
                position: relative;
                overflow: hidden;
            }

            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #00ff41 0%, #00cc33 100%);
                width: 0%;
                transition: width 0.3s ease;
                box-shadow: 0 0 10px #00ff41;
            }

            .progress-text {
                margin-top: 10px;
                text-align: center;
                font-size: 1em;
                color: #00ff41;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }

            th {
                padding: 12px;
                text-align: left;
                border-bottom: 2px solid #00ff41;
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #00ff41;
            }

            td {
                padding: 12px;
                border-bottom: 1px solid #003300;
            }

            .size {
                text-align: right;
                color: #00cc33;
                font-size: 0.85em;
                width: 120px;
                white-space: nowrap;
            }

            tr {
                transition: all 0.3s ease;
                cursor: pointer;
            }

            tr:hover {
                background-color: #0d1a0d;
                border-left: 3px solid #00ff41;
                transform: translateX(5px);
            }

            tr:hover td {
                color: #00cc33;
                text-shadow: 0 0 10px #00ff41;
            }

            tr:active {
                transform: translateX(2px) scale(0.98);
                background-color: #003300;
            }

            .icon {
                font-weight: bold;
                text-align: center;
                width: 50px;
                color: #00ff41;
                font-size: 0.9em;
            }

            .icon svg {
                display: inline-block;
                vertical-align: middle;
                filter: drop-shadow(0 0 2px #00ff41);
                transition: filter 0.3s ease, transform 0.3s ease;
            }

            tr:hover .icon svg {
                filter: drop-shadow(0 0 5px #00ff41);
                transform: scale(1.1);
            }

            tr:active .icon svg {
                transform: scale(0.95);
            }

            .upload {
                margin: 0;
                padding: 20px;
                border: 1px solid #00ff41;
                background: linear-gradient(135deg, #0d1a0d 0%, #0a0a0a 100%);
                max-width: 600px;
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                align-items: center;
                box-shadow: 0 0 15px rgba(0, 255, 65, 0.2);
            }

            input[type=file] {
                display: none;
            }

            label.file-upload {
                background: transparent;
                border: 1px solid #00ff41;
                color: #00ff41;
                font-family: 'Courier New', 'Consolas', monospace;
                font-size: 0.9em;
                padding: 10px 20px;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
                letter-spacing: 1px;
                position: relative;
                overflow: hidden;
            }

            label.file-upload:hover {
                background: #00ff41;
                color: #0a0a0a;
                box-shadow: 0 0 20px #00ff41;
                transform: translateY(-2px);
            }

            label.file-upload:active {
                transform: translateY(0) scale(0.95);
            }

            label.file-upload::after {
                content: '';
                position: absolute;
                top: 50%;
                left: 50%;
                width: 0;
                height: 0;
                border-radius: 50%;
                background: rgba(0, 255, 65, 0.3);
                transform: translate(-50%, -50%);
                transition: width 0.3s, height 0.3s;
            }

            label.file-upload:active::after {
                width: 200px;
                height: 200px;
            }

            input[type=submit] {
                background: transparent;
                border: 1px solid #00ff41;
                color: #00ff41;
                font-family: 'Courier New', 'Consolas', monospace;
                font-size: 0.9em;
                padding: 10px 20px;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
                letter-spacing: 1px;
                position: relative;
                overflow: hidden;
            }

            input[type=submit]:hover {
                background: #00ff41;
                color: #0a0a0a;
                box-shadow: 0 0 20px #00ff41;
                transform: translateY(-2px);
            }

            input[type=submit]:active {
                transform: translateY(0) scale(0.95);
            }

            input[type=submit]::after {
                content: '';
                position: absolute;
                top: 50%;
                left: 50%;
                width: 0;
                height: 0;
                border-radius: 50%;
                background: rgba(0, 255, 65, 0.3);
                transform: translate(-50%, -50%);
                transition: width 0.3s, height 0.3s;
            }

            input[type=submit]:active::after {
                width: 200px;
                height: 200px;
            }

            @media (max-width: 600px) {
                .app-container {
                    padding: 10px;
                }
                .upload {
                    flex-direction: column;
                }
                .header-bar {
                    flex-direction: column;
                    gap: 10px;
                }
            }
        </style>
        </head><body>
        ''')
        r.append('<div class="app-container">')
        r.append('<div class="header-section">')
        r.append('''
        <div class="header-bar">
            <div style="font-size: 0.9em; color: #00cc33;">> FTP SERVER ACTIVE</div>
            <button class="transfers-toggle" id="transfersToggle">Transfers (0)</button>
        </div>
        <div class="progress-container" id="progressContainer">
            <div class="transfer-info">
                <div class="transfer-filename" id="transferFilename">No active transfers</div>
                <div class="transfer-size" id="transferSize"></div>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="progress-text" id="progressText"></div>
        </div>
        ''')
        r.append('</div>')
        r.append('<div class="content-section">')
        r.append(f'<h2>Index of {displaypath}</h2><hr>')
        r.append('<table><tr><th class="icon"></th><th>Name</th><th class="size">Size</th></tr>')

        if displaypath != '/':
            up_icon = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ff41" stroke-width="1.5"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>'
            r.append(f'<tr onclick="window.location.href=\'..\'"><td class="icon">{up_icon}</td><td>[..]</td><td class="size">-</td></tr>')

        for name in entries:
            fullname = os.path.join(path, name)
            icon = self.get_icon(name, os.path.isdir(fullname))
            displayname = name + '/' if os.path.isdir(fullname) else name
            linkname = name + '/' if os.path.isdir(fullname) else name

            if os.path.isdir(fullname):
                size_str = "-"
            else:
                try:
                    size = os.path.getsize(fullname)
                    size_str = self.format_size(size)
                except OSError:
                    size_str = "?"

            r.append(f'<tr onclick="window.location.href=\'{linkname}\'"><td class="icon">{icon}</td><td>{displayname}</td><td class="size">{size_str}</td></tr>')

        r.append('</table><hr>')
        r.append('</div>')
        r.append('<div class="footer-section">')
        r.append('''
                    <div class="upload">
                <form enctype="multipart/form-data" method="post" id="uploadForm">
                    <label for="folderInput" class="file-upload">Upload Folder</label>
                    <input id="folderInput" name="file" type="file" webkitdirectory directory multiple style="display:none;">

                    <label for="fileInput" class="file-upload">Upload File(s)</label>
                    <input id="fileInput" name="file" type="file" multiple style="display:none;">

                    <input type="submit" value="Upload">
                </form>
            </div>
        ''')
        r.append('</div>')
        r.append('</div>')
        r.append('''
            <script>
                let activeTransfers = 0;

                function formatBytes(bytes) {
                    if (bytes === 0) return '0 B';
                    const k = 1024;
                    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
                }

                function updateTransfersButton() {
                    const toggle = document.getElementById("transfersToggle");
                    toggle.textContent = `Transfers (${activeTransfers})`;
                    if (activeTransfers > 0) {
                        toggle.classList.add("active");
                    } else {
                        toggle.classList.remove("active");
                    }
                }

                document.getElementById("transfersToggle").addEventListener("click", function() {
                    const progressContainer = document.getElementById("progressContainer");
                    progressContainer.classList.toggle("show");
                });

                // Touch feedback for mobile
                const touchElements = document.querySelectorAll('tr, label.file-upload, input[type=submit], .transfers-toggle');
                touchElements.forEach(el => {
                    el.addEventListener('touchstart', function() {
                        this.style.transform = 'scale(0.95)';
                    });
                    el.addEventListener('touchend', function() {
                        this.style.transform = '';
                    });
                });

                // Swipe gestures
                let touchStartY = 0;
                let touchEndY = 0;
                const contentSection = document.querySelector('.content-section');

                if (contentSection) {
                    contentSection.addEventListener('touchstart', e => {
                        touchStartY = e.changedTouches[0].screenY;
                    }, false);

                    contentSection.addEventListener('touchend', e => {
                        touchEndY = e.changedTouches[0].screenY;
                        handleSwipe();
                    }, false);

                    function handleSwipe() {
                        if (touchEndY < touchStartY - 50) {
                            // Swipe up - scroll to upload section
                            const uploadSection = document.querySelector('.upload');
                            if (uploadSection) {
                                uploadSection.scrollIntoView({ behavior: 'smooth' });
                            }
                        }
                        if (touchEndY > touchStartY + 50) {
                            // Swipe down - scroll to top
                            contentSection.scrollTo({ top: 0, behavior: 'smooth' });
                        }
                    }
                }

                function updateLabel(inputId, labelText) {
                    const input = document.getElementById(inputId);
                    const label = document.querySelector(`label[for=${inputId}]`);
                    input.addEventListener('change', () => {
                        const count = input.files.length;
                        label.textContent = count > 0 ? `${count} item(s) selected` : labelText;
                    });
                }
                updateLabel('fileInput', 'Upload File(s)');
                updateLabel('folderInput', 'Upload Folder');

                document.getElementById("uploadForm").addEventListener("submit", function(e) {
                    const folderFiles = document.getElementById("folderInput").files;
                    const fileFiles = document.getElementById("fileInput").files;
                    if (folderFiles.length === 0 && fileFiles.length === 0) {
                        e.preventDefault();
                        alert("Please select at least one file or folder to upload.");
                        return;
                    }

                    // Show progress bar
                    const progressContainer = document.getElementById("progressContainer");
                    const progressFill = document.getElementById("progressFill");
                    const progressText = document.getElementById("progressText");
                    const transferFilename = document.getElementById("transferFilename");
                    const transferSize = document.getElementById("transferSize");
                    progressContainer.classList.add("show");

                    // Get all selected files
                    const allFiles = folderFiles.length > 0 ? folderFiles : fileFiles;
                    const totalSize = Array.from(allFiles).reduce((sum, f) => sum + f.size, 0);
                    const fileCount = allFiles.length;
                    let displayName;
                    if (folderFiles.length > 0) {
                        displayName = fileCount === 1 ? "1 file (folder)" : `${fileCount} files (folder)`;
                    } else {
                        displayName = fileCount === 1 ? allFiles[0].name : `${fileCount} files`;
                    }

                    transferFilename.textContent = displayName;
                    transferSize.textContent = formatBytes(totalSize);
                    progressText.textContent = "0%";

                    // Use XMLHttpRequest for upload progress
                    e.preventDefault();
                    const formData = new FormData(this);
                    const xhr = new XMLHttpRequest();

                    activeTransfers++;
                    updateTransfersButton();

                    xhr.upload.addEventListener("progress", function(e) {
                        if (e.lengthComputable) {
                            const percentComplete = (e.loaded / e.total) * 100;
                            progressFill.style.width = percentComplete + "%";
                            progressText.textContent = Math.round(percentComplete) + "%";
                            transferSize.textContent = `${formatBytes(e.loaded)} / ${formatBytes(e.total)}`;
                        }
                    });

                    xhr.addEventListener("load", function() {
                        activeTransfers--;
                        updateTransfersButton();
                        if (xhr.status === 200) {
                            progressText.textContent = "Upload complete!";
                            transferSize.textContent = `${formatBytes(totalSize)} / ${formatBytes(totalSize)}`;
                            setTimeout(() => {
                                window.location.reload();
                            }, 1000);
                        } else {
                            progressText.textContent = "Upload failed!";
                            progressFill.style.backgroundColor = "#FF0000";
                        }
                    });

                    xhr.addEventListener("error", function() {
                        activeTransfers--;
                        updateTransfersButton();
                        progressText.textContent = "Upload error!";
                        progressFill.style.backgroundColor = "#FF0000";
                    });

                    xhr.open("POST", window.location.href);
                    xhr.send(formData);
                });


            </script>

                 </body></html>''')

        encoded = '\n'.join(r).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Client disconnected before response completed
            pass
        return None

    def get_icon(self, name, is_dir):
        if is_dir:
            return self.ICONS['folder']
        ext = os.path.splitext(name)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            return self.ICONS['image']
        elif ext in ['.mp4', '.mkv', '.avi', '.webm']:
            return self.ICONS['video']
        elif ext in ['.zip', '.rar', '.tar', '.gz', '.7z']:
            return self.ICONS['archive']
        else:
            return self.ICONS['file']

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                if unit == 'B':
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


def get_lan_ip_address():
    """
    Connects to an external service (Google DNS) to determine 
    the local machine's IP address on the active network interface.
    """
    s = None # Initialize s outside of try block
    try:
        # Create a UDP socket object
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Connect to a known external IP address (e.g., Google's public DNS: 8.8.8.8)
        # This doesn't send data, it just sets up the connection route.
        s.connect(("8.8.8.8", 80))
        
        # Get the IP address of the socket's connection endpoint (the local machine's IP)
        ip_address = s.getsockname()[0]
        
        return ip_address
    
    except socket.error as e:
        print(f"Error occurred: {e}")
        return "Could not determine LAN IP address"
        
    finally:
        # Close the socket cleanly if it was created
        if s:
            s.close()
