import pdfplumber
import pandas as pd

def extract_po_data(pdf_path):
    extracted_items = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # We use extract_table with default settings which is 
            # generally robust for this document type
            table = page.extract_table()
            
            if table:
                for row in table:
                    # Filter for rows that start with a number (Line #)
                    # We convert to string and check if it represents an integer
                    if row[0] and str(row[0]).strip().isdigit():
                        item = {
                            "Line #": row[0],
                            "Part #/Description": row[2], # The description often falls here
                            "Qty (Unit)": row[5],
                            "Unit Price": row[7],
                            "Subtotal": row[8]
                        }
                        extracted_items.append(item)
    
    return pd.DataFrame(extracted_items)

# Execute and view
df = extract_po_data("4540526620 THE LINDGREEN .pdf")
print(df)
# To save to Excel:
# df.to_excel("extracted_po.xlsx", index=False)