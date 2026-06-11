import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port  = int(os.getenv("PORT", 5000))
    print(f"\n  AI Personal Banking Financial Advisor")
    print(f"   → http://localhost:{port}/\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
