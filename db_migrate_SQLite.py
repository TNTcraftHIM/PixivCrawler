import traceback
import apsw
import os
import xxhash

def tagDB(db, picture_id: str):
    cursor = db.cursor()
    results = cursor_to_dict(cursor,
        "SELECT name, translated_name FROM tags WHERE tag_id IN (SELECT tag_id FROM picture_tags WHERE picture_id == '" + picture_id + "')")
    return results

def insertDB(db, pk, data, force_update=False):
    # convert pk into xxhash integer
    pk = xxhash.xxh32_intdigest(pk)
    try:
        # create a cursor object
        cursor = db.cursor()
        # check if force_update is True
        if force_update:
            # use the INSERT OR REPLACE statement to proform 'UPSERT' operation
            cursor.execute("INSERT OR REPLACE INTO pictures (picture_id, id, author_id, author_name, title, page_no, page_count, r18, ai_type, url, local_filename, local_filename_compressed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ((
                pk), data["id"], data["author_id"], data["author_name"], data["title"], data["page_no"], data["page_count"], data["r18"], data["ai_type"], data["url"], data["local_filename"], data["local_filename_compressed"]))
            # commit changes
            # commit by apsw
            # insert tags
            for tag in data["tags"]:
                # calculate tag_id by hashing tag name
                tag_id = xxhash.xxh32_intdigest(str(tag["name"]))
                # use the INSERT OR REPLACE statement to proform 'UPSERT' operation
                cursor.execute("INSERT OR REPLACE INTO tags (tag_id, name, translated_name) VALUES (?, ?, ?)", ((tag_id, tag["name"], tag["translated_name"])))
                # commit changes
                # commit by apsw
                # use the INSERT OR REPLACE statement to proform 'UPSERT' operation
                cursor.execute(
                    "INSERT OR REPLACE INTO picture_tags (picture_id, tag_id) VALUES (?, (SELECT tag_id FROM tags WHERE name = ?))", ((pk), tag["name"]))
                # commit changes
                # commit by apsw
        return True
    except apsw.ConstraintError as e:
        if force_update:
            print(
                "Aborting database insertion for picture_id: " + str(pk) + " due to error: " + str(e))
        return False
    except Exception as e:
        print("Aborting database insertion for picture_id: " + str(pk) + " due to error: " +
              str(e) + "\n" + traceback.format_exc())
        return False

def migrateDB(db, db_old):
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
        result = insertDB(db, pk, data, True)
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
    from pixiv_crawler import initDB, cursor_to_dict
    db_old = apsw.Connection(db_path + ".bak")
    db = initDB(db_path)
    migrateDB(db, db_old)
