
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

# LangChain imports
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

@dataclass
class PolicyChunk:
    """Represents a chunk of policy text with metadata"""
    content: str
    document_id: str
    document_title: str
    section: str
    subsection: str = ""
    chunk_type: str = ""  # section, subsection, example, table
    keywords: List[str] = None
    categories: List[str] = None  # Electronics, Clothing, etc.
    customer_tiers: List[str] = None  # Bronze, Silver, Gold, Platinum
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.categories is None:
            self.categories = []
        if self.customer_tiers is None:
            self.customer_tiers = []


class SOPDocumentProcessor:
    """Processes SOP markdown documents into semantic chunks"""
    
    def __init__(self):
        self.product_categories = ['Electronics', 'Clothing', 'Home & Garden', 'Books', 'Sports']
        self.customer_tiers = ['Bronze', 'Silver', 'Gold', 'Platinum']
        
    def load_sop_documents(self, sop_directory: str = "sop_documents") -> List[Dict]:
        """Load all SOP markdown documents"""
        documents = []
        sop_path = Path(sop_directory)
        
        if not sop_path.exists():
            logger.warning("SOP directory '%s' not found", sop_directory)
            return documents
        
        for md_file in sop_path.glob("*.md"):
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract document metadata from header
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            doc_id_match = re.search(r'\*\*Document ID:\*\*\s+(.+)$', content, re.MULTILINE)
            
            documents.append({
                'filename': md_file.name,
                'content': content,
                'title': title_match.group(1) if title_match else md_file.stem,
                'document_id': doc_id_match.group(1) if doc_id_match else md_file.stem
            })
            
        logger.info("Loaded %d SOP documents", len(documents))
        return documents
    
    def extract_sections(self, content: str) -> List[Dict]:
        """Extract sections and subsections from markdown content"""
        sections = []
        
        # Split by main sections (## headers)
        section_pattern = r'^##\s+(.+?)(?=^##|\Z)'
        section_matches = re.finditer(section_pattern, content, re.MULTILINE | re.DOTALL)
         
        for match in section_matches:
            section_content = match.group(0)
            section_title = match.group(1).strip()
            
            # Extract subsections (### headers)
            subsection_pattern = r'^###\s+(.+?)(?=^###|^##|\Z)'
            subsection_matches = list(re.finditer(subsection_pattern, section_content, re.MULTILINE | re.DOTALL))
            
            if subsection_matches:
                # Has subsections - process each
                for sub_match in subsection_matches:
                    subsection_content = sub_match.group(0)
                    subsection_title = sub_match.group(1).strip()
                    
                    sections.append({
                        'section': section_title,
                        'subsection': subsection_title,
                        'content': subsection_content,
                        'type': 'subsection'
                    })
            else:
                # No subsections - treat as main section
                sections.append({
                    'section': section_title,
                    'subsection': '',
                    'content': section_content,
                    'type': 'section'
                })
                
        return sections
    
    def extract_examples(self, content: str) -> List[Dict]:
        """Extract code blocks and examples for separate indexing"""
        examples = []
        
        # Extract code blocks
        code_pattern = r'```([\s\S]*?)```'
        code_matches = re.finditer(code_pattern, content)
        
        for i, match in enumerate(code_matches):
            examples.append({
                'content': match.group(0),
                'type': 'example',
                'example_id': f"example_{i+1}"
            })
            
        return examples
    
    def extract_metadata(self, content: str) -> Dict:
        """Extract keywords and categories from content"""
        content_lower = content.lower()
        
        # Extract product categories mentioned
        categories = [cat for cat in self.product_categories 
                     if cat.lower() in content_lower]
        
        # Extract customer tiers mentioned  
        tiers = [tier for tier in self.customer_tiers 
                if tier.lower() in content_lower]
        
        # Extract key policy terms
        policy_keywords = []
        keyword_patterns = [
            r'return window', r'refund', r'restocking fee', r'grace period',
            r'defective', r'damaged', r'warranty', r'exchange', r'shipping',
            r'escalation', r'exception', r'approval', r'processing time'
        ]
        
        for pattern in keyword_patterns:
            if re.search(pattern, content_lower):
                policy_keywords.append(pattern)
                
        return {
            'categories': categories,
            'customer_tiers': tiers,
            'keywords': policy_keywords
        }
    
    def create_chunks(self, documents: List[Dict]) -> List[PolicyChunk]:
        """Create semantic chunks from SOP documents"""
        all_chunks = []
        
        for doc in documents:
            logger.debug("Processing: %s", doc['title'])
            
            # Extract sections
            sections = self.extract_sections(doc['content'])
            
            for section_data in sections:
                # Extract metadata for this section
                metadata = self.extract_metadata(section_data['content'])
                
                # Create chunk
                chunk = PolicyChunk(
                    content=section_data['content'],
                    document_id=doc['document_id'],
                    document_title=doc['title'],
                    section=section_data['section'],
                    subsection=section_data['subsection'],
                    chunk_type=section_data['type'],
                    keywords=metadata['keywords'],
                    categories=metadata['categories'],
                    customer_tiers=metadata['customer_tiers']
                )
                all_chunks.append(chunk)
                
            # Extract examples separately
            examples = self.extract_examples(doc['content'])
            for example in examples:
                metadata = self.extract_metadata(example['content'])
                chunk = PolicyChunk(
                    content=example['content'],
                    document_id=doc['document_id'],
                    document_title=doc['title'],
                    section="Examples",
                    subsection=example.get('example_id', ''),
                    chunk_type='example',
                    keywords=metadata['keywords'],
                    categories=metadata['categories'],
                    customer_tiers=metadata['customer_tiers']
                )
                all_chunks.append(chunk)
                
        logger.info("Created %d semantic chunks", len(all_chunks))
        return all_chunks


