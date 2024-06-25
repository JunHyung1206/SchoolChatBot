import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from langchain_chroma import Chroma
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from prompt_template import template
from omegaconf import OmegaConf

conf = OmegaConf.load("api_key.yaml")
# Setup environment variables
os.environ['OPENAI_API_KEY'] = conf['openai_api_key']
DB_PATH = '../vector_DB'

# Initialize FastAPI
app = FastAPI()

# Define the Pydantic model for request body
class QueryRequest(BaseModel):
    query: str

# Initialize embedding function
embedding_function = SentenceTransformerEmbeddings(model_name="jhgan/ko-sroberta-multitask")

# Initialize Chroma DB
db = Chroma(
    persist_directory=DB_PATH,
    collection_name='school_docs',
    embedding_function=embedding_function
)

retriever = db.as_retriever(
    search_type="mmr",
    search_kwargs={
        # "score_threshold": 0.2,
        "k": 10,
        "fetch_k": 20
    }
)

# Initialize prompt template
prompt = ChatPromptTemplate.from_template(template)

# Initialize LLM
llm = ChatOpenAI(
    model='gpt-4o',
    temperature=0.2,
)

# Function to format documents
def format_docs(docs):
    page_content = []
    format_doc = ''
    for i,doc in enumerate(docs):
        format_doc = f"context{i+1}:{doc.metadata['title']} \ndate: {doc.metadata['date']} \nurl: {doc.metadata['url']} \n{doc.page_content}"
        page_content.append(format_doc)

    return '\n\n\n'.join(page_content)

# Initialize chain
chain = prompt | llm | StrOutputParser()

@app.post("/query")
async def handle_query(request: QueryRequest):
    query = request.query
    docs = retriever.get_relevant_documents(query)
    
    if not docs:
        raise HTTPException(status_code=404, detail="No relevant documents found")
    now = datetime.datetime.now()
    date = now.date().isoformat()
    response = chain.invoke({'context': format_docs(docs), 'question': query, 'date':date})
    return {"response": response}

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
