import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from store.db import Store
from config import STORE_PATH

s = Store(STORE_PATH)
for sess in s.list_sessions():
    token = sess.get("jwt_token", "")[:60]
    print(f"  {sess['id']:>3} | {sess['status']:<10} | {sess['email']:<30} | {token}...")
print(f"\nActive: {s.count_active()}")
