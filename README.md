# Hacker-styled FTP Server

A simple HTTP file server with a hacker/terminal aesthetic, featuring file uploads and download capabilities.

## Features

- Hacker-styled terminal interface with green-on-black theme
- File browsing and downloads
- Multi-file and folder uploads
- Upload progress bar
- Security fixes (path traversal protection)
- Handles large files (chunked upload)
- No external dependencies (Python standard library only)

## Project Structure

```
Hacker-styled-FTP/
├── hacker_ftp/           # Package directory
│   ├── __init__.py       # Package initialization
│   ├── server.py         # HTTP server and handler implementation
│   └── main.py           # Main entry point
├── main.py               # Project entry point (runs hacker_ftp.main)
├── requirements.txt      # Dependencies (none - stdlib only)
└── README.md             # This file
```

## Installation

No installation required - uses only Python standard library.

## Usage

Run the server:

```bash
python main.py
```

You will be prompted to:
1. Choose directory to serve (current, Android storage, or custom path)
2. Enter port number (default: 8080)

The server will display:
- Local IP address
- URL to open in browser

## Security Fixes

- **Path traversal vulnerability fixed**: Added validation to prevent `..` in filenames
- **Absolute path validation**: Ensures uploaded files stay within upload directory
- **Content-Type header handling**: Fixed KeyError when header is missing
- **Chunked file reading**: Handles large files (tested with 500MB+ files)

## Browser Features

- Upload individual files or entire folders
- Real-time upload progress bar
- Visual file type icons (folder, file, image, video, archive)
- Responsive design for mobile devices
