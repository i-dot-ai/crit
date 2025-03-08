import json
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urlparse
from pathlib import Path
import os
import sys
import time
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()


def scrape(tech_docs_url):
    url = urlparse(tech_docs_url)  # will raise if not a url, safe for shell
    output_dir = Path("1-scrapes") / url.hostname

    if output_dir.exists():
        print("scrape exists")
        return output_dir

    cmd = (
        "wget --mirror -A.html --convert-links --adjust-extension "
        f"--no-parent -P {str(output_dir)} {tech_docs_url}"
    )
    os.system(cmd)
    return output_dir


def extract_main_and_convert(html_file):
    with open(html_file, "r", encoding="utf-8") as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, "html.parser")
    main = soup.find("main")

    if not main:
        return None

    expiry_div = main.find("div", attrs={"data-module": "page-expiry"})
    if expiry_div:
        expiry_div.decompose()

    return md(str(main))


def scrape_to_json(directory_path):
    directory = Path(directory_path)
    html_files = list(directory.rglob("*.html"))

    data_dir = Path("1-scrapes")
    result_map = {}

    for html_file in html_files:
        file_path = html_file.relative_to(data_dir)
        markdown_content = extract_main_and_convert(html_file)
        result_map[str(file_path)] = markdown_content

    return result_map


def generate_prompt(json: str) -> str:
    prompts_path = Path("prompts")
    with Path.open(prompts_path / "combinations-v1.txt") as file:
        prompt = file.read()
    template = PromptTemplate.from_template(template=prompt)
    return template.format(json=json)


def crit(json_file_path):
    llm = AzureChatOpenAI(
        model_name="gpt-4o",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    json_path = Path(json_file_path)
    with Path.open(json_path) as file:
        json = file.read()

    prompt = generate_prompt(json)
    print(prompt)

    response = llm.invoke(prompt)
    print(response)
    return response.content


def main():
    fqurl = sys.argv[1]
    url = urlparse(fqurl)

    # scrape
    scrape_dir = scrape(fqurl)
    results = scrape_to_json(scrape_dir)

    # parse
    t = int(time.time())
    content_dir = Path("2-content") / url.hostname
    content_dir.mkdir(exist_ok=True)
    content_path = content_dir / f"content-{t}.json"

    with open(content_path, "w", encoding="utf-8") as json_file:
        json.dump(results, json_file, ensure_ascii=False, indent=2)

    # llm
    output_dir = Path("3-outputs") / url.hostname
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"output-{t}.json"
    output_json = crit(content_path)
    with open(output_path, "w", encoding="utf-8") as json_file:
        json.dump(output_json, json_file, ensure_ascii=False, indent=2)

    print(output_path)


if __name__ == "__main__":
    main()
