import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="PO Data Extractor", layout="wide")

st.title("📄 PO Data Extractor")
st.write("Upload your Purchase Order PDF to generate the Excel file.")

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file is not None:
    all_items = []
    
    # Use the file object directly from the uploader
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table:
                    # Clean row data: convert to string to avoid NoneType errors
                    row = [str(cell) if cell is not None else "" for cell in row]
                    
                    # Target rows that start with a digit (Line #)
                    # Adjust indices if your PDF column layout differs
                    if row[0].strip().isdigit():
                        all_items.append({
                            "Line #": row[0],
                            "Part #": row[2] if len(row) > 2 else "",
                            "Description": row[2] if len(row) > 2 else "",
                            "Qty (Unit)": row[5] if len(row) > 5 else "",
                            "Unit Price": row[7] if len(row) > 7 else "",
                            "Subtotal": row[8] if len(row) > 8 else ""
                        })

    if all_items:
        df = pd.DataFrame(all_items)
        st.success(f"Extracted {len(df)} items!")
        st.dataframe(df)

        # Generate Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button(
            label="⬇️ Download Excel File",
            data=output.getvalue(),
            file_name="extracted_po_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No table detected. Please ensure this is a text-based PDF.")