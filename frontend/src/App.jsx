import { useState, useEffect } from "react";
import {
  Upload,
  FileText,
  Sparkles,
  MessageSquare,
  Download,
  Trash2,
  Moon,
  Sun,
  AlertCircle,
  Check,
  Loader,
  GitCompare,
  BarChart3,
  Award,
} from "lucide-react";
import "./App.css";

const API_URL = "http://localhost:8000";

function App() {
  const [files, setFiles] = useState([]);
  const [uploadedPapers, setUploadedPapers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [darkMode, setDarkMode] = useState(false);
  const [apiHealth, setApiHealth] = useState(null);
  const [activeTab, setActiveTab] = useState("upload"); // upload, analyze, compare

  // Single paper state
  const [selectedPaper, setSelectedPaper] = useState(null);
  const [summary, setSummary] = useState(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);

  // Comparison state
  const [selectedForComparison, setSelectedForComparison] = useState([]);
  const [comparisonResult, setComparisonResult] = useState(null);

  useEffect(() => {
    checkHealth();
    loadCollections();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    document.body.className = darkMode ? "dark-mode" : "";
  }, [darkMode]);

  const checkHealth = async () => {
    try {
      const response = await fetch(`${API_URL}/health`);
      const data = await response.json();
      setApiHealth(data);
    } catch (err) {
      setApiHealth({ status: "unavailable" });
    }
  };

  const loadCollections = async () => {
    try {
      const response = await fetch(`${API_URL}/collections`);
      const data = await response.json();
      setUploadedPapers(data.collections || []);
    } catch (err) {
      console.error("Failed to load collections:", err);
    }
  };

  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    const pdfFiles = selectedFiles.filter((f) => f.type === "application/pdf");

    if (pdfFiles.length !== selectedFiles.length) {
      setError("Only PDF files are allowed");
      return;
    }

    if (pdfFiles.length > 5) {
      setError("Maximum 5 papers allowed");
      return;
    }

    setFiles(pdfFiles);
    setError(null);
  };

  const handleUploadMultiple = async () => {
    if (files.length === 0) {
      setError("Please select at least one PDF file");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    try {
      const response = await fetch(`${API_URL}/upload-multiple`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      const data = await response.json();

      if (data.uploaded > 0) {
        await loadCollections();
        setFiles([]);
        setActiveTab("analyze");
        setError(
          data.failed > 0
            ? `${data.uploaded} uploaded, ${data.failed} failed`
            : null
        );
      }
    } catch (err) {
      setError(err.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSummarize = async (paperId) => {
    setLoading(true);
    setError(null);
    setSelectedPaper(paperId);

    try {
      const response = await fetch(`${API_URL}/summarize/${paperId}`, {
        method: "POST",
      });

      if (!response.ok) throw new Error("Summarization failed");

      const data = await response.json();
      setSummary(data);
      setActiveTab("analyze");
    } catch (err) {
      setError(err.message || "Summarization failed");
    } finally {
      setLoading(false);
    }
  };

  const handleQuery = async () => {
    if (!selectedPaper) {
      setError("Please select a paper first");
      return;
    }

    if (!question.trim()) {
      setError("Please enter a question");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/query/${selectedPaper}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question }),
      });

      if (!response.ok) throw new Error("Query failed");

      const data = await response.json();
      setAnswer(data);
      setQuestion("");
    } catch (err) {
      setError(err.message || "Query failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    if (selectedForComparison.length < 2) {
      setError("Select at least 2 papers to compare");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          collection_ids: selectedForComparison,
          comparison_type: "comprehensive",
        }),
      });

      if (!response.ok) throw new Error("Comparison failed");

      const data = await response.json();
      setComparisonResult(data);
      setActiveTab("compare");
    } catch (err) {
      setError(err.message || "Comparison failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDeletePaper = async (paperId) => {
    try {
      await fetch(`${API_URL}/collection/${paperId}`, { method: "DELETE" });
      await loadCollections();
      if (selectedPaper === paperId) {
        setSelectedPaper(null);
        setSummary(null);
        setAnswer(null);
      }
      setSelectedForComparison((prev) => prev.filter((id) => id !== paperId));
    } catch (err) {
      setError("Delete failed");
    }
  };

  const togglePaperSelection = (paperId) => {
    setSelectedForComparison((prev) => {
      if (prev.includes(paperId)) {
        return prev.filter((id) => id !== paperId);
      } else if (prev.length < 5) {
        return [...prev, paperId];
      }
      return prev;
    });
  };

  const downloadComparison = () => {
    if (!comparisonResult) return;

    const content = `# Research Papers Comparison\n\n## Papers Analyzed\n${comparisonResult.papers
      .map(
        (p, i) => `${i + 1}. ${p.filename} (Quality: ${p.quality_score}/100)`
      )
      .join("\n")}\n\n## Comparison Analysis\n${
      comparisonResult.comparison_analysis
    }`;

    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "comparison-report.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  const formatSummary = (text) => {
    if (!text) return null;

    return text.split("\n").map((line, idx) => {
      if (line.startsWith("**") && line.endsWith("**")) {
        return (
          <h3 key={idx} className="summary-heading">
            {line.replace(/\*\*/g, "")}
          </h3>
        );
      }

      const citationRegex = /\[Page (\d+)\]/g;
      const parts = [];
      let lastIndex = 0;
      let match;

      while ((match = citationRegex.exec(line)) !== null) {
        if (match.index > lastIndex) {
          parts.push(line.substring(lastIndex, match.index));
        }
        parts.push(
          <span key={`cite-${idx}-${match.index}`} className="citation-badge">
            📄 Page {match[1]}
          </span>
        );
        lastIndex = match.index + match[0].length;
      }

      if (lastIndex < line.length) {
        parts.push(line.substring(lastIndex));
      }

      return parts.length > 0 ? (
        <p key={idx} className="summary-paragraph">
          {parts}
        </p>
      ) : (
        <p key={idx} className="summary-paragraph">
          {line}
        </p>
      );
    });
  };

  const getQualityColor = (score) => {
    if (score >= 85) return "#10b981";
    if (score >= 70) return "#3b82f6";
    if (score >= 55) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <div className="App">
      <header className="header">
   <div className="header-top">
    <div className="spacer"></div>

    <div className="header-title-section">
      <div className="logo-container">
        <img
          src="/src/assets/Logo.png"
          alt="Scholarsync Logo"
          className="logo-img"
        />
        <h1 className="app-title">AI Research Assistant</h1>
      </div>
    </div>

    <button onClick={() => setDarkMode(!darkMode)} className="theme-toggle">
      {darkMode ? <Sun size={28} /> : <Moon size={28} />}
    </button>
  </div>
        {apiHealth && (
          <div
            className={`status-badge ${
              apiHealth.status === "healthy" ? "status-healthy" : "status-error"
            }`}
          >
            <div
              className={`status-dot ${
                apiHealth.status === "healthy" ? "pulse" : ""
              }`}
            ></div>
            <span>
              {apiHealth.status === "healthy"
                ? `✓ System Online • ${apiHealth.model || "llama3.2"}`
                : "✗ Backend Unavailable"}
            </span>
          </div>
        )}
      </header>

      {/* Tab Navigation */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === "upload" ? "tab-active" : ""}`}
          onClick={() => setActiveTab("upload")}
        >
          <Upload size={20} />
          Upload Papers
        </button>
        <button
          className={`tab ${activeTab === "analyze" ? "tab-active" : ""}`}
          onClick={() => setActiveTab("analyze")}
          disabled={uploadedPapers.length === 0}
        >
          <Sparkles size={20} />
          Analyze Papers
        </button>
        <button
          className={`tab ${activeTab === "compare" ? "tab-active" : ""}`}
          onClick={() => setActiveTab("compare")}
          disabled={uploadedPapers.length < 2}
        >
          <GitCompare size={20} />
          Compare Papers ({selectedForComparison.length})
        </button>
      </div>

      <div className="main-content">
        {error && (
          <div className="error-msg">
            <AlertCircle size={28} />
            <div>
              <p className="error-title">Error</p>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Upload Tab */}
        {activeTab === "upload" && (
          <div className="card">
            <div className="card-header">
              <Upload size={32} />
              <h2>Upload Research Papers</h2>
            </div>

            <div className="upload-section">
              <input
                type="file"
                accept=".pdf"
                multiple
                onChange={handleFileSelect}
                className="file-input"
                disabled={loading}
              />
              <button
                onClick={handleUploadMultiple}
                disabled={files.length === 0 || loading}
                className="btn btn-primary"
              >
                {loading ? (
                  <span className="btn-content">
                    <Loader className="spin" size={20} />
                    Processing...
                  </span>
                ) : (
                  `Upload ${files.length} Paper${files.length !== 1 ? "s" : ""}`
                )}
              </button>
            </div>

            {files.length > 0 && (
              <div className="file-list">
                <p className="file-list-title">Selected files:</p>
                {files.map((file, idx) => (
                  <div key={idx} className="file-item">
                    <FileText size={18} />
                    <span>{file.name}</span>
                    <span className="file-size">
                      ({(file.size / 1024 / 1024).toFixed(2)} MB)
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="info-box">
              <h4>📚 Multi-Paper Analysis Features:</h4>
              <ul>
                <li>✓ Upload up to 5 papers simultaneously</li>
                <li>✓ AI-powered quality scoring for each paper</li>
                <li>✓ Compare methodologies and findings</li>
                <li>✓ Detect agreements and contradictions</li>
                <li>✓ Generate comparative reports</li>
              </ul>
            </div>
          </div>
        )}

        {/* Analyze Tab */}
        {activeTab === "analyze" && (
          <>
            <div className="card">
              <div className="card-header">
                <BarChart3 size={32} />
                <h2>Uploaded Papers</h2>
              </div>

              {uploadedPapers.length === 0 ? (
                <p className="empty-state">
                  No papers uploaded yet. Go to Upload tab to add papers.
                </p>
              ) : (
                <div className="papers-grid">
                  {uploadedPapers.map((paper) => (
                    <div
                      key={paper.id}
                      className={`paper-card ${
                        selectedPaper === paper.id ? "paper-selected" : ""
                      }`}
                    >
                      <div className="paper-header">
                        <FileText size={24} />
                        <button
                          onClick={() => handleDeletePaper(paper.id)}
                          className="delete-btn-small"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>

                      <h4 className="paper-title">{paper.filename}</h4>

                      <div className="paper-meta">
                        <span>📄 {paper.metadata.total_pages} pages</span>
                        <span>📦 {paper.total_chunks} chunks</span>
                      </div>

                      {paper.quality_score && (
                        <div className="quality-score">
                          <div className="quality-header">
                            <Award size={16} />
                            <span>Quality Score</span>
                          </div>
                          <div className="quality-bar-container">
                            <div
                              className="quality-bar-fill"
                              style={{
                                width: `${paper.quality_score.overall_score}%`,
                                background: getQualityColor(
                                  paper.quality_score.overall_score
                                ),
                              }}
                            ></div>
                          </div>
                          <p className="quality-text">
                            <strong>
                              {paper.quality_score.overall_score}/100
                            </strong>
                          </p>
                          <div className="quality-details">
                            <span>
                              📊 Methodology:{" "}
                              {paper.quality_score.methodology_score}
                            </span>
                            <span>
                              📈 Data: {paper.quality_score.data_score}
                            </span>
                            <span>
                              📚 Citations: {paper.quality_score.citation_score}
                            </span>
                            <span>
                              ✍️ Clarity: {paper.quality_score.clarity_score}
                            </span>
                          </div>
                        </div>
                      )}

                      <div className="paper-actions">
                        <button
                          onClick={() => handleSummarize(paper.id)}
                          className="btn btn-small btn-primary"
                          disabled={loading}
                        >
                          <Sparkles size={16} />
                          Summarize
                        </button>
                        <button
                          onClick={() => {
                            setSelectedPaper(paper.id);
                            setSummary(null);
                            setAnswer(null);
                          }}
                          className="btn btn-small btn-secondary"
                        >
                          <MessageSquare size={16} />
                          Ask Questions
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Summary Display */}
            {summary && selectedPaper && (
              <div className="card">
                <div className="card-header">
                  <Sparkles size={32} />
                  <h2>Paper Summary</h2>
                </div>

                <div className="result-box">
                  <div className="result-header">
                    <h3>📝 Summary</h3>
                  </div>
                  <div className="summary-text">
                    {formatSummary(summary.summary)}
                  </div>
                  <div className="metadata">
                    <span className="badge badge-blue">
                      📑 Cited Pages:{" "}
                      <strong>{summary.cited_pages.join(", ")}</strong>
                    </span>
                    <span className="badge badge-green">
                      📊 Chunks: <strong>{summary.chunks_used}</strong>
                    </span>
                    {summary.confidence_score && (
                      <span className="badge badge-yellow">
                        🎯 Confidence:{" "}
                        <strong>
                          {(summary.confidence_score * 100).toFixed(0)}%
                        </strong>
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Q&A Section */}
            {selectedPaper && (
              <div className="card">
                <div className="card-header">
                  <MessageSquare size={32} />
                  <h2>Ask Questions</h2>
                </div>

                <div className="query-section">
                  <input
                    type="text"
                    placeholder="What is the main contribution of this paper?"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyPress={(e) =>
                      e.key === "Enter" &&
                      !loading &&
                      question.trim() &&
                      handleQuery()
                    }
                    className="query-input"
                    disabled={loading}
                  />
                  <button
                    onClick={handleQuery}
                    disabled={loading || !question.trim()}
                    className="btn btn-primary"
                  >
                    {loading ? (
                      <span className="btn-content">
                        <Loader className="spin" size={20} />
                        Searching...
                      </span>
                    ) : (
                      "Ask"
                    )}
                  </button>
                </div>

                {answer && (
                  <div className="result-box">
                    <h3>💡 Answer</h3>
                    <div className="summary-text">
                      {formatSummary(answer.summary)}
                    </div>
                    <div className="metadata">
                      <span className="badge badge-blue">
                        📑 Cited Pages:{" "}
                        <strong>{answer.cited_pages.join(", ")}</strong>
                      </span>
                      <span className="badge badge-green">
                        📊 Chunks: <strong>{answer.chunks_used}</strong>
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* Compare Tab */}
        {activeTab === "compare" && (
          <>
            <div className="card">
              <div className="card-header">
                <GitCompare size={32} />
                <h2>Select Papers to Compare</h2>
              </div>

              <p className="compare-instructions">
                Select 2-5 papers below and click "Compare Papers" to analyze
                them side-by-side
              </p>

              <div className="papers-compare-grid">
                {uploadedPapers.map((paper) => (
                  <div
                    key={paper.id}
                    className={`compare-paper-card ${
                      selectedForComparison.includes(paper.id)
                        ? "compare-selected"
                        : ""
                    }`}
                    onClick={() => togglePaperSelection(paper.id)}
                  >
                    <div className="compare-checkbox">
                      {selectedForComparison.includes(paper.id) && (
                        <Check size={20} />
                      )}
                    </div>
                    <FileText size={20} />
                    <div className="compare-paper-info">
                      <p className="compare-paper-name">{paper.filename}</p>
                      <p className="compare-paper-meta">
                        {paper.metadata.total_pages} pages • Quality:{" "}
                        {paper.quality_score?.overall_score || 75}/100
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <button
                onClick={handleCompare}
                disabled={selectedForComparison.length < 2 || loading}
                className="btn btn-secondary"
              >
                {loading ? (
                  <span className="btn-content">
                    <Loader className="spin" size={20} />
                    Comparing...
                  </span>
                ) : (
                  `Compare ${selectedForComparison.length} Papers`
                )}
              </button>
            </div>

            {/* Comparison Results */}
            {comparisonResult && (
              <>
                <div className="card">
                  <div className="card-header">
                    <BarChart3 size={32} />
                    <h2>Comparison Results</h2>
                  </div>

                  <div className="comparison-header">
                    <h3>📊 Papers Being Compared</h3>
                    <button
                      onClick={downloadComparison}
                      className="btn-download"
                    >
                      <Download size={18} />
                      Export Report
                    </button>
                  </div>

                  <div className="comparison-papers">
                    {comparisonResult.papers.map((paper, idx) => (
                      <div key={idx} className="comparison-paper-item">
                        <div className="comparison-paper-number">
                          Paper {idx + 1}
                        </div>
                        <h4>{paper.filename}</h4>
                        <div className="comparison-paper-details">
                          <span>👤 {paper.metadata.author}</span>
                          <span>📄 {paper.metadata.total_pages} pages</span>
                          <span
                            style={{
                              color: getQualityColor(paper.quality_score),
                            }}
                          >
                            ⭐ Quality: {paper.quality_score}/100
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <GitCompare size={32} />
                    <h2>Detailed Analysis</h2>
                  </div>

                  <div className="result-box">
                    <div className="summary-text comparison-analysis">
                      {formatSummary(comparisonResult.comparison_analysis)}
                    </div>
                  </div>
                </div>

                {/* Similarity Matrix */}
                <div className="card">
                  <div className="card-header">
                    <BarChart3 size={32} />
                    <h2>Similarity Matrix</h2>
                  </div>

                  <div className="matrix-container">
                    <table className="similarity-matrix">
                      <thead>
                        <tr>
                          <th></th>
                          {comparisonResult.papers.map((_, idx) => (
                            <th key={idx}>Paper {idx + 1}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {comparisonResult.similarity_matrix.map((row, i) => (
                          <tr key={i}>
                            <th>Paper {i + 1}</th>
                            {row.map((score, j) => (
                              <td
                                key={j}
                                className="matrix-cell"
                                style={{
                                  background: `rgba(102, 126, 234, ${
                                    score / 100
                                  })`,
                                  color: score > 50 ? "white" : "#1f2937",
                                }}
                              >
                                {score}%
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>

      <footer className="footer">
        <p className="footer-main">
          Built with React + FastAPI + Ollama | 100% Free & Local
        </p>
        <p className="footer-sub">
          Multi-paper comparison • Quality scoring • Citation analysis
        </p>
      </footer>
    </div>
  );
}

export default App;
