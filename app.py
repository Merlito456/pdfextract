import streamlit as st
import pdfplumber
import pandas as pd

# Define the function to take the file object, not a string path
def extract_po_data(file_obj):
    extracted_items = []
    
    # Use the file object directly
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    # Robust check: Ensure row[0] exists and is a digit
                    if row[0] and str(row[0]).strip().isdigit():
                        item = {
                            "Line #": row[0],
                            "Part #/Description": row[2] if len(row) > 2 else "",
                            "Qty (Unit)": row[5] if len(row) > 5 else "",
                            "Unit Price": row[7] if len(row) > 7 else "",
                            "Subtotal": row[8] if len(row) > 8 else ""
                        }
                        extracted_items.append(item)
    return pd.DataFrame(extracted_items)

# Streamlit Interface
uploaded_file = st.file_uploader("Upload your PO PDF", type="pdf")

if uploaded_file is not None:
    # PASS THE UPLOADED FILE OBJECT HERE
    df = extract_po_data(uploaded_file)
    st.dataframe(df)