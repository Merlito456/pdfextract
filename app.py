import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

def parse_po_by_format(pdf_file):
    items = []
    # Regex for a typical line item: Starts with Line#, followed by content, 
    # ending with currency values for Price and Subtotal
    # Pattern: Line# | Not Available | Part#-Desc | Qty | Price | Subtotal
    item_pattern = re.compile(r'(\d+)\s+Not Available\s+(.*?)\s+(\d+[\d,.]*\s+\([A-Z]+\))\s+([\d,.]+\s+PHP)\s+([\d,.]+\s+PHP)')

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            # Find all matches based on your specified format
            matches = item_pattern.findall(text)
            
            for match in matches:
                line_no, raw_part_desc, qty, unit_price, subtotal = match
                
                # Logic to split Part# and Description
                # Look for the first comma or hyphen to separate them
                split_parts = re.split(r'[,|-]', raw_part_desc, maxsplit=1)
                part_no = split_parts[0].strip()
                description = split_parts[1].strip() if len(split_parts) > 1 else raw_part_desc
                
                items.append({
                    "Line #": line_no,
                    "Part #": part_no,
                    "Description": description,
                    "Qty (Unit)": qty,
                    "Unit Price": unit_price,
                    "Subtotal": subtotal
                })
    return pd.DataFrame(items)

# Streamlit UI
uploaded_file = st.file_uploader("Upload your Purchase Order PDF", type="pdf")

if uploaded_file is not None:
    df = parse_po_by_format(uploaded_file)
    if not df.empty:
        st.write("Extracted Items:")
        st.dataframe(df)
        
        # Excel Download
        output = io.BytesIO()
        df.to_excel(output, index=False)
        st.download_button("Download Excel", output.getvalue(), "extracted_po.xlsx")
    else:
        st.warning("No items found using the specified format. Checking PDF structure...")