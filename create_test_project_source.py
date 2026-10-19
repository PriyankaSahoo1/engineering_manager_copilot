import sys

from app.db.mongodb import Emc_db, projects_collection, sources_collection

# Projects are scoped to the owning user, so the test project
# needs a user_id or no API will return it.
#
#     python create_test_project_source.py user_0f8904fc073f

def create_test_data(user_id):
    project = {
        "_id": "x",
        "user_id": user_id,
        "project_name": "Attention Is All You Need Review",
        "objective": "Understand the key ideas, architecture, and contributions introduced in the Attention Is All You Need paper.",
        "analysis_focus": "Self-attention mechanism, Transformer architecture, multi-head attention, positional encoding, encoder-decoder design, training approach, and experimental results.",
    }
    projects_collection.update_one({"_id": project["_id"]}, {"$set": project}, upsert=True)
    print("Project created/updated")
    print("Project ID:", project["_id"])
    print("User ID:", user_id)
    print("Database:", Emc_db.name)
    print("Project count:", projects_collection.count_documents({}))
    print("Source count:", sources_collection.count_documents({}))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_test_project_source.py <user_id>")
        raise SystemExit(1)

    create_test_data(sys.argv[1])
