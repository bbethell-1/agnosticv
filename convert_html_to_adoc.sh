#!/bin/bash

# Script to convert HTML description files to AsciiDoc format

echo "Converting HTML files to AsciiDoc..."

# Function to convert HTML to AsciiDoc
convert_html_to_adoc() {
    local html_file="$1"
    local adoc_file="${html_file%.html}.adoc"
    
    echo "Converting $html_file to $adoc_file"
    
    # Read the HTML content
    content=$(cat "$html_file")
    
    # Convert HTML to AsciiDoc
    # Remove HTML tags and convert to AsciiDoc format
    adoc_content=$(echo "$content" | sed -e 's/<h1>/= /g' \
                                        -e 's/<\/h1>//g' \
                                        -e 's/<h2>/== /g' \
                                        -e 's/<\/h2>//g' \
                                        -e 's/<h3>/=== /g' \
                                        -e 's/<\/h3>//g' \
                                        -e 's/<h4>/==== /g' \
                                        -e 's/<\/h4>//g' \
                                        -e 's/<p>//g' \
                                        -e 's/<\/p>//g' \
                                        -e 's/<ul>//g' \
                                        -e 's/<\/ul>//g' \
                                        -e 's/<li>/* /g' \
                                        -e 's/<\/li>//g' \
                                        -e 's/<b>/\\*/g' \
                                        -e 's/<\/b>/\\*/g' \
                                        -e 's/<br>//g' \
                                        -e 's/<div[^>]*>//g' \
                                        -e 's/<\/div>//g' \
                                        -e 's/<a href="\([^"]*\)">\([^<]*\)<\/a>/link:\1[\2, window="_blank"]/g' \
                                        -e 's/&lt;/</g' \
                                        -e 's/&gt;/>/g' \
                                        -e 's/&amp;/&/g' \
                                        -e 's/&#174;/®/g' \
                                        -e 's/&#174;/®/g' \
                                        -e 's/  */ /g' \
                                        -e '/^[[:space:]]*$/d')
    
    # Write the converted content to the .adoc file
    echo "$adoc_content" > "$adoc_file"
    
    # Remove the original HTML file
    rm "$html_file"
    
    echo "Converted $html_file to $adoc_file"
}

# Find all HTML files and convert them
find . -name "description.html" | while read html_file; do
    convert_html_to_adoc "$html_file"
done

echo "Conversion complete!" 