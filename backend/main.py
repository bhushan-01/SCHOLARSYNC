from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions
import ollama
from typing import List, Dict, Optional
import uuid
import os
import re
from datetime import datetime
from pathlib import Path
import logging
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Research Paper Assistant",
    description="Multi-paper comparison and analysis system",
    version="3.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
CHROMA_PATH = "./chroma_db"
UPLOAD_DIR = "./uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
DEFAULT_MODEL = "llama3.2"
MAX_PAPERS_COMPARE = 5

# Create directories
Path(CHROMA_PATH).mkdir(exist_ok=True)
Path(UPLOAD_DIR).mkdir(exist_ok=True)

# Initialize ChromaDB
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    logger.info("✓ ChromaDB initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize ChromaDB: {e}")
    raise

# Store for active collections
active_collections = {}

# Pydantic models
class QueryRequest(BaseModel):
    question: str

class CompareRequest(BaseModel):
    collection_ids: List[str]
    comparison_type: Optional[str] = "comprehensive"  # comprehensive, methodology, findings


@app.on_event("startup")
async def startup_event():
    """Verify system on startup"""
    logger.info("=" * 60)
    logger.info("🚀 AI Research Paper Assistant API Starting...")
    logger.info("=" * 60)
    
    # Check Ollama
    try:
        models = ollama.list()
        num_models = len(models.get('models', []))
        logger.info(f"✓ Ollama is running with {num_models} model(s)")
        
        model_list = models.get('models', [])
        model_names = [m.get('name', '') for m in model_list]
        
        if any(DEFAULT_MODEL in name for name in model_names):
            logger.info(f"✓ Model '{DEFAULT_MODEL}' is ready")
        else:
            logger.warning(f"⚠️  Model '{DEFAULT_MODEL}' not found")
    except Exception as e:
        logger.error(f"❌ Ollama check failed: {e}")


def smart_chunk_text(text: str, page_num: int) -> List[Dict]:
    """Enhanced text chunking with sentence boundaries"""
    if not text or len(text.strip()) < 50:
        return []
    
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        words = sentence.split()
        sentence_length = len(words)
        
        if current_length + sentence_length > MAX_CHUNK_SIZE and current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'page': page_num,
                'id': str(uuid.uuid4())
            })
            
            if len(current_chunk) >= 3:
                overlap_sentences = current_chunk[-2:]
            else:
                overlap_sentences = current_chunk
            
            current_chunk = overlap_sentences + [sentence]
            current_length = sum(len(s.split()) for s in current_chunk)
        else:
            current_chunk.append(sentence)
            current_length += sentence_length
    
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        if len(chunk_text.strip()) > 50:
            chunks.append({
                'text': chunk_text,
                'page': page_num,
                'id': str(uuid.uuid4())
            })
    
    return chunks


def extract_text_from_pdf(pdf_path: str) -> Dict:
    """Extract text and metadata from PDF"""
    try:
        doc = fitz.open(pdf_path)
        chunks = []
        
        metadata = {
            'total_pages': len(doc),
            'title': doc.metadata.get('title', 'Unknown'),
            'author': doc.metadata.get('author', 'Unknown'),
        }
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            if text.strip():
                page_chunks = smart_chunk_text(text, page_num + 1)
                chunks.extend(page_chunks)
        
        doc.close()
        
        if not chunks:
            raise ValueError("No text could be extracted from PDF")
        
        return {
            'chunks': chunks,
            'metadata': metadata
        }
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise


def create_vector_db(chunks: List[Dict], collection_name: str):
    """Create vector database collection"""
    try:
        try:
            chroma_client.delete_collection(collection_name)
        except:
            pass
        
        collection = chroma_client.create_collection(
            name=collection_name,
            embedding_function=sentence_transformer_ef,
            metadata={"hnsw:space": "cosine"}
        )
        
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            collection.add(
                documents=[chunk['text'] for chunk in batch],
                metadatas=[{'page': chunk['page']} for chunk in batch],
                ids=[chunk['id'] for chunk in batch]
            )
        
        logger.info(f"✓ Vector DB created with {len(chunks)} chunks")
        return collection
    except Exception as e:
        logger.error(f"Vector DB creation failed: {e}")
        raise


def retrieve_relevant_chunks(collection, query: str, n_results: int = 8):
    """Retrieve most relevant chunks for query"""
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        retrieved = []
        for i, doc in enumerate(results['documents'][0]):
            page = results['metadatas'][0][i]['page']
            retrieved.append({
                'text': doc,
                'page': page,
                'relevance_score': 1.0 - (i * 0.08)
            })
        
        return retrieved
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise


