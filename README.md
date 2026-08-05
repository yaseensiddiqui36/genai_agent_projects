# Clinical Knowledge Assistant

RAG app that answers medical questions using a set of
clinical documents as its only source of truth. Ask it something covered in the documents and
it'll answer with citations. 

Streamlit and a REST API (FastAPI) are integrated for the better exerience. 



## How to install:

You'll need Python 3.11+ and a free [Groq API key](https://console.groq.com/keys).

**1. Install the dependencies**

With `uv` :
```bash
uv sync
```
- If the above uv package doesnt work then use the pip installer:
Or with plain `pip`:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**2. Add your API key**

Create a `.env` file in the project root:
```
GROQ_API_KEY=your_groq_api_key_here
```
Optional settings if you want to change the embedding model and behaviour of retrival:
```
GROQ_MODEL=llama-3.3-70b-versatile
RAG_DISTANCE_THRESHOLD=1.6
```

**3. Run it**

With `uv`:
```bash
uv run python app.py
```
With a plain venv after activating it:
```bash
python app.py
```

The first run builds the vector store from the files in `data/`.

After that it opens the chat app in your browser at `http://localhost:8501`.


## Using your own documents

If you want to use different set of documents then just drop them into `data/` — PDF, TXT,
CSV, XLSX, DOCX, and JSON are all supported — and run `python app.py` again. 


## To ru differnt components seperately:


**Just to run with API:**
```bash
uvicorn src.api:app --reload
```


**Just to check the UI**:
```bash
streamlit run streamlit_app.py
```

**Docker** (runs both the API and the Streamlit UI):
```bash
docker build -t clinical-rag .
docker run --env-file .env -p 8000:8000 -p 8501:8501 clinical-rag
```
API is at `http://localhost:8000` and the UI is at `http://localhost:8501`.


## What's in the sample data

Five clinical documents :
(mentalhth.pdf), hypertension, type 2 diabetes, seasonal influenza, and cardiovascular risk
factors. Swap these out any time to Using your own documents 

## Evaluation Questions

1. **How is the mental health of adults in the USA?**
   Should be answered from mentalhth.pdf, with that file showing up in the sources.

2. **What lifestyle changes are recommended to manage Type 2 diabetes?**
   Comes from type2_diabetes.txt — expect stuff like diet, exercise, weight loss, cutting
   smoking/alcohol.

3. **What blood pressure target is recommended for adults with hypertension?**
   Comes from hypertension.txt — the answer should land on below 130/80 mmHg.

4. **How can seasonal influenza be prevented?**
   Comes from seasonal_influenza.txt — vaccination, hand hygiene, avoiding sick contacts.

5. **What is the recommended dosage of trastuzumab for HER2-positive breast cancer?**
   "I don't have enough information in the provided documents to answer that question."




