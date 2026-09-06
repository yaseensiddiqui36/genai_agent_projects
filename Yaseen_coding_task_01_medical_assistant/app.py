"""Run this file to start the Clinical Knowledge Assistant.

It checks the data/ folder for new files, builds or rebuilds the vector store if needed,
then launches the Streamlit app in your browser. No other commands required.
"""
import os
import subprocess
import sys

from src.data_loader import load_all_documents
from src.vectorstore import FaissVectorStore

DATA_DIR = "data"
STORE_DIR = "faiss_store"
FILES_SNAPSHOT = os.path.join(STORE_DIR, "data_files.txt")


def list_data_files():
    return sorted(os.listdir(DATA_DIR))


def vector_store_needs_build():
    index_file = os.path.join(STORE_DIR, "faiss.index")
    meta_file = os.path.join(STORE_DIR, "metadata.pkl")

    if not os.path.exists(index_file) or not os.path.exists(meta_file):
        return True

    if not os.path.exists(FILES_SNAPSHOT):
        return True

    with open(FILES_SNAPSHOT) as f:
        files_used_last_time = f.read().splitlines()

    return files_used_last_time != list_data_files()


def build_vector_store():
    print("New or missing data found, building the vector store. This can take a minute...", flush=True)
    docs = load_all_documents(DATA_DIR)
    store = FaissVectorStore(STORE_DIR)
    store.build_from_documents(docs)

    with open(FILES_SNAPSHOT, "w") as f:
        f.write("\n".join(list_data_files()))

    print("Vector store is ready.", flush=True)


def main():
    if vector_store_needs_build():
        build_vector_store()
    else:
        print("Vector store is already up to date, skipping rebuild.", flush=True)

    print("Starting the app, your browser should open shortly...", flush=True)
    subprocess.run([sys.executable, "-m", "streamlit", "run", "streamlit_app.py"])


if __name__ == "__main__":
    main()