def generate_summary_with_citations(chunks: List[Dict], query: str = None) -> Dict:
    """Generate summary or answer with citations"""
    try:
        context = "\n\n".join([
            f"[Page {chunk['page']}]: {chunk['text']}" 
            for chunk in chunks
        ])
        
        if query:
            prompt = f"""You are a research assistant. Answer the question based on the provided excerpts.

Question: {query}

Excerpts:
{context}

Instructions:
1. Answer clearly and directly
2. Use ONLY information from excerpts
3. Cite pages using [Page X] format after EVERY claim
4. If answer not in excerpts, state so clearly

Answer:"""
        else:
            prompt = f"""Create a comprehensive summary with these sections:

Excerpts:
{context}

**Main Objective**
[Cite pages]

**Methodology**
[Cite pages]

**Key Findings**
[Cite pages]

**Conclusion**
[Cite pages]

Important: Cite [Page X] after EACH claim.

Summary:"""
        
        response = ollama.chat(
            model=DEFAULT_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False
        )
        
        summary = response['message']['content']
        citations = re.findall(r'\[Page (\d+)\]', summary)
        unique_pages = sorted(list(set([int(p) for p in citations])))
        
        sentences = [s for s in summary.split('.') if s.strip()]
        word_count = len(summary.split())
        citation_density = len(citations) / len(sentences) if sentences else 0
        
        density_score = min(1.0, citation_density / 0.4)
        coverage_score = min(1.0, len(unique_pages) / 4)
        length_score = 1.0 if 80 < word_count < 800 else 0.7
        
        confidence = (density_score * 0.5 + coverage_score * 0.3 + length_score * 0.2)
        confidence = max(0.3, min(1.0, confidence))
        
        return {
            'summary': summary,
            'cited_pages': unique_pages,
            'chunks_used': len(chunks),
            'confidence_score': round(confidence, 2),
            'metadata': {
                'word_count': word_count,
                'citation_count': len(citations),
                'unique_citations': len(unique_pages),
                'citation_density': round(citation_density, 2)
            }
        }
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


def analyze_paper_quality(chunks: List[Dict], metadata: Dict) -> Dict:
    """Analyze paper quality and generate score"""
    try:
        # Sample chunks for analysis
        sample_size = min(6, len(chunks))
        sample_chunks = chunks[:sample_size]
        
        context = "\n\n".join([chunk['text'] for chunk in sample_chunks])
        
        prompt = f"""Analyze this research paper's quality. Provide scores (0-100) for:

Paper Excerpts:
{context}

Analyze and score:
1. **Methodology Rigor** (0-100): How well-designed is the research approach?
2. **Data Quality** (0-100): How robust is the data and analysis?
3. **Citation Quality** (0-100): How well does it reference prior work?
4. **Clarity** (0-100): How clear and well-written is it?

Format your response EXACTLY like this:
Methodology Rigor: [score]
Data Quality: [score]
Citation Quality: [score]
Clarity: [score]
Overall Assessment: [2-3 sentences]

Be strict but fair in scoring."""
        
        response = ollama.chat(
            model=DEFAULT_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False
        )
        
        analysis = response['message']['content']
        
        # Extract scores
        methodology_match = re.search(r'Methodology Rigor:\s*(\d+)', analysis)
        data_match = re.search(r'Data Quality:\s*(\d+)', analysis)
        citation_match = re.search(r'Citation Quality:\s*(\d+)', analysis)
        clarity_match = re.search(r'Clarity:\s*(\d+)', analysis)
        
        methodology_score = int(methodology_match.group(1)) if methodology_match else 70
        data_score = int(data_match.group(1)) if data_match else 70
        citation_score = int(citation_match.group(1)) if citation_match else 70
        clarity_score = int(clarity_match.group(1)) if clarity_match else 70
        
        overall_score = (methodology_score + data_score + citation_score + clarity_score) / 4
        
        # Extract assessment
        assessment_match = re.search(r'Overall Assessment:\s*(.+?)(?:\n\n|$)', analysis, re.DOTALL)
        assessment = assessment_match.group(1).strip() if assessment_match else "Quality analysis completed."
        
        return {
            'overall_score': round(overall_score, 1),
            'methodology_score': methodology_score,
            'data_score': data_score,
            'citation_score': citation_score,
            'clarity_score': clarity_score,
            'assessment': assessment,
            'strengths': [],
            'weaknesses': []
        }
    except Exception as e:
        logger.error(f"Quality analysis failed: {e}")
        return {
            'overall_score': 75.0,
            'methodology_score': 75,
            'data_score': 75,
            'citation_score': 75,
            'clarity_score': 75,
            'assessment': 'Quality analysis unavailable',
            'strengths': [],
            'weaknesses': []
        }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload and process PDF"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    content = await file.read()
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_FILE_SIZE // (1024*1024)}MB")
    
    if file_size < 1000:
        raise HTTPException(status_code=400, detail="File too small or empty")
    
    file_id = uuid.uuid4().hex[:12]
    file_path = Path(UPLOAD_DIR) / f"{file_id}_{file.filename}"
    
    try:
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Processing PDF: {file.filename}")
        extraction_result = extract_text_from_pdf(str(file_path))
        chunks = extraction_result['chunks']
        metadata = extraction_result['metadata']
        
        logger.info(f"Extracted {len(chunks)} chunks from {metadata['total_pages']} pages")
        
        collection_name = f"doc_{file_id}"
        collection = create_vector_db(chunks, collection_name)
        
        # Analyze quality
        quality_analysis = analyze_paper_quality(chunks, metadata)
        
        active_collections[collection_name] = {
            'collection': collection,
            'filename': file.filename,
            'upload_time': datetime.now().isoformat(),
            'metadata': metadata,
            'total_chunks': len(chunks),
            'file_path': str(file_path),
            'quality_score': quality_analysis
        }
        
        logger.info(f"✓ Collection created: {collection_name}")
        
        return JSONResponse(content={
            'collection_id': collection_name,
            'total_chunks': len(chunks),
            'filename': file.filename,
            'paper_metadata': metadata,
            'quality_score': quality_analysis
        })
    
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-multiple")
async def upload_multiple_pdfs(files: List[UploadFile] = File(...)):
    """Upload multiple PDFs for comparison"""
    if len(files) > MAX_PAPERS_COMPARE:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PAPERS_COMPARE} papers allowed")
    
    results = []
    errors = []
    
    for file in files:
        try:
            result = await upload_pdf(file)
            results.append(result.body.decode())
        except Exception as e:
            errors.append({
                'filename': file.filename,
                'error': str(e)
            })
    
    return {
        'uploaded': len(results),
        'failed': len(errors),
        'results': [eval(r) for r in results],
        'errors': errors
    }


