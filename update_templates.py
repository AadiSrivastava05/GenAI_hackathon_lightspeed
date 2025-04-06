"""
This script helps convert HTML files to extend the base template structure.
It won't do the entire conversion automatically but provides a report
of which files need to be updated.
"""

import os
import re

def scan_templates_directory():
    """Scan the templates directory for HTML files and check if they extend base.html"""
    templates_dir = "templates"
    template_files = []
    updated_files = []
    
    if not os.path.exists(templates_dir):
        print(f"Error: {templates_dir} directory not found")
        return
    
    for filename in os.listdir(templates_dir):
        if filename.endswith(".html") and filename != "base.html":
            file_path = os.path.join(templates_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check if file already extends base.html
                if re.search(r"{% extends ['\"]base\.html['\"] %}", content):
                    updated_files.append(filename)
                else:
                    template_files.append(filename)
    
    return {
        "needs_update": template_files,
        "already_updated": updated_files
    }

def get_template_structure(filename):
    """Extract the structure of an HTML template to guide conversion"""
    file_path = os.path.join("templates", filename)
    structure = {
        "title": None,
        "styles": [],
        "scripts": []
    }
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # Extract title
        title_match = re.search(r"<title>(.*?)</title>", content)
        if title_match:
            structure["title"] = title_match.group(1)
        
        # Extract styles
        style_block = re.search(r"<style>(.*?)</style>", content, re.DOTALL)
        if style_block:
            structure["styles"] = style_block.group(1).strip()
        
        # Check for inline styles
        inline_styles = re.findall(r'style="([^"]*)"', content)
        if inline_styles:
            structure["inline_styles"] = inline_styles
        
        # Extract scripts
        script_block = re.search(r"<script>(.*?)</script>", content, re.DOTALL)
        if script_block:
            structure["scripts"] = script_block.group(1).strip()
        
        # Extract header title (h1)
        header_match = re.search(r'<h1[^>]*>(.*?)</h1>', content)
        if header_match:
            structure["header_title"] = header_match.group(1).strip()
        
        # Extract header subtitle
        subtitle_match = re.search(r'<p class="subtitle">(.*?)</p>', content)
        if subtitle_match:
            structure["header_subtitle"] = subtitle_match.group(1).strip()
        
        # Check for flashed messages
        if "get_flashed_messages" in content:
            structure["has_flash_messages"] = True
    
    return structure

def print_conversion_guide(filename, structure):
    """Print a guide for how to convert a specific template"""
    print(f"\n=== Conversion Guide for {filename} ===")
    
    print("\nTemplate Block Structure:")
    print("-------------------------")
    print("{% extends 'base.html' %}")
    print("")
    
    if structure.get("title"):
        print(f"{{% block title %}}{structure['title']}{{% endblock %}}")
    
    if structure.get("header_title"):
        print(f"\n{{% block header_title %}}{structure['header_title']}{{% endblock %}}")
    
    if structure.get("header_subtitle"):
        print(f"{{% block header_subtitle %}}{structure['header_subtitle']}{{% endblock %}}")
    
    if structure.get("styles"):
        print("\n{% block additional_styles %}")
        print("/* Add your custom styles here */")
        print("{% endblock %}")
    
    print("\n{% block content %}")
    print("<!-- Main content goes here -->")
    print("{% endblock %}")
    
    if structure.get("scripts"):
        print("\n{% block scripts %}")
        print("<!-- JavaScript goes here -->")
        print("{% endblock %}")
    
    print("\nNotes:")
    print("------")
    if structure.get("has_flash_messages"):
        print("- Flash messages are already included in the base template")
    
    if structure.get("inline_styles"):
        print("- Contains inline styles that should be moved to block additional_styles")
    
    print("- Remember to remove DOCTYPE, html, head, body tags and other elements included in base.html")
    print("- Make sure to adapt any custom styling to use CSS variables from the base template")

def main():
    print("Template Update Analysis Tool")
    print("============================")
    
    results = scan_templates_directory()
    
    if not results:
        return
    
    print(f"\nFiles already using base template ({len(results['already_updated'])}):")
    for filename in sorted(results['already_updated']):
        print(f"- {filename}")
    
    print(f"\nFiles needing conversion ({len(results['needs_update'])}):")
    for filename in sorted(results['needs_update']):
        print(f"- {filename}")
    
    if results['needs_update']:
        print("\nWould you like to see a conversion guide for a specific file? (y/n)")
        choice = input("> ").lower()
        
        if choice == 'y':
            print("\nEnter the filename (e.g., login.html):")
            filename = input("> ")
            
            if filename in results['needs_update']:
                structure = get_template_structure(filename)
                print_conversion_guide(filename, structure)
            else:
                print(f"Error: {filename} not found in the list of files needing conversion")

if __name__ == "__main__":
    main() 