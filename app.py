import streamlit as st
import pdfplumber
import pandas as pd
import io
import re

st.set_page_config(page_title="PO Data Extractor", layout="wide")
st.title("📄 Robust PO Data Extractor")
uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file is not None:
    all_items = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
            
    # Use Regex to find the pattern: Line Number + Description + Qty + Price + Subtotal
    # This pattern looks for lines starting with 1 to 23
    for i in range(1, 24):
        # Pattern looks for the Line #, followed by various data, then PHP amounts
        pattern = rf"{i}\s+(.*?)\s+(\d+[\d,]*\s+\(\w+\))\s+([\d,]+\.\d+\s+PHP)\s+([\d,]+\.\d+\s+PHP)"
        match = re.search(pattern, full_text)
        
        if match:
            all_items.append({
                "Line #": i,
                "Description": match.group(1).strip(),
                "Qty": match.group(2).strip(),
                "Unit Price": match.group(3).strip(),
                "Subtotal": match.group(4).strip()
            })

    if all_items:
        df = pd.DataFrame(all_items)
        st.dataframe(df)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button("⬇️ Download Excel", output.getvalue(), "extracted_po.xlsx")
    else:
        st.error("Could not parse the PDF structure. Please ensure it is the standard 'The Lindgreen' PO format.")