@app.post("/compare")
async def compare_papers(compare_req: CompareRequest):
    """Compare multiple research papers"""
    collection_ids = compare_req.collection_ids
    
    if len(collection_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 papers to compare")
    
    if len(collection_ids) > MAX_PAPERS_COMPARE:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PAPERS_COMPARE} papers allowed")
    
    # Validate collections
    for coll_id in collection_ids:
        if coll_id not in active_collections:
            raise HTTPException(status_code=404, detail=f"Collection {coll_id} not found")
    
    try:
        # Gather paper summaries
        paper_summaries = []
        
        for coll_id in collection_ids:
            collection = active_collections[coll_id]['collection']
            metadata = active_collections[coll_id]['metadata']
            filename = active_collections[coll_id]['filename']
            quality = active_collections[coll_id].get('quality_score', {})
            
            # Get representative chunks
            all_results = collection.get()
            total_chunks = len(all_results['ids'])
            
            sample_size = min(8, total_chunks)
            step = max(1, total_chunks // sample_size)
            indices = [i * step for i in range(sample_size)]
            
            sample_chunks = []
            for idx in indices:
                if idx < total_chunks:
                    sample_chunks.append({
                        'text': all_results['documents'][idx],
                        'page': all_results['metadatas'][idx]['page']
                    })
            
            # Generate summary
            summary_result = generate_summary_with_citations(sample_chunks)
            
            paper_summaries.append({
                'collection_id': coll_id,
                'filename': filename,
                'metadata': metadata,
                'summary': summary_result['summary'],
                'quality_score': quality.get('overall_score', 75)
            })
        
        # Generate comparison
        comparison_prompt = f"""You are comparing {len(paper_summaries)} research papers. Analyze and compare them.

"""
        
        for i, paper in enumerate(paper_summaries, 1):
            comparison_prompt += f"""
**Paper {i}: {paper['filename']}**
Author: {paper['metadata'].get('author', 'Unknown')}
Pages: {paper['metadata'].get('total_pages', 'Unknown')}
Quality Score: {paper['quality_score']}/100

Summary:
{paper['summary']}

---
"""
        
        comparison_prompt += """

Provide a detailed comparison with these sections:

**1. Research Objectives Comparison**
Compare what each paper aims to achieve. Are they addressing similar or different problems?

**2. Methodology Comparison**
Compare research methods, approaches, and techniques used.

**3. Key Findings Agreement/Disagreement**
Which findings align? Which contradict? Be specific.

**4. Strengths and Weaknesses**
For each paper, note unique strengths and limitations.

**5. Research Gap Analysis**
What gaps exist? What questions remain unanswered?

**6. Recommendation**
Which paper is most valuable for different use cases?

Be thorough, specific, and cite paper numbers [Paper 1], [Paper 2], etc."""
        
        response = ollama.chat(
            model=DEFAULT_MODEL,
            messages=[{'role': 'user', 'content': comparison_prompt}],
            stream=False
        )
        
        comparison_analysis = response['message']['content']
        
        # Create comparison matrix
        matrix = []
        for i, paper1 in enumerate(paper_summaries):
            row = []
            for j, paper2 in enumerate(paper_summaries):
                if i == j:
                    similarity = 100
                else:
                    # Simple similarity based on quality scores
                    similarity = 100 - abs(paper1['quality_score'] - paper2['quality_score'])
                row.append(round(similarity, 1))
            matrix.append(row)
        
        return {
            'papers': paper_summaries,
            'comparison_analysis': comparison_analysis,
            'similarity_matrix': matrix,
            'total_papers': len(paper_summaries),
            'comparison_type': compare_req.comparison_type
        }
    
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summarize/{collection_id}")
async def summarize_paper(collection_id: str):
    """Generate comprehensive paper summary"""
    if collection_id not in active_collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    try:
        collection = active_collections[collection_id]['collection']
        
        all_results = collection.get()
        total_chunks = len(all_results['ids'])
        
        if total_chunks == 0:
            raise HTTPException(status_code=500, detail="No content found")
        
        sample_size = min(10, total_chunks)
        indices = []
        
        if total_chunks <= 10:
            indices = list(range(total_chunks))
        else:
            step = total_chunks // (sample_size - 1)
            indices = [i * step for i in range(sample_size - 1)]
            indices.append(total_chunks - 1)
        
        sample_chunks = []
        for idx in indices:
            if idx < total_chunks:
                sample_chunks.append({
                    'text': all_results['documents'][idx],
                    'page': all_results['metadatas'][idx]['page']
                })
        
        result = generate_summary_with_citations(sample_chunks)
        logger.info(f"✓ Summary generated for {collection_id}")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/{collection_id}")
async def query_paper(collection_id: str, query_data: QueryRequest):
    """Answer specific questions about the paper"""
    if collection_id not in active_collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    question = query_data.question.strip()
    
    if not question or len(question) < 10:
        raise HTTPException(status_code=400, detail="Question too short")
    
    try:
        collection = active_collections[collection_id]['collection']
        relevant_chunks = retrieve_relevant_chunks(collection, question, n_results=8)
        result = generate_summary_with_citations(relevant_chunks, query=question)
        
        logger.info(f"✓ Query answered for {collection_id}")
        return result
    
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections")
async def list_collections():
    """List all active collections"""
    collections = []
    for coll_id, data in active_collections.items():
        collections.append({
            'id': coll_id,
            'filename': data['filename'],
            'upload_time': data['upload_time'],
            'total_chunks': data['total_chunks'],
            'metadata': data['metadata'],
            'quality_score': data.get('quality_score', {})
        })
    
    return {'collections': collections, 'total': len(collections)}


@app.delete("/collection/{collection_id}")
async def delete_collection(collection_id: str):
    """Delete a collection"""
    if collection_id not in active_collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    try:
        chroma_client.delete_collection(collection_id)
        
        file_path = Path(active_collections[collection_id].get('file_path', ''))
        if file_path.exists():
            file_path.unlink()
        
        del active_collections[collection_id]
        
        logger.info(f"✓ Collection deleted: {collection_id}")
        return {"message": "Collection deleted successfully"}
    
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """System health check"""
    try:
        ollama_status = "unavailable"
        try:
            ollama.list()
            ollama_status = "healthy"
        except:
            pass
        
        return {
            "status": "healthy",
            "message": "AI Research Assistant API is running",
            "ollama_status": ollama_status,
            "active_collections": len(active_collections),
            "model": DEFAULT_MODEL,
            "features": ["multi-paper-comparison", "quality-scoring", "citation-analysis"]
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("🚀 AI Research Paper Assistant API v3.0")
    print("=" * 60)
    print(f"📦 Model: {DEFAULT_MODEL}")
    print(f"🆕 Multi-Paper Comparison: Enabled")
    print(f"🎯 Quality Scoring: Enabled")
    print(f"📊 Max Papers: {MAX_PAPERS_COMPARE}")
    print("=" * 60)
    print("\n💡 Make sure Ollama is running!")
    print(f"   Start with: ollama run {DEFAULT_MODEL}\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")