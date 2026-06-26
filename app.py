# app.py
import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
import base64

st.set_page_config(
    page_title="PDF Data Extractor",
    page_icon="📄",
    layout="wide"
)

st.title("📄 PDF Data Extractor")
st.markdown("Extract line item data from PDF files")

def extract_data_from_pdf(pdf_file):
    """
    Extract data from PDF file with multiple parsing strategies
    """
    extracted_data = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"
            
            # Try table extraction first
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row and any(cell for cell in row if cell):
                                extracted_data.append(row)
            
            # If tables found, parse them
            if extracted_data:
                parsed = parse_table_data(extracted_data)
                if parsed:
                    return parsed
            
            # Fallback to text parsing
            return parse_text_data(all_text)
            
    except Exception as e:
        st.error(f"Error extracting data: {str(e)}")
        return []

def parse_table_data(table_data):
    """
    Parse table data into structured format
    """
    parsed_rows = []
    
    # Try to find header row
    header_row = None
    header_index = -1
    
    for idx, row in enumerate(table_data):
        if row:
            row_str = " ".join([str(cell).lower() if cell else "" for cell in row])
            keywords = ['line', 'description', 'qty', 'unit', 'price', 'subtotal']
            if any(keyword in row_str for keyword in keywords):
                header_row = row
                header_index = idx
                break
    
    # If we found headers, use them
    if header_row is not None:
        # Map columns based on header content
        col_map = {}
        for idx, header in enumerate(header_row):
            if header:
                header_lower = str(header).lower()
                if 'line' in header_lower or '#' in header_lower:
                    col_map['Line #'] = idx
                elif 'description' in header_lower or 'part' in header_lower:
                    col_map['Description'] = idx
                elif 'qty' in header_lower or 'quantity' in header_lower:
                    col_map['QTY'] = idx
                elif 'unit price' in header_lower:
                    col_map['Unit Price'] = idx
                elif 'subtotal' in header_lower:
                    col_map['Subtotal'] = idx
        
        # Extract data rows
        for row in table_data[header_index + 1:]:
            if row and any(cell for cell in row if cell):
                parsed_row = {}
                for field, col_idx in col_map.items():
                    if col_idx < len(row):
                        parsed_row[field] = str(row[col_idx]).strip() if row[col_idx] else ""
                if parsed_row:
                    parsed_rows.append(parsed_row)
    
    # If no headers found, try to parse rows directly
    if not parsed_rows:
        for row in table_data:
            if row and len([cell for cell in row if cell]) >= 3:
                parsed_row = parse_row_data(row)
                if parsed_row:
                    parsed_rows.append(parsed_row)
    
    return parsed_rows

def parse_text_data(text):
    """
    Parse text data using regex patterns
    """
    parsed_rows = []
    
    # Clean up text
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Pattern for the specific format in your sample
    # Looking for: Line number, then Not Available, then QTY, then date, then prices
    pattern1 = r'(\d+)\s+Not\s+Available\s+(\d+\([A-Z]+\))\s+[\d]+\s+[A-Za-z]+\s+[\d]+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+'
    
    # Pattern for format with product code
    pattern2 = r'(\d+)\s+([A-Z0-9\-_]+)\s+([A-Za-z0-9\s\._\-]+?)\s+(\d+\([A-Z]+\))\s+[\d]+\s+[A-Za-z]+\s+[\d]+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+'
    
    # Pattern for general format
    pattern3 = r'(\d+)\s+([A-Z0-9\-_]+)\s+([^\n]+?)\s+(\d+\([A-Z]+\))\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+'
    
    # Process each line
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Try each pattern
        for pattern in [pattern1, pattern2, pattern3]:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 6:
                    row_data = {
                        'Line #': groups[0].strip() if groups[0] else "",
                        'PU': groups[1].strip() if len(groups) > 1 and groups[1] else "",
                        'Description': groups[2].strip() if len(groups) > 2 and groups[2] else "",
                        'QTY': groups[3].strip() if len(groups) > 3 and groups[3] else "",
                        'Unit Price': groups[4].strip() if len(groups) > 4 and groups[4] else "",
                        'Subtotal': groups[5].strip() if len(groups) > 5 and groups[5] else ""
                    }
                    
                    # If description is too short, check next line
                    if len(row_data['Description']) < 10 and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if re.search(r'[A-Za-z]', next_line) and not re.search(r'[\d,]', next_line):
                            row_data['Description'] = next_line
                            i += 1
                    
                    parsed_rows.append(row_data)
                    break
        
        i += 1
    
    # If no data found, try a simpler approach
    if not parsed_rows:
        parsed_rows = parse_line_by_line(lines)
    
    return parsed_rows

