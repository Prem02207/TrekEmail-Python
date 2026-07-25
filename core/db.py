from pymongo import MongoClient

# Agar local MongoDB use kar rahe hain:
client = MongoClient("mongodb://localhost:27017/")

# Ya agar MongoDB Atlas (Cloud) use kar rahe hain toh apni connection string yahan dalein:
# client = MongoClient("mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority")

db = client['trekemail_db']  # Aapke Database ka naam
email_collection = db['email_tracking']  # Collection (Table jaisa) ka naam