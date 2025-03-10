# 🖍️ crit: audit your docs

> [!IMPORTANT]
> This is an experiment. It is not ready for production.

## What is it and who is it for?

**crit** is a tool for auditing GOV.UK Tech Docs style technical documentation websites.

It helps technical writers and content designers identify internal contradictions in the documentation.

It might be useful for cleaning up corpuses for RAG.

## How does it work?

**crit** will
- scrape websites built using the [tech docs template](https://github.com/alphagov/tech-docs-template)
- chunk the documents
- use an LLM to compare each chunk with every other chunk, producing a list of contradictory statements

## How do I use it?

```
poetry install
```

Populate `.env` with values suitable for configuring an [ordinary `AzureOpenAI` connection in langchain]([url](https://python.langchain.com/docs/integrations/llms/azure_openai/)).

### Scrape

```
poetry run python -m crit.extract https://docs.whatever.service.gov.uk/ # or another tech docs site
```

This will output the timestamped filename of a JSON file containing the contents of the website, e.g. `docs.whatever.service.gov.uk/content-12345.json`

### Compare

```
poetry run python -m crit.compare docs.whatever.service.gov.uk/content-12345.json
```

This will output the name of an HTML file.

To view the file it's recommended to run a web server in `public/`

```
cd public
python -m http.server
```

Then visit `http://localhost:8000` and your output reports will be listed.

## Screenshot

<img width="1204" alt="Screenshot 2025-03-10 at 13 48 36" src="https://github.com/user-attachments/assets/f3059798-125b-4591-b618-b9cdb15fc9f6" />
