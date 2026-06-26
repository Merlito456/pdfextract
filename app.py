import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

def extract_po_data_robust(uploaded_file):
    extracted_data = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            # Extract words and group them by their vertical position (Y-coordinate)
            words = page.extract_words(x_tolerance=2, y_tolerance=2)
            
            # Dictionary to group words into lines based on Y position
            lines = {}
            for word in words:
                y = round(word['top'])
                if y not in lines:
                    lines[y] = []
                lines[y].append(word['text'])
            
            # Sort by Y position to read top-to-bottom
            sorted_y = sorted(lines.keys())
            
            # Iterate through reconstructed lines to find the pattern
            for i in range(len(sorted_y)):
                line_text = " ".join(lines[sorted_y[i]])
                
                # Regex matches lines starting with the Line #
                # Pattern: Line# | Not Available | [Description] | [Qty] | [Price] | [Subtotal]
                match = re.match(r'^(\d+)\s+Not Available\s+(.*?)\s+(\d+[\d,.]*\s+\(?\w+\)?)\s+([\d,.]+\s+PHP)\s+([\d,.]+\s+PHP)', line_text)
                
                if match:
                    line_num, desc_part, qty, price, subtotal = match.groups()
                    
                    # Split Part# from Description using common delimiters (comma or hyphen)
                    parts = re.split(r'[,|-]', desc_part, maxsplit=1)
                    part_no = parts[0].strip()
                    description = parts[1].strip() if len(parts) > 1 else desc_part
                    
                    extracted_data.append({
                        "Line #": line_num,
                        "Part #": part_no,
                        "Description": description,
                        "Qty": qty,
                        "Unit Price": price,
                        "Subtotal": subtotal
                    })
                    
    return pd.DataFrame(extracted_data)

# Streamlit Interface
st.title("🚀 Precision PO Data Extractor")
uploaded_file = st.file_uploader("Upload your Purchase Order PDF", type="pdf")

if uploaded_file is not None:
    df = extract_po_data_robust(uploaded_file)
    if not df.empty:
        st.dataframe(df)
        
        # Excel Export
        output = io.BytesIO()
        df.to_excel(output, index=False)
        st.download_button("⬇️ Download Excel", output.getvalue(), "extracted_po.xlsx")
    else:
        st.error("Could not reconstruct the table. Please check if the PDF contains selectable text.")