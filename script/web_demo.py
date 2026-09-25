import json
import re
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# Dam bao import duoc src va venv
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
venv_site = project_root / ".venv" / "Lib" / "site-packages"
if venv_site.exists() and str(venv_site) not in sys.path:
    sys.path.insert(0, str(venv_site))

import pandas as pd
from core.config import load_settings
from core.utils import read_json
from retrieval.index import LocalEmbeddingIndex, SearchResult
from retrieval.qa import _extract_answer

# Load global caches
SETTINGS = load_settings()
INDEXES: dict[str, LocalEmbeddingIndex] = {}

# Doc testset va clean data de tra cuu chinh xac Ground Truth
TESTSET = read_json(SETTINGS.paths.eval_testset) if SETTINGS.paths.eval_testset.exists() else []
TESTSET_MAP = {item["question"].strip(): item for item in TESTSET}

CLEAN_DF = pd.read_json(SETTINGS.paths.clean_json) if SETTINGS.paths.clean_json.exists() else pd.DataFrame()
TITLE_TO_PAPER_ID = {}
if not CLEAN_DF.empty:
    for _, row in CLEAN_DF.iterrows():
        TITLE_TO_PAPER_ID[row["title"].strip().lower()] = str(row["paper_id"])


def get_or_load_index(collection_type: str) -> LocalEmbeddingIndex:
    if collection_type not in INDEXES:
        if collection_type == "corrupted":
            path = SETTINGS.paths.corrupted_embeddings_json
        elif collection_type == "repaired":
            path = SETTINGS.paths.repaired_embeddings_json
        else:
            path = SETTINGS.paths.embeddings_json
        INDEXES[collection_type] = LocalEmbeddingIndex.load(SETTINGS, path)
    return INDEXES[collection_type]


# Danh sach cau hoi kho thuan ngu nghia (Hard Semantic Queries - 100% Dense Vector Search)
SEMANTIC_CHALLENGES = [
    {
        "id": "sem_001",
        "category": "Drop Record",
        "tag": "🚨 Drop Record (Mất bài 20%)",
        "question": "Why do static benchmarks fail to capture domain drift in enterprise knowledge bases?",
        "target_doi": "10.1145/3637528.3671812",
        "target_title": "Continuous Benchmark Evaluation for Enterprise Retrieval Pipelines",
        "ground_truth": "Static benchmarks fail to capture domain drift in enterprise knowledge bases. We establish a synthetic test generator that auto-creates paired evaluation sets.",
        "flaw_explanation": "Bài báo gốc đã bị xóa khỏi kho Corrupted (Drop 20% bài mới). Trên Baseline tìm đúng 100%, trên Corrupted sẽ bị miss hoặc trượt sang bài khác!",
    },
    {
        "id": "sem_002",
        "category": "Drop Record",
        "tag": "🚨 Drop Record (Mất bài 20%)",
        "question": "How does multi-agent consensus prevent confirmation bias when evaluating retrieved evidence?",
        "target_doi": "10.1145/3637528.3671808",
        "target_title": "Multi-Agent Consensus for High-Stakes Fact Verification",
        "ground_truth": "A single LLM is susceptible to confirmation bias when evaluating retrieved evidence. We demonstrate a multi-agent debate architecture where specialized verifier agents critique and corroborate citations.",
        "flaw_explanation": "Bài báo gốc đã bị xóa khỏi kho Corrupted. Trên Baseline tìm ra ngay, trên Corrupted tìm trượt sang bài khác!",
    },
    {
        "id": "sem_003",
        "category": "Blank Summary",
        "tag": "⚠️ Blank Summary (Xóa tóm tắt)",
        "question": "What is the summary of the paper 'Data Observability and Quality Gates for Production RAG Systems'?",
        "target_doi": "10.1145/3637528.3671802",
        "target_title": "Data Observability and Quality Gates for Production RAG Systems",
        "ground_truth": "Silent data corruption in RAG pipelines degrades LLM answer faithfulness without throwing runtime errors. We introduce automated quality gates using Great Expectations 1.x.",
        "flaw_explanation": "Bài báo này bị xóa sạch trường summary! Khi truy vấn trên kho Corrupted, câu trả lời sẽ bị RỖNG HOÀN TOÀN!",
    },
    {
        "id": "sem_004",
        "category": "Noise Injection",
        "tag": "⚠️ Noise Tokens (Độc tố rác)",
        "question": "What is the summary of the paper 'Advanced Perspectives on Hybrid Search Architectures: Combining BM25 with Dense Representations'?",
        "target_doi": "10.1145/3637528.3671823",
        "target_title": "Advanced Perspectives on Hybrid Search Architectures: Combining BM25 with Dense Representations",
        "ground_truth": "Dense vector search excels at conceptual similarity but struggles with exact acronyms. Reciprocal Rank Fusion achieves optimal recall.",
        "flaw_explanation": "Bài báo này bị tiêm chuỗi ký tự rác '0xDEADBEEF'. Trên Corrupted bạn sẽ thấy AI trích dẫn nguyên chuỗi rác độc tố ra màn hình!",
    },
    {
        "id": "sem_005",
        "category": "Stale Date",
        "tag": "⚠️ Stale Date (Lùi 365 ngày)",
        "question": "When was the paper 'Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks' published?",
        "target_doi": "10.1145/3637528.3671801",
        "target_title": "Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks",
        "ground_truth": "2026-05-20",
        "flaw_explanation": "Bài báo bị lùi ngày xuất bản 365 ngày. Trên Baseline trả về '2026-05-20', nhưng trên Corrupted trả về '2025-05-20' (lỗi thời 1 năm, vi phạm Freshness SLA)!",
    },
]


HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG Data Observability & Quality Studio</title>
    <style>
        :root {
            --bg: #0b0f19;
            --surface: #111827;
            --surface-hover: #1f2937;
            --border: #374151;
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.15);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.15);
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.15);
            --warning: #f59e0b;
            --text-main: #f9fafb;
            --text-muted: #9ca3af;
            --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: var(--font);
            background: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            background: rgba(17, 24, 39, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            padding: 0.85rem 2rem;
            position: sticky;
            top: 0;
            z-index: 50;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .brand-icon {
            background: linear-gradient(135deg, #38bdf8, #6366f1);
            width: 36px;
            height: 36px;
            border-radius: 9px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.15rem;
        }
        .brand-title h1 {
            font-size: 1.1rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        .brand-title p {
            font-size: 0.72rem;
            color: var(--text-muted);
        }
        .nav-tabs {
            display: flex;
            gap: 0.4rem;
            background: #030712;
            padding: 0.25rem;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        .nav-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 0.45rem 0.9rem;
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.2s;
        }
        .nav-btn.active {
            background: var(--surface-hover);
            color: var(--primary);
            box-shadow: 0 1px 3px rgba(0,0,0,0.5);
        }
        .badge {
            font-size: 0.72rem;
            padding: 0.2rem 0.55rem;
            border-radius: 9999px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }
        .badge-success { background: var(--success-glow); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-danger { background: var(--danger-glow); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
        .badge-warning { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }

        main {
            flex: 1;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
            padding: 1.25rem 1.75rem;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.25s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

        /* Grid layout for QA */
        .qa-layout {
            display: grid;
            grid-template-columns: 460px 1fr;
            gap: 1.25rem;
        }
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.15rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        }
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.85rem;
            padding-bottom: 0.65rem;
            border-bottom: 1px solid var(--border);
        }
        .card-title {
            font-size: 0.92rem;
            font-weight: 700;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        /* Controls */
        .form-group {
            margin-bottom: 1rem;
        }
        .form-label {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 0.4rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .collection-selector {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 0.5rem;
        }
        .collection-opt {
            border: 2px solid var(--border);
            border-radius: 8px;
            padding: 0.6rem 0.4rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            background: #030712;
        }
        .collection-opt:hover { border-color: var(--primary); }
        .collection-opt.active.baseline {
            border-color: #10b981;
            background: var(--success-glow);
            color: #34d399;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.25);
        }
        .collection-opt.active.corrupted {
            border-color: #ef4444;
            background: var(--danger-glow);
            color: #f87171;
            box-shadow: 0 0 10px rgba(239, 68, 68, 0.25);
        }
        .collection-opt.active.repaired {
            border-color: #38bdf8;
            background: var(--primary-glow);
            color: #38bdf8;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.25);
        }
        .collection-opt .opt-title { font-size: 0.82rem; font-weight: 700; }
        .collection-opt .opt-desc { font-size: 0.65rem; color: var(--text-muted); margin-top: 2px; }

        .question-mode-tabs {
            display: flex;
            gap: 0.3rem;
            background: #030712;
            padding: 0.2rem;
            border-radius: 6px;
            border: 1px solid var(--border);
            margin-bottom: 0.5rem;
        }
        .q-mode-btn {
            flex: 1;
            padding: 0.4rem 0.3rem;
            font-size: 0.72rem;
            font-weight: 700;
            background: transparent;
            border: none;
            color: var(--text-muted);
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
            text-align: center;
        }
        .q-mode-btn.active {
            background: var(--surface-hover);
            color: #38bdf8;
        }

        .sample-chips {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            max-height: 240px;
            overflow-y: auto;
            padding-right: 4px;
        }
        .chip {
            background: #030712;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.55rem 0.7rem;
            font-size: 0.76rem;
            cursor: pointer;
            transition: all 0.15s;
            line-height: 1.35;
            color: #d1d5db;
        }
        .chip:hover {
            border-color: var(--primary);
            color: #fff;
            background: var(--surface-hover);
        }
        .chip.active {
            border-color: var(--primary);
            background: var(--primary-glow);
            color: var(--primary);
            font-weight: 600;
        }
        .chip-badge {
            font-size: 0.65rem;
            font-weight: 700;
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            display: inline-block;
            margin-bottom: 0.25rem;
        }
        .badge-flaw { background: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
        .badge-norm { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }

        textarea.query-input {
            width: 100%;
            background: #030712;
            border: 1px solid var(--border);
            border-radius: 8px;
            color: #fff;
            padding: 0.65rem;
            font-family: inherit;
            font-size: 0.85rem;
            line-height: 1.45;
            resize: vertical;
            min-height: 75px;
        }
        textarea.query-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 2px var(--primary-glow);
        }

        .btn-action-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
        }
        .btn-submit {
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #fff;
            border: none;
            padding: 0.7rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 700;
            cursor: pointer;
            transition: opacity 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
        }
        .btn-side-by-side {
            background: linear-gradient(135deg, #7c3aed, #4f46e5);
            color: #fff;
            border: none;
            padding: 0.7rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 700;
            cursor: pointer;
            transition: opacity 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
        }
        .btn-submit:hover, .btn-side-by-side:hover { opacity: 0.9; }

        /* Output View */
        .output-container {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .alert-banner {
            border-radius: 8px;
            padding: 0.85rem 1.15rem;
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            font-size: 0.88rem;
            line-height: 1.45;
        }
        .alert-hit {
            background: var(--success-glow);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #34d399;
        }
        .alert-miss {
            background: var(--danger-glow);
            border: 1px solid rgba(239, 68, 68, 0.5);
            color: #fca5a5;
        }
        .alert-custom {
            background: var(--primary-glow);
            border: 1px solid rgba(56, 189, 248, 0.4);
            color: #38bdf8;
        }
        .banner-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-weight: 700;
            font-size: 0.92rem;
        }
        .banner-body {
            font-size: 0.8rem;
            color: #e5e7eb;
        }

        .answer-box {
            background: #030712;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.9rem 1.15rem;
            font-size: 0.95rem;
            line-height: 1.5;
            color: #f3f4f6;
            border-left: 4px solid var(--primary);
        }
        .reference-box {
            background: #030712;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            font-size: 0.82rem;
            color: #9ca3af;
            border-left: 4px solid var(--warning);
            line-height: 1.45;
        }

        /* Side-by-side comparison modal/view */
        .side-by-side-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        .side-col {
            background: #030712;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
        }
        .side-header {
            font-size: 0.85rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            padding-bottom: 0.4rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .context-item {
            background: #030712;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.8rem 1rem;
            margin-bottom: 0.65rem;
        }
        .context-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.4rem;
        }
        .context-title {
            font-size: 0.82rem;
            font-weight: 700;
            color: #e5e7eb;
        }
        .context-body {
            font-size: 0.78rem;
            color: #9ca3af;
            line-height: 1.45;
            white-space: pre-wrap;
            background: #0b0f19;
            padding: 0.5rem;
            border-radius: 6px;
            border: 1px solid #1f2937;
        }

        /* Comparison Table */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1.15rem;
            text-align: center;
        }
        .stat-val { font-size: 1.8rem; font-weight: 800; margin: 0.3rem 0; }
        .stat-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
        .table-wrap {
            overflow-x: auto;
            border: 1px solid var(--border);
            border-radius: 10px;
            background: var(--surface);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            text-align: left;
        }
        th, td {
            padding: 0.85rem 1.15rem;
            border-bottom: 1px solid var(--border);
        }
        th { background: #030712; color: var(--text-muted); font-weight: 700; font-size: 0.78rem; text-transform: uppercase; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: var(--surface-hover); }

        .corruption-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        .corr-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1.15rem;
        }
        .corr-title {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.95rem;
            font-weight: 700;
            color: #f87171;
            margin-bottom: 0.5rem;
        }
        .corr-desc { font-size: 0.82rem; color: #d1d5db; line-height: 1.4; margin-bottom: 0.75rem; }
        .corr-tag { font-size: 0.72rem; padding: 0.2rem 0.5rem; border-radius: 4px; background: #1f2937; color: #9ca3af; }
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <div class="brand-icon">🔬</div>
            <div class="brand-title">
                <h1>RAG Observability & Quality Studio</h1>
                <p>Day 10: Data Pipeline & Observability for RAG Benchmark</p>
            </div>
        </div>
        <div class="nav-tabs">
            <button class="nav-btn active" onclick="switchTab('tab-qa')">🎯 Live RAG Query</button>
            <button class="nav-btn" onclick="switchTab('tab-matrix')">📊 3-State Matrix</button>
            <button class="nav-btn" onclick="switchTab('tab-corruptions')">🦠 6 Flaws Injected</button>
            <button class="nav-btn" onclick="switchTab('tab-quality')">🛡️ Quality Gate & SLA</button>
        </div>
        <div>
            <span class="badge badge-success">GX 1.x Ready</span>
            <span class="badge badge-warning">Freshness SLA Active</span>
        </div>
    </header>

    <main>
        <!-- TAB 1: LIVE RAG QA -->
        <div id="tab-qa" class="tab-content active">
            <div class="qa-layout">
                <!-- Left Panel -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">⚙️ Thiết Lập Truy Vấn RAG</div>
                    </div>

                    <div class="form-group">
                        <div class="form-label">
                            <span>1. Kho Vector Đang Chọn</span>
                        </div>
                        <div class="collection-selector">
                            <div class="collection-opt active baseline" id="opt-baseline" onclick="changeCollection('baseline')">
                                <div class="opt-title">🟢 Baseline</div>
                                <div class="opt-desc">Dữ liệu sạch (100%)</div>
                            </div>
                            <div class="collection-opt corrupted" id="opt-corrupted" onclick="changeCollection('corrupted')">
                                <div class="opt-title">🔴 Corrupted</div>
                                <div class="opt-desc">Tiêm lỗi (-40%)</div>
                            </div>
                            <div class="collection-opt repaired" id="opt-repaired" onclick="changeCollection('repaired')">
                                <div class="opt-title">🔵 Repaired</div>
                                <div class="opt-desc">Tự phục hồi</div>
                            </div>
                        </div>
                    </div>

                    <div class="form-group">
                        <div class="form-label">
                            <span>2. Chế Độ Câu Hỏi</span>
                        </div>
                        <div class="question-mode-tabs">
                            <button class="q-mode-btn active" id="btn-mode-semantic" onclick="setQuestionMode('semantic')">🔥 Thách Thức (5)</button>
                            <button class="q-mode-btn" id="btn-mode-standard" onclick="setQuestionMode('standard')">📋 Benchmark (10)</button>
                            <button class="q-mode-btn" id="btn-mode-custom" onclick="setQuestionMode('custom')">✏️ Tự Nhập Tự Do</button>
                        </div>
                        <div class="sample-chips" id="sample-list">
                            <!-- Populated via JS -->
                        </div>
                    </div>

                    <div class="form-group">
                        <div class="form-label">
                            <span>3. Câu Hỏi Gửi Tới ChromaDB</span>
                            <span id="input-mode-label" style="font-size:0.68rem; color:#38bdf8; text-transform:none;">Chế độ mẫu</span>
                        </div>
                        <textarea class="query-input" id="query-text" placeholder="Nhập câu hỏi tự nhiên hoặc từ khóa bất kỳ (ví dụ: 'BM25 and dense retrieval', 'data quality in CI/CD', 'multi-agent consensus')..."></textarea>
                    </div>

                    <div class="btn-action-row">
                        <button class="btn-submit" id="btn-run" onclick="submitQuery()">
                            <span>🚀 Chạy Truy Vấn RAG</span>
                        </button>
                        <button class="btn-side-by-side" onclick="runSideBySide()">
                            <span>⚡ So Sánh 2 Kho</span>
                        </button>
                    </div>
                </div>

                <!-- Right Panel: Output -->
                <div class="output-container">
                    <div id="status-banner" class="alert-banner alert-hit" style="display: none;">
                        <div class="banner-header">
                            <span id="banner-title">✅ RETRIEVAL HIT: Tìm đúng tài liệu mục tiêu!</span>
                            <span id="banner-badge" class="badge badge-success">Hit: True</span>
                        </div>
                        <div class="banner-body" id="banner-desc"></div>
                    </div>

                    <!-- Single View Output -->
                    <div id="single-view-output">
                        <div class="card" style="margin-bottom: 1rem;">
                            <div class="card-header">
                                <div class="card-title">🤖 Câu Trả Lời Của AI (Generated Answer)</div>
                                <span class="badge" id="ans-collection-badge">Collection: papers-baseline</span>
                            </div>
                            <div class="answer-box" id="answer-content">
                                Đang chờ truy vấn...
                            </div>
                        </div>

                        <div class="card" id="ref-card" style="margin-bottom: 1rem;">
                            <div class="card-header">
                                <div class="card-title" id="ref-card-title">🎯 Đáp Án Chuẩn & Giải Thích Hiện Tượng</div>
                                <span style="font-size: 0.72rem; color: var(--text-muted);" id="target-doi-badge">Target DOI</span>
                            </div>
                            <div class="reference-box" id="ref-content"></div>
                        </div>

                        <div class="card">
                            <div class="card-header">
                                <div class="card-title">🔍 Đoạn Trích Dẫn Ngữ Cảnh Thực Tế (ChromaDB Vector Retrieval)</div>
                                <span style="font-size: 0.72rem; color: #38bdf8;" id="context-count">Sentence-Transformers (384d)</span>
                            </div>
                            <div id="context-list">
                                <p style="color: var(--text-muted); font-size: 0.85rem; padding: 0.5rem 0;">Chưa có tài liệu truy xuất.</p>
                            </div>
                        </div>
                    </div>

                    <!-- Side-by-side View Output -->
                    <div id="side-by-side-output" style="display: none;">
                        <div class="card">
                            <div class="card-header">
                                <div class="card-title">⚡ ĐỐI CHIẾU TRỰC DIỆN: BASELINE (SẠCH) VS CORRUPTED (LỖI)</div>
                                <button class="nav-btn" style="background:#1f2937;" onclick="closeSideBySide()">✖ Đóng So Sánh</button>
                            </div>
                            <div class="side-by-side-grid">
                                <div class="side-col" style="border-top: 3px solid #10b981;">
                                    <div class="side-header" style="color: #34d399;">
                                        <span>🟢 KHO BASELINE (SẠCH)</span>
                                        <span class="badge badge-success" id="side-base-score">Score: 0%</span>
                                    </div>
                                    <div style="font-size:0.75rem; color:#9ca3af; margin-bottom:4px;">CÂU TRẢ LỜI CỦA AI:</div>
                                    <div class="answer-box" id="side-base-ans" style="margin-bottom:0.75rem; border-left-color:#10b981; font-size:0.88rem;"></div>
                                    <div style="font-size:0.75rem; color:#9ca3af; margin-bottom:4px;">BÀI BÁO ĐƯỢC RETRIEVE ĐẦU TIÊN:</div>
                                    <div id="side-base-doc" style="font-size:0.8rem; color:#e5e7eb; background:#0b0f19; padding:0.5rem; border-radius:6px;"></div>
                                </div>

                                <div class="side-col" style="border-top: 3px solid #ef4444;">
                                    <div class="side-header" style="color: #f87171;">
                                        <span>🔴 KHO CORRUPTED (LỖI)</span>
                                        <span class="badge badge-danger" id="side-corr-score">Score: 0%</span>
                                    </div>
                                    <div style="font-size:0.75rem; color:#9ca3af; margin-bottom:4px;">CÂU TRẢ LỜI CỦA AI:</div>
                                    <div class="answer-box" id="side-corr-ans" style="margin-bottom:0.75rem; border-left-color:#ef4444; font-size:0.88rem;"></div>
                                    <div style="font-size:0.75rem; color:#9ca3af; margin-bottom:4px;">BÀI BÁO ĐƯỢC RETRIEVE ĐẦU TIÊN:</div>
                                    <div id="side-corr-doc" style="font-size:0.8rem; color:#e5e7eb; background:#0b0f19; padding:0.5rem; border-radius:6px;"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 2: 3-STATE MATRIX -->
        <div id="tab-matrix" class="tab-content">
            <div class="metrics-grid">
                <div class="stat-card">
                    <div class="stat-label">Baseline Hit Rate</div>
                    <div class="stat-val" style="color: #34d399;">100%</div>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">Trạng thái sạch chuẩn</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Corrupted Hit Rate</div>
                    <div class="stat-val" style="color: #f87171;">60.0%</div>
                    <div style="font-size: 0.75rem; color: #f87171;">Sụt giảm -40.0%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Repaired Hit Rate</div>
                    <div class="stat-val" style="color: #38bdf8;">100%</div>
                    <div style="font-size: 0.75rem; color: #34d399;">Khôi phục hoàn toàn 100%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Silent Failure Detected</div>
                    <div class="stat-val" style="color: #fbbf24;">4/6 GX</div>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">Không hề văng crash app</div>
                </div>
            </div>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Tiêu Chí / Chỉ Số Đo Lường</th>
                            <th>Baseline (Dữ liệu Sạch)</th>
                            <th>Corrupted (Dữ liệu Lỗi)</th>
                            <th>Repaired (Sau Phục Hồi)</th>
                            <th>Mức Độ Sụt Giảm</th>
                            <th>Tỷ Lệ Phục Hồi</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>Great Expectations 1.x Gate</strong></td>
                            <td><span class="badge badge-success">PASSED (100%)</span></td>
                            <td><span class="badge badge-danger">FAILED (4/6)</span></td>
                            <td><span class="badge badge-success">PASSED (100%)</span></td>
                            <td style="color: #f87171;">Báo động vi phạm</td>
                            <td style="color: #34d399;">Khôi phục 100%</td>
                        </tr>
                        <tr>
                            <td><strong>Freshness SLA Status</strong></td>
                            <td><span class="badge badge-success">FRESH (4.2%)</span></td>
                            <td><span class="badge badge-danger">STALE (36.4%)</span></td>
                            <td><span class="badge badge-success">FRESH (4.2%)</span></td>
                            <td style="color: #f87171;">Vi phạm ngưỡng 25%</td>
                            <td style="color: #34d399;">Khôi phục 100%</td>
                        </tr>
                        <tr>
                            <td><strong>Retrieval Hit Rate</strong></td>
                            <td><strong style="color: #34d399;">1.000</strong></td>
                            <td><strong style="color: #f87171;">0.600</strong></td>
                            <td><strong style="color: #38bdf8;">1.000</strong></td>
                            <td style="color: #f87171;"><strong>-40.0%</strong></td>
                            <td style="color: #34d399;"><strong>100.0%</strong></td>
                        </tr>
                        <tr>
                            <td><strong>Mean Token F1</strong></td>
                            <td><strong>1.000</strong></td>
                            <td><strong>0.851</strong></td>
                            <td><strong>1.000</strong></td>
                            <td style="color: #f87171;">-14.9%</td>
                            <td style="color: #34d399;">100.0%</td>
                        </tr>
                        <tr>
                            <td><strong>LLM Judge Score (Thang 1-5)</strong></td>
                            <td><strong>5.00 / 5.0</strong></td>
                            <td><strong style="color: #fbbf24;">4.30 / 5.0</strong></td>
                            <td><strong>5.00 / 5.0</strong></td>
                            <td style="color: #fbbf24;">-0.70 điểm</td>
                            <td style="color: #34d399;">100.0%</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- TAB 3: 6 INJECTED CORRUPTIONS -->
        <div id="tab-corruptions" class="tab-content">
            <h2 style="font-size: 1.15rem; margin-bottom: 1rem;">🦠 6 Dạng Lỗi Tiêm Vào Dữ Liệu Để Chứng Minh Silent Failure</h2>
            <div class="corruption-grid">
                <div class="corr-card">
                    <div class="corr-title">1. Drop Latest Records (Bỏ rơi 20% bài mới)</div>
                    <div class="corr-desc">Xóa 4 bản ghi mới nhất trước khi nạp vào vector store. Khi người dùng hỏi về các nghiên cứu mới này, ChromaDB hoàn toàn không có dữ liệu dẫn đến trượt mục tiêu tìm kiếm (Retrieval Miss).</div>
                    <span class="corr-tag">Tác động: Retrieval Hit Rate sụt giảm trực tiếp (-40%)</span>
                </div>
                <div class="corr-card">
                    <div class="corr-title">2. Blank Summary (Xóa trắng tóm tắt)</div>
                    <div class="corr-desc">Xóa rỗng trường summary của 2 bài báo. Vector index mất thông tin cốt lõi khiến AI phải suy đoán bịa chuyện (Hallucination) hoặc trả về chuỗi rỗng.</div>
                    <span class="corr-tag">Tác động: Vi phạm ExpectColumnValueLengthsToBeBetween</span>
                </div>
                <div class="corr-card">
                    <div class="corr-title">3. Inject Noise Tokens (Chèn ký tự rác)</div>
                    <div class="corr-desc">Chèn chuỗi ký tự rác vô nghĩa [##$$!! ERR_CORRUPT_SEGMENT 0xDEADBEEF @@&&%%] vào tóm tắt, làm sai lệch không gian vector embeddings và phá vỡ độ tương đồng Cosine.</div>
                    <span class="corr-tag">Tác động: Giảm độ tương đồng Cosine Similarity</span>
                </div>
                <div class="corr-card">
                    <div class="corr-title">4. Truncate Titles (Cắt ngắn tiêu đề)</div>
                    <div class="corr-desc">Cắt toàn bộ tiêu đề bài báo xuống chữ "Paper", làm mất tính phân biệt và triệt tiêu khả năng tìm kiếm chính xác theo tên bài báo.</div>
                    <span class="corr-tag">Tác động: Lỗi tra cứu tựa đề nghiên cứu</span>
                </div>
                <div class="corr-card">
                    <div class="corr-title">5. Stale Dates (Lùi ngày xuất bản về quá khứ)</div>
                    <div class="corr-desc">Lùi ngày xuất bản về 365 ngày trước, khiến 36.4% bài báo bị quá hạn 180 ngày (vượt quá ngưỡng cho phép 25%), kích hoạt cảnh báo đỏ Freshness SLA.</div>
                    <span class="corr-tag">Tác động: is_fresh = False (Freshness SLA Violated)</span>
                </div>
                <div class="corr-card">
                    <div class="corr-title">6. Duplicate Rows (Nhân bản dữ liệu)</div>
                    <div class="corr-desc">Nhân bản trùng lặp các dòng dữ liệu bài báo gây lãng phí dung lượng và làm nhiễu kết quả Top-k tìm kiếm.</div>
                    <span class="corr-tag">Tác động: Vi phạm ExpectColumnValuesToBeUnique</span>
                </div>
            </div>
        </div>

        <!-- TAB 4: QUALITY GATE & SLA -->
        <div id="tab-quality" class="tab-content">
            <h2 style="font-size: 1.15rem; margin-bottom: 1rem;">🛡️ Trạm Kiểm Dịch Great Expectations 1.x & Freshness SLA</h2>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Expectation Kiểm Tra</th>
                            <th>Mục Tiêu Kiểm Định</th>
                            <th>Dữ Liệu Sạch (Baseline)</th>
                            <th>Dữ Liệu Lỗi (Corrupted)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><code>ExpectTableRowCountToBeBetween</code></td>
                            <td>Số lượng bản ghi trong khoảng 5 - 5000 dòng</td>
                            <td><span class="badge badge-success">PASSED (24 rows)</span></td>
                            <td><span class="badge badge-success">PASSED (22 rows)</span></td>
                        </tr>
                        <tr>
                            <td><code>ExpectColumnValuesToNotBeNull</code></td>
                            <td>Cột paper_id, title, text_for_embedding không null</td>
                            <td><span class="badge badge-success">PASSED (0 nulls)</span></td>
                            <td><span class="badge badge-success">PASSED</span></td>
                        </tr>
                        <tr>
                            <td><code>ExpectColumnValuesToBeUnique</code></td>
                            <td>Khóa định danh paper_id phải là duy nhất</td>
                            <td><span class="badge badge-success">PASSED (Unique)</span></td>
                            <td><span class="badge badge-danger">FAILED (Bị nhân bản)</span></td>
                        </tr>
                        <tr>
                            <td><code>ExpectColumnValueLengthsToBeBetween</code></td>
                            <td>Tóm tắt summary phải dài tối thiểu 30 ký tự</td>
                            <td><span class="badge badge-success">PASSED (>= 30 ký tự)</span></td>
                            <td><span class="badge badge-danger">FAILED (Xóa rỗng summary)</span></td>
                        </tr>
                        <tr>
                            <td><code>Freshness SLA (Ngưỡng 180 ngày)</code></td>
                            <td>Tỷ lệ bài báo quá hạn không vượt quá 25%</td>
                            <td><span class="badge badge-success">FRESH (4.2% &lt; 25%)</span></td>
                            <td><span class="badge badge-danger">STALE (36.4% &gt; 25%)</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <script>
        let currentCollection = 'baseline';
        let currentMode = 'semantic';
        let isCustomQuery = false;
        let standardQuestions = [];
        let semanticQuestions = [];
        let currentQuestions = [];

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }

        function changeCollection(col) {
            currentCollection = col;
            document.querySelectorAll('.collection-opt').forEach(el => el.classList.remove('active'));
            document.getElementById('opt-' + col).classList.add('active');
            closeSideBySide();
            submitQuery();
        }

        function setQuestionMode(mode) {
            currentMode = mode;
            document.getElementById('btn-mode-semantic').classList.toggle('active', mode === 'semantic');
            document.getElementById('btn-mode-standard').classList.toggle('active', mode === 'standard');
            document.getElementById('btn-mode-custom').classList.toggle('active', mode === 'custom');

            if (mode === 'custom') {
                enableCustomMode();
            } else {
                isCustomQuery = false;
                document.getElementById('input-mode-label').innerText = 'Chế độ câu hỏi mẫu';
                document.getElementById('input-mode-label').style.color = '#38bdf8';
                renderQuestions();
            }
        }

        function enableCustomMode() {
            isCustomQuery = true;
            document.querySelectorAll('.chip').forEach(el => el.classList.remove('active'));
            document.getElementById('input-mode-label').innerText = '✏️ Chế độ: Tự Nhập Tự Do';
            document.getElementById('input-mode-label').style.color = '#34d399';

            const container = document.getElementById('sample-list');
            container.innerHTML = `
                <div style="font-size:0.75rem; color:#9ca3af; line-height:1.45; padding:0.4rem 0.2rem;">
                    💡 <strong>Gợi ý từ khóa tìm kiếm vector:</strong><br>
                    • <em>"BM25 and dense representations"</em><br>
                    • <em>"continuous benchmark evaluation drift"</em><br>
                    • <em>"Great Expectations data quality CI/CD"</em><br>
                    • <em>"multi-agent debate architecture"</em>
                </div>
            `;

            const queryInput = document.getElementById('query-text');
            if (!queryInput.value || queryInput.value.includes("'")) {
                queryInput.value = "How does hybrid search combine BM25 with dense vector embeddings?";
            }
            queryInput.focus();

            const refCardTitle = document.getElementById('ref-card-title');
            const refContent = document.getElementById('ref-content');
            const doiBadge = document.getElementById('target-doi-badge');

            refCardTitle.innerText = "💡 Hướng Dẫn Truy Vấn Tự Do (Ad-hoc Search)";
            doiBadge.innerText = "Chế độ Ad-hoc";
            refContent.innerHTML = `
                Hệ thống đang chạy <strong>100% Dense Vector Search thực tế</strong>.<br>
                Mô hình <code>sentence-transformers/all-MiniLM-L6-v2</code> sẽ encode câu hỏi thành vector 384 chiều và tính toán độ tương đồng Cosine Similarity trực tiếp trên <strong>ChromaDB</strong>.
            `;

            closeSideBySide();
            submitQuery();
        }

        async function initData() {
            try {
                const resStd = await fetch('/api/questions');
                standardQuestions = await resStd.json();

                const resSem = await fetch('/api/semantic_challenges');
                semanticQuestions = await resSem.json();

                // Attach oninput event to textarea so typing switches cleanly to custom mode
                document.getElementById('query-text').addEventListener('input', () => {
                    isCustomQuery = true;
                    document.querySelectorAll('.chip').forEach(el => el.classList.remove('active'));
                    document.getElementById('input-mode-label').innerText = '✏️ Chế độ: Tự Nhập Tự Do';
                    document.getElementById('input-mode-label').style.color = '#34d399';
                    document.getElementById('btn-mode-semantic').classList.remove('active');
                    document.getElementById('btn-mode-standard').classList.remove('active');
                    document.getElementById('btn-mode-custom').classList.add('active');

                    document.getElementById('ref-card-title').innerText = "💡 Truy Vấn Tự Do (Ad-hoc Query)";
                    document.getElementById('target-doi-badge').innerText = "Ad-hoc";
                    document.getElementById('ref-content').innerHTML = "Đang gõ câu hỏi tự do. Bấm nút <strong>'🚀 Chạy Truy Vấn RAG'</strong> bên dưới để thực thi vector search.";
                });

                renderQuestions();
            } catch (err) {
                console.error(err);
            }
        }

        function renderQuestions() {
            currentQuestions = (currentMode === 'semantic') ? semanticQuestions : standardQuestions;
            const container = document.getElementById('sample-list');
            container.innerHTML = '';

            currentQuestions.forEach((q, idx) => {
                const chip = document.createElement('div');
                chip.className = 'chip' + (idx === 0 ? ' active' : '');

                let tagHtml = '';
                if (currentMode === 'semantic') {
                    tagHtml = `<span class="chip-badge badge-flaw">${q.tag}</span>`;
                } else {
                    const isFlawCandidate = idx < 4;
                    tagHtml = isFlawCandidate
                        ? `<span class="chip-badge badge-flaw">🚨 Drop Flaw (#${idx+1})</span>`
                        : `<span class="chip-badge badge-norm">✅ Clean (#${idx+1})</span>`;
                }

                chip.innerHTML = `
                    <div>${tagHtml}</div>
                    <div style="font-size:0.77rem; line-height:1.35;">${q.question}</div>
                `;
                chip.onclick = () => selectQuestion(idx);
                container.appendChild(chip);
            });

            if (currentQuestions.length > 0) {
                selectQuestion(0);
            }
        }

        function selectQuestion(idx) {
            isCustomQuery = false;
            document.getElementById('input-mode-label').innerText = 'Chế độ câu hỏi mẫu';
            document.getElementById('input-mode-label').style.color = '#38bdf8';

            document.querySelectorAll('.chip').forEach((el, i) => {
                if (i === idx) el.classList.add('active');
                else el.classList.remove('active');
            });
            const q = currentQuestions[idx];
            document.getElementById('query-text').value = q.question;

            const refCard = document.getElementById('ref-card');
            const refCardTitle = document.getElementById('ref-card-title');
            const refContent = document.getElementById('ref-content');
            const doiBadge = document.getElementById('target-doi-badge');

            refCard.style.display = 'block';
            refCardTitle.innerText = "🎯 Đáp Án Chuẩn & Giải Thích Hiện Tượng";
            let refText = q.ground_truth || '';
            if (q.flaw_explanation) {
                refText += `\\n\\n💡 GIẢI THÍCH HIỆN TƯỢNG:\\n${q.flaw_explanation}`;
            }
            refContent.innerText = refText;

            const doi = q.target_doi || (q.ground_truth_doc_ids ? q.ground_truth_doc_ids[0] : 'N/A');
            doiBadge.innerText = 'Target DOI: ' + doi;

            closeSideBySide();
            submitQuery();
        }

        async function submitQuery() {
            const query = document.getElementById('query-text').value.trim();
            if (!query) {
                alert('Vui lòng nhập nội dung câu hỏi!');
                return;
            }

            const btn = document.getElementById('btn-run');
            btn.disabled = true;
            btn.innerText = '⏳ Đang truy vấn ChromaDB...';

            try {
                const res = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: query,
                        collection: currentCollection,
                        top_k: 3
                    })
                });
                const data = await res.json();

                // 1. Update Answer Box
                const ansText = data.answer ? `"${data.answer}"` : "(⚠️ RỖNG: Không trích xuất được câu trả lời do trường summary của bài báo này bị xóa sạch!)";
                document.getElementById('answer-content').innerText = ansText;
                document.getElementById('ans-collection-badge').innerText = `Collection: ${data.collection_name}`;

                // 2. Update Status Banner with precise details
                const banner = document.getElementById('status-banner');
                const bannerTitle = document.getElementById('banner-title');
                const bannerBadge = document.getElementById('banner-badge');
                const bannerDesc = document.getElementById('banner-desc');
                banner.style.display = 'flex';

                if (data.is_custom) {
                    banner.className = 'alert-banner alert-custom';
                    bannerTitle.innerHTML = '🔍 <strong>CHROMA VECTOR SEARCH:</strong> Truy xuất thành công Top tài liệu liên quan!';
                    bannerBadge.className = 'badge badge-warning';
                    bannerBadge.innerText = `Top 1: ${data.top_score}%`;
                    bannerDesc.innerHTML = `
                        <strong>Truy vấn tự do:</strong> Đã encode câu hỏi qua mô hình Sentence-Transformers (384 chiều) và tìm kiếm Cosine Similarity.<br>
                        Tài liệu phù hợp nhất: <em>"${data.top_retrieved_title}"</em> (DOI: <code>${data.top_retrieved_doi}</code> - Độ tương đồng: <strong>${data.top_score}%</strong>).
                    `;
                } else if (data.is_hit) {
                    banner.className = 'alert-banner alert-hit';
                    bannerTitle.innerHTML = '✅ <strong>RETRIEVAL HIT:</strong> Tìm thấy chính xác bài báo mục tiêu trong Top 3!';
                    bannerBadge.className = 'badge badge-success';
                    bannerBadge.innerText = `Hit: True (${data.top_score}%)`;
                    bannerDesc.innerHTML = `Đã tìm đúng mã DOI mục tiêu: <code>${data.target_doc_id || 'N/A'}</code> trong Top-3 ChromaDB.`;
                } else {
                    banner.className = 'alert-banner alert-miss';
                    bannerTitle.innerHTML = '🚨 <strong>SILENT FAILURE DETECTED:</strong> Truy xuất THẤT BẠI (-40% degradation)!';
                    bannerBadge.className = 'badge badge-danger';
                    bannerBadge.innerText = 'Retrieval Miss';
                    bannerDesc.innerHTML = `
                        <strong>Hậu quả:</strong> Không tìm thấy bài báo mục tiêu <code>${data.target_doc_id || 'N/A'}</code> do đã bị lỗi dữ liệu xóa bỏ khỏi kho vector!<br>
                        Hệ thống đã truy xuất nhầm bài: <em>"${data.top_retrieved_title || 'N/A'}"</em> (DOI: <code>${data.top_retrieved_doi || 'N/A'}</code>).<br>
                        ⚠️ <strong>Đặc điểm Silent Failure:</strong> Ứng dụng AI không hề văng lỗi crash, nhưng đưa ra câu trả lời sai lệch hoặc rỗng cho người dùng!
                    `;
                }

                // 3. Update Context List with REAL similarity scores
                const ctxList = document.getElementById('context-list');
                ctxList.innerHTML = '';
                if (data.retrieved && data.retrieved.length > 0) {
                    data.retrieved.forEach((item, idx) => {
                        const div = document.createElement('div');
                        div.className = 'context-item';
                        if (item.is_target) {
                            div.style.borderColor = '#10b981';
                        }
                        div.innerHTML = `
                            <div class="context-header">
                                <span class="context-title">${idx + 1}. [DOI: ${item.doc_id}] - ${item.title}</span>
                                <div>
                                    ${item.is_target ? '<span class="badge badge-success" style="margin-right:6px;">🎯 TARGET MATCH</span>' : ''}
                                    <span class="badge" style="background:#1f2937; color:#38bdf8;">Chroma Cosine: ${item.score}%</span>
                                </div>
                            </div>
                            <div style="font-size:0.73rem; color:#6b7280; margin-bottom:0.35rem;">
                                👤 Tác giả: ${item.authors || 'N/A'} | 📅 Ngày xuất bản: ${item.published || 'N/A'}
                            </div>
                            <div class="context-body">${item.content}</div>
                        `;
                        ctxList.appendChild(div);
                    });
                    document.getElementById('context-count').innerText = `Tìm thấy ${data.retrieved.length} tài liệu (ChromaDB)`;
                } else {
                    ctxList.innerHTML = '<p style="color:var(--text-muted); padding:0.5rem 0;">Không tìm thấy tài liệu phù hợp.</p>';
                }

            } catch (err) {
                alert('Lỗi khi truy vấn: ' + err);
            } finally {
                btn.disabled = false;
                btn.innerText = '🚀 Chạy Truy Vấn RAG';
            }
        }

        async function runSideBySide() {
            const query = document.getElementById('query-text').value.trim();
            if (!query) {
                alert('Vui lòng nhập câu hỏi để so sánh!');
                return;
            }

            document.getElementById('status-banner').style.display = 'none';
            document.getElementById('single-view-output').style.display = 'none';
            document.getElementById('side-by-side-output').style.display = 'block';

            document.getElementById('side-base-ans').innerText = 'Đang truy vấn kho Baseline...';
            document.getElementById('side-corr-ans').innerText = 'Đang truy vấn kho Corrupted...';

            try {
                const [resBase, resCorr] = await Promise.all([
                    fetch('/api/ask', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ question: query, collection: 'baseline', top_k: 3 })
                    }).then(r => r.json()),
                    fetch('/api/ask', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ question: query, collection: 'corrupted', top_k: 3 })
                    }).then(r => r.json())
                ]);

                // Render Baseline
                document.getElementById('side-base-ans').innerText = resBase.answer || '(Rỗng)';
                document.getElementById('side-base-score').className = 'badge badge-success';
                document.getElementById('side-base-score').innerText = `Top 1: ${resBase.top_score}%`;
                document.getElementById('side-base-doc').innerHTML = `
                    <strong>[DOI: ${resBase.top_retrieved_doi}]</strong><br>
                    ${resBase.top_retrieved_title}<br>
                    <span style="font-size:0.72rem; color:#6b7280;">Similarity: ${resBase.top_score}%</span>
                `;

                // Render Corrupted
                document.getElementById('side-corr-ans').innerText = resCorr.answer || '(⚠️ RỖNG: Do trường summary bị xóa sạch!)';
                const isCorruptedFlaw = (resCorr.top_retrieved_doi !== resBase.top_retrieved_doi) || !resCorr.answer || resCorr.answer.includes('0xDEADBEEF');
                document.getElementById('side-corr-score').className = isCorruptedFlaw ? 'badge badge-danger' : 'badge badge-warning';
                document.getElementById('side-corr-score').innerText = `Top 1: ${resCorr.top_score}%`;
                document.getElementById('side-corr-doc').innerHTML = `
                    <strong>[DOI: ${resCorr.top_retrieved_doi}]</strong><br>
                    ${resCorr.top_retrieved_title}<br>
                    <span style="font-size:0.72rem; color:#6b7280;">Similarity: ${resCorr.top_score}%</span>
                `;

            } catch (err) {
                alert('Lỗi so sánh: ' + err);
            }
        }

        function closeSideBySide() {
            document.getElementById('side-by-side-output').style.display = 'none';
            document.getElementById('single-view-output').style.display = 'block';
        }

        window.onload = initData;
    </script>
