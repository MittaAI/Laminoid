import os
import json
import asyncio
import httpx
import shlex
import subprocess

from urllib.parse import urlparse
from werkzeug.utils import secure_filename
from quart import Quart, request, jsonify

app = Quart(__name__)

@app.route('/convert', methods=['POST'])
async def convert():
    data = await request.get_json()
    uid = data.get('uid')
    file_url = data.get('mitta_uri')
    callback_url = data.get('callback_url')
    ffmpeg_command = data.get('ffmpeg_command')
    output_file = data.get('output_file')

    # Creating user-specific directory
    user_dir = os.path.join("upload", uid)
    os.makedirs(user_dir, exist_ok=True)

    # Saving received data to data.json in the user's directory
    data_file_path = os.path.join(user_dir, 'data.json')
    with open(data_file_path, 'w') as file:
        json.dump(data, file)

    # Download the file
    local_file_path = await download_file(file_url, user_dir)

    try:
        # Processing with FFmpeg
        asyncio.create_task(run_ffmpeg(ffmpeg_command, user_dir, user_dir, uid))
        return jsonify({'result': 'success'})
    except:
        return jsonify({'result': 'failed'})

async def download_file(url, directory):
    local_filename = secure_filename(os.path.basename(urlparse(url).path))
    file_path = os.path.join(directory, local_filename)

    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)

        response.raise_for_status()  # Ensure the request was successful

        with open(file_path, 'wb') as f:
            async for chunk in response.aiter_bytes(chunk_size=8192):
                f.write(chunk)
    
    return file_path

def is_safe_filename(filename):
    # Check for dangerous characters or patterns
    return ".." not in filename and not filename.startswith('/')


async def run_ffmpeg(ffmpeg_command, user_directory, callback_url, uid):
    # Split the command string into arguments
    args = shlex.split(ffmpeg_command)

    # Check if the first argument is 'ffmpeg' and remove it if present
    if args[0] == 'ffmpeg':
        args = args[1:]

    # Change to the user directory
    original_directory = os.getcwd()
    os.chdir(user_directory)

    # Add 'ffmpeg' at the beginning of the command
    ffmpeg_command = ['ffmpeg'] + args

    try:
        subprocess.run(ffmpeg_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        await upload_file()
    except subprocess.CalledProcessError as e:
        with open('data.json', 'r') as file:
            data = json.load(file)
        callback_url = data.get('callback_url')
        
        # Remove data.json after reading
        os.remove('data.json')

        async with httpx.AsyncClient() as client:
            data = {'ffmpeg_result': "The request to convert the file failed."}
            response = await client.post(callback_url, data=data)

    finally:
        os.chdir(original_directory)


async def upload_file():
    # Read callback_url from data.json
    with open('data.json', 'r') as file:
        data = json.load(file)
    callback_url = data.get('callback_url')
    output_file = data.get('output_file')

    # Remove data.json after reading
    os.remove('data.json')

    async with httpx.AsyncClient() as client:
        with open(output_file, 'rb') as f:
            files = {'file': (os.path.basename(output_file), f)}
            data = {'filename': output_file}
            response = await client.post(callback_url, files=files, data=data)

        # Cleanup
        os.remove(output_file)

        if response.status_code != 200:
            print("Failed to upload the file to the callback URL.")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6969)

