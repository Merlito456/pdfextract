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
    Extract data from PDF file focusing on line items
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
    Parse table data into structured format, filtering out headers and tax rows
    """
    parsed_rows = []
    
    for row in table_data:
        if not row:
            continue
            
        # Skip rows that are headers or tax information
        row_str = " ".join([str(cell).lower() if cell else "" for cell in row])
        
        # Skip rows containing header or tax keywords
        skip_keywords = ['line # no', 'schedule lines', 'part # / description', 
                        'tax category', 'tax rate', 'taxable amount', 'tax amount',
                        'tax location', 'exempt detail', 'return qty', 'need by']
        
        if any(keyword in row_str for keyword in skip_keywords):
            continue
        
        # Try to parse as a data row
        parsed_row = parse_row_data(row)
        if parsed_row and (parsed_row.get('PU') or parsed_row.get('Description')):
            parsed_rows.append(parsed_row)
    
    return parsed_rows

def parse_text_data(text):
    """
    Parse text data using regex patterns, filtering out headers and tax rows
    """
    parsed_rows = []
    
    # Clean up text
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Skip header lines
    skip_keywords = ['line # no', 'schedule lines', 'part # / description', 
                    'tax category', 'tax rate', 'taxable amount', 'tax amount',
                    'tax location', 'exempt detail', 'return qty', 'need by']
    
    # Pattern for the specific format in your sample
    # Looking for: Line number, then Not Available or product code, then QTY, then date, then prices
    pattern1 = r'(\d+)\s+(?:Not\s+Available|([A-Z0-9\-_]+))\s+(\d+\([A-Z]+\))\s+[\d]+\s+[A-Za-z]+\s+[\d]+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+(?:\s+([\d,]+\.\d+)\s+[A-Z]+)?'
    
    # Pattern for format with product code
    pattern2 = r'(\d+)\s+([A-Z0-9\-_]+)\s+([A-Za-z0-9\s\._\-]+?)\s+(\d+\([A-Z]+\))\s+[\d]+\s+[A-Za-z]+\s+[\d]+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+'
    
    # Pattern for general format
    pattern3 = r'(\d+)\s+([A-Z0-9\-_]+)\s+([^\n]+?)\s+(\d+\([A-Z]+\))\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+'
    
    # Pattern for simple format with just prices
    pattern4 = r'(\d+)\s+([A-Z0-9\-_]+)\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+'
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip header and tax lines
        if any(keyword in line.lower() for keyword in skip_keywords):
            i += 1
            continue
        
        # Try each pattern
        matched = False
        for pattern in [pattern1, pattern2, pattern3, pattern4]:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Extract data based on pattern
                row_data = {'Line #': "", 'PU': "", 'Description': "", 'QTY': "", 'Unit Price': "", 'Subtotal': ""}
                
                if len(groups) >= 4:
                    row_data['Line #'] = groups[0].strip() if groups[0] else ""
                    
                    # Find PU (could be in different positions)
                    pu_found = False
                    for g in groups[1:]:
                        if g and re.search(r'[A-Z0-9\-_]{4,}', g) and not pu_found:
                            row_data['PU'] = g.strip()
                            pu_found = True
                            break
                    
                    # Find QTY
                    for g in groups:
                        if g and re.search(r'\d+\([A-Z]+\)', g):
                            row_data['QTY'] = g.strip()
                            break
                    
                    # Find prices (last two numbers with commas and decimals)
                    price_matches = re.findall(r'([\d,]+\.\d+)', line)
                    if len(price_matches) >= 2:
                        row_data['Unit Price'] = price_matches[-2]
                        row_data['Subtotal'] = price_matches[-1]
                    elif len(price_matches) == 1:
                        row_data['Subtotal'] = price_matches[0]
                    
                    # If description not found, try to extract from line
                    if not row_data['Description']:
                        # Remove known fields from line
                        desc_line = line
                        for field in [row_data['Line #'], row_data['PU'], row_data['QTY'], row_data['Unit Price'], row_data['Subtotal']]:
                            if field:
                                desc_line = desc_line.replace(field, '')
                        desc_line = re.sub(r'\s+', ' ', desc_line).strip()
                        desc_line = re.sub(r'PHP|₱|Not Available', '', desc_line).strip()
                        if desc_line and len(desc_line) > 5:
                            row_data['Description'] = desc_line
                        elif i + 1 < len(lines):
                            # Check next line for description
                            next_line = lines[i + 1].strip()
                            if re.search(r'[A-Za-z]', next_line) and not re.search(r'[\d,]', next_line):
                                row_data['Description'] = next_line
                                i += 1
                    
                    # Clean up description
                    if row_data['Description']:
                        row_data['Description'] = re.sub(r'Not Available', '', row_data['Description']).strip()
                        row_data['Description'] = re.sub(r'\s+', ' ', row_data['Description']).strip()
                    
                    if row_data['Line #'] or row_data['PU']:
                        parsed_rows.append(row_data)
                        matched = True
                        break
        
        i += 1
    
    # If no data found, try a simpler approach
    if not parsed_rows:
        parsed_rows = parse_line_by_line(lines)
    
    return parsed_rows

def parse_line_by_line(lines):
    """
    Parse data line by line using simpler heuristics, filtering out headers and tax rows
    """
    parsed_rows = []
    
    skip_keywords = ['line # no', 'schedule lines', 'part # / description', 
                    'tax category', 'tax rate', 'taxable amount', 'tax amount',
                    'tax location', 'exempt detail', 'return qty', 'need by']
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip header and tax lines
        if any(keyword in line.lower() for keyword in skip_keywords):
            i += 1
            continue
        
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
            elif len(price_matches) == 1:
                subtotal = price_matches[0]
            
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
            
            # Clean description
            if description:
                description = re.sub(r'Not Available', '', description).strip()
                description = re.sub(r'\s+', ' ', description).strip()
            
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
    Parse a single row of data, filtering out headers and tax rows
    """
    # Clean the row
    clean_row = [str(cell).strip() if cell else "" for cell in row]
    clean_row = [cell for cell in clean_row if cell]
    
    if len(clean_row) < 3:
        return {}
    
    # Skip if this looks like a header or tax row
    row_str = " ".join(clean_row).lower()
    skip_keywords = ['line # no', 'schedule lines', 'part # / description', 
                    'tax category', 'tax rate', 'taxable amount', 'tax amount',
                    'tax location', 'exempt detail', 'return qty', 'need by']
    
    if any(keyword in row_str for keyword in skip_keywords):
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
        # Clean description
        parsed['Description'] = re.sub(r'Not Available', '', parsed['Description']).strip()
        parsed['Description'] = re.sub(r'\s+', ' ', parsed['Description']).strip()
    
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
            
            # Remove duplicate headers if any
            df = df[~df['Line #'].astype(str).str.contains('Line #', case=False, na=False)]
            df = df[~df['PU'].astype(str).str.contains('Tax', case=False, na=False)]
            
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
                        st.text(text[:2000])
                except Exception as e:
                    st.error(f"Could not display PDF text: {str(e)}")
    else:
        st.info("👈 Please upload a PDF file to extract data")

if __name__ == "__main__":
    main()