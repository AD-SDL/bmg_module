#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <search_string> <replace_string>"
  exit 1
fi

search_string=$1
replace_string=$2

# Replace string in filenames
git ls-files | grep "$search_string" | while read -r file; do
  new_file=$(echo "$file" | sed "s/$search_string/$replace_string/g")
  mkdir -p $(dirname $new_file)
  git mv "$file" "$new_file"
done

# Replace string in file contents
git ls-files | xargs -I {} sed -i "s/$search_string/$replace_string/g" {}

echo "Replacement completed"
