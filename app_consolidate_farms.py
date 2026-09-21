import streamlit as st
import pandas as pd

SOURCE_FILE_COLUMN = "source_file"
FIELDS = [
    "sucafina_plot_id",
    "supplier_plot_id",
    "farmer_id",
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
    "is_organic_certified",
    "is_fairtrade_certified",
    "other_certification_name",
    "plot_supply_chain",
    "plot_farmer_group",
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
    page_title="Join Standardized Farm Plot Data",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="auto",
)

st.title("Join Standardized Farm Plot Data 📦")
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

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Files Read", num_files)
        with col2:
            st.metric("Rows", f"{num_rows:,}")

        st.subheader("All Standardized files merged")
        st.dataframe(consolidated_df, height=400, use_container_width=True)

        st.download_button(
            label="Download merged raw CSV",
            data=consolidated_df.to_csv(index=False),
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
                selected_fields = [field for field in FIELDS if field in consolidated_df.columns]
                duplicate_summary = get_duplicate_summary(consolidated_df, subset=selected_fields)
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
                duplicate_summary = get_duplicate_summary(consolidated_df, subset=selected_fields)
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


    except Exception as e:
        st.error(f"Error merging farm plot files: {str(e)}")
