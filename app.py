import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

def extract_po_data_robust(uploaded_file):
    extracted_data = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            # Extract text with layout analysis
            text_blocks = page.extract_words(x_tolerance=2, y_tolerance=2)
            
            # Grouping by Y-coordinate to reconstruct lines
            rows = {}
            for block in text_blocks:
                y = round(block['top'])
                if y not in rows: rows[y] = []
                rows[y].append(block['text'])
            
            # Processing rows
            for y in sorted(rows.keys()):
                line_text = " ".join(rows[y])
                
                # Look for lines starting with a number (Line #)
                # Matches format: 1  Not Available  [Part-Desc]  [Qty]  [Price]  [Subtotal]
                match = re.match(r'^(\d+)\s+Not Available\s+(.*?)\s+(\d+[\d\.]*\s+\(?\w+\)?)\s+([\d\.,]+\s+PHP)\s+([\d\.,]+\s+PHP)', line_text)
                
                if match:
                    line_num, desc_part, qty, price, subtotal = match.groups()
                    
                    # Splitting the Part# from Description
                    # Looking for the pattern: 610035,ML, Aerial OR 900020-Cable...
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

# Streamlit interface
uploaded_file = st.file_uploader("Upload your PO PDF", type="pdf")
if uploaded_file:
    df = extract_po_data_robust(uploaded_file)
    if not df.empty:
        st.dataframe(df)
        # Download logic...
    else:
        st.error("Still no items found. The layout is highly fragmented.")