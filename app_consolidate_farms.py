import streamlit as st
import pandas as pd

SOURCE_FILE_COLUMN = "source_file"
FIELDS = [
    "sucafina_plot_id",
    "supplier_plot_id",
    "farmer_id",
    "supplier_code",
    "plot_region",
    "plot_district",
    "plot_area_ha",
    "plot_longitude",
    "plot_latitude",
    "plot_gps_point",
    "plot_gps_polygon",
    "plot_wkt",
    "is_geodata_validated",
    "is_cafe_practices_certified",
    "is_rfa_utz_certified",
    "is_impact_certified",
    "is_4c_certified",
    "is_organic_certified",
    "is_fairtrade_certified",
    "other_certification_name",
    "plot_supply_chain",
    "plot_farmer_group",
]

CERTIFICATION_FIELDS = [
    "is_cafe_practices_certified",
    "is_rfa_utz_certified",
    "is_impact_certified",
    "is_4c_certified",
    "is_organic_certified",
    "is_fairtrade_certified",
    "other_certification_name",
]


def get_duplicate_subset(df, subset=None):
    """Resolve the columns used to identify duplicates."""
    if subset is None:
        subset = list(df.columns)

    selected_fields = [field for field in subset if field in df.columns]
    if not selected_fields:
        return list(df.columns)
    return selected_fields


def count_duplicates(df, subset=None):
    """Count duplicated rows using the selected field subset."""
    duplicate_subset = get_duplicate_subset(df, subset)
    if df.empty:
        return 0
    return int(df.duplicated(subset=duplicate_subset).sum())


def get_duplicates_df(df, subset=None):
    """Return all rows duplicated under the selected comparison fields."""
    duplicate_subset = get_duplicate_subset(df, subset)
    if df.empty:
        return df.copy()

    duplicate_df = df[df.duplicated(subset=duplicate_subset, keep=False)].copy()
    if duplicate_df.empty:
        return duplicate_df.reset_index(drop=True)

    sort_cols = [field for field in duplicate_subset if field in duplicate_df.columns]
    if sort_cols:
        duplicate_df = duplicate_df.sort_values(by=sort_cols, na_position="last")
    return duplicate_df.reset_index(drop=True)


def get_duplicate_summary(df, subset=None):
    """Return duplicate counts and matching rows for a chosen duplicate subset."""
    duplicate_subset = get_duplicate_subset(df, subset)
    duplicate_df = get_duplicates_df(df, subset=duplicate_subset)
    return {
        "subset": duplicate_subset,
        "count": int(len(duplicate_df)),
        "rows": duplicate_df,
    }


def consolidate_raw_files(uploaded_csv_files):
    """Read each uploaded CSV and merge them into one combined dataframe."""
    frames = []

    for uploaded_file in uploaded_csv_files:
        df = pd.read_csv(uploaded_file)
        df = df.copy()
        df[SOURCE_FILE_COLUMN] = uploaded_file.name
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=[*FIELDS, SOURCE_FILE_COLUMN])

    consolidated_df = pd.concat(frames, ignore_index=True, sort=False)

    ordered_columns = []
    for field in FIELDS:
        if field in consolidated_df.columns:
            ordered_columns.append(field)

    for column in consolidated_df.columns:
        if column not in ordered_columns and column != SOURCE_FILE_COLUMN:
            ordered_columns.append(column)

    if SOURCE_FILE_COLUMN in consolidated_df.columns:
        ordered_columns.append(SOURCE_FILE_COLUMN)

    return consolidated_df.loc[:, list(dict.fromkeys(ordered_columns))].reset_index(drop=True)


st.set_page_config(
    page_title="Sucafina - Generate DLUC Certification Data",
    # page_icon="📦",
    # use svg in root folder for page_icon
    page_icon="globe-svgfind-com.svg",
    layout="wide",
    initial_sidebar_state="auto",
)

st.title("Sucafina - Generate DLUC Certification Data 📦")
st.write(
    "Upload the farm plot CSV files to merge them into a single standardized dataframe. "
    "This version does not drop missing certification data or resolve duplicates; "
    "it simply merges everything so duplicates can be reviewed later."
)

uploaded_csv_files = st.file_uploader(
    "Upload CSV files with farm plot data:",
    type=["csv"],
    accept_multiple_files=True,
    key="raw_farm_plot_files",
)

