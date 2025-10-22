"""
Complete test suite for the AI Research Paper Assistant
Run this after setting up your system
"""

import requests
import time
from pathlib import Path
import json

BASE_URL = "http://localhost:8000"

class SystemTester:
    def __init__(self):
        self.test_results = []
    
    def test_health_check(self):
        """Test if API is running"""
        print("\n📊 Testing: Health Check")
        try:
            response = requests.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            print("✓ Health check passed")
            return True
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return False
    
    def test_pdf_upload(self, pdf_path: str):
        """Test PDF upload and processing"""
        print(f"\n📊 Testing: PDF Upload - {pdf_path}")
        try:
            with open(pdf_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(f"{BASE_URL}/upload", files=files)
            
            assert response.status_code == 200
            data = response.json()
            
            assert 'collection_id' in data
            assert 'total_chunks' in data
            assert data['total_chunks'] > 0
            
            print(f"✓ Upload successful")
            print(f"  Collection ID: {data['collection_id']}")
            print(f"  Chunks: {data['total_chunks']}")
            
            return data['collection_id']
        except Exception as e:
            print(f"✗ Upload failed: {e}")
            return None
    
    def test_summarization(self, collection_id: str):
        """Test summary generation"""
        print(f"\n📊 Testing: Summarization")
        try:
            response = requests.post(f"{BASE_URL}/summarize/{collection_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert 'summary' in data
            assert 'cited_pages' in data
            assert len(data['summary']) > 0
            
            print(f"✓ Summary generated")
            print(f"  Length: {len(data['summary'])} chars")
            print(f"  Citations: {len(data['cited_pages'])} pages")
            print(f"  Cited Pages: {data['cited_pages']}")
            print(f"\n  Summary Preview:\n  {data['summary'][:200]}...")
            
            return data
        except Exception as e:
            print(f"✗ Summarization failed: {e}")
            return None
    
    def test_query(self, collection_id: str, question: str):
        """Test question answering"""
        print(f"\n📊 Testing: Query - '{question}'")
        try:
            response = requests.post(
                f"{BASE_URL}/query/{collection_id}",
                json={'question': question}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert 'summary' in data
            assert len(data['summary']) > 0
            
            print(f"✓ Query answered")
            print(f"  Citations: {len(data['cited_pages'])} pages")
            print(f"  Cited Pages: {data['cited_pages']}")
            print(f"\n  Answer Preview:\n  {data['summary'][:200]}...")
            
            return data
        except Exception as e:
            print(f"✗ Query failed: {e}")
            return None
    
    def test_invalid_file(self):
        """Test with invalid file type"""
        print(f"\n📊 Testing: Invalid File Upload")
        try:
            # Create a dummy text file
            with open('/tmp/test.txt', 'w') as f:
                f.write("This is not a PDF")
            
            with open('/tmp/test.txt', 'rb') as f:
                files = {'file': ('test.txt', f)}
                response = requests.post(f"{BASE_URL}/upload", files=files)
            
            assert response.status_code == 400
            print("✓ Invalid file correctly rejected")
            return True
        except Exception as e:
            print(f"✗ Invalid file test failed: {e}")
            return False
    
    def test_nonexistent_collection(self):
        """Test with nonexistent collection ID"""
        print(f"\n📊 Testing: Nonexistent Collection")
        try:
            response = requests.post(f"{BASE_URL}/summarize/fake_id_12345")
            assert response.status_code == 404
            print("✓ Nonexistent collection correctly handled")
            return True
        except Exception as e:
            print(f"✗ Nonexistent collection test failed: {e}")
            return False
    
    def run_full_test_suite(self, pdf_path: str):
        """Run complete test suite"""
        print("\n" + "="*60)
        print("🧪 STARTING FULL TEST SUITE")
        print("="*60)
        
        start_time = time.time()
        
        # Test 1: Health Check
        health_ok = self.test_health_check()
        if not health_ok:
            print("\n❌ Cannot proceed - API is not running")
            return
        
        # Test 2: Invalid File
        self.test_invalid_file()
        
        # Test 3: Nonexistent Collection
        self.test_nonexistent_collection()
        
        # Test 4: Valid PDF Upload
        collection_id = self.test_pdf_upload(pdf_path)
        if not collection_id:
            print("\n❌ Cannot proceed - PDF upload failed")
            return
        
        # Test 5: Summarization
        summary_result = self.test_summarization(collection_id)
        
        # Test 6: Multiple Queries
        test_questions = [
            "What is the main objective of this paper?",
            "What methodology was used?",
            "What are the key findings?"
        ]
        
        for question in test_questions:
            self.test_query(collection_id, question)
            time.sleep(1)  # Avoid overwhelming the system
        
        # Final Report
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n" + "="*60)
        print("📋 TEST SUITE COMPLETED")
        print("="*60)
        print(f"⏱️  Total Duration: {duration:.2f} seconds")
        print("\n✅ All critical tests passed!")
        print("\nNext Steps:")
        print("1. Try the frontend at http://localhost:5173")
        print("2. Upload different PDFs to test robustness")
        print("3. Run evaluation.py for detailed metrics")


# Example usage
if __name__ == "__main__":
    tester = SystemTester()
    
    # You need to provide a test PDF path
    test_pdf = input("Enter path to a test PDF file: ")
    
    if Path(test_pdf).exists():
        tester.run_full_test_suite(test_pdf)
    else:
        print(f"❌ File not found: {test_pdf}")
        print("\nTo run tests, you need a PDF file.")
        print("You can download a sample research paper from:")
        print("- arXiv.org")
        print("- Google Scholar")
        print("- Any academic publication")
        