class PolicyVectorStore:
    """Vector store for policy documents using FAISS and local HuggingFace embeddings"""
    
    def __init__(self, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
        self.vector_store = None
        self.chunks = []
        
    def create_vector_store(self, chunks: List[PolicyChunk]):
        """Create FAISS vector store from policy chunks"""
        logger.info("Creating vector embeddings...")
        
        # Convert chunks to LangChain documents
        documents = []
        for chunk in chunks:
            # Create comprehensive metadata
            metadata = {
                'document_id': chunk.document_id,
                'document_title': chunk.document_title,
                'section': chunk.section,
                'subsection': chunk.subsection,
                'chunk_type': chunk.chunk_type,
                'categories': ','.join(chunk.categories),
                'customer_tiers': ','.join(chunk.customer_tiers),
                'keywords': ','.join(chunk.keywords),
                'content_length': len(chunk.content)
            }
            
            doc = Document(
                page_content=chunk.content,
                metadata=metadata
            )
            documents.append(doc)
            
        # Create FAISS vector store
        self.vector_store = FAISS.from_documents(
            documents=documents,
            embedding=self.embeddings
        )
        self.chunks = chunks
        
        logger.info("Created vector store with %d document embeddings", len(documents))
        
    def save_vector_store(self, path: str = "vector_db"):
        """Save vector store to disk"""
        if self.vector_store is None:
            raise ValueError("Vector store not created yet")
            
        # Create directory if it doesn't exist
        Path(path).mkdir(exist_ok=True)
            
        # Save FAISS index
        self.vector_store.save_local(path)
        
        # Save chunk metadata separately for reconstruction
        chunk_metadata = []
        for chunk in self.chunks:
            chunk_metadata.append({
                'content': chunk.content,
                'document_id': chunk.document_id,
                'document_title': chunk.document_title,
                'section': chunk.section,
                'subsection': chunk.subsection,
                'chunk_type': chunk.chunk_type,
                'keywords': chunk.keywords,
                'categories': chunk.categories,
                'customer_tiers': chunk.customer_tiers
            })
            
        with open(f"{path}/chunk_metadata.json", 'w') as f:
            json.dump(chunk_metadata, f, indent=2)
            
        logger.info("Saved vector store to %s/", path)
        
    def load_vector_store(self, path: str = "vector_db"):
        """Load vector store from disk"""
        self.vector_store = FAISS.load_local(
            path, 
            self.embeddings,
            allow_dangerous_deserialization=True
        )
        
        # Load chunk metadata
        with open(f"{path}/chunk_metadata.json", 'r') as f:
            chunk_metadata = json.load(f)
            
        self.chunks = []
        for meta in chunk_metadata:
            chunk = PolicyChunk(
                content=meta['content'],
                document_id=meta['document_id'],
                document_title=meta['document_title'],
                section=meta['section'],
                subsection=meta['subsection'],
                chunk_type=meta['chunk_type'],
                keywords=meta['keywords'],
                categories=meta['categories'],
                customer_tiers=meta['customer_tiers']
            )
            self.chunks.append(chunk)
            
        logger.info("Loaded vector store from %s/", path)
        
    def search_policies(self, query: str, k: int = 5, filters: Dict = None) -> List[Dict]:
        """Search for relevant policy documents"""
        if self.vector_store is None:
            raise ValueError("Vector store not created yet")
            
        # Perform similarity search
        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        # Format results
        formatted_results = []
        for doc, score in results:
            result = {
                'content': doc.page_content,
                'metadata': doc.metadata,
                'similarity_score': float(score),
                'relevance': 1 - float(score)  # Convert distance to relevance
            }
            
            # Apply filters if provided
            if filters:
                if self._matches_filters(result, filters):
                    formatted_results.append(result)
            else:
                formatted_results.append(result)
                
        return formatted_results
        
    def _matches_filters(self, result: Dict, filters: Dict) -> bool:
        """Check if result matches the provided filters"""
        metadata = result['metadata']
        
        for key, value in filters.items():
            if key in metadata:
                if isinstance(value, list):
                    # Check if any of the filter values are in the metadata
                    meta_values = metadata[key].split(',') if metadata[key] else []
                    if not any(v in meta_values for v in value):
                        return False
                else:
                    if value not in metadata[key]:
                        return False
        return True


def create_vector_database():
    """Main function to create vector database from SOP documents"""
    print("Starting vector database creation...")
    
    # Initialize processor
    processor = SOPDocumentProcessor()
    
    # Load SOP documents
    documents = processor.load_sop_documents()
    
    if not documents:
        print("No SOP documents found. Please ensure sop_documents/ directory exists with .md files.")
        return None
    
    # Create chunks
    chunks = processor.create_chunks(documents)
    
    # Create vector store
    vector_store = PolicyVectorStore()
    vector_store.create_vector_store(chunks)
    
    # Save vector store
    vector_store.save_vector_store("policy_vector_db")
    
    print("Vector database creation completed!")
    return vector_store


def test_vector_database():
    """Test the created vector database"""
    print("\nTesting vector database...")
    
    try:
        # Load existing vector store
        vector_store = PolicyVectorStore()
        vector_store.load_vector_store("policy_vector_db")
        
        # Test queries
        test_queries = [
            "Electronics return window timeframe",
            "Platinum customer restocking fee reduction", 
            "Defective product refund calculation"
        ]
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            print("-" * 40)
            results = vector_store.search_policies(query, k=2)
            
            for i, result in enumerate(results, 1):
                print(f"Result {i} (Relevance: {result['relevance']:.3f})")
                print(f"Document: {result['metadata']['document_title']}")
                print(f"Section: {result['metadata']['section']}")
                print(f"Content Preview: {result['content'][:150]}...")
                print()
                
    except Exception as e:
        print(f"Error testing vector database: {e}")


if __name__ == "__main__":
    # Create vector database
    vector_store = create_vector_database()
    
    if vector_store:
        # Test the database
        test_vector_database()