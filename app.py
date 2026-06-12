import streamlit as st
import re
import pandas as pd

SOURCE_FILE_COLUMN = "source_file"
DUPLICATE_KEY_FIELDS = ["sucafina_plot_id", "plot_wkt"]
TRUE_CERTIFICATION_VALUES = {"true", "t", "yes", "y", "1", "1.0"}
FALSE_CERTIFICATION_VALUES = {"false", "f", "no", "n", "0", "0.0"}

def get_duplicate_key_fields(df):
    """Get the fields used to identify duplicate farm plots."""
    missing_fields = [field for field in DUPLICATE_KEY_FIELDS if field not in df.columns]
    if missing_fields:
        missing_fields_text = ", ".join(missing_fields)
        raise ValueError(f"Missing duplicate key field(s): {missing_fields_text}")
    return DUPLICATE_KEY_FIELDS

def count_duplicates(df):
    """Count the number of duplicate rows in the dataframe."""
    return df.duplicated(subset=get_duplicate_key_fields(df)).sum()

def get_duplicates_df(df):
    """Get all duplicate rows from the dataframe."""
    return df[df.duplicated(subset=get_duplicate_key_fields(df), keep=False)].sort_values(by=list(df.columns)).reset_index(drop=True)

def get_existing_certification_fields(df):
    """Get certification field names that exist in the dataframe."""
    return [field for field in get_certification_fields() if field in df.columns]

def get_boolean_certification_fields(df):
    """Get certification fields that store true/false values."""
    return [field for field in get_existing_certification_fields(df) if field.startswith("is_")]

def get_missing_certifications_mask(df):
    """Identify records where all certification fields are empty."""
    existing_cert_fields = get_existing_certification_fields(df)
    if not existing_cert_fields:
        return pd.Series(False, index=df.index)
    certification_values = df[existing_cert_fields].replace(r"^\s*$", pd.NA, regex=True)
    return certification_values.isna().all(axis=1)

def normalize_certification_value(value):
    """Normalize common true/false certification values."""
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    value_text = str(value).strip().lower()
    if value_text in TRUE_CERTIFICATION_VALUES:
        return True
    if value_text in FALSE_CERTIFICATION_VALUES:
        return False
    return None

def has_true_and_false_certifications(row, certification_fields):
    """Check whether a record has at least one true and one false certification value."""
    normalized_values = {
        normalize_certification_value(row[field])
        for field in certification_fields
    }
    return True in normalized_values and False in normalized_values

def trim_consolidated_dataframe(df):
    """
    Remove missing-certification records and resolve duplicate farm plots.
    Duplicate farm plots are identified by sucafina_plot_id and plot_wkt.
    """
    key_fields = get_duplicate_key_fields(df)
    trimmed_df = df.loc[~get_missing_certifications_mask(df)].copy()
    if trimmed_df.empty:
        return trimmed_df.reset_index(drop=True)

    boolean_cert_fields = get_boolean_certification_fields(trimmed_df)
    if not boolean_cert_fields:
        return trimmed_df.drop_duplicates(subset=key_fields, keep="first").reset_index(drop=True)
    cert_profile_fields = get_existing_certification_fields(trimmed_df)

    mixed_cert_mask = trimmed_df.apply(
        lambda row: has_true_and_false_certifications(row, boolean_cert_fields),
        axis=1
    )
    working_df = trimmed_df.assign(_has_true_and_false_certifications=mixed_cert_mask)
    retained_groups = []

    for _, group_df in working_df.groupby(key_fields, dropna=False, sort=False):
        if len(group_df) == 1:
            retained_groups.append(group_df)
            continue

        preferred_group_df = group_df[group_df["_has_true_and_false_certifications"]]
        if preferred_group_df.empty:
            retained_groups.append(group_df.head(1))
        else:
            retained_groups.append(preferred_group_df.drop_duplicates(subset=cert_profile_fields, keep="first"))

    return (
        pd.concat(retained_groups, ignore_index=True)
        .drop(columns=["_has_true_and_false_certifications"])
        .reset_index(drop=True)
    )

def count_missing_certifications(df):
    """
    Count records that lack certification information.
    A record is considered to lack certification if ALL certification fields are NULL.
    """
    return get_missing_certifications_mask(df).sum()

def get_missing_certifications_df(df):
    """Get all records that lack certification information."""
    missing_cert_mask = get_missing_certifications_mask(df)
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

def extract_data_by_filter(
    consolidated_df,
    meridia_df,
    filter_type,
    consolidated_match_col,
    meridia_match_col
):
    existing_cert_fields = get_existing_certification_fields(consolidated_df)

    matched_df = pd.merge(
    consolidated_df,
    meridia_df,
    left_on=consolidated_match_col,
    right_on=meridia_match_col,
    how="inner"
)
    # ✅ Prevent row explosion from duplicates
    matched_df = matched_df.drop_duplicates(subset=[consolidated_match_col]).reset_index(drop=True)

    # ✅ Only keep relevant consolidated columns
    if filter_type == "Certification Details":
        columns_to_select = list(
            dict.fromkeys(
                [consolidated_match_col] + existing_cert_fields
            )
        )
        return matched_df[columns_to_select]

    if filter_type in matched_df.columns:
        return matched_df[[consolidated_match_col, filter_type]]

    return matched_df[[consolidated_match_col]]

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
    page_icon="🤗",
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

st.title("Consolidate farm plot data 🤗")
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
            df[SOURCE_FILE_COLUMN] = uploaded_file.name
            dfs_list.append(df)
        
        raw_consolidated_df = pd.concat(dfs_list, ignore_index=True)
        consolidated_df = trim_consolidated_dataframe(raw_consolidated_df)
        
        # Calculate statistics
        num_files = len(uploaded_csv_files)
        raw_num_rows = raw_consolidated_df.shape[0]
        raw_num_columns = raw_consolidated_df.shape[1]
        num_rows = raw_num_rows
        num_columns = raw_num_columns
        trimmed_num_rows = consolidated_df.shape[0]
        trimmed_num_columns = consolidated_df.shape[1]
        num_duplicates = count_duplicates(raw_consolidated_df)
        num_missing_certifications = count_missing_certifications(raw_consolidated_df)
        num_removed_records = raw_num_rows - trimmed_num_rows
        
        # Display enhanced success message
        st.success("✓ Successfully consolidated farm plot data")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Files Read", num_files)
        with col2:
            st.metric("Shape", f"{num_rows:,} rows × {num_columns} cols")
        with col3:
            st.metric("Duplicates", num_duplicates)
            if st.button("Preview", key="btn_duplicates"):
                st.session_state.show_duplicates_modal = True
            if st.session_state.show_duplicates_modal:
                duplicates_df = get_duplicates_df(raw_consolidated_df)
                show_duplicates_modal(duplicates_df)
                st.session_state.show_duplicates_modal = False
        with col4:
            st.metric("Missing Certifications", num_missing_certifications)
            if st.button("Preview", key="btn_missing_certs"):
                st.session_state.show_missing_certs_modal = True
            if st.session_state.show_missing_certs_modal:
                missing_cert_df = get_missing_certifications_df(raw_consolidated_df)
                show_missing_certifications_modal(missing_cert_df)
                st.session_state.show_missing_certs_modal = False
        with col5:
            st.metric("Trimmed Shape", f"{trimmed_num_rows:,} rows x {trimmed_num_columns} cols", delta=f"-{num_removed_records:,} rows")
        
        # Display the first few rows
        st.subheader("Consolidated Data Preview (free of duplicates and missing certifications)")
        st.dataframe(consolidated_df, height=200)
        
        st.write("Data consolidation and trimming complete. Now, please upload the Meridia file for comparison.")
        
        # Set session state to show file uploader
        st.session_state.data_loaded = True
        
    except Exception as e:
        st.error(f"Error reading or consolidating CSV files: {str(e)}")


