import tiktoken
import json
import os
import itertools
from typing import Dict, List, Tuple, Any
import datetime
from langchain_openai import AzureChatOpenAI
from pathlib import Path
from langchain_core.prompts import PromptTemplate
import sys
import hashlib
import time
import random
from crit.logging import logger
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
import mistune
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)
from pydantic import BaseModel


load_dotenv()


class Chunk(BaseModel):
    id: str
    text: str
    title: str
    document: str


def content_json_to_chunks(
    scrape: dict, chunk_size: int, overlap: int
) -> Dict[str, Chunk]:
    doc_count = len(scrape.keys())
    logger.info(
        "Turning scrape into chunks. "
        f"Documents in scrape: {doc_count}. "
        f"Chunk size {chunk_size}. Overlap {overlap}."
    )

    output = {}
    for document, content in scrape.items():
        if not content:
            continue

        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(content["text"])

        i = 0

        while i < len(tokens):
            end = min(i + chunk_size, len(tokens))
            chunk_tokens = tokens[i:end]

            chunk_text = enc.decode(chunk_tokens)
            id = hashlib.shake_128(chunk_text.encode("utf-8")).hexdigest(
                4
            )  # consistent hashes

            output[id] = Chunk(
                id=id,
                text=chunk_text,
                title=content["title"],
                document=document,
            )

            i += chunk_size - overlap

    logger.info(f"Chunk count: {len(output.keys())}")
    return output


def generate_comparison_pairs(
    chunk_ids: List[str],
) -> list[Tuple[str, str], None, None]:
    return list(itertools.combinations_with_replacement(chunk_ids, 2))


def process_llm_comparisons(
    chunks: Dict[str, Chunk], comparison_pairs: list[Tuple[str, str], None, None]
) -> List[Dict[str, Any]]:
    results = []
    comparison_count = len(comparison_pairs)

    experimenting = True
    if experimenting:
        max_pairs = 2
        random.shuffle(comparison_pairs)
        comparison_pairs = comparison_pairs[:max_pairs]
        logger.info(f"Comparing up to {max_pairs} pairs (experiment=True)")
    else:
        logger.info(f"Comparing all {comparison_count} pairs")

    i = 1
    token_counts = {"input": 0, "output": 0, "cost": 0.0}
    for chunk1_id, chunk2_id in comparison_pairs:
        logger.info(f"Comparison {i} of {comparison_count}: {
                    chunk1_id} vs {chunk2_id}")
        chunk1 = chunks[chunk1_id]
        chunk2 = chunks[chunk2_id]

        llm_result = llm_compare_chunks(chunk1, chunk2, token_counts)

        output = {
            "result": llm_result,
            "chunk1": chunk1.model_dump_json(),
            "chunk2": chunk2.model_dump_json(),
        }

        results.append(output)
        logger.info(token_counts)  # keep a running total
        i += 1

    return results


@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def llm_compare_chunks(chunk1, chunk2, token_counts) -> Dict[str, Any]:
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
        chunk1_id=chunk1.id,
        chunk2_id=chunk2.id,
        chunk1_doc=chunk1.document,
        chunk2_doc=chunk2.document,
        chunk1_title=chunk1.title,
        chunk2_title=chunk2.title,
        chunk1_text=chunk1.text,
        chunk2_text=chunk2.text
    )

    response = llm.invoke(prompt)
    output = json.loads(response.content)
    token_counts["input"] += response.usage_metadata["input_tokens"]
    token_counts["output"] += response.usage_metadata["output_tokens"]

    input_cost = 0.000000015 * token_counts["input"]
    output_cost = 0.0000006 * token_counts["output"]
    token_counts["cost"] += input_cost + output_cost

    return output


def reduce_findings(
    comparison_results: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    reduced_findings = []

    for result in comparison_results:
        findings = result["result"]["findings"]
        reduced_findings.extend(findings)

    return reduced_findings


def generate_crit_report(findings, output_path):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("report.html")

    # markdown -> HTML
    for finding in findings:
        for ref in finding["references"]:
            ref["quotation_html"] = mistune.html(ref["quotation"])

    html = template.render(
        findings=findings, generation_date=datetime.datetime.now().strftime("%B %d, %Y")
    )

    # Write to file
    real_output_path = Path("public") / output_path
    with open(real_output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"Report generated: {os.path.abspath(real_output_path)}")
    return os.path.abspath(output_path)


def main(scrape: dict):
    approach = "brute"

    chunk_map = content_json_to_chunks(scrape, chunk_size=768, overlap=20)

    if approach == "brute":
        chunk_ids = list(chunk_map.keys())
        comparison_pairs = generate_comparison_pairs(chunk_ids)
    elif approach == "vector":
        comparison_pairs = generate_comparison_pairs_by_vector(chunk_map)

    comparison_results = process_llm_comparisons(chunk_map, comparison_pairs)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, ensure_ascii=False, indent=4)

    reduced_findings = reduce_findings(comparison_results)

    findings_count = len(reduced_findings)

    if findings_count == 0:
        logger.info("No contradictions found")
        exit(0)
    else:
        logger.info(f"Found {len(reduced_findings)} contradiction(s)")

    t = int(time.time())
    with open(f"3-outputs/{t}.json", "w", encoding="utf-8") as f:
        json.dump(reduced_findings, f, ensure_ascii=False, indent=4)

    output = []
    for finding in reduced_findings:
        rationale = finding["rationale"]
        references = []
        for fragment in finding["fragments"]:
            chunk_id = fragment["chunk_id"]
            chunk_details = chunk_map[chunk_id]

            document = chunk_details["document"]
            quotation = fragment["quotation"]

            references.append({"document": document, "quotation": quotation})

        output.append({"rationale": rationale, "references": references})

    output_path = generate_crit_report(output, f"report-{t}.html")
    logger.info(f"Wrote report to {output_path}")


# Example usage
if __name__ == "__main__":
    content_file = sys.argv[1]
    logger.info("🖍️🖍️🖍️ crit 🖍️🖍️🖍️")
    logger.info(f"Loading scrape content from {content_file}")
    with Path.open(f"2-content/{content_file}") as file:
        scrape_content = json.load(file)

    main(scrape_content)
