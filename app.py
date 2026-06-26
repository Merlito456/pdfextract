import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="PO Data Extractor", layout="wide")

st.title("📄 PO Data Extractor")
st.write("Upload your Purchase Order PDF to convert it into a structured Excel file.")

uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file is not None:
    all_items = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        # Loop through pages
        for page in pdf.pages:
            # Extract tables - 'lattice' works best for structured POs
            table = page.extract_table(table_settings={"strategy": "lines"})
            
            if table:
                for row in table:
                    # Filter for rows that contain data (Line # as the identifier)
                    # Adjust 'row[0]' index if your specific PDF has different column spacing
                    if row[0] and str(row[0]).strip().isdigit():
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
        
        # Data Cleaning: remove 'PHP' and commas for clean numeric export
        for col in ["Unit Price", "Subtotal"]:
            df[col] = df[col].replace(r'[^0-9.]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')

        st.success(f"Successfully extracted {len(df)} items!")
        st.dataframe(df)

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='PO Data')
        
        st.download_button(
            label="⬇️ Download Excel File",
            data=output.getvalue(),
            file_name="extracted_po_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Could not find tabular data in this PDF. Please verify the file format.")

# Conceptual diagram showing how the data pipeline works: