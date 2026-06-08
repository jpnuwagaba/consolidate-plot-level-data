import streamlit as st
import pandas as pd
import os

def count_duplicates(df):
    """Count the number of duplicate rows in the dataframe."""
    return df.duplicated().sum()

def get_duplicates_df(df):
    """Get all duplicate rows from the dataframe."""
    return df[df.duplicated(keep=False)].sort_values(by=list(df.columns)).reset_index(drop=True)

def count_missing_certifications(df):
    """
    Count records that lack certification information.
    A record is considered to lack certification if ALL certification fields are NULL.
    """
    certification_fields = [
        'is_cafe_practices_certified',
        'is_rfa_utz_certified',
        'is_impact_certified',
        'is_organic_certified',
        'is_4c_certified',
        'is_fairtrade_certified',
        'other_certification_name'
    ]
    
    # Filter only the certification fields that exist in the dataframe
    existing_cert_fields = [field for field in certification_fields if field in df.columns]
    
    # Count rows where ALL certification fields are NULL/NaN
    missing_cert_mask = df[existing_cert_fields].isna().all(axis=1)
    return missing_cert_mask.sum()

def get_missing_certifications_df(df):
    """Get all records that lack certification information."""
    certification_fields = [
        'is_cafe_practices_certified',
        'is_rfa_utz_certified',
        'is_impact_certified',
        'is_organic_certified',
        'is_4c_certified',
        'is_fairtrade_certified',
        'other_certification_name'
    ]
    
    # Filter only the certification fields that exist in the dataframe
    existing_cert_fields = [field for field in certification_fields if field in df.columns]
    
    # Get rows where ALL certification fields are NULL/NaN
    missing_cert_mask = df[existing_cert_fields].isna().all(axis=1)
    return df[missing_cert_mask].reset_index(drop=True)

def get_certification_fields():
    """Get all certification field names."""
    return [
        'is_cafe_practices_certified',
        'is_rfa_utz_certified',
        'is_impact_certified',
        'is_organic_certified',
        'is_4c_certified',
        'is_fairtrade_certified',
        'other_certification_name'
    ]

def extract_data_by_filter(df, filter_type):
    """Extract data from dataframe based on filter selection."""
    certification_fields = get_certification_fields()
    existing_cert_fields = [field for field in certification_fields if field in df.columns]
    
    if filter_type == "Certification Details":
        # Return only certification-related columns plus ID columns (excluding cert name field duplication)
        id_cols = [col for col in df.columns if 'id' in col.lower()]
        # Combine and remove duplicates while preserving order
        columns_to_select = list(dict.fromkeys(id_cols + existing_cert_fields))
        return df[columns_to_select].reset_index(drop=True)
    else:
        # For other filters, return rows grouped by that field with relevant details
        if filter_type in df.columns:
            # Get all columns for better context
            return df[[col for col in df.columns if col != filter_type] + [filter_type]].reset_index(drop=True)
        return df

@st.dialog("Duplicate Records", width="large")
def show_duplicates_modal(duplicates_df):
    """Display duplicate records in a modal."""
    st.write(f"Total duplicate records: {len(duplicates_df)}")
    st.dataframe(duplicates_df, height=500)
    
    # Download button
    csv = duplicates_df.to_csv(index=False)
    st.download_button(
        label="Download duplicates as CSV",
        data=csv,
        file_name="duplicate_records.csv",
        mime="text/csv"
    )

@st.dialog("Missing Certifications", width="large")
def show_missing_certifications_modal(missing_cert_df):
    """Display records with missing certifications in a modal."""
    st.write(f"Total records with missing certifications: {len(missing_cert_df)}")
    st.dataframe(missing_cert_df, height=500)
    
    # Download button
    csv = missing_cert_df.to_csv(index=False)
    st.download_button(
        label="Download missing certifications as CSV",
        data=csv,
        file_name="missing_certifications.csv",
        mime="text/csv"
    )

st.set_page_config(
    page_title="Consolidate farm plot data",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="auto",
)

# Initialize session state for tracking data load
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'show_duplicates_modal' not in st.session_state:
    st.session_state.show_duplicates_modal = False
if 'show_missing_certs_modal' not in st.session_state:
    st.session_state.show_missing_certs_modal = False
if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None

st.title("Consolidate farm plot data")
st.write("This tool will help you upload farm plot data CSV files and consolidate them into a single dataframe. You will then upload a file downloaded Meridia containing the same scope (country-level) of data, and the tool will compare the two datasets and facilitate extraction of key information at farm plot level like certification details.")

# File uploader for CSV files
st.subheader("Step 1: Upload Farm Plot Data Files")
st.write("Upload one or more CSV files containing farm plot data. They will be automatically consolidated.")
uploaded_csv_files = st.file_uploader(
    "Upload CSV files with farm plot data:",
    type=["csv"],
    accept_multiple_files=True,
    key="farm_plot_files"
)

if uploaded_csv_files:
    try:
        # Read and consolidate all uploaded CSV files
        dfs_list = []
        for uploaded_file in uploaded_csv_files:
            df = pd.read_csv(uploaded_file)
            dfs_list.append(df)
        
        consolidated_df = pd.concat(dfs_list, ignore_index=True)
        
        # Calculate statistics
        num_files = len(uploaded_csv_files)
        num_rows = consolidated_df.shape[0]
        num_columns = consolidated_df.shape[1]
        num_duplicates = count_duplicates(consolidated_df)
        num_missing_certifications = count_missing_certifications(consolidated_df)
        
        # Display enhanced success message
        st.success("✓ Successfully consolidated farm plot data")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Files Read", num_files)
        with col2:
            st.metric("Shape", f"{num_rows:,} rows × {num_columns} cols")
        with col3:
            st.metric("Duplicates", num_duplicates)
            if st.button("Preview", key="btn_duplicates"):
                st.session_state.show_duplicates_modal = True
            if st.session_state.show_duplicates_modal:
                duplicates_df = get_duplicates_df(consolidated_df)
                show_duplicates_modal(duplicates_df)
                st.session_state.show_duplicates_modal = False
        with col4:
            st.metric("Missing Certifications", num_missing_certifications)
            if st.button("Preview", key="btn_missing_certs"):
                st.session_state.show_missing_certs_modal = True
            if st.session_state.show_missing_certs_modal:
                missing_cert_df = get_missing_certifications_df(consolidated_df)
                show_missing_certifications_modal(missing_cert_df)
                st.session_state.show_missing_certs_modal = False
        
        # Display the first few rows
        st.subheader("Consolidated Data Preview")
        st.dataframe(consolidated_df, height=200)
        
        st.write("Data consolidation complete. Now, please upload the Meridia file for comparison.")
        
        # Set session state to show file uploader
        st.session_state.data_loaded = True
        
    except Exception as e:
        st.error(f"Error reading or consolidating CSV files: {str(e)}")


# file uploader for Meridia file - only show if data has been loaded
if st.session_state.data_loaded:
    st.subheader("Farm Plot-Level Data Extraction")
    
    col1, gap, col2 = st.columns([0.875, 0.25, 1.875])
    
    with col1:
        st.write("**Upload & Filter Options**")
        st.write("Please upload the Meridia file (CSV or Excel format) to extract certification details and compare with the consolidated data.")
        uploaded_file = st.file_uploader("Upload the Meridia file:", type=["csv", "xlsx"], key="meridia_uploader")
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith(".csv"):
                    meridia_df = pd.read_csv(uploaded_file)
                else:
                    meridia_df = pd.read_excel(uploaded_file)
                st.success("✓ Meridia file uploaded successfully.")
                st.write(f"Meridia shape: {meridia_df.shape[0]:,} rows × {meridia_df.shape[1]} columns")
                
                # Extract dynamic filter options from consolidated data
                cert_fields = get_certification_fields()
                existing_cert_fields = [field for field in cert_fields if field in consolidated_df.columns]
                
                # Build filter options: Certification Details first, then other fields
                filter_options = ["Certification Details"]
                # Add other meaningful fields (exclude IDs and coordinates)
                excluded_patterns = ['id', 'gps', 'point', 'polygon', 'wkt', 'latitude', 'longitude']
                for col in consolidated_df.columns:
                    if col not in existing_cert_fields and not any(pattern in col.lower() for pattern in excluded_patterns):
                        filter_options.append(col)
                
                st.write("**Select Extraction Filter:**")
                selected_filter = st.selectbox(
                    "Choose which data to extract:",
                    filter_options,
                    key="extraction_filter"
                )
                
                # Initialize session state for extracted data
                if 'extracted_data' not in st.session_state:
                    st.session_state.extracted_data = None
                
                # Extract data based on filter
                st.session_state.extracted_data = extract_data_by_filter(consolidated_df, selected_filter)
                
                st.write(f"**Extracted Data Shape:** {st.session_state.extracted_data.shape[0]:,} rows × {st.session_state.extracted_data.shape[1]} columns")
                
                # Download button for extracted data
                csv = st.session_state.extracted_data.to_csv(index=False)
                st.download_button(
                    label="📥 Download Extracted Data",
                    data=csv,
                    file_name=f"extracted_{selected_filter.lower().replace(' ', '_')}.csv",
                    mime="text/csv"
                )
            
            except Exception as e:
                st.error(f"Error reading the Meridia file: {str(e)}")
    
    with col2:
        st.write("**Preview**")
        if 'extracted_data' in st.session_state and st.session_state.extracted_data is not None:
            st.dataframe(st.session_state.extracted_data, height=500, use_container_width=True)
        else:
            st.write("Upload a Meridia file and select a filter to preview extracted data here.")