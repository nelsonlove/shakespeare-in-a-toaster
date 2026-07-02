#!/bin/sh
# Copy the single-source lexicon into the static bundle.
set -e
cd "$(dirname "$0")"
cp ../src/toaster/data/lexicon.json public/lexicon.json
echo "lexicon.json copied ($(wc -c < public/lexicon.json) bytes)"