if uploaded_csv_files:
    try:
        consolidated_df = consolidate_raw_files(uploaded_csv_files)

        num_files = len(uploaded_csv_files)
        num_rows = len(consolidated_df)
        num_cols = consolidated_df.shape[1]

        st.success("✓ Files merged successfully")

        # create a sanitized working copy for downstream use so empty certification values are treated as False
        processed_df = consolidated_df.copy()
        for field in ["is_geodata_validated", *CERTIFICATION_FIELDS]:
            processed_df[field] = processed_df[field].map(
                lambda value: False if pd.isna(value) or (isinstance(value, str) and value.strip() == "") else value
            )

        # add a third metric for number of records with empty certification fields
        # modify the empty_certification_count calculation to count rows where any or all certification fields are null
        # create a dataframe of these rows and a preview button below the "Empty Certification Rows" metric that pops up a modal with these rows displayed in a table
        empty_certification_mask = consolidated_df[CERTIFICATION_FIELDS].isnull().any(axis=1)
        empty_certification_rows = consolidated_df.loc[empty_certification_mask].copy()
        empty_certification_count = int(empty_certification_mask.sum())
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Files Read", num_files)
        with col2:
            st.metric("Rows", f"{num_rows:,}")
        with col3:
            st.metric("Empty Certification Rows", empty_certification_count)
            if empty_certification_count:
                if hasattr(st, "dialog"):
                    if st.button("Preview", key="view_empty_certification_rows"):
                        @st.dialog("Rows with empty certification values", width="large")
                        def show_empty_certification_modal():
                            st.dataframe(empty_certification_rows, use_container_width=True)

                        show_empty_certification_modal()
                else:
                    with st.expander("Preview"):
                        st.dataframe(empty_certification_rows, use_container_width=True)

        st.subheader("All Standardized files merged")
        st.dataframe(processed_df, height=400, use_container_width=True)

        st.download_button(
            label="Download merged raw CSV",
            data=processed_df.to_csv(index=False),
            file_name="merged_raw_farm_plot_data.csv",
            mime="text/csv",
        )   

        st.divider()

        st.subheader("Duplicate Review")
        duplicate_review_left, duplicate_review_right = st.columns([1, 1])

        with duplicate_review_left:
            duplicate_mode = st.radio(
                "Choose duplicate logic:",
                ["Duplicates by all fields", "Duplicates by key fields"],
                horizontal=True,
            )

            if duplicate_mode == "Duplicates by all fields":
                selected_fields = [field for field in FIELDS if field in processed_df.columns]
                duplicate_summary = get_duplicate_summary(processed_df, subset=selected_fields)
                st.caption(
                    f"Duplicate check on {len(selected_fields)} field(s): "
                    f"{', '.join(selected_fields) if selected_fields else 'none'}"
                )
            else:
                default_key_fields = ["sucafina_plot_id", "plot_wkt"]
                selected_fields = st.multiselect(
                    "Duplicate key fields",
                    options=FIELDS,
                    default=[field for field in default_key_fields if field in FIELDS],
                    help="Start with sucafina_plot_id and plot_wkt, then add or remove fields from the FIELDS list.",
                )
                if not selected_fields:
                    selected_fields = [field for field in default_key_fields if field in FIELDS]
                duplicate_summary = get_duplicate_summary(processed_df, subset=selected_fields)
                st.caption(f"Duplicate check on {len(selected_fields)} field(s): {', '.join(selected_fields)}")

            st.metric("Duplicate Rows", duplicate_summary["count"])
            if duplicate_summary["rows"].empty:
                st.info("No duplicate rows found for the selected comparison fields.")

            duplicate_csv = duplicate_summary["rows"].to_csv(index=False)
            st.download_button(
                label="Download duplicate rows as CSV",
                data=duplicate_csv,
                file_name="duplicate_rows_selected_fields.csv",
                mime="text/csv",
            )

        with duplicate_review_right:
            if duplicate_summary["rows"].empty:
                st.info("No duplicate rows to display for the selected comparison fields.")
            else:
                st.dataframe(duplicate_summary["rows"], height=400, use_container_width=True)

        # conditionally display the sections below if there are duplicate rows found
        if not duplicate_summary["rows"].empty:
            st.divider()
            st.subheader("De-Duplicate")

            dedupe_left, dedupe_right = st.columns([1.1, 1.2])

            with dedupe_left:
                st.info(
                    "The de-duplication process will consolidate duplicate records into a single record. "
                    "For boolean fields, if any record has True, the consolidated record will be True; "
                    "if all records are False, the consolidated record will be False. "
                    "For non-boolean fields, you can select which record to keep for each field."
                )

                duplicate_rows = duplicate_summary["rows"].copy()
                duplicate_group_fields = duplicate_summary["subset"] if duplicate_summary["subset"] else [col for col in duplicate_rows.columns if col != SOURCE_FILE_COLUMN]
                grouped_duplicates = duplicate_rows.groupby(duplicate_group_fields, dropna=False, sort=False)

                target_fields = ["farmer_id", "plot_region", "plot_district", "plot_supply_chain", "plot_farmer_group"]
                boolean_fields = [
                    "is_geodata_validated",
                    "is_cafe_practices_certified",
                    "is_rfa_utz_certified",
                    "is_impact_certified",
                    "is_organic_certified",
                    "is_fairtrade_certified",
                ]

                source_names = sorted(duplicate_rows[SOURCE_FILE_COLUMN].dropna().astype(str).unique().tolist())

                if source_names:
                    st.caption("Choose a source per field to determine which duplicate record should be kept. Leave a field empty to keep the first row value.")

                    field_source_selections = {}
                    field_source_lookup = {}
                    for field in target_fields:
                        option_labels = [""]
                        source_lookup_for_field = {"": None}

                        for source_name in source_names:
                            source_rows = duplicate_rows[duplicate_rows[SOURCE_FILE_COLUMN].astype(str) == str(source_name)]
                            field_values = source_rows[field].dropna().astype(str).unique().tolist()
                            sample_values = ", ".join(field_values[:3]) if field_values else "no values"
                            option_text = f"{source_name} — examples: {sample_values}"
                            option_labels.append(option_text)
                            source_lookup_for_field[option_text] = source_name

                        selected_label = st.selectbox(
                            f"{field}",
                            options=option_labels,
                            index=0,
                            key=f"global_dedup_{field}",
                        )
                        field_source_selections[field] = selected_label
                        field_source_lookup[field] = source_lookup_for_field

                    consolidated_duplicate_rows = []
                    for _, group_df in grouped_duplicates:
                        group_df = group_df.reset_index(drop=True)
                        first_row = group_df.iloc[0].copy()
                        consolidated_row = first_row.copy()

                        for field in boolean_fields:
                            if field in consolidated_row.index:
                                consolidated_row[field] = bool(group_df[field].map(lambda value: bool(value) if pd.notna(value) else False).any())

                        for field in target_fields:
                            if field not in consolidated_row.index:
                                continue
                            source_label = field_source_selections.get(field, "")
                            if source_label in ("", None):
                                consolidated_row[field] = first_row.get(field)
                                continue

                            selected_source = field_source_lookup.get(field, {}).get(source_label)
                            if selected_source is None:
                                consolidated_row[field] = first_row.get(field)
                                continue

                            matching_rows = group_df[group_df[SOURCE_FILE_COLUMN].astype(str) == str(selected_source)]
                            if matching_rows.empty:
                                consolidated_row[field] = first_row.get(field)
                            else:
                                consolidated_row[field] = matching_rows.iloc[0].get(field)

                        for field in FIELDS:
                            if field in consolidated_row.index and field not in boolean_fields and field not in target_fields:
                                if field == SOURCE_FILE_COLUMN:
                                    continue
                                consolidated_row[field] = first_row.get(field)

                        consolidated_duplicate_rows.append(consolidated_row.to_dict())

                    if consolidated_duplicate_rows:
                        deduped_df = pd.DataFrame(consolidated_duplicate_rows)
                        deduped_df = deduped_df[[field for field in FIELDS if field in deduped_df.columns]]
                        with dedupe_right:
                            st.dataframe(deduped_df, use_container_width=True)
                            # success message that includes the number of rows in the deduplicated dataframe
                            st.success(f"✓ Deduplication completed successfully. {len(deduped_df)} rows in the deduplicated dataframe.")
                            st.download_button(
                                label="Download deduplicated records",
                                data=deduped_df.to_csv(index=False),
                                file_name="deduplicated_records.csv",
                                mime="text/csv",
                            )
                    else:
                        with dedupe_right:
                            st.info("No records were selected for consolidation.")
                else:
                    with dedupe_right:
                        st.info("No source names available to resolve duplicate fields.")
            
        # generate final dataframe that includes the deduplicated records and the copy of the original dataframe with duplicates removed
        if not duplicate_summary["rows"].empty:
            deduped_df = pd.DataFrame(consolidated_duplicate_rows)
            deduped_df = deduped_df[[field for field in FIELDS if field in deduped_df.columns]]
            non_duplicate_df = processed_df.drop(duplicate_summary["rows"].index, errors="ignore")
            final_df = pd.concat([non_duplicate_df, deduped_df], ignore_index=True, sort=False)
            final_df = final_df[[field for field in FIELDS if field in final_df.columns]]
            st.divider()
            # st.subheader("Final Consolidated Data")
            # include count in the subheader
            st.subheader(f"Final Consolidated Data ({len(final_df)} Plots)")
            st.dataframe(final_df, height=400, use_container_width=True)
            st.download_button(
                label="Download final consolidated data",
                data=final_df.to_csv(index=False),
                # file_name="final_consolidated_data.csv",
                # use an input field to allow the user to specify the file name
                file_name=st.text_input("Enter file name:", value="final_consolidated_data.csv"),
                mime="text/csv",
            )

    except Exception as e:
        st.error(f"Error merging farm plot files: {str(e)}")
