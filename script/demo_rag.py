import sys
import warnings
from pathlib import Path

# Tranh loi font tren Windows console
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

warnings.filterwarnings("ignore")

# Dam bao import duoc src va venv
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
venv_site = project_root / ".venv" / "Lib" / "site-packages"
if venv_site.exists() and str(venv_site) not in sys.path:
    sys.path.insert(0, str(venv_site))

import pandas as pd
from core.config import load_settings
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def run_interactive_demo():
    settings = load_settings()
    print("=" * 70)
    print("      LIVE DEMO: HE THONG RETRIEVAL-AUGMENTED GENERATION (RAG)")
    print("=" * 70)
    print("Dang ket noi Vector Database (ChromaDB)...")

    # 1. Load Clean Data & Index
    clean_df = pd.read_json(settings.paths.clean_json)
    baseline_index = LocalEmbeddingIndex.build(
        clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    print(f"[OK] Da san sang collection '{settings.baseline_collection_name}' ({len(clean_df)} papers)")

    # 2. Danh sach cau hoi mau san co
    sample_questions = [
        "What is the summary of the paper 'Continuous Benchmark Evaluation for Enterprise Retrieval Pipelines'?",
        "Who authored the paper 'Multi-Agent Consensus for High-Stakes Fact Verification'?",
        "When was the paper 'Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks' published?",
        "What categories does the paper 'Evaluating Retrieval Precision with Token F1 and LLM Judges' belong to?",
    ]

    print("\n--- DANH SACH CAU HOI MAU DEMO NHANH ---")
    for idx, q in enumerate(sample_questions, 1):
        print(f"[{idx}] {q}")
    print("[0] Tu nhap cau hoi cua ban (Custom query)")
    print("-" * 70)

    while True:
        try:
            choice = input("\nChon so thu tu cau hoi (1-4, 0 de tu go, 'q' de thoat): ").strip()
            if choice.lower() in ("q", "exit", "quit"):
                print("Tam biet!")
                break

            if choice == "0":
                query = input("Nhap cau hoi RAG: ").strip()
                if not query:
                    continue
            elif choice.isdigit() and 1 <= int(choice) <= len(sample_questions):
                query = sample_questions[int(choice) - 1]
            else:
                print("Lua chon khong hop le, vui long chon lai.")
                continue

            print("\n" + "=" * 70)
            print(f"❓ CAU HOI (QUERY): {query}")
            print("=" * 70)

            # Chay RAG Pipeline: Vector Search -> Grounding -> Answer
            result = answer_question(query, settings=settings, index=baseline_index, top_k=3)

            print("\n🔍 KET QUA RETRIEVAL (TOP 3 CHROMA VECTOR SEARCH):")
            for i, (doc_id, title) in enumerate(zip(result.retrieved_doc_ids, result.retrieved_titles), 1):
                print(f"  {i}. [DOI: {doc_id}] - {title}")

            print("\n📄 NGU CANH TRICH XUAT (TOP CONTEXT):")
            top_ctx = result.retrieved_contexts[0] if result.retrieved_contexts else "N/A"
            for line in top_ctx.split("\n"):
                print(f"   | {line}")

            print("\n🤖 CAU TRA LOI CUA RAG (GENERATED ANSWER):")
            print(f"   👉 \"{result.answer}\"")
            print("=" * 70)

        except KeyboardInterrupt:
            print("\nThoat demo.")
            break
        except Exception as e:
            print(f"\n[Loi]: {e}")


if __name__ == "__main__":
    run_interactive_demo()