</body>
</html>
"""


class StudioServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if path == "/api/questions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(TESTSET).encode("utf-8"))
            return

        if path == "/api/semantic_challenges":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(SEMANTIC_CHALLENGES).encode("utf-8"))
            return

        if path == "/api/status":
            summary = {
                "baseline": read_json(SETTINGS.paths.baseline_metrics) if SETTINGS.paths.baseline_metrics.exists() else {},
                "corrupted": read_json(SETTINGS.paths.corrupted_metrics) if SETTINGS.paths.corrupted_metrics.exists() else {},
                "repaired": read_json(SETTINGS.paths.repaired_metrics) if SETTINGS.paths.repaired_metrics.exists() else {},
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(summary).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/ask":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            question = data.get("question", "").strip()
            collection_type = data.get("collection", "baseline")
            top_k = int(data.get("top_k", 3))

            index = get_or_load_index(collection_type)

            # 1. Thuc hien Dense Vector Search thuc te 100% tren ChromaDB
            retrieved_raw: list[SearchResult] = index.search(question, top_k=top_k)

            # 2. Kiem tra xem cau hoi co chua tieu de trong dau ngoac don de ho tro exact lookup (nhu code Member 1)
            title_match = re.search(r"'([^']+)'", question)
            exact = index.lookup(title_match.group(1)) if title_match else None

            if exact:
                exact_result = SearchResult(
                    paper_id=exact["paper_id"],
                    title=exact["title"],
                    score=1.0,
                    content=exact["content"],
                    metadata=exact["metadata"],
                )
                deduped = [exact_result] + [item for item in retrieved_raw if item.paper_id != exact_result.paper_id]
                retrieved_results = deduped[:top_k]
            else:
                retrieved_results = retrieved_raw

            # 3. Trich xuat cau tra loi (qua ham chuan _extract_answer cua Member 1)
            if not retrieved_results:
                answer = "I don't know from the indexed corpus."
            else:
                answer = _extract_answer(question, retrieved_results[0])

            # 4. Kiem tra xem co phai cau hoi mau khong (de bat Ground Truth DOI)
            target_doc_id = None
            expected_title = None

            for sem in SEMANTIC_CHALLENGES:
                if sem["question"].strip().lower() == question.lower():
                    target_doc_id = sem["target_doi"]
                    expected_title = sem["target_title"]
                    break

            if not target_doc_id:
                item = TESTSET_MAP.get(question)
                if item and item.get("ground_truth_doc_ids"):
                    target_doc_id = item["ground_truth_doc_ids"][0]

            if not target_doc_id and title_match:
                expected_title = title_match.group(1).strip()
                target_doc_id = TITLE_TO_PAPER_ID.get(expected_title.lower())

            # Neu khong khop voi bat ky cau benchmark nao -> Day la cau hoi tu do (Custom Query)
            is_custom = (target_doc_id is None)

            # Kiem tra Retrieval Hit chuan xac
            is_hit = False
            if target_doc_id:
                is_hit = any(item.paper_id == target_doc_id for item in retrieved_results)

            retrieved_items = []
            for item in retrieved_results:
                is_target = (target_doc_id is not None and item.paper_id == target_doc_id)
                # Lay diem Cosine Similarity THUC TE tu ChromaDB (item.score)
                real_score_pct = round(item.score * 100, 2)
                retrieved_items.append({
                    "doc_id": item.paper_id,
                    "title": item.title,
                    "content": item.content,
                    "score": real_score_pct,
                    "is_target": is_target,
                    "authors": item.metadata.get("authors_joined", ""),
                    "published": item.metadata.get("published", ""),
                    "categories": item.metadata.get("categories_joined", ""),
                })

            top_retrieved_doi = retrieved_results[0].paper_id if retrieved_results else "N/A"
            top_retrieved_title = retrieved_results[0].title if retrieved_results else "N/A"
            top_score = round(retrieved_results[0].score * 100, 2) if retrieved_results else 0.0

            response = {
                "question": question,
                "answer": answer,
                "collection_name": index.collection_name,
                "is_custom": is_custom,
                "target_doc_id": target_doc_id,
                "expected_title": expected_title,
                "top_retrieved_doi": top_retrieved_doi,
                "top_retrieved_title": top_retrieved_title,
                "top_score": top_score,
                "is_hit": is_hit,
                "retrieved": retrieved_items,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


def start_server(port: int = 8501):
    actual_port = port
    for p in (port, 8080, 8000, 8888):
        try:
            httpd = HTTPServer(("127.0.0.1", p), StudioServer)
            actual_port = p
            break
        except OSError:
            continue
    else:
        print("[Loi] Khong the mo port tren localhost.")
        return

    url = f"http://127.0.0.1:{actual_port}"
    print("=" * 72)
    print("  🚀 RAG DATA OBSERVABILITY & QUALITY STUDIO ĐÃ KHỞI CHẠY THÀNH CÔNG!")
    print(f"  👉 Truy cập giao diện trực tiếp tại: {url}")
    print("  👉 Nhấn Ctrl + C trong terminal này để dừng.")
    print("=" * 72)

    threading.Thread(target=lambda: (time.sleep(1), webbrowser.open(url)), daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Studio] Da dong server thanh cong.")


if __name__ == "__main__":
    start_server()