def parse_line_by_line(lines):
    """
    Parse data line by line using simpler heuristics
    """
    parsed_rows = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for line that might contain product data
        if re.search(r'\d+', line) and (re.search(r'[A-Z0-9\-_]{4,}', line) or re.search(r'PHP|₱', line)):
            parts = line.split()
            
            # Try to extract fields
            line_num = ""
            pu = ""
            qty = ""
            unit_price = ""
            subtotal = ""
            description_parts = []
            
            # Look for line number (first number)
            for part in parts:
                if part.isdigit() and not line_num:
                    line_num = part
                    break
            
            # Look for product code (alphanumeric with special chars)
            for part in parts:
                if re.search(r'[A-Z0-9\-_]{4,}', part) and not pu:
                    pu = part
                    break
            
            # Look for QTY (number with parentheses)
            for part in parts:
                if re.search(r'\d+\([A-Z]+\)', part) and not qty:
                    qty = part
                    break
            
            # Look for prices
            price_matches = re.findall(r'([\d,]+\.\d+)', line)
            if len(price_matches) >= 2:
                unit_price = price_matches[-2] if len(price_matches) >= 2 else ""
                subtotal = price_matches[-1] if price_matches else ""
            
            # Everything else might be description
            for part in parts:
                if (part not in [line_num, pu, qty, unit_price, subtotal] and 
                    not re.search(r'PHP|₱|Not|Available', part)):
                    description_parts.append(part)
            
            description = " ".join(description_parts)
            
            # If description is empty, check next line
            if not description and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if re.search(r'[A-Za-z]', next_line) and not re.search(r'[\d,]', next_line):
                    description = next_line
                    i += 1
            
            if line_num or pu:
                parsed_rows.append({
                    'Line #': line_num,
                    'PU': pu,
                    'Description': description,
                    'QTY': qty if qty else "1(EA)",
                    'Unit Price': unit_price,
                    'Subtotal': subtotal
                })
        
        i += 1
    
    return parsed_rows

def parse_row_data(row):
    """
    Parse a single row of data
    """
    # Clean the row
    clean_row = [str(cell).strip() if cell else "" for cell in row]
    clean_row = [cell for cell in clean_row if cell]
    
    if len(clean_row) < 3:
        return {}
    
    parsed = {
        'Line #': "",
        'PU': "",
        'Description': "",
        'QTY': "",
        'Unit Price': "",
        'Subtotal': ""
    }
    
    # Find line number
    for cell in clean_row:
        if cell.isdigit() and len(cell) <= 4:
            parsed['Line #'] = cell
            break
    
    # Find PU code
    for cell in clean_row:
        if re.search(r'[A-Z0-9\-_]{4,}', cell) and not parsed['PU']:
            parsed['PU'] = cell
            break
    
    # Find QTY
    for cell in clean_row:
        if re.search(r'\d+\([A-Z]+\)', cell) and not parsed['QTY']:
            parsed['QTY'] = cell
            break
    
    # Find prices
    prices = []
    for cell in clean_row:
        if re.search(r'[\d,]+\.\d+', cell):
            prices.append(cell)
    
    if len(prices) >= 2:
        parsed['Unit Price'] = prices[-2]
        parsed['Subtotal'] = prices[-1]
    elif len(prices) == 1:
        parsed['Subtotal'] = prices[0]
    
    # Find description (remaining cells)
    excluded = [parsed['Line #'], parsed['PU'], parsed['QTY'], parsed['Unit Price'], parsed['Subtotal']]
    remaining = [cell for cell in clean_row if cell not in excluded and not re.search(r'PHP|₱|Not|Available', cell)]
    
    if remaining:
        parsed['Description'] = " ".join(remaining)
    
    return parsed

