import requests
import os

FILE_PATH = "https://images.unsplash.com/photo-1719937206491-ed673f64be1f?q=80&w=1974&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDF8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"


def download_file(download_path, dir_name, file_name):
    print("Downloading file...")
    response = requests.get(FILE_PATH)
    os.makedirs("./downloads" + dir_name, exist_ok=True)
    save_to = f"./downloads/{dir_name}/{file_name}"
    with open(f"./downloads/image.jpg", "wb") as file:
        file.write(response.content)
