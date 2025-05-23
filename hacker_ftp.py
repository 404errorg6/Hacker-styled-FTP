
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote
import cgi

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
            super().do_GET()

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
                    background-color: black; color: #00FF00;
                    font-family: monospace; padding: 1em;
                }}
                a {{ color: #00FF00; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h2>{info}</h2>
            <a href="..">Back to directory</a>
        </body>
        </html>
        """
        self.wfile.write(response.encode('utf-8'))

    def deal_post_data(self):
        content_type = self.headers.get('Content-Type')
        if not content_type:
            return False, "No Content-Type header"

        ctype, pdict = cgi.parse_header(content_type)
        if ctype != 'multipart/form-data':
            return False, "Content-Type not multipart/form-data"

        pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
        pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])
        try:
            fields = cgi.parse_multipart(self.rfile, pdict)
        except Exception as e:
            return False, f"Error parsing multipart data: {e}"

        if 'file' not in fields:
            return False, "No file field in form"

        file_data = fields['file'][0]
        filename = self.get_filename(fields)
        if not filename:
            return False, "No filename provided"

        dest_path = os.path.join(os.getcwd(), filename)
        try:
            with open(dest_path, 'wb') as f:
                f.write(file_data)
        except Exception as e:
            return False, f"Failed to save file: {e}"

        return True, f"File '{filename}' uploaded successfully."

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

        </style>
        </head><body>
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
                <label for="fileInput" class="file-upload">Choose File</label>
                <input id="fileInput" name="file" type="file" required style="display:none;">
                <input type="submit" value="Upload File">
            </form>
        </div>
        <script>
            const fileInput = document.getElementById('fileInput');
            const fileLabel = document.querySelector('label.file-upload');
            fileInput.addEventListener('change', () => {
                fileLabel.textContent = fileInput.files.length > 0 ? fileInput.files[0].name : 'Choose File';
            });
        </script>
        </body></html>''')

        encoded = '\n'.join(r).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
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

def run():
    import sys
    print("Choose directory to serve:")
    print("1) Current directory")
    print("2) /storage/emulated/0 (Android default storage)")
    print("3) Custom path")
    choice = input("Enter choice (1/2/3): ").strip() or "1"

    if choice == '1':
        serve_path = '.'
    elif choice == '2':
        serve_path = '/storage/emulated/0'
    elif choice == '3':
        serve_path = input("Enter full custom path: ").strip()
        if serve_path == '':
            print("Empty path, exiting.")
            sys.exit(1)
    else:
        print("Invalid choice, exiting.")
        sys.exit(1)

    if not os.path.isdir(serve_path):
        print(f"Error: {serve_path} is not a directory.")
        sys.exit(1)

    port_input = input("Enter port number (default 8080): ").strip()
    port = int(port_input) if port_input.isdigit() else 8080
    os.chdir(os.path.abspath(serve_path))

    print(f"Serving directory: {os.getcwd()}")
    print(f"Starting server on port {port}...")
    server_address = ('', port)
    httpd = HTTPServer(server_address, HackerHTTPHandler)
    print(f"Open in browser: http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == '__main__':
    run()