def create_download_link(df, filename="extracted_data.xlsx"):
    """Create download link for Excel file"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Extracted Data')
    excel_data = output.getvalue()
    
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 Download Excel File</a>'
    return href

# Main app UI
def main():
    uploaded_file = st.file_uploader("Upload PDF file", type=['pdf'])
    
    if uploaded_file is not None:
        st.success("✅ File uploaded successfully!")
        
        with st.spinner("Extracting data from PDF..."):
            extracted_data = extract_data_from_pdf(uploaded_file)
        
        if extracted_data:
            # Convert to DataFrame
            df = pd.DataFrame(extracted_data)
            
            # Clean up
            df = df.replace('', pd.NA).dropna(how='all')
            df = df.fillna('')
            
            # Reorder columns if they exist
            desired_columns = ['Line #', 'PU', 'Description', 'QTY', 'Unit Price', 'Subtotal']
            existing_columns = [col for col in desired_columns if col in df.columns]
            if existing_columns:
                df = df[existing_columns]
            
            # Display results
            st.subheader("📊 Extracted Data")
            st.dataframe(df, use_container_width=True)
            
            # Display statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Items", len(df))
            with col2:
                if 'Subtotal' in df.columns and not df['Subtotal'].empty:
                    # Clean subtotal column for calculation
                    subtotal_clean = df['Subtotal'].astype(str).str.replace(',', '').str.replace(' PHP', '').str.replace('₱', '').str.replace(' ', '')
                    subtotal_clean = subtotal_clean.replace('', '0')
                    try:
                        subtotal_sum = pd.to_numeric(subtotal_clean, errors='coerce').sum()
                        if not pd.isna(subtotal_sum):
                            st.metric("Total Value", f"₱{subtotal_sum:,.2f}")
                        else:
                            st.metric("Total Value", "N/A")
                    except:
                        st.metric("Total Value", "N/A")
            with col3:
                st.metric("Fields Extracted", len(df.columns))
            
            # Download options
            st.subheader("📥 Download Extracted Data")
            
            col1, col2 = st.columns(2)
            with col1:
                # Excel download
                st.markdown(create_download_link(df), unsafe_allow_html=True)
            
            with col2:
                # CSV download
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download CSV File",
                    data=csv,
                    file_name="extracted_data.csv",
                    mime="text/csv"
                )
            
            # Show raw extracted data
            with st.expander("🔍 View Raw Extracted Data"):
                st.json(extracted_data)
                
        else:
            st.warning("No data could be extracted from the PDF. Please check if the PDF contains tabular data.")
            
            # Show raw text for debugging
            with st.expander("📄 Show raw PDF text"):
                try:
                    with pdfplumber.open(uploaded_file) as pdf:
                        text = ""
                        for page in pdf.pages:
                            text += page.extract_text() or ""
                        st.text(text[:2000])  # Show first 2000 characters
                except Exception as e:
                    st.error(f"Could not display PDF text: {str(e)}")
    else:
        st.info("👈 Please upload a PDF file to extract data")
        
        # Show instructions
        with st.expander("📖 Instructions"):
            st.markdown("""
            ### How to use this app:
            1. Upload a PDF file containing line items or product data
            2. The app will automatically extract:
               - Line Number
               - Product Unit (PU)
               - Description
               - Quantity (QTY)
               - Unit Price
               - Subtotal
            3. View the extracted data in a table
            4. Download the data as Excel or CSV
            
            ### Sample Data Format:
            The app can extract data from various PDF formats including:
            - Tabular data with headers
            - Structured text with line items
            - Invoices and purchase orders
            
            ### Sample Input:
Line # No. Schedule Lines Part # / Description Type Return Qty (Unit) Need By Unit Price Subtotal Tax
13 Not Available 1(EA) 30 May 2025 21,363.27 PHP 21,363.27 PHP 2,563.59 PHP
900020-Cable Entrance Facilities_OSP Lab

### Extracted Output:
- Line #: 13
- PU: 900020
- Description: Cable Entrance Facilities_OSP Lab
- QTY: 1(EA)
- Unit Price: 21,363.27 PHP
- Subtotal: 21,363.27 PHP
""")

if __name__ == "__main__":
main()