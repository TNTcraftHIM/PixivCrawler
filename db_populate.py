from pixiv_crawler import initDB

db = initDB()
cursor = db.cursor()
# Populate the tags_fts table
cursor.execute("INSERT INTO tags_fts SELECT name, translated_name FROM tags;")
# Print the result
print("Populated the tags_fts table.")
db.close()