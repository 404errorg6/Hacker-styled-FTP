import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote
import cgi
import socket


class HackerHTTPHandler(SimpleHTTPRequestHandler):
    ICONS = {
        'folder': '\u2554\u2550\u2550\u2550\u2557',
        'file': '\u250F\u2501\u2501\u2501\u2513',
        'image': '\u255A\u2550\u2665\u2550\u255D',
        'video': '\u255A\u2550\u25B6\u2550\u255D',
        'archive': '\u255A\u2550\u25A1\u2550\u255D'
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
            html { box-sizing: border-box; }
	*, *::before, *::after { box-sizing: inherit; }
body {
    background-color: black;
    color: #00FF00;
    font-family: monospace;
    margin: 0; padding: 1em;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}
a { color: #00FF00; text-decoration: none; }
a:hover { text-decoration: underline; }

table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border-bottom: 2px solid #006600; /* bottom border for entire table */
}

tr {
    display: block;
    border-bottom: 1px solid #006600; /* full width separator line */
    width: 100%;
    box-sizing: border-box;
}

th, td {
    border-bottom: none; /* remove cell borders */
    display: inline-block;
    vertical-align: middle;
}

th {
    width: 5ch; /* fixed width for icon column */
    font-weight: bold;
    text-align: center;
}

td:not(:first-child) {
    width: calc(100% - 5ch); /* rest of the width for filename */
    word-break: break-word;
    text-align: left;
    padding-left: 0.5em;
}

th {
    padding: 0.5em;
}

td {
    padding: 0.5em;
}

/* Responsive tweaks */
@media (max-width: 600px) {
    body {
        padding: 0.5em;
        font-size: 0.9em;
    }
    th, td {
        padding: 0.3em;
    }
    th {
        width: 3ch;
        font-size: 0.8em;
    }
    td:not(:first-child) {
        width: calc(100% - 3ch);
    }
}

/* Upload form styling */
.upload {
    margin-top: 1em;
    flex-direction: row;
    gap: 0.5em;
    padding: 1em;
    border: 1px solid #00FF00;
    background-color: #002200;
    max-width: 400px;
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
}

/* Progress bar styling */
.header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1em;
    padding: 0.5em;
    border: 1px solid #00FF00;
    background-color: #002200;
}

.transfers-toggle {
    background: black;
    border: 1px solid #00FF00;
    color: #00FF00;
    font-family: monospace;
    font-size: 1em;
    padding: 0.3em 1em;
    cursor: pointer;
    transition: background-color 0.2s, color 0.2s;
}

.transfers-toggle:hover {
    background-color: #00FF00;
    color: black;
}

.transfers-toggle.active {
    background-color: #00FF00;
    color: black;
}

.progress-container {
    width: 100%;
    max-width: 500px;
    margin-top: 1em;
    padding: 1em;
    border: 1px solid #00FF00;
    background-color: #002200;
    display: none;
}

.progress-container.show {
    display: block;
}

.transfer-info {
    margin-bottom: 0.5em;
    font-size: 0.9em;
}

.transfer-filename {
    font-weight: bold;
    margin-bottom: 0.3em;
    word-break: break-all;
}

.transfer-size {
    font-size: 0.85em;
    color: #00CC00;
}

.progress-bar {
    width: 100%;
    height: 20px;
    background-color: #001100;
    border: 1px solid #00FF00;
    position: relative;
}

.progress-fill {
    height: 100%;
    background-color: #00FF00;
    width: 0%;
    transition: width 0.3s ease;
}

.progress-text {
    margin-top: 0.5em;
    text-align: center;
    font-size: 0.9em;
}
input[type=file] {
    flex-grow: 1;
    background: black;
    border: 1px solid #00FF00;
    color: #00FF00;
    font-family: monospace;
    font-size: 1em;
    padding: 0.2em 0.5em;
    cursor: pointer;
}
input[type=file]::-webkit-file-upload-button,
input[type=file]::file-selector-button {
    visibility: hidden;
}
label.file-upload {
    background: black;
    border: 1px solid #00FF00;
    color: #00FF00;
    font-family: monospace;
    font-size: 1em;
    padding: 0.3em 1em;
    cursor: pointer;
    margin-left: 0.5em;
    user-select: none;
    transition: background-color 0.2s, color 0.2s;
}
label.file-upload:hover {
    background-color: #00FF00;
    color: black;
}
input[type=submit] {
    background: black;
    border: 1px solid #00FF00;
    color: #00FF00;
    font-family: monospace;
    font-size: 1em;
    padding: 0.3em 1em;
    cursor: pointer;
    margin-left: 0.5em;
    user-select: none;
    transition: background-color 0.2s, color 0.2s;
}
input[type=submit]:hover {
    background-color: #00FF00;
    color: black;
}
tr {
    display: flex;
    border-bottom: 1px solid #004400;
    padding: 0.2em 0.5em;
    transition: background-color 0.25s ease-in-out;
}

tr:hover {
    background-color: #002d00; /* darker green */
    border-left: 4px solid #00cc00;
    cursor: pointer;
}

a {
    color: #00FF00;
    text-decoration: none;
    width: 100%;
    display: inline-block;
    transition: background-color 0.4s ease-in-out, color 0.4s ease-in-out;
}





        </style>
        </head><body>
        ''')
        r.append('''
        <div class="header-bar">
            <div></div>
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
        r.append(f'<h2>Index of {displaypath}</h2><hr>')
        r.append('<table><tr><th class="icon">Type</th><th>Name</th></tr>')

        if displaypath != '/':
            r.append(f'<tr><td class="icon">{self.ICONS["folder"]}</td><td><a href="..">[..]</a></td></tr>')

        for name in entries:
            fullname = os.path.join(path, name)
            icon = self.get_icon(name, os.path.isdir(fullname))
            displayname = name + '/' if os.path.isdir(fullname) else name
            linkname = name + '/' if os.path.isdir(fullname) else name
            r.append(f'<tr><td class="icon">{icon}</td><td><a href="{linkname}">{displayname}</a></td></tr>')

        r.append('</table><hr>')
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
