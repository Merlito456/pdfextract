import streamlit as st
import pdfplumber
import pandas as pd
import io

st.set_page_config(page_title="PO Data Extractor", layout="wide")
st.title("🎯 Precision PO Data Extractor")

uploaded_file = st.file_uploader("Upload your Purchase Order PDF", type="pdf")

def clean_value(val):
    """Cleans currency strings and removes unwanted characters."""
    if val is None: return ""
    return str(val).replace("PHP", "").replace(",", "").strip()

if uploaded_file is not None:
    all_items = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            # We look for the table using line detection
            # If the PDF is a complex Ariba layout, we use the 'lines' strategy
            tables = page.extract_tables(table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"})
            
            for table in tables:
                for row in table:
                    # Filter rows: A valid line item starts with a digit 1-23
                    if row[0] and str(row[0]).strip().isdigit():
                        all_items.append({
                            "Line #": row[0],
                            "Description": row[2],
                            "Qty": row[4],
                            "Unit Price": row[6],
                            "Subtotal": row[7]
                        })

    if all_items:
        df = pd.DataFrame(all_items)
        st.dataframe(df)
        
        # Create Excel
        output = io.BytesIO()
        df.to_excel(output, index=False)
        st.download_button("Download Corrected Excel", output.getvalue(), "PO_Corrected_Data.xlsx")
    else:
        st.error("No structured table detected. The PDF might be an image-based scan.")