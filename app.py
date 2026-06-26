import streamlit as st
import pdfplumber
import pandas as pd
import io

st.title("PO Data Extractor")
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    all_items = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            # table_settings helps handle complex PDF tables
            table = page.extract_table(table_settings={
                "vertical_strategy": "lines", 
                "horizontal_strategy": "text",
                "join_tolerance": 5
            })
            
            if table:
                for row in table:
                    # Check if the row looks like a line item (starts with a number)
                    # We look for the structure: [Line #, Material, Desc, Qty, Price, Subtotal]
                    # Adjust index based on visual inspection of your specific PDF
                    if row[0] and str(row[0]).strip().isdigit():
                        all_items.append({
                            "Line #": row[0],
                            "Part #": row[1] if len(row) > 1 else "",
                            "Description": row[2] if len(row) > 2 else "",
                            "Qty": row[4] if len(row) > 4 else "",
                            "Unit Price": row[6] if len(row) > 6 else "",
                            "Subtotal": row[7] if len(row) > 7 else ""
                        })

    df = pd.DataFrame(all_items)
    
    if not df.empty:
        st.write("Extracted Data Preview:")
        st.dataframe(df)
        
        # Download button
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button("Download Excel", output.getvalue(), "extracted_po.xlsx")
    else:
        st.warning("No data found. The PDF table structure might be different than expected.")