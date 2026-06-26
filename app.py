import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="PO Data Extractor", layout="wide")

st.title("📄 PO Data Extractor")
uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file is not None:
    all_items = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            # Simplified table extraction to avoid the TypeError
            # We use the default settings first
            table = page.extract_table()
            
            if table:
                for row in table:
                    # Clean the row to ensure we aren't processing empty lists
                    row = [str(cell) if cell is not None else "" for cell in row]
                    
                    # Logic: Look for rows starting with a digit (Line #)
                    if row[0].strip().isdigit():
                        all_items.append({
                            "Line #": row[0],
                            "PU": row[1] if len(row) > 1 else "",
                            "Description": row[2] if len(row) > 2 else "",
                            "QTY": row[3] if len(row) > 3 else "",
                            "Unit Price": row[4] if len(row) > 4 else "",
                            "Subtotal": row[5] if len(row) > 5 else ""
                        })

    if all_items:
        df = pd.DataFrame(all_items)
        st.dataframe(df)

        # Generate Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button("⬇️ Download Excel", output.getvalue(), "extracted.xlsx")
    else:
        st.error("No table detected. Please check if the PDF is text-based or scanned.")