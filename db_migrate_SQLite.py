import apsw
import os

def tagDB(db, picture_id: str):
    cursor = db.cursor()
    results = cursor_to_dict(cursor,
        "SELECT name, translated_name FROM tags WHERE tag_id IN (SELECT tag_id FROM picture_tags WHERE picture_id == '" + picture_id + "')")
    return results

def migrateDB(db_old):
    global db
    # transform the old database to the new database
    cursor = db_old.cursor()
    results = cursor_to_dict(cursor, "SELECT * FROM pictures")
    success_count = 0
    for item in results:
        data = {
            "id": item["id"],
            "author_id": item["author_id"],
            "author_name": item["author_name"],
            "title": item["title"],
            "page_no": item["page_no"],
            "page_count": item["page_count"],
            "r18": item["r18"],
            "ai_type": item["ai_type"],
            "url": item["url"],
            "local_filename": item["local_filename"],
            "local_filename_compressed": item["local_filename_compressed"] if "local_filename_compressed" in item else "",
        }
        pk = item["picture_id"]
        data["tags"] = tagDB(db_old, pk)
        result = insertDB(pk, data, True)
        print("Migrating {}... {}".format(
            pk, "Success" if result else "Failed"))
        success_count += 1 if result else 0
    print("Migration finished. {}/{} records migrated.".format(success_count, len(results)))


if __name__ == "__main__":
    # transform the database from old structure to new structure according to the path given in the user input
    db_path = input(
        "Please enter the path of the SQLite database file (default: db.sqlite3): ")
    # rename the database file to the backup file
    os.rename(db_path, db_path + ".bak")
    # import necessary functions from pixiv_crawler
    from pixiv_crawler import initDB, insertDB, cursor_to_dict
    db_old = apsw.Connection(db_path + ".bak")
    db = initDB(db_path)
    migrateDB(db_old)
