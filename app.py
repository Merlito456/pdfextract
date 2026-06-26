import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="Advanced PO Extractor", layout="wide")
st.title("🚀 Advanced PO Data Extractor")
uploaded_file = st.file_uploader("Upload your SAP PO PDF", type="pdf")

def parse_advanced(pdf_file):
    items = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # We extract words with their coordinates to understand the layout
            words = page.extract_words(use_text_flow=True)
            text = page.extract_text()
            
            # Logic: Split the page by lines and look for rows starting with a Line Number
            lines = text.split('\n')
            for line in lines:
                # Regex looks for lines starting with a number followed by space
                # This catches the typical "1  Part#  Desc  Qty  Price  Subtotal" format
                if line.strip() and line.strip()[0].isdigit():
                    parts = line.split()
                    if len(parts) >= 6:
                        items.append({
                            "Line #": parts[0],
                            "Description": " ".join(parts[1:3]), # Basic grouping
                            "Qty": parts[3],
                            "Unit Price": parts[-2],
                            "Subtotal": parts[-1]
                        })
    return pd.DataFrame(items)

if uploaded_file is not None:
    try:
        df = parse_advanced(uploaded_file)
        if not df.empty:
            st.dataframe(df)
            
            # Excel export
            output = io.BytesIO()
            df.to_excel(output, index=False)
            st.download_button("Download Results", output.getvalue(), "extracted.xlsx")
        else:
            st.warning("No line items identified. The text layout might be too fragmented.")
    except Exception as e:
        st.error(f"Advanced Parsing Error: {e}")