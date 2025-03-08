import tiktoken
import json
import itertools
from typing import Dict, List, Tuple, Generator, Any
from langchain_openai import AzureChatOpenAI
from pathlib import Path
from langchain_core.prompts import PromptTemplate
import uuid


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 20) -> Dict[str, str]:
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)

    chunks = {}
    i = 0

    while i < len(tokens):
        id = str(uuid.uuid4())[:8]
        end = min(i + chunk_size, len(tokens))
        chunk_tokens = tokens[i:end]

        chunk_text = enc.decode(chunk_tokens)
        chunks[id] = chunk_text

        i += chunk_size - overlap

    return chunks


def generate_comparison_pairs(
    chunk_ids: List[str],
) -> Generator[Tuple[str, str], None, None]:
    return itertools.combinations_with_replacement(chunk_ids, 2)


def process_llm_comparisons(
    chunks: Dict[str, str], comparison_pairs: Generator[Tuple[str, str], None, None]
) -> List[Dict[str, Any]]:
    results = []
    for chunk1_id, chunk2_id in comparison_pairs:
        chunk1_text = chunks[chunk1_id]
        chunk2_text = chunks[chunk2_id]

        llm_result = llm_compare_chunks(
            chunk1_id, chunk2_id, chunk1_text, chunk2_text)

        results.append(llm_result)

    return results


def llm_compare_chunks(
    chunk1_id: str, chunk2_id: str, chunk1_text: str, chunk2_text: str
) -> Dict[str, Any]:
    llm = AzureChatOpenAI(
        model_name="gpt-4o",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    prompts_path = Path("prompts")
    with Path.open(prompts_path / "combinations-v1.txt") as file:
        prompt = file.read()
    template = PromptTemplate.from_template(template=prompt)
    prompt = template.format(
        chunk1_id=chunk1_id,
        chunk2_id=chunk2_id,
        chunk1_text=chunk1_text,
        chunk2_text=chunk2_text,
    )

    print(prompt)

    response = llm.invoke(prompt)
    print(response)
    exit()

def reduce_findings(
    comparison_results: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Reduce the list of comparison results into a structure mapping
    chunk IDs to their findings.

    Args:
        comparison_results: List of comparison result dictionaries

    Returns:
        Dictionary mapping chunk IDs to lists of findings
    """
    reduced_findings = {}

    for result in comparison_results:
        chunk1_id = result["chunk1"]
        findings = result["findings"]

        if chunk1_id not in reduced_findings:
            reduced_findings[chunk1_id] = []

        reduced_findings[chunk1_id].append(findings)

    return reduced_findings


def main(text: str):
    """
    Main function to process a text document.

    Args:
        text: Input text to process
    """
    # Step 1: Break text into chunks
    chunks = chunk_text(text, chunk_size=512, overlap=20)
    print(f"Created {len(chunks)} chunks")

    # Step 2: Generate comparison pairs
    chunk_ids = list(chunks.keys())
    comparison_pairs = generate_comparison_pairs(chunk_ids)

    # Step 3: Process comparisons through LLM
    comparison_results = process_llm_comparisons(chunks, comparison_pairs)

    # Step 4: Reduce findings
    reduced_findings = reduce_findings(comparison_results)

    # Output the results
    print(json.dumps(reduced_findings, indent=2))

    return reduced_findings


# Example usage
if __name__ == "__main__":
    sample_text = """This is a sample text. It will be broken into chunks using tiktoken.
    Each chunk will be compared with other chunks to analyze similarities and differences.
    The results will be processed and reduced into a structured format."""

    main(sample_text)
