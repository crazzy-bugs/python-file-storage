import os
import sqlite3
import uuid
import mimetypes
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, abort

app = Flask(__name__)

# Configuration
STORAGE_DIR = './storage'
DB_FILE = './metadata.db'

# Ensure storage directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)

# Initialize SQLite Database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            filename TEXT,
            filepath TEXT,
            timestamp TEXT,
            size INTEGER,
            mimetype TEXT,
            status TEXT DEFAULT 'unscanned',
            secure BOOLEAN DEFAULT FALSE,
            result TEXT DEFAULT '{}',
            final_result TEXT DEFAULT 'unknown'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Helper Functions
def generate_file_id():
    return str(uuid.uuid4())

def get_file_metadata(file_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id=?", (file_id,))
    result = c.fetchone()
    conn.close()
    return result

def save_metadata(metadata):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO files (id, filename, filepath, timestamp, size, mimetype, status, secure, result, final_result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        metadata['id'], metadata['filename'], metadata['filepath'], metadata['timestamp'],
        metadata['size'], metadata['mimetype'], metadata['status'], metadata['secure'],
        str(metadata['result']), metadata['final_result']
    ))
    conn.commit()
    conn.close()

# API Endpoints
@app.route('/files', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Generate a unique ID and prepare paths
    file_id = generate_file_id()
    filename = file.filename
    dir_path = os.path.join(STORAGE_DIR, file_id)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, filename)

    # Save the file
    file.save(filepath)

    # Extract metadata
    metadata = {
        'id': file_id,
        'filename': filename,
        'filepath': filepath,
        'timestamp': datetime.utcnow().isoformat(),
        'size': os.path.getsize(filepath),
        'mimetype': mimetypes.guess_type(filepath)[0] or 'application/octet-stream',
        'status': 'unscanned',
        'secure': False,
        'result': {},
        'final_result': 'unknown'
    }

    # Save metadata to the database
    save_metadata(metadata)

    return jsonify({'message': 'File uploaded', 'metadata': metadata}), 201

@app.route('/files/<file_id>', methods=['GET'])
def get_file(file_id):
    metadata = get_file_metadata(file_id)
    if not metadata:
        return jsonify({'error': 'File not found'}), 404

    filepath = metadata[2]  # filepath is the 3rd column in the DB
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found on disk'}), 404

    return send_from_directory(os.path.dirname(filepath), os.path.basename(filepath))

@app.route('/files/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    metadata = get_file_metadata(file_id)
    if not metadata:
        return jsonify({'error': 'File not found'}), 404

    filepath = metadata[2]
    if os.path.exists(filepath):
        os.remove(filepath)

    # Remove metadata from the database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM files WHERE id=?", (file_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'File deleted'}), 200

@app.route('/files/<file_id>/info', methods=['GET'])
def file_info(file_id):
    metadata = get_file_metadata(file_id)
    if not metadata:
        return jsonify({'error': 'Metadata not found'}), 404

    # Convert DB row to JSON
    metadata_dict = {
        'id': metadata[0],
        'filename': metadata[1],
        'filepath': metadata[2],
        'timestamp': metadata[3],
        'size': metadata[4],
        'mimetype': metadata[5],
        'status': metadata[6],
        'secure': bool(metadata[7]),
        'result': eval(metadata[8]),
        'final_result': metadata[9]
    }

    return jsonify(metadata_dict), 200

@app.route('/files/<file_id>', methods=['PUT'])
def update_file(file_id):
    metadata = get_file_metadata(file_id)
    if not metadata:
        return jsonify({'error': 'File not found'}), 404

    # Parse updates from request JSON
    updates = request.json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE files
        SET status = COALESCE(?, status),
            secure = COALESCE(?, secure),
            result = COALESCE(?, result),
            final_result = COALESCE(?, final_result)
        WHERE id = ?
    ''', (
        updates.get('status'),
        updates.get('secure'),
        str(updates.get('result')),
        updates.get('final_result'),
        file_id
    ))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Metadata updated'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
