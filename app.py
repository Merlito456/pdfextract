import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO
import base64
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

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
        match = re.search(r'^(\d+)\s+(?:Not\s+Available|Material)\s+([\d,]+(?:\.\d+)?\s*\([A-Z]+\))\s+\d+\s+[A-Za-z]+\s+\d+\s+([\d,]+\.\d+)\s+[A-Z]+\s+([\d,]+\.\d+)\s+[A-Z]+(?:\s+([\d,]+\.\d+)\s+[A-Z]+)?', line, re.IGNORECASE)
        
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
                
                # Try to extract PU and Description
                pu_match = re.search(r'^(\d+)[,\-]?\s*(.+)$', next_line)
                if pu_match:
                    pu = pu_match.group(1).strip()
                    description = pu_match.group(2).strip()
                else:
                    pu_match2 = re.search(r'^([A-Z0-9\-_]+)[,\s]+(.+)$', next_line)
                    if pu_match2:
                        pu = pu_match2.group(1).strip()
                        description = pu_match2.group(2).strip()
                    else:
                        pu_match3 = re.search(r'^([A-Z0-9\-_]+)', next_line)
                        if pu_match3:
                            potential_pu = pu_match3.group(1).strip()
                            if re.match(r'^\d+$', potential_pu) or re.match(r'^\d+[A-Z\-_]', potential_pu):
                                pu = potential_pu
                                description = next_line.replace(pu, '').strip()
                                if description.startswith(','):
                                    description = description[1:].strip()
                                if description.startswith('-'):
                                    description = description[1:].strip()
                            else:
                                description = next_line
                        else:
                            description = next_line
            
            # If we still don't have PU, try to extract from the line
            if not pu:
                pu_match_in_line = re.search(r'([A-Z0-9\-_]{6,})', line)
                if pu_match_in_line:
                    pu = pu_match_in_line.group(1)
            
            # Clean up description
            if description:
                description = re.sub(r'^[,:\-\s]+', '', description)
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
            
            # Extract QTY
            qty_match = re.search(r'([\d,]+(?:\.\d+)?\s*\([A-Z]+\))', line)
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
                    pu_match = re.search(r'^(\d+)[,\-]?\s*(.+)$', next_line)
                    if pu_match:
                        pu = pu_match.group(1).strip()
                        current_row['PU'] = pu
                        description = pu_match.group(2).strip()
                        if description.startswith(','):
                            description = description[1:].strip()
                        if description.startswith('-'):
                            description = description[1:].strip()
                        current_row['Description'] = description
                    else:
                        pu_match2 = re.search(r'^([A-Z0-9\-_]+)[,\s]+(.+)$', next_line)
                        if pu_match2:
                            pu = pu_match2.group(1).strip()
                            current_row['PU'] = pu
                            description = pu_match2.group(2).strip()
                            current_row['Description'] = description
                        else:
                            current_row['Description'] = next_line
                    i += 1
        
        i += 1
    
    # Add the last row
    if current_row:
        parsed_rows.append(current_row)
    
    return parsed_rows

def create_excel_with_style(df, filename):
    """
    Create Excel file with professional styling and formatting
    """
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Extracted Data')
        
        # Get the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Extracted Data']
        
        # Define styles
        header_font = Font(name='Calibri', size=12, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        cell_font = Font(name='Calibri', size=11)
        cell_alignment = Alignment(horizontal='left', vertical='center')
        number_alignment = Alignment(horizontal='right', vertical='center')
        
        # Define borders
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Apply header styles
        for col in range(1, len(df.columns) + 1):
            cell = worksheet.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # Apply data styles
        for row in range(2, len(df) + 2):
            for col in range(1, len(df.columns) + 1):
                cell = worksheet.cell(row=row, column=col)
                cell.font = cell_font
                cell.border = thin_border
                
                # Apply right alignment for number columns
                if col in [5, 6]:  # Unit Price and Subtotal columns
                    cell.alignment = number_alignment
                    # Format as number with 2 decimal places
                    if cell.value and isinstance(cell.value, (int, float)):
                        cell.number_format = '#,##0.00'
                else:
                    cell.alignment = cell_alignment
        
        # Set column widths
        column_widths = {
            'A': 12,  # Line #
            'B': 15,  # PU
            'C': 50,  # Description
            'D': 15,  # QTY
            'E': 18,  # Unit Price
            'F': 18   # Subtotal
        }
        
        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width
        
        # Freeze the header row
        worksheet.freeze_panes = 'A2'
        
        # Add a title row above the data (optional)
        # Uncomment if you want a title
        # worksheet.insert_rows(1)
        # title_cell = worksheet.cell(row=1, column=1)
        # title_cell.value = f"Extracted Data from {filename}"
        # title_cell.font = Font(name='Calibri', size=14, bold=True)
        # worksheet.merge_cells(f'A1:F1')
    
    return output.getvalue()

def create_download_link(df, filename):
    """
    Create download link for Excel file with filename matching uploaded file
    """
    # Remove .pdf extension and add .xlsx
    base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    excel_filename = f"{base_name}_extracted.xlsx"
    
    excel_data = create_excel_with_style(df, base_name)
    
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{excel_filename}">📥 Download Excel File</a>'
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
            
            # Get original filename
            original_filename = uploaded_file.name
            
            col1, col2 = st.columns(2)
            with col1:
                # Excel download with styling and matching filename
                st.markdown(create_download_link(df, original_filename), unsafe_allow_html=True)
            
            with col2:
                # CSV download with matching filename
                base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
                csv_filename = f"{base_name}_extracted.csv"
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download CSV File",
                    data=csv,
                    file_name=csv_filename,
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