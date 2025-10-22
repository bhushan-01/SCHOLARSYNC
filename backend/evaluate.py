"""
Evaluation script for AI Research Paper Assistant
Tests: Citation accuracy, summary quality, retrieval relevance
"""

import json
import re
from typing import List, Dict
from collections import Counter


class Evaluator:
    def __init__(self):
        self.results = []
    
    def evaluate_citations(self, summary: str, expected_pages: List[int]) -> Dict:
        """
        Evaluate if citations are present and accurate
        
        Metrics:
        - Citation presence rate
        - Citation accuracy (if ground truth available)
        - Average citations per claim
        """
        # Extract citations from summary
        citations = re.findall(r'\[Page (\d+)\]', summary)
        cited_pages = [int(p) for p in citations]
        
        # Calculate metrics
        has_citations = len(cited_pages) > 0
        unique_citations = len(set(cited_pages))
        
        # If expected pages provided, check accuracy
        accuracy = 0
        if expected_pages:
            correct = sum(1 for page in cited_pages if page in expected_pages)
            accuracy = correct / len(cited_pages) if cited_pages else 0
        
        # Count sentences/claims
        sentences = len([s for s in summary.split('.') if s.strip()])
        citation_density = len(cited_pages) / sentences if sentences > 0 else 0
        
        return {
            'has_citations': has_citations,
            'total_citations': len(cited_pages),
            'unique_citations': unique_citations,
            'citation_accuracy': accuracy,
            'citation_density': citation_density,
            'cited_pages': sorted(set(cited_pages))
        }
    
    def evaluate_summary_quality(self, summary: str, reference: str = None) -> Dict:
        """
        Evaluate summary quality using simple metrics
        
        Metrics:
        - Length appropriateness
        - Sentence structure
        - Coverage of key terms (if reference provided)
        """
        # Basic metrics
        word_count = len(summary.split())
        sentence_count = len([s for s in summary.split('.') if s.strip()])
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        
        # Check for structure keywords
        structure_keywords = ['objective', 'method', 'result', 'conclusion', 
                             'finding', 'approach', 'study', 'research']
        has_structure = any(kw in summary.lower() for kw in structure_keywords)
        
        result = {
            'word_count': word_count,
            'sentence_count': sentence_count,
            'avg_sentence_length': avg_sentence_length,
            'has_structure': has_structure
        }
        
        # If reference summary provided, calculate overlap
        if reference:
            summary_words = set(summary.lower().split())
            reference_words = set(reference.lower().split())
            
            overlap = len(summary_words & reference_words)
            coverage = overlap / len(reference_words) if reference_words else 0
            
            result['word_overlap'] = overlap
            result['coverage_score'] = coverage
        
        return result
    
    def evaluate_retrieval(self, query: str, retrieved_chunks: List[Dict], 
                          relevant_pages: List[int] = None) -> Dict:
        """
        Evaluate retrieval quality
        
        Metrics:
        - Number of chunks retrieved
        - Page diversity
        - Relevance (if ground truth provided)
        """
        retrieved_pages = [chunk['page'] for chunk in retrieved_chunks]
        unique_pages = len(set(retrieved_pages))
        
        result = {
            'chunks_retrieved': len(retrieved_chunks),
            'unique_pages': unique_pages,
            'page_diversity': unique_pages / len(retrieved_chunks) if retrieved_chunks else 0
        }
        
        # If relevant pages provided, calculate precision
        if relevant_pages:
            relevant_retrieved = sum(1 for page in retrieved_pages if page in relevant_pages)
            precision = relevant_retrieved / len(retrieved_pages) if retrieved_pages else 0
            recall = relevant_retrieved / len(relevant_pages) if relevant_pages else 0
            
            result['precision'] = precision
            result['recall'] = recall
            result['f1_score'] = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return result
    
    def run_test_case(self, test_name: str, summary: str, 
                      expected_pages: List[int] = None,
                      reference_summary: str = None) -> Dict:
        """Run a complete test case"""
        
        citation_metrics = self.evaluate_citations(summary, expected_pages or [])
        quality_metrics = self.evaluate_summary_quality(summary, reference_summary)
        
        test_result = {
            'test_name': test_name,
            'citation_metrics': citation_metrics,
            'quality_metrics': quality_metrics,
            'passed': citation_metrics['has_citations'] and quality_metrics['word_count'] > 50
        }
        
        self.results.append(test_result)
        return test_result
    
    def generate_report(self) -> str:
        """Generate evaluation report"""
        if not self.results:
            return "No test results available"
        
        report = "=" * 60 + "\n"
        report += "EVALUATION REPORT\n"
        report += "=" * 60 + "\n\n"
        
        passed = sum(1 for r in self.results if r['passed'])
        total = len(self.results)
        
        report += f"Tests Passed: {passed}/{total} ({passed/total*100:.1f}%)\n\n"
        
        for result in self.results:
            report += f"\nTest: {result['test_name']}\n"
            report += f"Status: {'✓ PASSED' if result['passed'] else '✗ FAILED'}\n"
            
            report += "\nCitation Metrics:\n"
            cm = result['citation_metrics']
            report += f"  - Total Citations: {cm['total_citations']}\n"
            report += f"  - Unique Pages: {cm['unique_citations']}\n"
            report += f"  - Citation Density: {cm['citation_density']:.2f}\n"
            report += f"  - Cited Pages: {cm['cited_pages']}\n"
            
            report += "\nQuality Metrics:\n"
            qm = result['quality_metrics']
            report += f"  - Word Count: {qm['word_count']}\n"
            report += f"  - Sentences: {qm['sentence_count']}\n"
            report += f"  - Avg Sentence Length: {qm['avg_sentence_length']:.1f}\n"
            report += f"  - Has Structure: {qm['has_structure']}\n"
            
            report += "\n" + "-" * 60 + "\n"
        
        return report
    
    def export_json(self, filename: str = "evaluation_results.json"):
        """Export results to JSON"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Results exported to {filename}")


# Example usage
if __name__ == "__main__":
    evaluator = Evaluator()
    
    # Test Case 1: Basic summary with citations
    test_summary_1 = """
    This paper investigates neural network optimization techniques [Page 3]. 
    The authors propose a novel adaptive learning rate method [Page 7]. 
    Experimental results show 15% improvement over baseline [Page 12].
    """
    
    evaluator.run_test_case(
        "Basic Summary Test",
        test_summary_1,
        expected_pages=[3, 7, 12]
    )
    
    # Test Case 2: Summary without citations (should fail)
    test_summary_2 = """
    This paper discusses machine learning approaches to computer vision problems.
    """
    
    evaluator.run_test_case(
        "No Citations Test",
        test_summary_2
    )
    
    # Generate report
    print(evaluator.generate_report())
    evaluator.export_json()