import streamlit as st
import pdfplumber
import pandas as pd
import io

st.title("PO Data Extractor")
st.write("Upload a PDF Purchase Order to extract line items.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    # Read the file
    with pdfplumber.open(uploaded_file) as pdf:
        all_items = []
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Adjust column indexing based on your specific PDF structure
                    if row[0] and str(row[0]).isdigit():
                        all_items.append({
                            "Line #": row[0],
                            "PU": row[2],
                            "Description": row[3],
                            "QTY": row[5],
                            "Unit Price": row[7],
                            "Subtotal": row[8]
                        })

    df = pd.DataFrame(all_items)
    st.write("Extracted Data:", df)

    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    
    st.download_button(
        label="Download Excel File",
        data=output.getvalue(),
        file_name="extracted_po.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )