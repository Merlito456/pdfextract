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
    Extract data from PDF file
    """
    extracted_data = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"
            
            # Parse the text
            return parse_pdf_text(all_text)
            
    except Exception as e:
        st.error(f"Error extracting data: {str(e)}")
        return []

def parse_pdf_text(text):
    """
    Parse the PDF text to extract line item data
    """
    parsed_rows = []
    
    # Clean up text
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for line items - they start with "Line #No. Schedule Lines"
        if 'Line #No. Schedule Lines' in line or 'Line #No. Schedule LinesPart # / Description' in line.replace(' ', ''):
            i += 1
            continue
        
        # Look for data rows starting with line number
        # Pattern: Line number, then "Not Available" or "Material", then QTY, then date, then prices
        match = re.search(r'^(\d+)\s+(?:Not\s+Available|Material)\s+(\d+(?:\.\d+)?\s*\([A-Z]+\))\s+\d+\s+[A-Za-z]+\s+\d+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+(?:\s+([\d,]+\.\d+)\s+[A-Z]+)?', line, re.IGNORECASE)
        
        if match:
            groups = match.groups()
            
            # Extract data
            line_num = groups[0].strip()
            qty = groups[1].strip() if len(groups) > 1 else ""
            unit_price = groups[2].strip() if len(groups) > 2 else ""
            subtotal = groups[3].strip() if len(groups) > 3 else ""
            
            # Look for product code and description
            pu = ""
            description = ""
            
            # Check next line for product code and description
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Look for product code pattern (like 900020-Cable Entrance Facilities_OSP Lab)
                pu_match = re.search(r'^([A-Z0-9\-_]+)[,\s]+([A-Za-z0-9\s\._\-]+)', next_line)
                if pu_match:
                    pu = pu_match.group(1).strip()
                    description = pu_match.group(2).strip()
                else:
                    # Try alternative pattern
                    pu_match2 = re.search(r'^([A-Z0-9\-_]+)', next_line)
                    if pu_match2:
                        pu = pu_match2.group(1).strip()
                        # Rest is description
                        description = next_line.replace(pu, '').strip()
                        if description.startswith(','):
                            description = description[1:].strip()
                    else:
                        # If no product code found, the whole line might be description
                        if not re.search(r'[\d,]', next_line):
                            description = next_line
            
            # If we still don't have PU, try to extract from the line
            if not pu:
                pu_match_in_line = re.search(r'([A-Z0-9\-_]{6,})', line)
                if pu_match_in_line:
                    pu = pu_match_in_line.group(1)
            
            # Clean up description
            if description:
                description = re.sub(r'^[,:\s]+', '', description)
                description = re.sub(r'\s+', ' ', description).strip()
            
            # Add the row
            if line_num:
                parsed_rows.append({
                    'Line #': line_num,
                    'PU': pu,
                    'Description': description,
                    'QTY': qty,
                    'Unit Price': unit_price,
                    'Subtotal': subtotal
                })
                
                # Skip the description line if we used it
                if pu or description:
                    i += 1
        
        i += 1
    
    # If no data found with the main pattern, try alternative parsing
    if not parsed_rows:
        parsed_rows = parse_alternative(text)
    
    return parsed_rows

def parse_alternative(text):
    """
    Alternative parsing method for the data
    """
    parsed_rows = []
    
    # Split by line items
    lines = text.split('\n')
    
    current_row = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for line number
        line_num_match = re.search(r'^(\d+)\s+(?:Not\s+Available|Material)', line)
        if line_num_match:
            # If we have a previous row, save it
            if current_row:
                parsed_rows.append(current_row)
            
            # Start new row
            current_row = {
                'Line #': line_num_match.group(1),
                'PU': '',
                'Description': '',
                'QTY': '',
                'Unit Price': '',
                'Subtotal': ''
            }
            
            # Extract QTY - look for pattern like "3 (EA)" or "100 (M)"
            qty_match = re.search(r'(\d+(?:\.\d+)?\s*\([A-Z]+\))', line)
            if qty_match:
                current_row['QTY'] = qty_match.group(1).strip()
            
            # Extract prices
            price_matches = re.findall(r'([\d,]+\.\d+)\s+PHP', line)
            if len(price_matches) >= 2:
                current_row['Unit Price'] = price_matches[0]
                current_row['Subtotal'] = price_matches[1]
            elif len(price_matches) == 1:
                current_row['Subtotal'] = price_matches[0]
            
            # Check next line for PU and Description
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('STATUS') and 'Tax' not in next_line and 'Unconfirmed' not in next_line:
                    # Try to extract PU
                    pu_match = re.search(r'^([A-Z0-9\-_]+)', next_line)
                    if pu_match:
                        pu = pu_match.group(1)
                        current_row['PU'] = pu
                        # Rest is description
                        desc = next_line.replace(pu, '').strip()
                        if desc.startswith(','):
                            desc = desc[1:].strip()
                        current_row['Description'] = desc
                    else:
                        current_row['Description'] = next_line
                    i += 1
        
        i += 1
    
    # Add the last row
    if current_row:
        parsed_rows.append(current_row)
    
    return parsed_rows

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
            
            # Remove any rows with headers
            df = df[~df['Line #'].astype(str).str.contains('Line', case=False, na=False)]
            
            # Reorder columns
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
                st.markdown(create_download_link(df), unsafe_allow_html=True)
            
            with col2:
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
            st.warning("No data could be extracted from the PDF.")
            
            # Show raw text for debugging
            with st.expander("📄 Show raw PDF text"):
                try:
                    with pdfplumber.open(uploaded_file) as pdf:
                        text = ""
                        for page in pdf.pages:
                            text += page.extract_text() or ""
                        st.text(text[:3000])
                except Exception as e:
                    st.error(f"Could not display PDF text: {str(e)}")
    else:
        st.info("👈 Please upload a PDF file to extract data")

if __name__ == "__main__":
    main()