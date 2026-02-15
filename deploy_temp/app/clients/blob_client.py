from azure.storage.blob import BlobServiceClient
from typing import Optional


class BlobClient:
    def __init__(self, connection_string: str):
        self.service = BlobServiceClient.from_connection_string(connection_string)

    def upload_text(self, container: str, blob_name: str, text: str) -> str:
        container_client = self.service.get_container_client(container)
        try:
            container_client.create_container()
        except Exception:
            pass
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(text, overwrite=True)
        return blob_client.url


