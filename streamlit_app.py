import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
import pandas as pd
from datetime import date


def get_db_collection():
    """Return the MongoDB campaigns collection."""
    client = MongoClient("mongodb://localhost:27017/")
    db = client.campaign_db
    return db.campaigns


collection = get_db_collection()

st.set_page_config(page_title="Campaign Tracker", layout="wide")

STATUS_OPTIONS = ["Active", "Paused", "Completed"]


def add_campaign_ui():
    st.header("Add New Campaign")
    with st.form("add_campaign_form"):
        name = st.text_input("Campaign Name")
        client_name = st.text_input("Client Name")
        start_date = st.date_input("Start Date", value=date.today())
        status = st.selectbox("Status", STATUS_OPTIONS)
        submitted = st.form_submit_button("Add Campaign")

    if submitted:
        if not name or not client_name:
            st.warning("Please fill in the campaign name and client name.")
            return

        doc = {
            "name": name,
            "client": client_name,
            "startDate": start_date.isoformat(),
            "status": status,
        }
        collection.insert_one(doc)
        st.success("Campaign added")


def alter_campaigns_ui():
    st.header("Alter Campaigns")
    docs = list(collection.find())
    if not docs:
        st.info("No campaigns found. Add one from 'New Campaign'.")
        return

    # show table
    df = pd.DataFrame([
        {
            "_id": str(d.get("_id")),
            "Campaign Name": d.get("name", ""),
            "Client": d.get("client", ""),
            "Start Date": d.get("startDate", ""),
            "Status": d.get("status", ""),
        }
        for d in docs
    ])

    st.dataframe(df.drop(columns=["_id"]))

    st.markdown("---")
    st.subheader("Edit individual campaigns")

    for d in docs:
        cid = str(d.get("_id"))
        with st.expander(f"{d.get('name', '')} — {d.get('client', '')}"):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write("Start Date:", d.get("startDate", ""))
            with col2:
                current = d.get("status", STATUS_OPTIONS[0])
                new_status = st.selectbox(
                    "Status",
                    STATUS_OPTIONS,
                    index=STATUS_OPTIONS.index(current) if current in STATUS_OPTIONS else 0,
                    key=f"status_{cid}",
                )
            with col3:
                if st.button("Update", key=f"update_{cid}"):
                    collection.update_one({"_id": ObjectId(cid)}, {"$set": {"status": new_status}})
                    st.success("Updated")
                if st.button("Delete", key=f"delete_{cid}"):
                    collection.delete_one({"_id": ObjectId(cid)})
                    st.warning("Deleted")


def report_ui():
    st.header("Campaigns Report")
    status_filter = st.selectbox("Filter by Status", ["All"] + STATUS_OPTIONS)
    query = {} if status_filter == "All" else {"status": status_filter}
    docs = list(collection.find(query))

    if not docs:
        st.info("No campaigns match the selected filter.")
        return

    df = pd.DataFrame([
        {
            "Campaign Name": d.get("name", ""),
            "Client": d.get("client", ""),
            "Start Date": d.get("startDate", ""),
            "Status": d.get("status", ""),
        }
        for d in docs
    ])

    st.dataframe(df)

    # basic summary
    st.markdown("---")
    st.subheader("Summary")
    counts = df["Status"].value_counts().reindex(STATUS_OPTIONS, fill_value=0)
    st.table(counts.rename_axis("Status").reset_index(name="Count"))


def main():
    st.title("Campaign Tracker")

    page = st.sidebar.radio("Navigation", ["New Campaign", "Alter Campaigns", "Reports"])

    if page == "New Campaign":
        add_campaign_ui()
    elif page == "Alter Campaigns":
        alter_campaigns_ui()
    elif page == "Reports":
        report_ui()


if __name__ == "__main__":
    main()
