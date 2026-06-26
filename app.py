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
            
            # Strategy 1: Try to find structured table data
            if pdf.pages:
                # Try table extraction
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                if row and any(row):
                                    extracted_data.append(row)
                
                # If tables found, try to parse them
                if extracted_data:
                    parsed_data = parse_table_data(extracted_data)
                    if parsed_data:
                        return parsed_data
            
            # Strategy 2: Fallback to text parsing with regex
            return parse_text_data(all_text)
            
    except Exception as e:
        st.error(f"Error extracting data: {str(e)}")
        return []

def parse_table_data(table_data):
    """
    Parse table data into structured format
    """
    parsed_rows = []
    headers = []
    
    # Try to find header row
    for row in table_data:
        if row and any(row):
            row_str = " ".join([str(cell) if cell else "" for cell in row])
            if any(keyword in row_str.lower() for keyword in ['line', 'description', 'qty', 'unit', 'price']):
                headers = row
                break
    
    # If no headers found, try to identify columns by position
    if not headers:
        # Look for patterns in the data
        for row in table_data:
            if row and len(row) >= 6:
                # Try to identify if this is a data row
                row_str = " ".join([str(cell) if cell else "" for cell in row])
                if re.search(r'\d+', row_str) and re.search(r'PHP|₱', row_str):
                    parsed_rows.append(parse_row_data(row))
    else:
        # Parse with headers
        header_index = table_data.index(headers) if headers in table_data else 0
        for row in table_data[header_index + 1:]:
            if row and any(row):
                parsed_rows.append(parse_row_data(row))
    
    return parsed_rows

def parse_text_data(text):
    """
    Parse text data using regex patterns
    """
    parsed_rows = []
    
    # Pattern to match lines with product data
    # This pattern looks for line numbers followed by product codes and descriptions
    patterns = [
        # Pattern: Line number, Product code, Description, QTY, Date, Unit Price, Subtotal, Tax
        r'(\d+)\s+([A-Z0-9\-_]+)\s+([A-Za-z0-9\s\._\-]+?)\s+(\d+\([A-Z]+\))\s+\d+\s+[A-Za-z]+\s+\d+,\d+\.\d+\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+',
        
        # Pattern for simpler format
        r'(\d+)\s+([A-Z0-9\-_]+)\s+([^\n]+?)\s+(\d+\([A-Z]+\))\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+',
        
        # Pattern for the sample format
        r'(\d+)\s+Not Available\s+(\d+\([A-Z]+\))\s+\d+\s+[A-Za-z]+\s+\d+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([A-Za-z0-9\s\._\-]+)',
    ]
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 6:
                    row_data = {
                        'Line #': groups[0].strip(),
                        'PU': groups[1].strip(),
                        'Description': groups[2].strip() if len(groups) > 2 else '',
                        'QTY': groups[3].strip() if len(groups) > 3 else '',
                        'Unit Price': groups[4].strip() if len(groups) > 4 else '',
                        'Subtotal': groups[5].strip() if len(groups) > 5 else ''
                    }
                    parsed_rows.append(row_data)
                    break
    
    # If no data found with regex, try line by line parsing
    if not parsed_rows:
        parsed_rows = parse_line_by_line(text)
    
    return parsed_rows

def parse_line_by_line(text):
    """
    Parse data line by line using heuristics
    """
    parsed_rows = []
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for lines containing product codes (alphanumeric with hyphens/underscores)
        if re.search(r'[A-Z0-9\-_]{6,}', line):
            # Try to extract description from next line if current line is short
            description = line
            qty = "1(EA)"  # Default
            unit_price = ""
            subtotal = ""
            line_num = ""
            pu = ""
            
            # Extract line number and PU code
            line_parts = line.split()
            if len(line_parts) >= 2:
                # First part might be line number
                if line_parts[0].isdigit():
                    line_num = line_parts[0]
                    # Look for PU code
                    for part in line_parts[1:]:
                        if re.search(r'[A-Z0-9\-_]{6,}', part):
                            pu = part
                            break
                else:
                    for part in line_parts:
                        if re.search(r'[A-Z0-9\-_]{6,}', part):
                            pu = part
                            break
            
            # Check next lines for price information
            j = i + 1
            while j < len(lines) and j < i + 3:
                next_line = lines[j].strip()
                # Look for price patterns
                price_matches = re.findall(r'([\d,]+\.\d+)\s+PHP', next_line)
                if price_matches and len(price_matches) >= 2:
                    unit_price = price_matches[0]
                    subtotal = price_matches[1]
                    # If description was too short, combine with next line
                    if len(description.split()) < 3:
                        description = line + " " + next_line
                j += 1
            
            # If we have the data, add it
            if pu or description:
                parsed_rows.append({
                    'Line #': line_num if line_num else str(i + 1),
                    'PU': pu if pu else '',
                    'Description': description if description else '',
                    'QTY': qty,
                    'Unit Price': unit_price if unit_price else '',
                    'Subtotal': subtotal if subtotal else ''
                })
        i += 1
    
    return parsed_rows

