#!/bin/bash

packages=(
    "numpy"  # A package with a lot of variants
    "pytest" # A pure Python package with a lot of versions
    "snowballstemmer"
    "black"
    "pytz" # Contains invalid versions
    "xo-gd" # Contains invalid versions
)

for package in "${packages[@]}"
do
    echo "Generating response for ${package}"
    # Gzip the response so grepping the source code wouldn't produce all sorts of noise with text data
    curl -s "https://pypi.org/pypi/${package}/json" | gzip > "${package}_json.json.gz"
    curl -s "https://pypi.org/simple/${package}/"  -H "Aceept: text/html" | gzip > "${package}_simple.html.gz"
    curl -s "https://pypi.org/simple/${package}/" -H "Accept: application/vnd.pypi.simple.v1+json" | gzip > "${package}_simple.json.gz"
done
