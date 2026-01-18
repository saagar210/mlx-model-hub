# LangChain Document Loading

LangChain provides a unified interface for loading documents from various sources through its DocumentLoader system.

## Core Concepts

### Document Class

The base unit in LangChain is the `Document`:

```python
from langchain_core.documents import Document

doc = Document(
    page_content="The actual text content",
    metadata={
        "source": "file.pdf",
        "page": 1,
        "author": "John Doe"
    }
)
```

### DocumentLoader Interface

All loaders implement a common interface:

```python
from langchain_community.document_loaders import TextLoader

loader = TextLoader("path/to/file.txt")
documents = loader.load()  # Returns list[Document]

# Lazy loading for large files
for doc in loader.lazy_load():
    process(doc)
```

## Common Document Loaders

### Text Files

```python
from langchain_community.document_loaders import TextLoader

loader = TextLoader("document.txt", encoding="utf-8")
docs = loader.load()
```

### PDF Files

```python
from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader("document.pdf")
docs = loader.load()  # One Document per page

# With page numbers
for doc in docs:
    print(f"Page {doc.metadata['page']}: {doc.page_content[:100]}")
```

### Web Pages

```python
from langchain_community.document_loaders import WebBaseLoader

loader = WebBaseLoader("https://example.com/article")
docs = loader.load()
```

### CSV Files

```python
from langchain_community.document_loaders import CSVLoader

loader = CSVLoader("data.csv")
docs = loader.load()  # One Document per row
```

### JSON Files

```python
from langchain_community.document_loaders import JSONLoader

loader = JSONLoader(
    file_path="data.json",
    jq_schema=".messages[]",  # Extract specific fields
    text_content=False
)
docs = loader.load()
```

### Directories

```python
from langchain_community.document_loaders import DirectoryLoader

loader = DirectoryLoader(
    "path/to/docs/",
    glob="**/*.md",  # Pattern matching
    loader_cls=TextLoader
)
docs = loader.load()
```

### YouTube Transcripts

```python
from langchain_community.document_loaders import YoutubeLoader

loader = YoutubeLoader.from_youtube_url(
    "https://www.youtube.com/watch?v=VIDEO_ID",
    add_video_info=True
)
docs = loader.load()
```

### Notion

```python
from langchain_community.document_loaders import NotionDirectoryLoader

loader = NotionDirectoryLoader("path/to/notion/export")
docs = loader.load()
```

### Google Drive

```python
from langchain_community.document_loaders import GoogleDriveLoader

loader = GoogleDriveLoader(
    folder_id="FOLDER_ID",
    credentials_path="credentials.json"
)
docs = loader.load()
```

## Document Transformers

After loading, documents often need processing.

### Text Splitting

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", " ", ""]
)

# Split loaded documents
split_docs = splitter.split_documents(docs)
```

### Markdown Splitting

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter

headers_to_split_on = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on
)
split_docs = splitter.split_text(markdown_text)
```

### Code Splitting

```python
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

python_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON,
    chunk_size=1000,
    chunk_overlap=200
)

split_docs = python_splitter.split_documents(docs)
```

## Complete RAG Pipeline Example

```python
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# 1. Load documents
loader = DirectoryLoader(
    "docs/",
    glob="**/*.pdf",
    loader_cls=PyPDFLoader
)
documents = loader.load()

# 2. Split into chunks
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
chunks = splitter.split_documents(documents)

# 3. Create embeddings and store
embeddings = OpenAIEmbeddings()
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db"
)

# 4. Query
results = vectorstore.similarity_search("your query", k=5)
```

## Custom Document Loader

```python
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from typing import Iterator

class CustomLoader(BaseLoader):
    def __init__(self, file_path: str):
        self.file_path = file_path

    def lazy_load(self) -> Iterator[Document]:
        """Lazily load documents."""
        with open(self.file_path) as f:
            for line_number, line in enumerate(f):
                yield Document(
                    page_content=line.strip(),
                    metadata={
                        "source": self.file_path,
                        "line": line_number
                    }
                )

    def load(self) -> list[Document]:
        """Load all documents."""
        return list(self.lazy_load())
```

## Best Practices

1. **Use lazy_load() for large files**: Prevents memory issues
2. **Preserve metadata**: Include source, page numbers, timestamps
3. **Choose appropriate chunk sizes**: 500-1500 characters typical for RAG
4. **Use semantic chunking when possible**: Split on logical boundaries
5. **Handle encoding**: Specify encoding for text files

## References

- LangChain Document Loaders: https://python.langchain.com/docs/modules/data_connection/document_loaders/
- LangChain Text Splitters: https://python.langchain.com/docs/modules/data_connection/document_transformers/