# file uploader for Meridia file - only show if data has been loaded
if st.session_state.data_loaded:
    st.subheader("Farm Plot-Level Data Extraction")
    
    col1, gap, col2 = st.columns([4.75, 0.5, 4.75])
    
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

                st.write("#### Matching Configuration")

                left_col, right_col = st.columns(2)

                with left_col:
                    match_col_meridia = st.selectbox(
                    "Meridia ID Column",
                    meridia_df.columns,
                    index=meridia_df.columns.get_loc("farm_plot_id")
                    if "farm_plot_id" in meridia_df.columns
                    else 0
                )

                    # ✅ Deduplicate Meridia using the selected match column
                    if match_col_meridia in meridia_df.columns:
                        if "dataset_name" in meridia_df.columns:
                            meridia_df = (
                                meridia_df
                                .sort_values(by="dataset_name", ascending=False)
                                .drop_duplicates(subset=[match_col_meridia], keep="first")
                                .reset_index(drop=True)
                            )
                        else:
                            meridia_df = (
                                meridia_df
                                .drop_duplicates(subset=[match_col_meridia])
                                .reset_index(drop=True)
                            )

                    
                    st.success("✓ Meridia file uploaded successfully.")
                    st.write(f"Meridia shape: {meridia_df.shape[0]:,} rows × {meridia_df.shape[1]} columns")                

                with right_col:
                    match_col_consolidated = st.selectbox(
                        "Consolidated ID Column",
                        consolidated_df.columns,
                        index=consolidated_df.columns.get_loc("sucafina_plot_id")
                        if "sucafina_plot_id" in consolidated_df.columns
                        else 0
                    )
                
                    # Extract dynamic filter options from consolidated data
                    existing_cert_fields = get_existing_certification_fields(consolidated_df)
                    
                    # Build filter options: Certification Details first, then other fields
                    filter_options = ["Certification Details"]
                    # Add other meaningful fields (exclude IDs and coordinates)
                    excluded_patterns = ['id', 'gps', 'point', 'polygon', 'wkt', 'latitude', 'longitude']
                    for col in consolidated_df.columns:
                        if col not in existing_cert_fields and not any(pattern in col.lower() for pattern in excluded_patterns):
                            filter_options.append(col)
                    
                    st.write("**Select Extraction Filter:**")
                    selected_filters = st.multiselect(
                        "Choose which data to extract:",
                        filter_options,
                        default=["Certification Details"],  # optional default
                        key="extraction_filter"
                    )
                
                    # Initialize session state for extracted data
                    if 'extracted_data' not in st.session_state:
                        st.session_state.extracted_data = None

                    # ✅ DEBUG: Check actual matching IDs
                    common_ids = (
                        set(consolidated_df[match_col_consolidated].dropna()) &
                        set(meridia_df[match_col_meridia].dropna())
                    )

                    st.write(f"✅ Unique matching IDs: {len(common_ids)}")
                    
                    # Extract data based on filter
                    if selected_filters:
                        dfs = []

                        for filt in selected_filters:
                            df_part = extract_data_by_filter(
                                consolidated_df=consolidated_df,
                                meridia_df=meridia_df,
                                filter_type=filt,
                                consolidated_match_col=match_col_consolidated,
                                meridia_match_col=match_col_meridia
                            )
                            dfs.append(df_part)

                        # ✅ Merge all selected outputs on the ID column
                        extracted_df = dfs[0]

                        for df_part in dfs[1:]:
                            extracted_df = extracted_df.merge(
                                df_part,
                                on=match_col_consolidated,
                                how="outer"
                            )

                        st.session_state.extracted_data = extracted_df.reset_index(drop=True)
                    else:
                        st.session_state.extracted_data = None
                    
                    st.write(f"**Extracted Data Shape:** {st.session_state.extracted_data.shape[0]:,} rows × {st.session_state.extracted_data.shape[1]} columns")
                            
            except Exception as e:
                st.error(f"Error reading the Meridia file: {str(e)}")
    
    with col2:
        st.write("**Preview with Match Statistics**")

        if (
            'extracted_data' in st.session_state and 
            st.session_state.extracted_data is not None
        ):
            # ✅ Match statistics ABOVE table
            matching_ids = (
                set(consolidated_df[match_col_consolidated].dropna()) &
                set(meridia_df[match_col_meridia].dropna())
            )

            col_a, col_b, col_c = st.columns(3)

            with col_a:
                st.metric("Consolidated Records", f"{len(consolidated_df):,}")

            with col_b:
                st.metric("Meridia Records", f"{len(meridia_df):,}")

            with col_c:
                st.metric("Matching IDs", f"{len(matching_ids):,}")

            # ✅ Preview table
            st.dataframe(
                st.session_state.extracted_data,
                height=500,
                use_container_width=True
            )

            # ✅ Download button BELOW table
            
            import zipfile
            import io

            # ✅ Scope input
            scope_name = st.text_input(
                label="",
                placeholder="Specify scope e.g., Costa Rica or TPJC"
            )

            scope_clean = scope_name.strip() if scope_name else ""
            is_valid_scope = bool(scope_clean)

            safe_scope = scope_clean.lower().replace(" ", "_")

            df = st.session_state.extracted_data

            # ✅ Always prepare main CSV
            main_csv = df.to_csv(index=False)

            # ✅ Check if Certification Details is selected
            is_cert_filter = (
                selected_filters == ["Certification Details"] or
                (len(selected_filters) == 1 and selected_filters[0] == "Certification Details")
            )

            # ✅ Get certification fields
            cert_fields = get_boolean_certification_fields(df)

            # ✅ Map fields to friendly names
            cert_mapping = {
                "is_cafe_practices_certified": "CP",
                "is_rfa_utz_certified": "RF",
                "is_organic_certified": "Organic",
                "is_4c_certified": "4C",
                "is_fairtrade_certified": "Fairtrade",
                "is_impact_certified": "Impact"
            }

            # ✅ Count certified plots per certification
            cert_summary = []

            for field in cert_fields:
                normalized = df[field].apply(normalize_certification_value)
                count = (normalized == True).sum()

                if count > 0:
                    cert_summary.append({
                        "Certification": cert_mapping.get(field, field),
                        "Count": count
                    })

            # cert_summary_df = pd.DataFrame(cert_summary)


            if is_cert_filter and cert_fields:

                def classify_row(row):
                    values = [normalize_certification_value(row[f]) for f in cert_fields]

                    has_true = True in values
                    has_false = False in values
                    has_any = any(v is not None for v in values)

                    if has_true:
                        return "certified"
                    elif has_any and not has_true:
                        return "non_certified"
                    else:
                        return "missing"

                df["__cert_status"] = df.apply(classify_row, axis=1)

                certified_df = df[df["__cert_status"] == "certified"]
                non_certified_df = df[df["__cert_status"] == "non_certified"]
                missing_df = df[df["__cert_status"] == "missing"]

                # ✅ Counts
                total = len(df)
                certified_count = len(certified_df)
                non_certified_count = len(non_certified_df)
                missing_count = len(missing_df)

                # ✅ Create ZIP in memory
                zip_buffer = io.BytesIO()

                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

                    # ✅ Always include extracted data
                    zf.writestr(f"{scope_clean}.csv", main_csv)

                    # ✅ Conditional exports (skip empty)
                    if certified_count > 0:
                        zf.writestr(
                            "Certified Farm Plots.csv",
                            certified_df.drop(columns="__cert_status").to_csv(index=False)
                        )

                    if non_certified_count > 0:
                        zf.writestr(
                            "Non-certified Farm Plots.csv",
                            non_certified_df.drop(columns="__cert_status").to_csv(index=False)
                        )

                    if missing_count > 0:
                        zf.writestr(
                            "Missing Certification Information.csv",
                            missing_df.drop(columns="__cert_status").to_csv(index=False)
                        )

                    # ✅ TXT REPORT (always included)
                    report = f"""{scope_clean}
                    Farm Plots = {total}
                    Certified Farm Plots = {certified_count}
                    Non-certified Farm Plots = {non_certified_count}
                    Farm Plots missing Certification Information = {missing_count}
                    """

                    # ✅ Add certification breakdown section
                    report += "\nCertifications List:\n"

                    # ✅ Build alphabetical certification list
                    if cert_summary:
                        cert_names = sorted([item["Certification"] for item in cert_summary])
                        report += ", ".join(cert_names) + "\n\n"

                        # ✅ Breakdown counts
                        # add a sub title for the breakdown section
                        report += "Certifications Numbers:\n"
                        for item in cert_summary:
                            report += f"{item['Certification']} = {item['Count']}\n"
                    else:
                        report += "No certification data available\n"


                    zf.writestr(f"{scope_clean}.txt", report)

                zip_buffer.seek(0)

                # ✅ Download ZIP
                st.download_button(
                label="Download Certification Data (ZIP)",
                data=zip_buffer,
                file_name=f"{scope_clean}.zip" if is_valid_scope else "disabled.zip",
                mime="application/zip",
                disabled=not is_valid_scope
            )

            else:
                # ✅ Default CSV behavior (unchanged)
                file_name = f"{safe_scope}.csv" if scope_name else "extracted_data.csv"

                st.download_button(
                label="Download Extracted Data",
                data=main_csv,
                file_name=f"{scope_clean}.csv" if is_valid_scope else "disabled.csv",
                mime="text/csv",
                disabled=not is_valid_scope
            )

        else:
            st.write("Upload a Meridia file and select a filter to preview extracted data here.")

