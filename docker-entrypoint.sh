#!/bin/sh
set -e

python -c "
import app
if app.vector_store_needs_build():
    app.build_vector_store()
"

uvicorn src.api:app --host 0.0.0.0 --port 8000 &
exec streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
