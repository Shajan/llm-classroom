import streamlit as st
import openai
import os
import requests
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any
import chromadb
import uuid
from sentence_transformers import SentenceTransformer
import PyPDF2
import docx
from io import BytesIO
import pandas as pd
import logging
from datetime import datetime

# Load environment variables from parent directory
# Handle both running from 4/ directory and from parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(parent_dir, ".env")
load_dotenv(env_path)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(current_dir, 'rag_app.log'))
    ]
)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Handle document processing and text extraction."""
    
    @staticmethod
    def extract_text_from_pdf(file_content: bytes) -> str:
        """Extract text from PDF file."""
        try:
            logger.info("🔍 Starting PDF text extraction")
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            text = ""
            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += page_text + "\n"
                logger.info(f"📄 Extracted {len(page_text)} characters from page {i+1}")
            
            total_chars = len(text)
            logger.info(f"✅ PDF extraction complete: {total_chars} total characters, {len(pdf_reader.pages)} pages")
            return text
        except Exception as e:
            logger.error(f"❌ Error reading PDF: {str(e)}")
            st.error(f"Error reading PDF: {str(e)}")
            return ""
    
    @staticmethod
    def extract_text_from_docx(file_content: bytes) -> str:
        """Extract text from DOCX file."""
        try:
            logger.info("🔍 Starting DOCX text extraction")
            doc = docx.Document(BytesIO(file_content))
            text = ""
            paragraph_count = 0
            for paragraph in doc.paragraphs:
                para_text = paragraph.text
                text += para_text + "\n"
                if para_text.strip():  # Only count non-empty paragraphs
                    paragraph_count += 1
            
            total_chars = len(text)
            logger.info(f"✅ DOCX extraction complete: {total_chars} characters, {paragraph_count} paragraphs")
            return text
        except Exception as e:
            logger.error(f"❌ Error reading DOCX: {str(e)}")
            st.error(f"Error reading DOCX: {str(e)}")
            return ""
    
    @staticmethod
    def extract_text_from_txt(file_content: bytes) -> str:
        """Extract text from TXT file."""
        try:
            logger.info("🔍 Starting TXT text extraction")
            text = file_content.decode('utf-8')
            logger.info(f"✅ TXT extraction complete: {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"❌ Error reading TXT: {str(e)}")
            st.error(f"Error reading TXT: {str(e)}")
            return ""
    
    @staticmethod
    def fetch_url_content(url: str) -> str:
        """Fetch content from URL."""
        try:
            logger.info(f"🌐 Fetching content from URL: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            content = response.text
            logger.info(f"✅ URL fetch complete: {len(content)} characters from {url}")
            return content
        except Exception as e:
            logger.error(f"❌ Error fetching URL {url}: {str(e)}")
            st.error(f"Error fetching URL content: {str(e)}")
            return ""

class VectorStore:
    """Handle vector database operations using ChromaDB."""
    
    def __init__(self):
        # Initialize ChromaDB client with absolute path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "chroma_db")
        
        logger.info(f"🗄️ Initializing ChromaDB at: {db_path}")
        
        # Use PersistentClient for proper persistence in ChromaDB 1.0+
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Get or create collection
        self.collection_name = "rag_documents"
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
            existing_count = self.collection.count()
            logger.info(f"📚 Connected to existing collection '{self.collection_name}' with {existing_count} documents")
        except:
            self.collection = self.client.create_collection(name=self.collection_name)
            logger.info(f"📚 Created new collection '{self.collection_name}'")
        
        # Initialize embedding model
        logger.info("🧠 Loading embedding model: all-MiniLM-L6-v2")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("✅ Embedding model loaded successfully")
    
    def add_document(self, text: str, metadata: Dict[str, Any]) -> None:
        """Add document to vector store."""
        try:
            source = metadata.get('source', 'unknown')
            logger.info(f"📝 Starting document processing for: {source}")
            logger.info(f"📊 Document metadata: {metadata}")
            logger.info(f"📏 Document length: {len(text)} characters")
            
            # Split text into chunks
            chunks = self._split_text(text)
            logger.info(f"✂️ Split document into {len(chunks)} chunks")
            
            added_chunks = 0
            for i, chunk in enumerate(chunks):
                # Generate embedding
                logger.info(f"🧠 Generating embedding for chunk {i+1}/{len(chunks)} (length: {len(chunk)} chars)")
                embedding = self.embedding_model.encode(chunk).tolist()
                
                # Create unique ID
                doc_id = f"{metadata.get('source', 'unknown')}_{i}_{uuid.uuid4().hex[:8]}"
                
                # Enhanced metadata with chunk info
                chunk_metadata = {
                    **metadata, 
                    "chunk_id": i,
                    "chunk_length": len(chunk),
                    "total_chunks": len(chunks),
                    "timestamp": datetime.now().isoformat(),
                    "embedding_model": "all-MiniLM-L6-v2"
                }
                
                logger.info(f"💾 Adding chunk to ChromaDB:")
                logger.info(f"   📍 ID: {doc_id}")
                logger.info(f"   📄 Text preview: {chunk[:100]}...")
                logger.info(f"   🏷️ Metadata: {chunk_metadata}")
                logger.info(f"   🔢 Embedding dimensions: {len(embedding)}")
                
                # Add to collection
                self.collection.add(
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[chunk_metadata],
                    ids=[doc_id]
                )
                
                added_chunks += 1
                logger.info(f"✅ Successfully added chunk {i+1}/{len(chunks)} to ChromaDB")
            
            # Final summary
            logger.info(f"🎉 Document processing complete for '{source}':")
            logger.info(f"   📊 Total chunks added: {added_chunks}")
            logger.info(f"   📏 Average chunk length: {len(text) // len(chunks) if chunks else 0} chars")
            
            # Update collection stats
            total_docs = self.collection.count()
            logger.info(f"📚 Collection now contains {total_docs} total chunks")
            
            st.success(f"✅ Added {len(chunks)} chunks from {source}")
            
        except Exception as e:
            error_msg = f"Error adding document to vector store: {str(e)}"
            logger.error(f"❌ {error_msg}")
            st.error(error_msg)
    
    def search(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Search for relevant documents."""
        try:
            logger.info(f"🔍 Starting search for query: '{query}'")
            logger.info(f"🎯 Requesting {n_results} results")
            
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            logger.info(f"🧠 Generated query embedding (dimensions: {len(query_embedding)})")
            
            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            logger.info(f"📊 Search results summary:")
            logger.info(f"   📄 Found {len(results['documents'][0])} documents")
            
            # Format results
            formatted_results = []
            for i in range(len(results['documents'][0])):
                distance = results['distances'][0][i] if 'distances' in results else None
                result = {
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': distance
                }
                formatted_results.append(result)
                
                # Log each result
                source = result['metadata'].get('source', 'unknown')
                chunk_id = result['metadata'].get('chunk_id', 'unknown')
                distance_str = f"{distance:.4f}" if distance is not None else 'N/A'
                logger.info(f"   🔗 Result {i+1}: {source} (chunk {chunk_id}), distance: {distance_str}")
                logger.info(f"      📝 Text preview: {result['text'][:150]}...")
            
            logger.info(f"✅ Search complete, returning {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            error_msg = f"Error searching vector store: {str(e)}"
            logger.error(f"❌ {error_msg}")
            st.error(error_msg)
            return []
    
    def _split_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        logger.info(f"✂️ Splitting text into chunks (size: {chunk_size}, overlap: {overlap})")
        
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
                logger.info(f"   📄 Chunk {len(chunks)}: {len(chunk)} chars, words {i+1}-{min(i+chunk_size, len(words))}")
        
        logger.info(f"✅ Text splitting complete: {len(chunks)} chunks created from {len(words)} words")
        return chunks
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        try:
            count = self.collection.count()
            logger.info(f"📊 Collection statistics: {count} total chunks")
            
            # Get some sample metadata to show sources
            if count > 0:
                sample_results = self.collection.get(limit=min(10, count))
                sources = set()
                for metadata in sample_results['metadatas']:
                    if 'source' in metadata:
                        sources.add(metadata['source'])
                
                logger.info(f"📚 Unique sources in collection: {list(sources)}")
                return {
                    "document_count": count,
                    "unique_sources": list(sources),
                    "total_sources": len(sources)
                }
            else:
                return {"document_count": 0, "unique_sources": [], "total_sources": 0}
        except Exception as e:
            logger.error(f"❌ Error getting collection stats: {str(e)}")
            return {"document_count": 0, "unique_sources": [], "total_sources": 0}

class RAGChat:
    """Handle RAG-based chat functionality."""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def get_response(self, query: str, model: str = "gpt-4o-mini") -> str:
        """Get RAG-enhanced response."""
        try:
            logger.info(f"🤖 Starting RAG response generation")
            logger.info(f"   📝 Query: {query}")
            logger.info(f"   🧠 Model: {model}")
            
            # Search for relevant context
            relevant_docs = self.vector_store.search(query, n_results=3)
            
            if not relevant_docs:
                logger.warning("⚠️ No relevant documents found for query")
                return "I don't have enough relevant information in my knowledge base to answer that question. Please upload relevant documents or provide URLs with the information you're looking for."
            
            # Build context from relevant documents
            context_parts = []
            for i, doc in enumerate(relevant_docs):
                source = doc['metadata'].get('source', 'Unknown source')
                chunk_id = doc['metadata'].get('chunk_id', 'Unknown')
                context_parts.append(f"Source {i+1} ({source}, chunk {chunk_id}):\n{doc['text']}")
            
            context = "\n\n".join(context_parts)
            logger.info(f"📚 Built context from {len(relevant_docs)} documents:")
            for i, doc in enumerate(relevant_docs):
                source = doc['metadata'].get('source', 'Unknown')
                distance = doc.get('distance', None)
                similarity_str = f"{1-distance:.3f}" if distance is not None else 'N/A'
                logger.info(f"   📖 {i+1}. {source} (similarity: {similarity_str})")
            
            # Create system prompt with context
            system_prompt = f"""You are a helpful assistant that answers questions based on the provided context. 
            Use the context below to answer the user's question accurately and concisely. If the context doesn't 
            contain enough information to answer the question, say so clearly and suggest what additional 
            information might be needed.

            Context:
            {context}
            """
            
            logger.info(f"📤 Sending request to OpenAI with {len(context)} context characters")
            
            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            logger.info(f"✅ Received response from OpenAI ({len(answer)} characters)")
            logger.info(f"💬 Response preview: {answer[:150]}...")
            
            return answer
            
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return error_msg

def get_available_models() -> List[str]:
    """Get list of available OpenAI models."""
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        models = client.models.list()
        
        chat_models = []
        for model in models.data:
            model_id = model.id
            if any(keyword in model_id.lower() for keyword in ["gpt", "o1"]):
                chat_models.append(model_id)
        
        chat_models.sort(reverse=True)
        return chat_models
    except Exception as e:
        st.error(f"Error fetching models: {str(e)}")
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
        logger.info("💬 Initialized empty message history")
    
    if "vector_store" not in st.session_state:
        logger.info("🗄️ Initializing vector store...")
        st.session_state.vector_store = VectorStore()
        logger.info("✅ Vector store initialized")
    
    if "rag_chat" not in st.session_state:
        logger.info("🤖 Initializing RAG chat...")
        st.session_state.rag_chat = RAGChat(st.session_state.vector_store)
        logger.info("✅ RAG chat initialized")
    
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = None

def main():
    logger.info("🚀 Starting RAG Chat Application")
    
    st.set_page_config(
        page_title="RAG Chat Application",
        page_icon="📚",
        layout="wide"
    )
    
    st.title("📚 RAG Chat Application")
    st.markdown("Upload documents or provide URLs, then chat with your knowledge base!")
    
    # Initialize session state
    logger.info("⚙️ Initializing application state")
    initialize_session_state()
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OpenAI API key not found in environment variables")
        st.error("⚠️ OpenAI API key not found! Please add your API key to the `.env` file in the parent directory.")
        st.stop()
    else:
        logger.info("✅ OpenAI API key found")
    
    # Sidebar for document management and settings
    with st.sidebar:
        st.header("📄 Document Management")
        
        # File upload section
        st.subheader("Upload Files")
        uploaded_files = st.file_uploader(
            "Choose files",
            accept_multiple_files=True,
            type=['pdf', 'txt', 'docx'],
            help="Upload PDF, TXT, or DOCX files"
        )
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                if st.button(f"Process {uploaded_file.name}", key=f"process_{uploaded_file.name}"):
                    logger.info(f"🚀 User initiated processing of file: {uploaded_file.name}")
                    logger.info(f"📁 File details - Name: {uploaded_file.name}, Type: {uploaded_file.type}, Size: {uploaded_file.size} bytes")
                    
                    with st.spinner(f"Processing {uploaded_file.name}..."):
                        file_content = uploaded_file.read()
                        
                        # Extract text based on file type
                        if uploaded_file.type == "application/pdf":
                            logger.info(f"📄 Processing as PDF file")
                            text = DocumentProcessor.extract_text_from_pdf(file_content)
                        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                            logger.info(f"📝 Processing as DOCX file")
                            text = DocumentProcessor.extract_text_from_docx(file_content)
                        else:  # txt file
                            logger.info(f"📃 Processing as TXT file")
                            text = DocumentProcessor.extract_text_from_txt(file_content)
                        
                        if text.strip():
                            # Add to vector store
                            metadata = {
                                "source": uploaded_file.name,
                                "type": "file",
                                "file_type": uploaded_file.type,
                                "file_size": uploaded_file.size
                            }
                            logger.info(f"✅ Text extraction successful, adding to vector store")
                            st.session_state.vector_store.add_document(text, metadata)
                        else:
                            logger.warning(f"⚠️ No text extracted from {uploaded_file.name}")
                            st.warning(f"No text could be extracted from {uploaded_file.name}")
        
        # URL input section
        st.subheader("Add from URL")
        url_input = st.text_input("Enter URL", placeholder="https://example.com")
        if st.button("Process URL") and url_input:
            logger.info(f"🚀 User initiated URL processing: {url_input}")
            with st.spinner("Fetching URL content..."):
                text = DocumentProcessor.fetch_url_content(url_input)
                if text.strip():
                    metadata = {
                        "source": url_input,
                        "type": "url"
                    }
                    logger.info(f"✅ URL content extracted, adding to vector store")
                    st.session_state.vector_store.add_document(text, metadata)
                else:
                    logger.warning(f"⚠️ No content extracted from URL: {url_input}")
                    st.warning(f"No content could be extracted from the URL")
        
        st.markdown("---")
        
        # Model selection
        st.subheader("⚙️ Settings")
        available_models = get_available_models()
        selected_model = st.selectbox(
            "Select Model:",
            available_models,
            index=0 if available_models else None,
            help="Choose an OpenAI model for the conversation"
        )
        st.session_state.selected_model = selected_model
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        
        # Vector store statistics
        st.subheader("📊 Knowledge Base Stats")
        stats = st.session_state.vector_store.get_collection_stats()
        st.metric("Documents in Knowledge Base", stats["document_count"])
        if stats.get("unique_sources"):
            st.metric("Unique Sources", stats["total_sources"])
            with st.expander("📚 Sources in Knowledge Base"):
                for source in stats["unique_sources"]:
                    st.write(f"• {source}")
        
        st.metric("Chat Messages", len(st.session_state.messages))
        
        # Show recent logs
        st.subheader("📋 Recent Activity")
        log_file_path = os.path.join(current_dir, 'rag_app.log')
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'r') as f:
                    lines = f.readlines()
                    recent_lines = lines[-10:] if len(lines) > 10 else lines
                    if recent_lines:
                        with st.expander("View Recent Logs", expanded=False):
                            for line in recent_lines:
                                # Color code log levels
                                if "ERROR" in line:
                                    st.error(line.strip())
                                elif "WARNING" in line:
                                    st.warning(line.strip())
                                elif "INFO" in line:
                                    st.info(line.strip())
                                else:
                                    st.text(line.strip())
            except Exception as e:
                st.error(f"Could not read log file: {e}")
    
    # Main chat interface
    if not st.session_state.selected_model:
        st.warning("Please select a model to start chatting.")
        return
    
    # Display current model
    st.info(f"🎯 Currently using: **{st.session_state.selected_model}**")
    
    # Chat messages container
    chat_container = st.container()
    
    with chat_container:
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your documents..."):
        logger.info(f"💬 User submitted query: {prompt}")
        
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get RAG response
        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base and generating response..."):
                logger.info(f"🔄 Processing query through RAG pipeline")
                response = st.session_state.rag_chat.get_response(
                    prompt, 
                    st.session_state.selected_model
                )
                st.markdown(response)
                logger.info(f"✅ Response delivered to user")
        
        # Add assistant response to chat
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
