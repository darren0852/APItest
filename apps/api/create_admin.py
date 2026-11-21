"""Admin CLI: create or promote a user to admin role."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from database import SessionLocal, User
from auth import hash_password

def main():
    if len(sys.argv) >= 3:
        email, password = sys.argv[1], sys.argv[2]
    else:
        email = input("Admin email: ").strip()
        password = input("Admin password (min 8 chars): ").strip()
    if len(password) < 8:
        print("Error: password must be at least 8 characters")
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.status = "admin"
            db.commit()
            print(f"Existing user {email} promoted to admin (id={user.id})")
        else:
            new_user = User(email=email, password_hash=hash_password(password), status="admin")
            db.add(new_user)
            db.flush()
            from wallet import WalletService
            WALLET_SERVICE = WalletService()
            WALLET_SERVICE.ensure_wallet(db, new_user.id)
            db.commit()
            print(f"Admin created: {email} (id={new_user.id})")
    finally:
        db.close()

if __name__ == "__main__":
    main()