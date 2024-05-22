from langchain_chroma import Chroma
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


DB_PATH = './vector_DB'

loader = CSVLoader(file_path='../datasets/datasets.csv', encoding= 'utf8', metadata_columns = ['id', 'title', 'category', 'url', 'source', 'date'] )
documents = loader.load()

text_splitter = RecursiveCharacterTextSplitter(chunk_size = 1000, chunk_overlap=200)
docs = text_splitter.split_documents(documents)

# create the open-source embedding function
embedding_function = SentenceTransformerEmbeddings(model_name="jhgan/ko-sroberta-multitask")

# load it into Chroma
db = Chroma.from_documents(
    docs,
    embedding_function,
    collection_name = 'school_docs',
    persist_directory=DB_PATH
    )