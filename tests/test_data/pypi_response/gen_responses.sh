#!/bin/bash

packages=(
    "black"
    "pytest"
    "snowballstemmer"
)

for package in "${packages[@]}"
do
    echo "Generating response for ${package}"
    curl -s "https://pypi.org/pypi/${package}/json" > "${package}_json.json"
    # curl -s "https://pypi.org/simple/${package}/"  > "${package}_simple.html"
    curl -s "https://pypi.org/simple/${package}/" -H "Accept: application/vnd.pypi.simple.v1+json" > "${package}_simple.json"
done