"""
mkdir -p /Users/maddisenmohnsen/Desktop/standards_scraper
cd /Users/maddisenmohnsen/Desktop/standards_scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python standards_scraper.py
"""

import requests
from io import BytesIO
from PyPDF2 import PdfReader
import re

def clean_text(text):
    """Clean and normalize text from PDF"""
    # Replace multiple spaces and newlines with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove any non-breaking spaces
    text = text.replace('\xa0', ' ')
    return text.strip()

def extract_section_data(section_text):
    """Extract and match weight classes with their totals from a section."""
    # Updated pattern to better handle +kg weight classes
    weight_pattern = r"(?:Weight class|Class)[:\s]*((?:\d+(?:\.\d+)?kg|\+\d+kg)(?:\s+(?:\d+(?:\.\d+)?kg|\+\d+kg))*)"
    total_pattern = r"Total[:\s]*((?:\d+(?:kg)?(?:\s+\d+(?:kg)?)*))(?:\s|$)"
    
    weight_line = re.search(weight_pattern, section_text, re.IGNORECASE)
    total_line = re.search(total_pattern, section_text, re.IGNORECASE)
    
    if not (weight_line and total_line):
        return [], []
    
    # Split into individual values and clean them
    weight_classes = [w.strip() for w in weight_line.group(1).split() if w.strip()]
    totals = [t.replace('kg', '').strip() for t in total_line.group(1).split() if t.strip()]
    
    return weight_classes, totals

def scrape_weightlifting_standards(pdf_url, standard_label='a'):
    """
    Scrapes weightlifting standards from a PDF URL.
    Args:
        pdf_url: The URL of the PDF document
        standard_label: 'a' or 'b' to indicate which standard this represents
    """
    response = requests.get(pdf_url)
    response.raise_for_status()  # Raise an exception for bad status codes

    pdf_file = BytesIO(response.content)
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()

    # Clean and normalize the extracted text
    text = clean_text(text)
    
    data = []
    age_groups = ["Youth Women", "Youth Men", "Junior Women", "Junior Men", "Senior Women", "Senior Men"]

    # Debug full text
    print("Full text:", text[:200])  # Print first 200 chars to check format

    for i, group in enumerate(age_groups):
        # Find the section for current group
        section_start = text.find(group + ":")
        if section_start == -1:
            continue
            
        # Find the end of the section
        next_section_start = len(text)
        for next_group in age_groups[i+1:]:
            next_pos = text.find(next_group + ":")
            if next_pos != -1:
                next_section_start = next_pos
                break
                
        section_text = text[section_start:next_section_start]
        print(f"\nProcessing section for {group}:")
        print(section_text[:200])  # Debug output
        
        weight_classes, totals = extract_section_data(section_text)
        
        if len(weight_classes) == len(totals):
            # Match weight classes with their corresponding totals
            for weight_class, total in zip(weight_classes, totals):
                data.append({
                    "Age Group": group,
                    "Weight Class": weight_class,
                    "Weight Standard": total
                })
            
            print(f"Found {len(weight_classes)} weight classes and {len(totals)} totals")
        else:
            print(f"Mismatch: {len(weight_classes)} weight classes and {len(totals)} totals")
            
    return data

def weight_class_sort_key(weight_class):
    """Custom sort key function for weight classes"""
    gender, weight = weight_class.split(' ', 1)
    # Move '+' classes to the end by giving them a high number
    if weight.startswith('+'):
        return (gender, float('inf'))
    # Convert regular weight classes to float for proper numeric sorting
    return (gender, float(weight.replace('kg', '')))

def format_as_typescript(a_data, b_data):
    """Convert both A and B standard data to TypeScript format."""
    typescript_output = "export const standards = {\n"
    
    # Group by age group first
    age_group_data = {
        "Youth": {},
        "Junior": {},
        "Senior": {}
    }
    
    # Process A standards
    for entry in a_data:
        age_group = entry["Age Group"].split()[0]
        gender = "Female" if "Women" in entry["Age Group"] else "Male"
        weight_class = f"{gender} {entry['Weight Class']}"
        standard_a = int(float(entry["Weight Standard"]))
        
        if weight_class not in age_group_data[age_group]:
            age_group_data[age_group][weight_class] = {"a": standard_a, "b": 0}
    
    # Process B standards
    for entry in b_data:
        age_group = entry["Age Group"].split()[0]
        gender = "Female" if "Women" in entry["Age Group"] else "Male"
        weight_class = f"{gender} {entry['Weight Class']}"
        standard_b = int(float(entry["Weight Standard"]))
        
        if weight_class in age_group_data[age_group]:
            age_group_data[age_group][weight_class]["b"] = standard_b
        else:
            age_group_data[age_group][weight_class] = {"a": 0, "b": standard_b}

    # Generate TypeScript formatted output
    for age_group, weights in age_group_data.items():
        typescript_output += f"    {age_group}: {{\n"
        
        # Use custom sort function
        for weight_class, standards in sorted(weights.items(), key=lambda x: weight_class_sort_key(x[0])):
            typescript_output += f'        "{weight_class}": {{ qualifyingStandards: {{ a: {standards["a"]}, b: {standards["b"]} }} }},\n'
        
        typescript_output += "    },\n"
    
    typescript_output += "};\n"
    return typescript_output

if __name__ == "__main__":
    a_standards_url = "https://assets.contentstack.io/v3/assets/blteb7d012fc7ebef7f/bltb4577197252782a8/65e75351ed46610094787c44/2024_A_Standards_Updated.pdf"
    b_standards_url = "https://assets.contentstack.io/v3/assets/blteb7d012fc7ebef7f/bltff0fa4e0e845cbfa/65e753516f950cfb558c6787/2024_B_Standards_Updated.pdf"
    
    # Extract both A and B standards
    a_data = scrape_weightlifting_standards(a_standards_url, 'a')
    b_data = scrape_weightlifting_standards(b_standards_url, 'b')
    
    # Format and output as TypeScript
    typescript_formatted = format_as_typescript(a_data, b_data)
    
    # Print to console
    print(typescript_formatted)
    
    # Write to a TypeScript file
    with open('qualifyingTotals.ts', 'w') as f:
        f.write(typescript_formatted)