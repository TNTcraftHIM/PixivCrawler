from pixiv_crawler import initDB, insertDB
from tinydb import TinyDB


def migrateDB(db_path: str = "db.json"):
    # transform the database from tinydb to sqlite3
    tinydb = TinyDB(db_path, ensure_ascii=False, encoding='utf-8')
    tinydb = tinydb.table("_default", cache_size=None)
    success_count = 0
    for item in tinydb.all():
        data = {
            "id": item["id"],
            "author_id": item["author_id"],
            "author_name": item["author_name"],
            "title": item["title"],
            "page_no": item["page_no"],
            "page_count": item["page_count"],
            "r18": item["r18"],
            "ai_type": item["ai_type"],
            "tags": item["tags"],
            "url": item["url"],
            "local_filename": item["local_filename"],
            "local_filename_compressed": item["local_filename_compressed"]
        }
        pk = str(item["id"]) + "_p" + str(item["page_no"])
        result = insertDB(pk, data, False)
        print("Migrating {}... {}".format(
            pk, "Success" if result else "Failed"))
        success_count += 1 if result else 0
    print("Migration finished. {}/{} records migrated.".format(success_count, len(tinydb)))


if __name__ == "__main__":
    # transform the database from tinydb to sqlite3 according to the path given in the user input
    db_path = input(
        "Please enter the path of the TinyDB database file (default: db.json): ")
    db = initDB()

    if db_path == "":
        migrateDB()
    else:
        migrateDB(db_path)
