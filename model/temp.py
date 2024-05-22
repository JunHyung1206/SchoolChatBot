from langchain_chroma import Chroma
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_text_splitters import CharacterTextSplitter


DB_PATH = './vector_DB'

embedding_function = SentenceTransformerEmbeddings(model_name="jhgan/ko-sroberta-multitask")

db = Chroma(
    persist_directory=DB_PATH,
    collection_name = 'school_docs',
    embedding_function=embedding_function
    )

query = "학과 특식"
docs = db.similarity_search(query)
print(docs[0])