def parse_row_data(row):
    """
    Parse a single row of data
    """
    # Clean the row
    clean_row = [str(cell).strip() if cell else '' for cell in row]
    
    # Try to identify data based on patterns
    parsed = {
        'Line #': '',
        'PU': '',
        'Description': '',
        'QTY': '',
        'Unit Price': '',
        'Subtotal': ''
    }
    
    # Look for line number (digits)
    for cell in clean_row:
        if cell.isdigit() and len(cell) <= 4:
            parsed['Line #'] = cell
            break
    
    # Look for PU code (alphanumeric with hyphens/underscores)
    for cell in clean_row:
        if re.search(r'[A-Z0-9\-_]{6,}', cell):
            parsed['PU'] = cell
            break
    
    # Look for QTY (digits with (EA) or similar)
    for cell in clean_row:
        if re.search(r'\d+\([A-Z]+\)', cell):
            parsed['QTY'] = cell
            break
    
    # Look for prices (numbers with commas and decimals)
    prices = []
    for cell in clean_row:
        if re.search(r'[\d,]+\.\d+', cell):
            prices.append(cell)
    
    if len(prices) >= 2:
        parsed['Unit Price'] = prices[0]
        parsed['Subtotal'] = prices[1]
    elif len(prices) == 1:
        parsed['Subtotal'] = prices[0]
    
    # Everything else might be description
    for cell in clean_row:
        if (cell not in [parsed['Line #'], parsed['PU'], parsed['QTY'], parsed['Unit Price'], parsed['Subtotal']] 
            and len(cell) > 10):
            parsed['Description'] = cell
            break
    
    # If description is empty, try to combine remaining cells
    if not parsed['Description']:
        remaining = [cell for cell in clean_row if cell not in [parsed['Line #'], parsed['PU'], parsed['QTY'], parsed['Unit Price'], parsed['Subtotal']]]
        if remaining:
            parsed['Description'] = ' '.join(remaining)
    
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
uploaded_file = st.file_uploader("Upload PDF file", type=['pdf'])

if uploaded_file is not None:
    st.success("✅ File uploaded successfully!")
    
    with st.spinner("Extracting data from PDF..."):
        extracted_data = extract_data_from_pdf(uploaded_file)
    
    if extracted_data:
        # Convert to DataFrame
        df = pd.DataFrame(extracted_data)
        
        # Clean up empty rows
        df = df.replace('', pd.NA).dropna(how='all')
        df = df.fillna('')
        
        # Display results
        st.subheader("📊 Extracted Data")
        st.dataframe(df, use_container_width=True)
        
        # Display statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items", len(df))
        with col2:
            if 'Subtotal' in df.columns:
                subtotal_col = df['Subtotal'].replace('', '0').str.replace(',', '').str.replace(' PHP', '').str.replace('₱', '')
                subtotal_col = pd.to_numeric(subtotal_col, errors='coerce')
                st.metric("Total Value", f"₱{subtotal_col.sum():,.2f}" if not subtotal_col.isna().all() else "N/A")
        with col3:
            st.metric("Fields Extracted", len(df.columns))
        
        # Show sample data
        with st.expander("📋 View Sample Data"):
            st.write("Sample of extracted data:")
            st.dataframe(df.head(10))
        
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
            with pdfplumber.open(uploaded_file) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                st.text(text)
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