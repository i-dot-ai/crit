#!/bin/bash

poetry run python extract.py
cat html_to_markdown_mapping.json
cat html_to_markdown_mapping.json | pbcopy
printf "\nCopied to clipboard!\n"
