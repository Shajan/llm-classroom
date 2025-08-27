# RAG Chat Application

This folder contains a Retrieval-Augmented Generation (3. **Ask Questions**: Chat with your knowledge base using natural language
4. **Model Selection**: Choose different OpenAI models for varying response quality

## Running from Parent Directory

The application is designed to work when run from the parent directory:

```bash
# From llm-classroom/ directory
streamlit run 4/rag_app.py
```

All paths are automatically resolved correctly regardless of the working directory.G) chat application built with Streamlit. The application allows users to upload documents or provide URLs, builds a vector database from the content, and then uses this knowledge base to provide contextual answers to user questions.

## Features

- **Document Upload**: Support for PDF, TXT, and DOCX files
- **URL Content**: Fetch and process content from web URLs
- **Vector Database**: Uses ChromaDB for efficient semantic search
- **RAG-based Chat**: Combines retrieved context with LLM responses
- **Multiple Models**: Support for various OpenAI models
- **Real-time Processing**: Documents are processed and indexed in real-time

## Architecture

### Components

1. **DocumentProcessor**: Handles text extraction from various file formats
   - PDF processing using PyPDF2
   - DOCX processing using python-docx
   - URL content fetching using requests

2. **VectorStore**: Manages the vector database operations
   - Uses ChromaDB for persistence
   - Sentence Transformers for embeddings (all-MiniLM-L6-v2)
   - Text chunking with overlap for better retrieval

3. **RAGChat**: Implements the RAG pipeline
   - Semantic search for relevant context
   - Context-aware prompt construction
   - OpenAI API integration for response generation

### RAG Pipeline

1. **Document Ingestion**:
   - Extract text from uploaded files or URLs
   - Split text into overlapping chunks (1000 words with 200-word overlap)
   - Generate embeddings using Sentence Transformers
   - Store in ChromaDB vector database

2. **Query Processing**:
   - User submits a question
   - Generate query embedding
   - Search vector database for relevant chunks (top 3)
   - Combine retrieved context with user query

3. **Response Generation**:
   - Send context-enhanced prompt to OpenAI
   - Generate response based on retrieved knowledge
   - Display response to user

## Setup

1. Install dependencies:
   ```bash
   pip install -r 4/requirements.txt
   ```

2. Set up environment variables:
   Create a `.env` file in the parent directory with:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

3. Run the application:
   ```bash
   # From parent directory (recommended)
   streamlit run 4/rag_app.py
   
   # Or from the 4/ directory
   cd 4/
   streamlit run rag_app.py
   ```

**Generated Files:** The application will create:
- `chroma_db/` directory - Vector database storage (persisted between sessions)
- `rag_app.log` file - Detailed application logs

These files are automatically excluded from git tracking.

## Usage

1. **Upload Documents**: Use the sidebar to upload PDF, TXT, or DOCX files
2. **Add URLs**: Enter URLs to fetch and process web content
3. **Monitor Knowledge Base**: Check the statistics to see how many documents are indexed
4. **Ask Questions**: Chat with your knowledge base using natural language
5. **Model Selection**: Choose different OpenAI models for varying response quality

## Technical Details

### Embedding Model
- Uses `all-MiniLM-L6-v2` from Sentence Transformers
- 384-dimensional embeddings
- Good balance between speed and quality

### Vector Database
- ChromaDB for local persistence
- Cosine similarity for semantic search
- Metadata storage for document tracking

### Text Processing
- Chunk size: 1000 words
- Overlap: 200 words
- Preserves context across chunk boundaries

### Supported File Types
- **PDF**: Text extraction using PyPDF2
- **DOCX**: Document processing using python-docx
- **TXT**: Plain text files
- **URLs**: Web content fetching

## Limitations

- Only processes text content (no images or tables)
- Requires OpenAI API key for chat functionality
- Local storage only (ChromaDB persists to disk)
- Single collection for all documents

## Future Enhancements

- Support for more file formats (CSV, HTML, Markdown)
- Document deletion and management
- Advanced chunking strategies
- Multiple collections/namespaces
- Citation and source tracking
- Conversation memory beyond single session
