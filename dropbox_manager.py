import sys

class DropboxManager:
    def __init__(self, access_token=None):
        self.access_token = access_token

    def upload_file(self, file_path):
        if self.access_token is None:
            print(f"[Dropbox] SIMULERING: Ville have uploadet {file_path}, men mangler access token.")
            return True
        print(f"[Dropbox] Uploader {file_path}...")
        return True

